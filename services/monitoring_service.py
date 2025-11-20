"""Service de monitoring custom avancé - Remplace Prometheus + Grafana."""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import WebSocket

from utils.logger import get_logger
from models.schemas import WorkflowStatus
from models.state import GraphState

logger = get_logger(__name__)

@dataclass
class MetricPoint:
    """Point de métrique avec timestamp."""
    timestamp: datetime
    value: float
    labels: Dict[str, str]
    metric_name: str

@dataclass
class WorkflowMetrics:
    """Métriques spécifiques aux workflows."""
    workflow_id: str
    task_id: str
    status: str
    duration: Optional[float] = None
    steps_completed: int = 0
    errors_count: int = 0
    ai_provider: Optional[str] = None
    ai_tokens_used: int = 0
    ai_cost: float = 0.0
    tests_passed: int = 0
    tests_failed: int = 0
    files_modified: int = 0
    pr_created: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class MonitoringDashboard:
    """Dashboard de monitoring en temps réel."""

    def __init__(self):
        self.metrics_store: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.workflow_metrics: Dict[str, WorkflowMetrics] = {}
        self.active_workflows: Dict[str, Dict] = {}
        self.connected_clients: List[WebSocket] = []
        self.alert_rules: List[Dict] = []

        self.background_tasks: List[asyncio.Task] = []
        self.is_monitoring_active = False

        self.real_time_stats = {
            "active_workflows": 0,
            "completed_today": 0,
            "failed_today": 0,
            "avg_duration": 0.0,
            "success_rate": 100.0,
            "ai_costs_today": 0.0,
            "tests_run_today": 0
        }

    async def start_monitoring(self):
        """Démarre le monitoring en arrière-plan."""
        if self.is_monitoring_active:
            logger.warning("🔄 Monitoring déjà actif")
            return

        logger.info("🚀 Démarrage du monitoring custom")
        self.is_monitoring_active = True

        try:
            self.background_tasks = [
                asyncio.create_task(self._metrics_aggregator()),
                asyncio.create_task(self._alert_checker()),
                asyncio.create_task(self._cleanup_old_metrics()),
                asyncio.create_task(self._monitoring_watchdog())
            ]
            
            await asyncio.sleep(0.1)
            logger.info(f"✅ {len(self.background_tasks)} tâches de monitoring lancées")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du lancement du monitoring: {e}")
            self.is_monitoring_active = False

    async def stop_monitoring(self):
        """Arrête proprement le monitoring."""
        if not self.is_monitoring_active:
            return

        logger.info("🛑 Arrêt du monitoring")
        self.is_monitoring_active = False

        for task in self.background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.background_tasks.clear()
        logger.info("✅ Monitoring arrêté proprement")

    async def record_metric(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Enregistre une métrique."""
        labels = labels or {}
        point = MetricPoint(
            timestamp=datetime.now(timezone.utc),
            value=value,
            labels=labels,
            metric_name=metric_name
        )

        self.metrics_store[metric_name].append(point)

        await self._broadcast_metric(point)

    async def start_workflow_monitoring(self, workflow_id: str, task_request: Dict):
        """Démarre le monitoring d'un workflow."""
        workflow_metrics = WorkflowMetrics(
            workflow_id=workflow_id,
            task_id=task_request.get("task_id", "unknown"),
            status=WorkflowStatus.PENDING.value,
            ai_provider=task_request.get("preferred_ai_provider", "claude")
        )

        self.workflow_metrics[workflow_id] = workflow_metrics
        self.active_workflows[workflow_id] = {
            "start_time": time.time(),
            "current_step": "starting",
            "progress": 0,
            "logs": deque(maxlen=100)
        }

        self.real_time_stats["active_workflows"] += 1

        logger.info(
            "📊 Monitoring démarré pour workflow",
            workflow_id=workflow_id,
            task_id=workflow_metrics.task_id
        )

        await self.record_metric("workflow_started", 1, {
            "workflow_id": workflow_id,
            "task_type": task_request.get("task_type", "unknown")
        })

    async def update_workflow_step(self, workflow_id: str, step_name: str,
                                 progress: int, logs: List[str] = None):
        """Met à jour le statut d'une étape de workflow."""
        if workflow_id not in self.active_workflows:
            return

        workflow = self.active_workflows[workflow_id]
        workflow["current_step"] = step_name
        workflow["progress"] = progress

        if logs:
            for log in logs:
                workflow["logs"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "step": step_name,
                    "message": log
                })

        if workflow_id in self.workflow_metrics:
            self.workflow_metrics[workflow_id].steps_completed = progress

        await self.record_metric("workflow_progress", progress, {
            "workflow_id": workflow_id,
            "step": step_name
        })

        await self._broadcast_workflow_update(workflow_id)

    async def complete_workflow(self, workflow_id: str, success: bool,
                                                             final_state: GraphState = None):
        """Finalise le monitoring d'un workflow."""
        if workflow_id not in self.active_workflows:
            return

        workflow = self.active_workflows[workflow_id]
        metrics = self.workflow_metrics.get(workflow_id)

        if metrics:
            duration = time.time() - workflow["start_time"]
            metrics.duration = duration
            metrics.status = WorkflowStatus.COMPLETED.value if success else WorkflowStatus.FAILED.value

            if final_state:
                metrics.files_modified = len(getattr(final_state, 'modified_files', []) or [])
                test_results = getattr(final_state, 'test_results', []) or []
                metrics.tests_passed = sum(1 for t in test_results if getattr(t, 'passed', False))
                metrics.tests_failed = sum(1 for t in test_results if not getattr(t, 'passed', False))
                metrics.pr_created = getattr(final_state, 'pr_info', None) is not None
                error_logs = getattr(final_state, 'error_logs', []) or []
                metrics.errors_count = len(error_logs)

        self.real_time_stats["active_workflows"] -= 1
        if success:
            self.real_time_stats["completed_today"] += 1
        else:
            self.real_time_stats["failed_today"] += 1

        total_today = self.real_time_stats["completed_today"] + self.real_time_stats["failed_today"]
        if total_today > 0:
            self.real_time_stats["success_rate"] = (self.real_time_stats["completed_today"] / total_today) * 100

        await self.record_metric("workflow_completed", 1, {
            "workflow_id": workflow_id,
            "success": str(success),
            "duration": str(duration) if duration else "0"
        })

        del self.active_workflows[workflow_id]

        logger.info(
            f"{'✅' if success else '❌'} Workflow terminé",
            workflow_id=workflow_id,
            success=success,
            duration=duration
        )

    async def log_ai_usage(self, workflow_id: str, provider: str,
                          tokens_used: int, estimated_cost: float):
        """Log l'utilisation de l'IA."""
        if workflow_id in self.workflow_metrics:
            metrics = self.workflow_metrics[workflow_id]
            metrics.ai_provider = provider
            metrics.ai_tokens_used += tokens_used
            metrics.ai_cost += estimated_cost

        self.real_time_stats["ai_costs_today"] += estimated_cost

        await self.record_metric("ai_tokens_used", tokens_used, {
            "provider": provider,
            "workflow_id": workflow_id
        })

        await self.record_metric("ai_cost", estimated_cost, {
            "provider": provider,
            "workflow_id": workflow_id
        })

    async def save_ai_interaction(self, run_step_id: int, provider: str,
                                 model_name: str, prompt: str, response: str,
                                 token_usage: Dict[str, int], latency_ms: int = None) -> int:
        """Sauvegarde une interaction IA en base de données."""
        try:
            from admin.backend.database import get_db_connection

            conn = await get_db_connection()

            result = await conn.fetchrow("""
                INSERT INTO ai_interactions (
                    run_step_id, ai_provider, model_name, prompt, response,
                    token_usage, latency_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING ai_interactions_id
            """,
                run_step_id,
                provider,
                model_name,
                prompt,
                response,
                json.dumps(token_usage),
                latency_ms
            )

            interaction_id = result['ai_interactions_id']
            logger.info(f"💾 Interaction IA sauvegardée: {interaction_id}")
            return interaction_id

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde interaction IA: {e}")
            return -1
        finally:
            if 'conn' in locals():
                await conn.close()

    async def save_ai_code_generation(self, task_run_id: int, provider: str,
                                    model: str, generation_type: str, prompt: str,
                                    generated_code: str, tokens_used: int,
                                    response_time_ms: int, cost_estimate: float,
                                    files_modified: List[str] = None) -> int:
        """Sauvegarde une génération de code IA en base de données."""
        try:
            from admin.backend.database import get_db_connection

            conn = await get_db_connection()

            result = await conn.fetchrow("""
                INSERT INTO ai_code_generations (
                    task_run_id, provider, model, generation_type, prompt,
                    generated_code, tokens_used, response_time_ms, cost_estimate,
                    files_modified
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING ai_code_generations_id
            """,
                task_run_id,
                provider,
                model,
                generation_type,
                prompt,
                generated_code,
                tokens_used,
                response_time_ms,
                cost_estimate,
                json.dumps(files_modified or [])
            )

            generation_id = result['ai_code_generations_id']
            logger.info(f"💾 Génération de code sauvegardée: {generation_id}")
            return generation_id

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde génération de code: {e}")
            return -1
        finally:
            if 'conn' in locals():
                await conn.close()

    async def add_alert_rule(self, name: str, condition: str, threshold: float,
                           message: str):
        """Ajoute une règle d'alerte."""
        rule = {
            "name": name,
            "condition": condition,
            "threshold": threshold,
            "message": message,
            "last_triggered": None
        }
        self.alert_rules.append(rule)

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Récupère toutes les données pour le dashboard."""
        return {
            "real_time_stats": self.real_time_stats,
            "active_workflows": {
                wf_id: {
                    **workflow,
                    "metrics": self.workflow_metrics.get(wf_id, {}).to_dict() if wf_id in self.workflow_metrics else {}
                }
                for wf_id, workflow in self.active_workflows.items()
            },
            "recent_metrics": {
                name: [asdict(point) for point in list(points)[-50:]]
                for name, points in self.metrics_store.items()
            },
            "completed_workflows_today": [
                {
                    "workflow_id": wf_id,
                    **metrics.to_dict()
                }
                for wf_id, metrics in self.workflow_metrics.items()
                if metrics.status in [WorkflowStatus.COMPLETED.value, WorkflowStatus.FAILED.value]
                and self._is_today(datetime.now(timezone.utc))
            ]
        }

    async def register_websocket(self, websocket: WebSocket):
        """Enregistre un client WebSocket pour les mises à jour temps réel."""
        self.connected_clients.append(websocket)

        initial_data = await self.get_dashboard_data()
        await websocket.send_json({
            "type": "initial_data",
            "data": initial_data
        })

    async def unregister_websocket(self, websocket: WebSocket):
        """Désenregistre un client WebSocket."""
        if websocket in self.connected_clients:
            self.connected_clients.remove(websocket)

    async def _broadcast_metric(self, metric: MetricPoint):
        """Diffuse une métrique à tous les clients connectés."""
        if not self.connected_clients:
            return

        message = {
            "type": "metric_update",
            "data": asdict(metric)
        }

        disconnected = []
        for client in self.connected_clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.append(client)

        for client in disconnected:
            self.connected_clients.remove(client)

    async def _broadcast_workflow_update(self, workflow_id: str):
        """Diffuse une mise à jour de workflow."""
        if not self.connected_clients or workflow_id not in self.active_workflows:
            return

        workflow_data = {
            **self.active_workflows[workflow_id],
            "metrics": self.workflow_metrics.get(workflow_id, {}).to_dict() if workflow_id in self.workflow_metrics else {}
        }

        message = {
            "type": "workflow_update",
            "workflow_id": workflow_id,
            "data": workflow_data
        }

        for client in self.connected_clients[:]:
            try:
                await client.send_json(message)
            except Exception:
                self.connected_clients.remove(client)

    async def _monitoring_watchdog(self):
        """Surveille et redémarre les tâches de monitoring si nécessaire."""
        while self.is_monitoring_active:
            try:
                await asyncio.sleep(300)

                dead_tasks = []
                task_names = ["_metrics_aggregator", "_alert_checker", "_cleanup_old_metrics"]

                for i, task in enumerate(self.background_tasks[:3]):
                    if task.done() and not task.cancelled():
                        logger.warning(f"⚠️ Tâche de monitoring {task_names[i]} terminée inopinément")
                        dead_tasks.append((i, task_names[i]))

                for task_index, task_name in dead_tasks:
                    logger.info(f"🔄 Redémarrage de la tâche {task_name}")
                    try:
                        if task_name == "_metrics_aggregator":
                            new_task = asyncio.create_task(self._metrics_aggregator())
                        elif task_name == "_alert_checker":
                            new_task = asyncio.create_task(self._alert_checker())
                        elif task_name == "_cleanup_old_metrics":
                            new_task = asyncio.create_task(self._cleanup_old_metrics())

                        self.background_tasks[task_index] = new_task
                        logger.info(f"✅ Tâche {task_name} redémarrée avec succès")

                    except Exception as e:
                        logger.error(f"❌ Erreur redémarrage {task_name}: {e}")

            except asyncio.CancelledError:
                logger.info("🐕 Surveillance du monitoring arrêtée")
                break
            except Exception as e:
                logger.error(f"❌ Erreur dans le watchdog du monitoring: {e}")
                await asyncio.sleep(60)

    async def _metrics_aggregator(self):
        """Agrège les métriques périodiquement."""
        retry_count = 0
        max_retries = 5

        while self.is_monitoring_active:
            try:
                completed_workflows = [
                    m for m in self.workflow_metrics.values()
                    if m.duration is not None
                ]

                if completed_workflows:
                    avg_duration = sum(m.duration for m in completed_workflows) / len(completed_workflows)
                    self.real_time_stats["avg_duration"] = round(avg_duration, 2)

                total_tests = sum(
                    m.tests_passed + m.tests_failed
                    for m in self.workflow_metrics.values()
                )
                self.real_time_stats["tests_run_today"] = total_tests

                retry_count = 0
                await asyncio.sleep(10)

            except asyncio.CancelledError:
                logger.info("📊 Agrégateur de métriques arrêté")
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Erreur dans l'agrégateur de métriques (tentative {retry_count}/{max_retries}): {e}")

                if retry_count >= max_retries:
                    logger.error("❌ Arrêt de l'agrégateur après trop d'erreurs")
                    break

                await asyncio.sleep(min(30 * retry_count, 300))

    async def _alert_checker(self):
        """Vérifie les règles d'alertes."""
        retry_count = 0
        max_retries = 5

        while self.is_monitoring_active:
            try:
                for rule in self.alert_rules:
                    if rule["condition"] == "error_rate > threshold":
                        total = self.real_time_stats["completed_today"] + self.real_time_stats["failed_today"]
                        if total > 0:
                            error_rate = (self.real_time_stats["failed_today"] / total) * 100
                            if error_rate > rule["threshold"]:
                                await self._trigger_alert(rule, {"error_rate": error_rate})

                retry_count = 0
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                logger.info("🚨 Vérificateur d'alertes arrêté")
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Erreur dans le vérificateur d'alertes (tentative {retry_count}/{max_retries}): {e}")

                if retry_count >= max_retries:
                    logger.error("❌ Arrêt du vérificateur après trop d'erreurs")
                    break

                await asyncio.sleep(min(60 * retry_count, 300))

    async def _trigger_alert(self, rule: Dict, context: Dict):
        """Déclenche une alerte."""
        now = datetime.now(timezone.utc)

        if rule["last_triggered"]:
            if (now - rule["last_triggered"]).seconds < 3600:
                return

        rule["last_triggered"] = now

        alert_message = {
            "type": "alert",
            "rule": rule["name"],
            "message": rule["message"],
            "context": context,
            "timestamp": now.isoformat()
        }

        logger.warning(
            f"🚨 ALERTE: {rule['name']}",
            rule=rule["name"],
            context=context
        )

        for client in self.connected_clients[:]:
            try:
                await client.send_json(alert_message)
            except Exception:
                self.connected_clients.remove(client)

    async def _cleanup_old_metrics(self):
        """Nettoie les anciennes métriques."""
        retry_count = 0
        max_retries = 5

        while self.is_monitoring_active:
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

                for metric_name, points in self.metrics_store.items():
                    while points and points[0].timestamp < cutoff:
                        points.popleft()

                old_workflows = [
                    wf_id for wf_id, metrics in self.workflow_metrics.items()
                    if metrics.status in [WorkflowStatus.COMPLETED.value, WorkflowStatus.FAILED.value]
                    and (datetime.now(timezone.utc) - datetime.fromisoformat(metrics.workflow_id.split("_")[-1]) if "_" in metrics.workflow_id else datetime.now(timezone.utc)).days > 7
                ]

                for wf_id in old_workflows:
                    del self.workflow_metrics[wf_id]

                retry_count = 0
                await asyncio.sleep(3600)

            except asyncio.CancelledError:
                logger.info("🧹 Nettoyeur de métriques arrêté")
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Erreur dans le nettoyage des métriques (tentative {retry_count}/{max_retries}): {e}")

                if retry_count >= max_retries:
                    logger.error("❌ Arrêt du nettoyeur après trop d'erreurs")
                    break

                await asyncio.sleep(min(3600 * retry_count, 7200))

    def _is_today(self, timestamp: datetime) -> bool:
        """Vérifie si un timestamp est d'aujourd'hui."""
        return timestamp.date() == datetime.now(timezone.utc).date()

def monitor_workflow_step(step_name: str):
    """Décorateur pour monitorer automatiquement une étape de workflow."""
    def decorator(func):
        async def wrapper(state: GraphState, *args, **kwargs):
            workflow_id = getattr(getattr(state, 'task', None), 'task_id', "unknown") if getattr(state, 'task', None) else "unknown"

            start_time = time.time()

            try:
                await monitoring_service.update_workflow_step(
                    workflow_id,
                    step_name,
                    getattr(state, 'current_progress', 0),
                    [f"Début de l'étape: {step_name}"]
                )

                result = await func(state, *args, **kwargs)

                execution_time = time.time() - start_time
                await monitoring_service.update_workflow_step(
                    workflow_id,
                    step_name,
                    getattr(state, 'current_progress', 0) + 10,
                    [f"Étape terminée: {step_name}"]
                )

                logger.info(f"✅ Étape {step_name} terminée", extra={
                    "workflow_id": workflow_id,
                    "step_name": step_name,
                    "duration": execution_time,
                    "progress": getattr(state, 'current_progress', 0)
                })

                return result

            except Exception as e:
                duration = time.time() - start_time
                await monitoring_service.record_metric(
                    f"step_{step_name}_duration",
                    duration,
                    {"workflow_id": workflow_id, "status": "error"}
                )

                await monitoring_service.update_workflow_step(
                    workflow_id,
                    step_name,
                    getattr(state, 'current_progress', 0),
                    [f"Erreur dans l'étape: {step_name} - {str(e)}"]
                )

                raise

        return wrapper
    return decorator

@asynccontextmanager
async def workflow_monitoring_context(workflow_id: str, task_request: Dict):
    """Context manager pour le monitoring complet d'un workflow."""
    try:
        await monitoring_service.start_workflow_monitoring(workflow_id, task_request)
        yield monitoring_service
    except Exception:
        await monitoring_service.complete_workflow(workflow_id, False)
        raise
    else:
        await monitoring_service.complete_workflow(workflow_id, True)

async def get_costs_summary_impl(self, period: str = "today") -> Dict[str, Any]:
    """Retourne un résumé des coûts et tokens."""
    try:
        from admin.backend.database import get_db_connection

        conn = await get_db_connection()

        if period == "today":
            date_filter = "WHERE DATE(created_at) = CURRENT_DATE"
        elif period == "week":
            date_filter = "WHERE created_at >= NOW() - INTERVAL '7 days'"
        elif period == "month":
            date_filter = "WHERE created_at >= NOW() - INTERVAL '30 days'"
        else:
            date_filter = ""

        result = await conn.fetchrow(f"""
            SELECT
                COUNT(*) as total_interactions,
                SUM((token_usage->>'prompt_tokens')::int) as total_input_tokens,
                SUM((token_usage->>'completion_tokens')::int) as total_output_tokens,
                SUM((token_usage->>'total_tokens')::int) as total_tokens,
                SUM(
                    CASE
                        WHEN ai_provider = 'claude' THEN
                            ((token_usage->>'prompt_tokens')::int * 0.000003) +
                            ((token_usage->>'completion_tokens')::int * 0.000015)
                        WHEN ai_provider = 'openai' THEN
                            ((token_usage->>'total_tokens')::int * 0.00003)
                        ELSE 0
                    END
                ) as total_cost
            FROM ai_interactions
            {date_filter}
        """)

        provider_details = await conn.fetch(f"""
            SELECT
                ai_provider,
                COUNT(*) as interactions,
                SUM((token_usage->>'total_tokens')::int) as tokens,
                SUM(
                    CASE
                        WHEN ai_provider = 'claude' THEN
                            ((token_usage->>'prompt_tokens')::int * 0.000003) +
                            ((token_usage->>'completion_tokens')::int * 0.000015)
                        WHEN ai_provider = 'openai' THEN
                            ((token_usage->>'total_tokens')::int * 0.00003)
                        ELSE 0
                    END
                ) as cost
            FROM ai_interactions
            {date_filter}
            GROUP BY ai_provider
            ORDER BY cost DESC
        """)

        return {
            "period": period,
            "summary": {
                "total_interactions": result['total_interactions'] or 0,
                "total_input_tokens": result['total_input_tokens'] or 0,
                "total_output_tokens": result['total_output_tokens'] or 0,
                "total_tokens": result['total_tokens'] or 0,
                "total_cost_usd": float(result['total_cost'] or 0)
            },
            "by_provider": [
                {
                    "provider": row['ai_provider'],
                    "interactions": row['interactions'],
                    "tokens": row['tokens'] or 0,
                    "cost_usd": float(row['cost'] or 0)
                }
                for row in provider_details
            ]
        }

    except Exception as e:
        logger.error(f"❌ Erreur récupération coûts: {e}")
        return {"error": str(e)}
    finally:
        if 'conn' in locals():
            await conn.close()

MonitoringDashboard.get_costs_summary = get_costs_summary_impl

monitoring_service = MonitoringDashboard()
monitoring_dashboard = monitoring_service
