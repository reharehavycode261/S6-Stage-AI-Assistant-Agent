"""
Service de persistence en temps réel pour le workflow.
Sauvegarde automatiquement toutes les données dans les tables de base2.sql.
"""

import asyncpg
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from decimal import Decimal

from config.settings import get_settings
from utils.logger import get_logger
from utils.database_manager import db_manager  

logger = get_logger(__name__)


class DatabasePersistenceService:
    """Service de persistence en temps réel pour le workflow."""

    def __init__(self):
        self.settings = get_settings()
        self.db_manager = db_manager

    async def initialize(self):
        """Initialise la connexion à la base de données."""
        try:
            await self.db_manager.initialize()
            logger.info("✅ Service de persistence initialisé avec gestionnaire centralisé")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation persistence: {e}")
            raise

    async def close(self):
        """Ferme les connexions à la base de données."""
        logger.info("🔒 Service de persistence fermé (connexions partagées restent actives)")

    async def create_task_from_monday(self, monday_payload: Dict[str, Any]) -> int:
        """Crée une nouvelle tâche depuis un webhook Monday.com."""
        async with self.db_manager.get_connection() as conn:
            item_id = monday_payload.get("pulseId") or monday_payload.get("itemId")
            board_id = monday_payload.get("boardId")
            item_name = monday_payload.get("pulseName") or monday_payload.get("itemName", "Tâche sans titre")

            raw_columns = monday_payload.get("columnValues", monday_payload.get("column_values", {}))

            normalized_columns = {}
            if isinstance(raw_columns, list):
                for col in raw_columns:
                    if isinstance(col, dict) and "id" in col:
                        normalized_columns[col["id"]] = col
                logger.info(f"🔧 Conversion colonnes liste → dict: {len(normalized_columns)} colonnes")
            elif isinstance(raw_columns, dict):
                normalized_columns = raw_columns
            else:
                logger.warning(f"⚠️ Format colonnes non reconnu: {type(raw_columns)}")
                normalized_columns = {}

            description = ""
            priority = "medium"
            repository_url = ""

            def safe_extract_text(col_id: str, default: str = "") -> str:
                """Extrait le texte d'une colonne de manière sécurisée."""
                col_data = normalized_columns.get(col_id, {})
                if isinstance(col_data, dict):
                    col_type = col_data.get("type", "")
                    if col_type == "link":
                        url_value = col_data.get("url")
                        if url_value:
                            return url_value.strip()
                        text_value = col_data.get("text")
                        if text_value:
                            return text_value.strip()
                    
                    return (col_data.get("text") or
                           col_data.get("value") or
                           col_data.get("url") or
                           str(col_data.get("display_value", "")) or
                           default).strip()
                return default

            from config.settings import get_settings
            settings = get_settings()
            
            if settings.monday_repository_url_column_id:
                extracted_url = safe_extract_text(settings.monday_repository_url_column_id)
                if extracted_url:
                    repository_url = extracted_url
                    logger.info(f"🔗 URL repository trouvée dans colonne configurée ({settings.monday_repository_url_column_id}): {repository_url}")
            
            if not repository_url or repository_url.strip() == "":
                logger.info(f"🔄 URL repository non définie - recherche dans les PR précédentes...")
                
                try:
                    from services.repository_url_resolver import RepositoryUrlResolver
                    resolved_url = await RepositoryUrlResolver.resolve_repository_url(
                        monday_item_id=item_id,
                        task_db_id=None  
                    )
                    
                    if resolved_url:
                        repository_url = resolved_url
                        logger.info(f"✅ URL repository résolue via PR: {repository_url}")
                    else:
                        logger.warning(f"⚠️ Impossible de résoudre l'URL repository pour item {item_id}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erreur résolution URL repository: {e}")
            
            for col_id, col_value in normalized_columns.items():
                col_id_lower = col_id.lower()

                if any(keyword in col_id_lower for keyword in
                      ["description", "desc", "details", "text", "note", "comment", "sujet"]):
                    extracted_desc = safe_extract_text(col_id)
                    if extracted_desc and len(extracted_desc) > len(description):
                        description = extracted_desc
                        logger.info(f"📝 Description trouvée dans colonne '{col_id}': {description[:50]}...")

                elif any(keyword in col_id_lower for keyword in ["priority", "priorité", "prio"]):
                    extracted_priority = safe_extract_text(col_id, "medium").lower()
                    if extracted_priority in ["low", "medium", "high", "urgent", "bas", "moyen", "élevé"]:
                        priority = extracted_priority
                        logger.info(f"📊 Priorité trouvée: {priority}")

                elif not repository_url and any(keyword in col_id_lower for keyword in
                        ["repo", "repository", "url", "github", "git", "project"]):
                    extracted_url = safe_extract_text(col_id)
                    if extracted_url and ("github.com" in extracted_url or "git" in extracted_url):
                        repository_url = extracted_url
                        logger.info(f"🔗 URL repository trouvée dans colonne '{col_id}': {repository_url}")

            if not repository_url and description:
                from utils.github_parser import extract_github_url_from_description
                extracted_url = extract_github_url_from_description(description)
                if extracted_url:
                    repository_url = extracted_url
                    logger.info(f"🎯 URL GitHub extraite de la description: {repository_url}")

            if not repository_url:
                logger.warning(f"⚠️ Aucune URL repository trouvée pour l'item {item_id}")
                logger.warning(f"📋 Colonnes disponibles ({len(normalized_columns)}): {list(normalized_columns.keys())}")
                logger.warning(f"📝 Description ({len(description)} chars): {description[:100] if description else 'VIDE'}...")
                
                logger.warning(f"🔍 DEBUG - Détails des colonnes:")
                for col_id, col_data in list(normalized_columns.items())[:5]:  # 5 premières colonnes
                    if isinstance(col_data, dict):
                        logger.warning(f"  • {col_id}: text='{col_data.get('text', '')}', type='{col_data.get('type', '')}'")

            task_id = await conn.fetchval("""
                INSERT INTO tasks (
                    monday_item_id, monday_board_id, title, description,
                    priority, repository_url, repository_name,
                    monday_status, internal_status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING tasks_id
            """,
                item_id, board_id, item_name, description,
                priority, repository_url,
                repository_url.split('/')[-1] if repository_url else "",
                "nouveau", "pending"
            )

            logger.info(f"📝 Tâche créée: {task_id} - {item_name}")
            logger.info(f"🔗 URL: {repository_url or 'NON DÉFINIE'}")
            logger.info(f"📄 Description: {description[:50] + '...' if description else 'NON DÉFINIE'}")
            return task_id

    async def start_task_run(self, task_id: Optional[int], celery_task_id: str,
                            ai_provider: str = "claude", custom_run_id: str = None, 
                            precreated_run_id: Optional[int] = None) -> int:
        """Démarre une nouvelle exécution de tâche."""
        
        async with self.db_manager.get_connection() as conn:
            effective_task_id = custom_run_id or celery_task_id

            if task_id:
                current_status = await conn.fetchval("""
                    SELECT internal_status FROM tasks WHERE tasks_id = $1
                """, task_id)
                
                if current_status == 'completed':
                    logger.info(f"🔄 Création d'un nouveau run pour tâche {task_id} terminée (réactivation autorisée)")
            
            if task_id:
                run_number = await conn.fetchval("""
                    SELECT COALESCE(MAX(run_number), 0) + 1
                    FROM task_runs WHERE task_id = $1
                """, task_id)
            else:
                run_number = await conn.fetchval("""
                    SELECT COALESCE(MAX(run_number), 0) + 1
                    FROM task_runs WHERE task_id IS NULL
                """) or 1

            if precreated_run_id:
                logger.info(f"✅ Adoption du run pré-créé: ID={precreated_run_id}")
                await conn.execute("""
                    UPDATE task_runs 
                    SET celery_task_id = $1,
                        ai_provider = $2,
                        current_node = $3,
                        progress_percentage = $4
                    WHERE tasks_runs_id = $5
                """, effective_task_id, ai_provider, "prepare_environment", 0, precreated_run_id)
                
                logger.info(f"✅ Run {precreated_run_id} adopté et mis à jour avec celery_task_id={effective_task_id}")
                return precreated_run_id
            
            existing_run = await conn.fetchval("""
                SELECT tasks_runs_id 
                FROM task_runs 
                WHERE celery_task_id = $1
            """, effective_task_id)
            
            if existing_run:
                logger.info(f"✅ Run existant trouvé: ID={existing_run} pour celery_task_id={effective_task_id}")
                return existing_run
            
            run_id = await conn.fetchval("""
                INSERT INTO task_runs (
                    task_id, run_number, status, celery_task_id,
                    ai_provider, current_node, progress_percentage,
                    is_reactivation, reactivation_count
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, 0)
                RETURNING tasks_runs_id
            """,
                task_id, run_number, "started", effective_task_id,
                ai_provider, "prepare_environment", 0
            )

            if task_id:
                await conn.execute("""
                    UPDATE tasks
                    SET last_run_id = $1, internal_status = $2, started_at = NOW()
                    WHERE tasks_id = $3
                """, run_id, "processing", task_id)

            logger.info(f"🚀 Run démarré: {run_id} (UUID: {effective_task_id}) pour tâche {task_id or 'standalone'}")
            return run_id

    def _truncate_node_name(self, node_name: str, max_length: int = 50) -> str:
        """
        Tronque le nom du nœud s'il est trop long pour la base de données.
        Garde les parties importantes et indique la troncature.

        Note: max_length réduit à 50 pour assurer compatibilité avec colonnes VARCHAR(100)
        """
        if len(node_name) <= max_length:
            return node_name

        if node_name.startswith("ChannelWrite<"):
            return "ChannelWrite<...>"

        if node_name.startswith("__start__") or node_name.startswith("__end__"):
            return node_name[:max_length-3] + "..."

        if ":" in node_name:
            prefix = node_name.split(":")[0]
            if len(prefix) <= max_length - 4:
                return prefix + ":..."

        return node_name[:max_length-3] + "..."

    async def create_run_step(self, task_run_id: int, node_name: str,
                             step_order: int, input_data: Dict[str, Any] = None) -> int:
        """Crée une nouvelle étape de run."""
        async with self.db_manager.get_connection() as conn:
            truncated_node_name = self._truncate_node_name(node_name)

            input_data_json = None
            if input_data is not None:
                try:
                    clean_data = self._clean_for_json_serialization(input_data)
                    input_data_json = json.dumps(clean_data, ensure_ascii=False, separators=(',', ':'))
                    max_size = 64000  
                    if len(input_data_json) > max_size:
                        logger.warning(f"⚠️ Données JSON trop volumineuses ({len(input_data_json)} chars), troncature nécessaire")
                        truncated_data = {
                            "truncated": True,
                            "original_size": len(input_data_json),
                            "node_name": clean_data.get("node_name") if isinstance(clean_data, dict) else None,
                            "summary": str(clean_data)[:1000] + "..." if len(str(clean_data)) > 1000 else str(clean_data),
                            "truncated_at": datetime.now().isoformat()
                        }
                        input_data_json = json.dumps(truncated_data, ensure_ascii=False, separators=(',', ':'))

                except (TypeError, ValueError, OverflowError) as e:
                    logger.warning(f"⚠️ Échec sérialisation input_data: {e}. Utilisation fallback sécurisé.")
                    fallback_data = {
                        "serialization_error": True,
                        "error_type": type(e).__name__,
                        "error_message": str(e)[:200],
                        "original_type": str(type(input_data)),
                        "data_structure": self._get_data_structure_info(input_data),
                        "timestamp": datetime.now().isoformat()
                    }

                    try:
                        if hasattr(input_data, '__dict__'):
                            fallback_data["available_attributes"] = list(input_data.__dict__.keys())[:10]
                        elif isinstance(input_data, dict):
                            fallback_data["dict_keys"] = list(input_data.keys())[:10]
                        elif isinstance(input_data, (list, tuple)):
                            fallback_data["sequence_length"] = len(input_data)
                            fallback_data["first_elements"] = [str(item)[:50] for item in input_data[:3]]
                    except Exception:
                        pass  

                    input_data_json = json.dumps(fallback_data, ensure_ascii=False, separators=(',', ':'))

            step_id = await conn.fetchval("""
                INSERT INTO run_steps (
                    task_run_id, node_name, step_order, status,
                    input_data, started_at
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                RETURNING run_steps_id
            """,
                task_run_id, truncated_node_name, step_order, "running",
                input_data_json
            )

            await conn.execute("""
                UPDATE task_runs
                SET current_node = $1, progress_percentage = $2
                WHERE tasks_runs_id = $3
            """, truncated_node_name, min(step_order * 12, 90), task_run_id)

            logger.debug(f"📍 Étape créée: {node_name} ({step_id})")
            return step_id

    def _clean_for_json_serialization(self, data: Any) -> Any:
        if data is None:
            return None
        elif isinstance(data, (str, int, float, bool)):
            return data
        elif isinstance(data, (list, tuple)):
            return [self._clean_for_json_serialization(item) for item in data]
        elif isinstance(data, dict):
            return {
                str(key): self._clean_for_json_serialization(value)
                for key, value in data.items()
            }
        elif hasattr(data, 'dict') and callable(getattr(data, 'dict')):
            return self._clean_for_json_serialization(data.dict())
        elif hasattr(data, '__dict__'):
            return self._clean_for_json_serialization(data.__dict__)
        elif hasattr(data, '_asdict') and callable(getattr(data, '_asdict')):
            return self._clean_for_json_serialization(data._asdict())
        else:
            return str(data)

    def _get_data_structure_info(self, data: Any) -> str:
        """
        Obtient une description sécurisée de la structure de données pour le debug.

        Args:
            data: Données à analyser

        Returns:
            Description textuelle de la structure
        """
        try:
            if data is None:
                return "None"
            elif isinstance(data, (str, int, float, bool)):
                return f"{type(data).__name__}({len(str(data))} chars)" if isinstance(data, str) else f"{type(data).__name__}"
            elif isinstance(data, (list, tuple)):
                return f"{type(data).__name__}(length={len(data)}, types={[type(item).__name__ for item in data[:3]]})"
            elif isinstance(data, dict):
                return f"dict(keys={len(data)}, sample_keys={list(data.keys())[:5]})"
            elif hasattr(data, '__dict__'):
                attrs = list(data.__dict__.keys())[:5]
                return f"{type(data).__name__}(attributes={attrs})"
            else:
                return f"{type(data).__name__}(repr_length={len(repr(data)[:100])})"
        except Exception:
            return f"{type(data).__name__}(analysis_failed)"

    async def complete_run_step(self, step_id: int, status: str = "completed",
                               output_data: Dict[str, Any] = None,
                               error_details: str = None):
        """Termine une étape de run."""
        async with self.db_manager.get_connection() as conn:
            step_info = await conn.fetchrow("""
                SELECT started_at, task_run_id FROM run_steps WHERE run_steps_id = $1
            """, step_id)

            if step_info:
                duration = (datetime.now(timezone.utc) - step_info['started_at']).total_seconds()

                output_data_json = None
                if output_data:
                    try:
                        clean_output = self._clean_for_json_serialization(output_data)
                        output_data_json = json.dumps(clean_output)
                    except (TypeError, ValueError) as e:
                        logger.warning(f"⚠️ Impossible de sérialiser output_data: {e}")
                        output_data_json = json.dumps({
                            "error": "Sérialisation échouée",
                            "original_type": str(type(output_data)),
                            "str_representation": str(output_data)[:500]
                        })

                await conn.execute("""
                    UPDATE run_steps
                    SET status = $1, completed_at = NOW(), duration_seconds = $2,
                        output_data = $3, error_details = $4
                    WHERE run_steps_id = $5
                """,
                    status, int(duration),
                    output_data_json,
                    error_details, step_id
                )

                logger.debug(f"✅ Étape terminée: {step_id} - {status}")

    async def log_ai_interaction(self, run_step_id: int, ai_provider: str,
                                model: str, prompt: str, response: str = None,
                                token_usage: Dict[str, int] = None,
                                latency_ms: int = None):
        """Enregistre une interaction IA."""
        async with self.db_manager.get_connection() as conn:
            interaction_id = await conn.fetchval("""
                INSERT INTO ai_interactions (
                    run_step_id, ai_provider, model_name, prompt,
                    response, token_usage, latency_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING ai_interactions_id
            """,
                run_step_id, ai_provider, model, prompt,
                response, json.dumps(token_usage) if token_usage else None,
                latency_ms
            )

            logger.debug(f"🤖 Interaction IA loggée: {interaction_id}")
            return interaction_id

    async def log_code_generation(self, task_run_id: int, provider: str, model: str,
                                 generation_type: str, prompt: str,
                                 generated_code: str = None, tokens_used: int = None,
                                 response_time_ms: int = None, cost_estimate: float = None,
                                 files_modified: List[str] = None):
        """Enregistre une génération de code."""
        async with self.db_manager.get_connection() as conn:
            gen_id = await conn.fetchval("""
                INSERT INTO ai_code_generations (
                    task_run_id, provider, model, generation_type, prompt,
                    generated_code, tokens_used, response_time_ms, cost_estimate,
                    files_modified
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING ai_code_generations_id
            """,
                task_run_id, provider, model, generation_type, prompt,
                generated_code, tokens_used, response_time_ms,
                Decimal(str(cost_estimate)) if cost_estimate else None,
                json.dumps(files_modified) if files_modified else None
            )

            logger.debug(f"💾 Génération code loggée: {gen_id}")
            return gen_id

    async def log_test_results(self, task_run_id: int, passed: bool, status: str,
                              tests_total: int = 0, tests_passed: int = 0,
                              tests_failed: int = 0, tests_skipped: int = 0,
                              coverage_percentage: float = None,
                              pytest_report: Dict[str, Any] = None,
                              duration_seconds: int = None):
        """Enregistre les résultats de tests."""
        async with self.db_manager.get_connection() as conn:
            test_id = await conn.fetchval("""
                INSERT INTO test_results (
                    task_run_id, passed, status, tests_total, tests_passed,
                    tests_failed, tests_skipped, coverage_percentage,
                    pytest_report, duration_seconds
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING test_results_id
            """,
                task_run_id, passed, status, tests_total, tests_passed,
                tests_failed, tests_skipped,
                Decimal(str(coverage_percentage)) if coverage_percentage else None,
                json.dumps(pytest_report) if pytest_report else None,
                duration_seconds
            )

            logger.debug(f"🧪 Résultats tests loggés: {test_id}")
            return test_id

    async def create_pull_request(self, task_id: int, task_run_id: int,
                                 github_pr_number: int, github_pr_url: str,
                                 pr_title: str, pr_description: str = None,
                                 head_sha: str = None, base_branch: str = "main",
                                 feature_branch: str = None):
        """Enregistre une pull request."""
        async with self.db_manager.get_connection() as conn:
            pr_id = await conn.fetchval("""
                INSERT INTO pull_requests (
                    task_id, task_run_id, github_pr_number, github_pr_url,
                    pr_title, pr_description, pr_status, head_sha,
                    base_branch, feature_branch
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING pull_requests_id
            """,
                task_id, task_run_id, github_pr_number, github_pr_url,
                pr_title, pr_description, "open", head_sha,
                base_branch, feature_branch
            )

            await conn.execute("""
                UPDATE task_runs
                SET pull_request_url = $1
                WHERE tasks_runs_id = $2
            """, github_pr_url, task_run_id)

            logger.info(f"🔀 Pull request créée: {pr_id} - {github_pr_url}")
            return pr_id

    async def update_last_merged_pr_url(self, task_run_id: int, last_merged_pr_url: str):
        """
        Met à jour l'URL de la dernière PR fusionnée récupérée depuis GitHub.
        
        Args:
            task_run_id: ID du task_run
            last_merged_pr_url: URL de la dernière PR fusionnée
        """
        if not self.db_manager._is_initialized:
            logger.warning("Gestionnaire DB non initialisé - impossible de sauvegarder last_merged_pr_url")
            return False
        
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE task_runs
                    SET last_merged_pr_url = $1
                    WHERE tasks_runs_id = $2
                """, last_merged_pr_url, task_run_id)
                
                logger.info(f"✅ URL dernière PR fusionnée sauvegardée en base: {last_merged_pr_url}")
                return True
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde de last_merged_pr_url: {e}")
            return False

    async def complete_task_run(self, task_run_id: int, status: str = "completed",
                               result: Dict[str, Any] = None, error_message: str = None):
        """Termine une exécution de tâche."""
        async with self.db_manager.get_connection() as conn:
            run_info = await conn.fetchrow("""
                SELECT started_at, task_id FROM task_runs WHERE tasks_runs_id = $1
            """, task_run_id)

            if run_info:
                duration = (datetime.now(timezone.utc) - run_info['started_at']).total_seconds()

                browser_qa_json = None
                if result and "browser_qa" in result:
                    browser_qa_json = json.dumps(result["browser_qa"])
                
                await conn.execute("""
                    UPDATE task_runs
                    SET status = $1, completed_at = NOW(), duration_seconds = $2,
                        result = $3, error_message = $4, progress_percentage = $5,
                        browser_qa_results = $7
                    WHERE tasks_runs_id = $6
                """,
                    status, int(duration),
                    json.dumps(result) if result else None,
                    error_message, 100 if status == "completed" else 50,
                    task_run_id,
                    browser_qa_json
                )

                final_status = "completed" if status == "completed" else "failed"
                await conn.execute("""
                    UPDATE tasks
                    SET internal_status = $1, completed_at = NOW()
                    WHERE tasks_id = $2
                """, final_status, run_info['task_id'])

                logger.info(f"🏁 Run terminé: {task_run_id} - {status}")

    async def log_application_event(self, task_id: int = None, task_run_id: int = None,
                                   run_step_id: int = None, level: str = "INFO",
                                   source_component: str = "workflow",
                                   action: str = "", message: str = "",
                                   metadata: Dict[str, Any] = None):
        """Enregistre un événement d'application."""
        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                INSERT INTO application_logs (
                    task_id, task_run_id, run_step_id, level,
                    source_component, action, message, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                task_id, task_run_id, run_step_id, level,
                source_component, action, message,
                json.dumps(self._clean_for_json_serialization(metadata)) if metadata else None
            )

    async def record_performance_metrics(self, task_id: int, task_run_id: int,
                                       total_duration_seconds: int = None,
                                       ai_processing_time_seconds: int = None,
                                       testing_time_seconds: int = None,
                                       total_ai_calls: int = 0,
                                       total_tokens_used: int = 0,
                                       total_ai_cost: float = 0.0,
                                       test_coverage_final: float = None,
                                       retry_attempts: int = 0):
        """Enregistre les métriques de performance."""
        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                INSERT INTO performance_metrics (
                    task_id, task_run_id, total_duration_seconds,
                    ai_processing_time_seconds, testing_time_seconds,
                    total_ai_calls, total_tokens_used, total_ai_cost,
                    test_coverage_final, retry_attempts
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                task_id, task_run_id, total_duration_seconds,
                ai_processing_time_seconds, testing_time_seconds,
                total_ai_calls, total_tokens_used, Decimal(str(total_ai_cost)),
                Decimal(str(test_coverage_final)) if test_coverage_final else None,
                retry_attempts
            )

            logger.info(f"📊 Métriques enregistrées pour run {task_run_id}")

    # ===== MÉTHODES WEBHOOK =====

    async def _log_webhook_event(self, source: str, event_type: str, payload: Dict[str, Any],
                                headers: Dict[str, str] = None, signature: str = None) -> int:
        """Enregistre un événement webhook."""
        async with self.db_manager.get_connection() as conn:
            webhook_id = await conn.fetchval("""
                INSERT INTO webhook_events (
                    source, event_type, payload, headers, signature, received_at
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                RETURNING webhook_events_id
            """,
                source, event_type, json.dumps(payload),
                json.dumps(headers) if headers else None, signature
            )

            return webhook_id

    async def _mark_webhook_processed(self, webhook_id: int, success: bool, error_message: str = None):
        """Marque un webhook comme traité."""
        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                UPDATE webhook_events
                SET processed = $1, processing_status = $2, processed_at = NOW(),
                    error_message = $3
                WHERE webhook_events_id = $4
            """,
                success, "completed" if success else "failed",
                error_message, webhook_id
            )

    async def _link_webhook_to_task(self, webhook_id: int, task_id: int):
        """Lie un webhook à une tâche."""
        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                UPDATE webhook_events
                SET related_task_id = $1
                WHERE webhook_events_id = $2
            """, task_id, webhook_id)
    
    async def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère une tâche par son ID.
        
        Args:
            task_id: ID de la tâche (tasks_id)
            
        Returns:
            Dictionnaire avec les données de la tâche ou None si non trouvée
        """
        try:
            logger.debug(f"🔍 Recherche tâche ID: {task_id}")
            
            async with self.db_manager.get_connection() as conn:
                task_row = await conn.fetchrow("""
                    SELECT 
                        tasks_id,
                        monday_item_id,
                        monday_board_id,
                        title,
                        description,
                        priority,
                        repository_url,
                        repository_name,
                        default_branch,
                        monday_status,
                        internal_status,
                        reactivation_count,
                        last_run_id,
                        created_at,
                        updated_at
                    FROM tasks
                    WHERE tasks_id = $1
                """, task_id)
                
                if not task_row:
                    logger.warning(f"⚠️ Tâche {task_id} non trouvée")
                    return None
                
                # Convertir asyncpg.Record en dict
                task_data = dict(task_row)
                logger.debug(f"✅ Tâche {task_id} trouvée: {task_data.get('title', 'N/A')}")
                return task_data
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération tâche {task_id}: {e}", exc_info=True)
            return None

    async def _find_task_by_monday_id(self, monday_item_id) -> Optional[int]:
        """Recherche une tâche par son ID Monday.com."""
        # ✅ CORRECTION: Conversion automatique string → int pour compatibilité webhooks
        try:
            # Normaliser l'ID en int (les webhooks envoient parfois des strings)
            monday_id_int = int(monday_item_id) if monday_item_id is not None else None
            if monday_id_int is None:
                logger.warning(f"⚠️ monday_item_id est None, impossible de rechercher")
                return None
                
            async with self.db_manager.get_connection() as conn:
                # ✅ LOGS DEBUG: Afficher ce qu'on recherche
                logger.info(f"🔍 Recherche tâche avec monday_item_id={monday_id_int}")
                
                task_id = await conn.fetchval("""
                    SELECT tasks_id FROM tasks WHERE monday_item_id = $1
                """, monday_id_int)
                
                # ✅ LOGS DEBUG: Afficher le résultat
                if task_id:
                    logger.info(f"✅ Tâche trouvée: tasks_id={task_id} pour monday_item_id={monday_id_int}")
                else:
                    logger.warning(f"⚠️ AUCUNE tâche trouvée pour monday_item_id={monday_id_int}")
                    # Vérifier si des tâches existent dans la table
                    all_tasks = await conn.fetch("""
                        SELECT tasks_id, monday_item_id, title 
                        FROM tasks 
                        ORDER BY tasks_id DESC 
                        LIMIT 10
                    """)
                    logger.warning(f"📋 Dernières tâches en DB ({len(all_tasks)}):")
                    for t in all_tasks:
                        logger.warning(f"   - ID {t['tasks_id']}: monday_item_id={t['monday_item_id']}, title='{t['title']}'")

                return task_id
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ ID Monday.com invalide: {monday_item_id} - {e}")
            return None

    async def _update_task_from_monday(self, task_id: int, monday_payload: Dict[str, Any]) -> int:
        """Met à jour une tâche existante depuis un payload Monday.com."""
        async with self.db_manager.get_connection() as conn:
            # Extraire les nouvelles données avec protection des types
            item_name = monday_payload.get("pulseName") or monday_payload.get("itemName", "")
            item_id = monday_payload.get("pulseId") or monday_payload.get("itemId")

            # ✅ PROTECTION: S'assurer que value est un dictionnaire
            value_data = monday_payload.get("value", {})
            if isinstance(value_data, dict):
                label_data = value_data.get("label", {})
                if isinstance(label_data, dict):
                    status = label_data.get("text", "")
                else:
                    status = ""
            else:
                status = ""

            # ✅ AMÉLIORATION: Extraire aussi les colonnes pour mettre à jour description et repository_url
            raw_columns = monday_payload.get("columnValues", monday_payload.get("column_values", {}))
            
            # Normaliser les colonnes en dictionnaire
            normalized_columns = {}
            if isinstance(raw_columns, list):
                for col in raw_columns:
                    if isinstance(col, dict) and "id" in col:
                        normalized_columns[col["id"]] = col
            elif isinstance(raw_columns, dict):
                normalized_columns = raw_columns
            
            # Fonction helper pour extraction sécurisée
            def safe_extract_text(col_id: str, default: str = "") -> str:
                """Extrait le texte d'une colonne de manière sécurisée."""
                col_data = normalized_columns.get(col_id, {})
                if isinstance(col_data, dict):
                    col_type = col_data.get("type", "")
                    if col_type == "link":
                        url_value = col_data.get("url")
                        if url_value:
                            return url_value.strip()
                        text_value = col_data.get("text")
                        if text_value:
                            return text_value.strip()
                    
                    return (col_data.get("text") or
                           col_data.get("value") or
                           col_data.get("url") or
                           str(col_data.get("display_value", "")) or
                           default).strip()
                return default
            
            # Extraire description et repository_url
            description = ""
            repository_url = ""
            
            # ✅ DEBUG: Afficher toutes les colonnes disponibles
            logger.info(f"🔍 DEBUG: Colonnes Monday.com disponibles ({len(normalized_columns)}):")
            for col_id, col_data in list(normalized_columns.items())[:10]:  # Afficher les 10 premières
                if isinstance(col_data, dict):
                    col_type = col_data.get("type", "unknown")
                    col_text = col_data.get("text", "")
                    col_value = col_data.get("value", "")
                    logger.info(f"   • {col_id} (type: {col_type}): text='{col_text[:50]}...', value='{str(col_value)[:50]}...'")
            
            # Description - recherche élargie
            for col_id in normalized_columns.keys():
                col_id_lower = col_id.lower()
                col_data = normalized_columns.get(col_id, {})
                
                # ✅ AMÉLIORATION: Recherche plus large de colonnes de description
                if any(keyword in col_id_lower for keyword in
                      ["description", "desc", "details", "text", "note", "comment", "sujet", "long_text", "body"]):
                    extracted_desc = safe_extract_text(col_id)
                    if extracted_desc and len(extracted_desc) > len(description):
                        description = extracted_desc
                        logger.info(f"📝 Description mise à jour depuis colonne '{col_id}': '{extracted_desc[:100]}...'")
                
                # ✅ NOUVEAU: Recherche par type de colonne (long_text, text)
                elif isinstance(col_data, dict) and col_data.get("type") in ["long_text", "text"]:
                    extracted_desc = safe_extract_text(col_id)
                    if extracted_desc and len(extracted_desc) > len(description):
                        description = extracted_desc
                        logger.info(f"📝 Description mise à jour depuis colonne de type '{col_data.get('type')}' ('{col_id}'): '{extracted_desc[:100]}...'")
            
            # ✅ FALLBACK: Si toujours pas de description, essayer de récupérer les updates Monday.com
            if not description:
                logger.info("🔄 Aucune description trouvée dans les colonnes, tentative récupération des updates...")
                try:
                    from tools.monday_tool import MondayTool
                    monday_tool = MondayTool()
                    
                    # Récupérer les updates de l'item
                    updates_result = await monday_tool._arun(action="get_item_updates", item_id=str(item_id))
                    
                    if updates_result and isinstance(updates_result, dict) and "updates" in updates_result:
                        updates = updates_result["updates"]
                        logger.info(f"📋 {len(updates)} updates récupérées depuis Monday.com")
                        
                        # Chercher le premier update avec du contenu
                        for update in updates:
                            if isinstance(update, dict):
                                update_body = update.get('body', '').strip()
                                if update_body:
                                    # Nettoyer le HTML
                                    import re
                                    import html
                                    clean_body = re.sub(r'<[^>]+>', '', update_body)
                                    clean_body = html.unescape(clean_body).strip()
                                    
                                    if clean_body and len(clean_body) > 10:  # Au moins 10 caractères
                                        description = clean_body
                                        logger.info(f"📝 Description extraite depuis update Monday.com: '{description[:100]}...'")
                                        break
                    else:
                        logger.info("ℹ️ Aucun update trouvé dans Monday.com")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erreur récupération updates Monday.com: {e}")
            
            # ✅ FALLBACK FINAL: Utiliser le nom de l'item comme description
            if not description:
                description = f"Tâche: {item_name}"
                logger.info(f"📝 Description générée depuis le nom de l'item: '{description}'")
            
            # Repository URL - chercher d'abord dans les colonnes
            from config.settings import get_settings
            settings = get_settings()
            
            if settings.monday_repository_url_column_id:
                extracted_url = safe_extract_text(settings.monday_repository_url_column_id)
                if extracted_url:
                    repository_url = extracted_url
                    logger.info(f"🔗 URL repository trouvée dans colonne configurée: {repository_url}")
            
            # Fallback: chercher dans toutes les colonnes
            if not repository_url:
                for col_id in normalized_columns.keys():
                    col_id_lower = col_id.lower()
                    if any(keyword in col_id_lower for keyword in
                          ["repo", "repository", "url", "github", "git", "project"]):
                        extracted_url = safe_extract_text(col_id)
                        if extracted_url and ("github.com" in extracted_url or "git" in extracted_url):
                            repository_url = extracted_url
                            logger.info(f"🔗 URL repository trouvée dans colonne '{col_id}': {repository_url}")
                            break
            
            # ✅ CORRECTION CRITIQUE: Si pas d'URL trouvée, utiliser le resolver pour récupérer depuis les PR
            if not repository_url or repository_url.strip() == "":
                logger.info(f"🔄 URL repository non définie - recherche via PR précédentes pour tâche {task_id}")
                
                try:
                    from services.repository_url_resolver import RepositoryUrlResolver
                    resolved_url = await RepositoryUrlResolver.resolve_repository_url(
                        task_db_id=task_id,
                        monday_item_id=item_id
                    )
                    
                    if resolved_url:
                        repository_url = resolved_url
                        logger.info(f"✅ URL repository résolue via PR: {repository_url}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erreur résolution URL repository: {e}")
            
            # Construire la requête de mise à jour dynamiquement
            updates = ["monday_status = $1", "updated_at = NOW()"]
            params = [status]
            param_count = 2
            
            if item_name:
                updates.append(f"title = ${param_count}")
                params.append(item_name)
                param_count += 1
            
            if description:
                updates.append(f"description = ${param_count}")
                params.append(description)
                param_count += 1
                logger.info(f"📝 Description mise à jour: {description[:50]}...")
            
            if repository_url:
                updates.append(f"repository_url = ${param_count}")
                params.append(repository_url)
                param_count += 1
                
                # Mettre à jour aussi le nom du repository
                repo_name = repository_url.split('/')[-1] if repository_url else ""
                updates.append(f"repository_name = ${param_count}")
                params.append(repo_name)
                param_count += 1
                
                logger.info(f"🔗 URL repository mise à jour: {repository_url}")
            
            # Ajouter task_id en dernier paramètre
            params.append(task_id)
            
            # Exécuter la mise à jour
            query = f"""
                UPDATE tasks
                SET {', '.join(updates)}
                WHERE tasks_id = ${param_count}
            """
            
            await conn.execute(query, *params)
            logger.info(f"✅ Tâche {task_id} mise à jour avec {len(updates)} champs")

            return task_id

    async def save_run_step_checkpoint(self, step_id: int, checkpoint_data: Dict[str, Any]):
        """Sauvegarde un checkpoint pour une étape de run."""
        try:
            async with self.db_manager.get_connection() as conn:
                # Nettoyer les données pour la sérialisation JSON
                clean_data = self._clean_for_json_serialization(checkpoint_data)
                checkpoint_json = json.dumps(clean_data)

                await conn.execute("""
                    UPDATE run_steps
                    SET checkpoint_data = $1, checkpoint_saved_at = NOW()
                    WHERE run_steps_id = $2
                """, checkpoint_json, step_id)

                logger.debug(f"💾 Checkpoint sauvegardé pour étape {step_id}")

        except Exception as e:
            logger.warning(f"⚠️ Erreur sauvegarde checkpoint étape {step_id}: {e}")
            # Ne pas faire échouer le workflow pour un problème de checkpoint

    async def get_step_id_by_task_run_and_node(self, task_run_id: int, node_name: str) -> Optional[int]:
        """Récupère l'ID du step à partir du task_run_id et du nom du nœud."""
        try:
            async with self.db_manager.get_connection() as conn:
                # Tronquer le nom du nœud pour correspondre à ce qui est en base
                truncated_node_name = self._truncate_node_name(node_name)

                step_id = await conn.fetchval("""
                    SELECT run_steps_id FROM run_steps
                    WHERE task_run_id = $1 AND node_name = $2
                    ORDER BY step_order DESC
                    LIMIT 1
                """, task_run_id, truncated_node_name)

                return step_id

        except Exception as e:
            logger.warning(f"⚠️ Erreur récupération step_id pour task_run_id={task_run_id}, node={node_name}: {e}")
            return None

    async def save_node_checkpoint(self, task_run_id: int, node_name: str, checkpoint_data: Dict[str, Any]):
        """
        Sauvegarde un checkpoint pour un nœud avec gestion robuste des steps.

        Cette méthode garantit l'existence d'un step avant de sauvegarder le checkpoint,
        avec gestion des race conditions et validation des données.

        Args:
            task_run_id: ID du run de tâche
            node_name: Nom du nœud (sera tronqué si nécessaire)
            checkpoint_data: Données du checkpoint à sauvegarder

        Raises:
            ValueError: Si les paramètres sont invalides
        """
        # ✅ VALIDATION: Vérifier les paramètres d'entrée
        if not task_run_id or task_run_id <= 0:
            raise ValueError(f"task_run_id invalide: {task_run_id}")
        if not node_name or not isinstance(node_name, str):
            raise ValueError(f"node_name invalide: {node_name}")
        if not isinstance(checkpoint_data, dict):
            raise ValueError(f"checkpoint_data doit être un dictionnaire: {type(checkpoint_data)}")

        try:
            # ✅ ROBUSTESSE: Utiliser une transaction pour éviter les race conditions
            async with self.db_manager.get_connection() as conn:
                async with conn.transaction():
                    # Récupérer ou créer le step de manière atomique
                    step_id = await self._get_or_create_step_atomic(
                        conn, task_run_id, node_name, checkpoint_data
                    )

                    if step_id:
                        # Nettoyer les données avant sauvegarde
                        cleaned_data = self._clean_for_json_serialization(checkpoint_data)

                        # Sauvegarder le checkpoint
                        await self._save_checkpoint_atomic(conn, step_id, cleaned_data)

                        logger.debug(f"💾 Checkpoint sauvé pour {node_name} (step_id: {step_id}, task_run_id: {task_run_id})")
                    else:
                        logger.error(f"❌ Impossible de créer ou récupérer step_id pour task_run_id={task_run_id}, node={node_name}")

        except ValueError as ve:
            logger.error(f"❌ Erreur validation checkpoint {node_name}: {ve}")
            raise  # Re-lever les erreurs de validation
        except Exception as e:
            logger.warning(f"⚠️ Erreur sauvegarde checkpoint {node_name}: {e}")
                         # Ne pas faire échouer le workflow pour un problème de checkpoint non-critique

    async def _get_or_create_step_atomic(self, conn, task_run_id: int, node_name: str, checkpoint_data: Dict[str, Any]) -> Optional[int]:
        """
        Récupère ou crée un step de manière atomique pour éviter les race conditions.

        Args:
            conn: Connexion de base de données (dans une transaction)
            task_run_id: ID du run de tâche
            node_name: Nom du nœud
            checkpoint_data: Données pour créer le step si nécessaire

        Returns:
            ID du step ou None si impossible
        """
        try:
            # Tronquer le nom du nœud pour correspondre à la base
            truncated_node_name = self._truncate_node_name(node_name)

            # Essayer de récupérer un step existant
            step_id = await conn.fetchval("""
                SELECT run_steps_id FROM run_steps
                WHERE task_run_id = $1 AND node_name = $2
                ORDER BY step_order DESC
                LIMIT 1
            """, task_run_id, truncated_node_name)

            if step_id:
                logger.debug(f"📋 Step existant trouvé: {step_id} pour {node_name}")
                return step_id

            # Si aucun step trouvé, en créer un nouveau
            logger.info(f"🔄 Création nouveau step pour {node_name} (task_run_id: {task_run_id})")

            # Déterminer le step_order suivant
            next_order = await conn.fetchval("""
                SELECT COALESCE(MAX(step_order), 0) + 1
                FROM run_steps WHERE task_run_id = $1
            """, task_run_id) or 1

            # Déterminer le statut approprié
            status = checkpoint_data.get("status", "completed")
            if status not in ["pending", "running", "completed", "failed", "skipped"]:
                status = "completed"

            # Créer le step avec sérialisation JSON correcte
            clean_checkpoint = self._clean_for_json_serialization(checkpoint_data)
            checkpoint_json = json.dumps(clean_checkpoint, ensure_ascii=False, separators=(',', ':'))

            step_id = await conn.fetchval("""
                INSERT INTO run_steps (task_run_id, node_name, status, step_order, started_at, input_data)
                VALUES ($1, $2, $3, $4, NOW(), $5)
                RETURNING run_steps_id
            """, task_run_id, truncated_node_name, status, next_order,
                checkpoint_json)

            logger.info(f"✅ Step créé: {step_id} pour {node_name} (order: {next_order})")
            return step_id

        except Exception as e:
            logger.error(f"❌ Erreur création step atomique pour {node_name}: {e}")
            return None

    async def _save_checkpoint_atomic(self, conn, step_id: int, checkpoint_data: Dict[str, Any]):
        """
        Sauvegarde un checkpoint de manière atomique.

        Args:
            conn: Connexion de base de données (dans une transaction)
            step_id: ID du step
            checkpoint_data: Données du checkpoint (déjà nettoyées)
        """
        try:
            checkpoint_json = json.dumps(checkpoint_data, ensure_ascii=False, separators=(',', ':'))

            existing_checkpoint = await conn.fetchval("""
                SELECT checkpoint_id FROM run_step_checkpoints
                WHERE step_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """, step_id)

            if existing_checkpoint:
                await conn.execute("""
                    UPDATE run_step_checkpoints
                    SET checkpoint_data = $2, updated_at = NOW()
                    WHERE checkpoint_id = $1
                """, existing_checkpoint, checkpoint_json)
                logger.debug(f"📝 Checkpoint mis à jour: {existing_checkpoint}")
            else:
                checkpoint_id = await conn.fetchval("""
                    INSERT INTO run_step_checkpoints (step_id, checkpoint_data, created_at)
                    VALUES ($1, $2, NOW())
                    RETURNING checkpoint_id
                """, step_id, checkpoint_json)
                logger.debug(f"📝 Nouveau checkpoint créé: {checkpoint_id}")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde checkpoint atomique: {e}")
            raise
    
    async def create_update_trigger(
        self,
        task_id: int,
        monday_update_id: str,
        webhook_id: Optional[int],
        update_text: str,
        detected_type: str,
        confidence: float,
        requires_workflow: bool,
        analysis_reasoning: str,
        extracted_requirements: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Enregistre un déclenchement de workflow depuis un update Monday.
        
        Args:
            task_id: ID de la tâche
            monday_update_id: ID de l'update Monday.com
            webhook_id: ID du webhook (optionnel)
            update_text: Texte du commentaire
            detected_type: Type détecté (UpdateType)
            confidence: Confiance du LLM (0-1)
            requires_workflow: Si un workflow est requis
            analysis_reasoning: Explication de l'analyse
            extracted_requirements: Requirements extraits (JSON)
            
        Returns:
            ID du trigger créé
        """
        async with self.db_manager.get_connection() as conn:
            trigger_id = await conn.fetchval("""
                INSERT INTO task_update_triggers (
                    task_id, monday_update_id, webhook_id, update_text,
                    detected_type, confidence, requires_workflow,
                    analysis_reasoning, extracted_requirements
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING trigger_id
            """,
                task_id, monday_update_id, webhook_id, update_text,
                detected_type, confidence, requires_workflow,
                analysis_reasoning,
                json.dumps(extracted_requirements) if extracted_requirements else None
            )
            
            logger.info(f"📝 Update trigger créé: {trigger_id} (type={detected_type}, confidence={confidence})")
            return trigger_id
    
    async def mark_trigger_as_processed(
        self,
        trigger_id: int,
        triggered_workflow: bool,
        new_run_id: Optional[int] = None,
        celery_task_id: Optional[str] = None
    ):
        """
        Marque un trigger comme traité.
        
        Args:
            trigger_id: ID du trigger
            triggered_workflow: Si un workflow a été déclenché
            new_run_id: ID du nouveau run créé (si applicable)
            celery_task_id: ID de la tâche Celery (si applicable)
        """
        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                UPDATE task_update_triggers
                SET triggered_workflow = $1,
                    new_run_id = $2,
                    celery_task_id = $3,
                    processed_at = NOW()
                WHERE trigger_id = $4
            """,
                triggered_workflow, new_run_id, celery_task_id, trigger_id
            )
            
            logger.debug(f"✅ Trigger {trigger_id} marqué comme traité (workflow={triggered_workflow})")
    
    async def get_task_update_triggers(
        self,
        task_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Récupère les triggers d'update pour une tâche.
        
        Args:
            task_id: ID de la tâche
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des triggers
        """
        async with self.db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT 
                    trigger_id,
                    monday_update_id,
                    update_text,
                    detected_type,
                    confidence,
                    requires_workflow,
                    triggered_workflow,
                    new_run_id,
                    created_at,
                    processed_at
                FROM task_update_triggers
                WHERE task_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, task_id, limit)
            
            return [dict(row) for row in rows]
    
    async def get_update_trigger_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques des triggers d'update.
        
        Returns:
            Dictionnaire avec les statistiques
        """
        async with self.db_manager.get_connection() as conn:
            stats = await conn.fetch("""
                SELECT 
                    detected_type,
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN requires_workflow THEN 1 ELSE 0 END) AS requires_workflow_count,
                    SUM(CASE WHEN triggered_workflow THEN 1 ELSE 0 END) AS triggered_workflow_count,
                    AVG(confidence) AS avg_confidence
                FROM task_update_triggers
                GROUP BY detected_type
                ORDER BY total_count DESC
            """)
            
            return {
                "by_type": [dict(row) for row in stats],
                "total": sum(row['total_count'] for row in stats)
            }
    
    async def log_reactivation(
        self,
        task_id: int,
        run_id: Optional[int],
        trigger_type: str,
        update_text: Optional[str] = None,
        update_data: Optional[Dict[str, Any]] = None,
        confidence_score: Optional[float] = None,
        reasoning: Optional[str] = None,
        triggered_by: Optional[str] = None,
        celery_task_id: Optional[str] = None
    ) -> int:
        """
        ⚠️ DEPRECATED & BROKEN: Cette méthode N'EST PLUS UTILISÉE et NE FONCTIONNE PAS!
        
        ❌ CRITIQUE: Essaie d'INSERT dans des colonnes qui N'EXISTENT PAS:
           run_id, trigger_source, triggered_by, update_text, confidence_score,
           reasoning, celery_task_id, started_at, reactivation_id
        
        ✅ UTILISER: WorkflowReactivationService._log_reactivation_attempt() à la place
        
        Cette méthode redirige automatiquement vers la méthode correcte.
        """
        logger.warning(f"⚠️ DEPRECATED: log_reactivation() appelée pour task_id={task_id}")
        logger.warning("⚠️ Cette méthode utilise un schéma obsolète!")
        logger.warning("⚠️ Redirection vers WorkflowReactivationService._log_reactivation_attempt()")
        
        # Redirection vers la méthode correcte
        try:
            from services.workflow_reactivation_service import WorkflowReactivationService
            service = WorkflowReactivationService()
            reactivation_id = await service._log_reactivation_attempt(
                task_id=task_id,
                trigger_type=trigger_type,
                update_data=update_data or {}
            )
            logger.info(f"✅ Redirection réussie: reactivation_id={reactivation_id}")
            return reactivation_id
        except Exception as e:
            logger.error(f"❌ Erreur redirection log_reactivation: {e}", exc_info=True)
            raise
    
    async def update_reactivation_status(
        self,
        reactivation_id: int,
        status: str,
        success: Optional[bool] = None,
        error_message: Optional[str] = None,
        previous_tasks_revoked: Optional[int] = None
    ):
        """
        ⚠️ DEPRECATED: Cette méthode n'est plus utilisée.
        Utiliser WorkflowReactivationService._update_reactivation_status() à la place.
        
        Met à jour le statut d'une réactivation.
        
        Args:
            reactivation_id: ID de la réactivation
            status: Nouveau statut ('processing', 'completed', 'failed')
            success: Si la réactivation a réussi
            error_message: Message d'erreur si échec
            previous_tasks_revoked: Nombre de tâches révoquées
        """
        try:
            async with self.db_manager.get_connection() as conn:
                completed_at = datetime.now(timezone.utc) if status in ['completed', 'failed'] else None
                
                await conn.execute("""
                    UPDATE workflow_reactivations
                    SET status = $1,
                        success = $2,
                        error_message = $3,
                        previous_tasks_revoked = COALESCE($4, previous_tasks_revoked),
                        completed_at = COALESCE($5, completed_at)
                    WHERE reactivation_id = $6
                """,
                status,
                success,
                error_message,
                previous_tasks_revoked,
                completed_at,
                reactivation_id
                )
                
                logger.debug(f"📝 Réactivation {reactivation_id} mise à jour: {status}")
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour réactivation {reactivation_id}: {e}", exc_info=True)


db_persistence = DatabasePersistenceService()