"""Application Celery pour tout le background processing du projet AI-Agent."""

import warnings
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from celery import Celery

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)                    
    print(f"[CELERY_APP.PY] ✅ PYTHONPATH ajouté au démarrage: {PROJECT_ROOT}", flush=True)

try:
    from langchain_core._api.beta_decorator import LangChainBetaWarning
    warnings.simplefilter("ignore", LangChainBetaWarning)
except ImportError:
    warnings.filterwarnings("ignore", message="This API is in beta and may change in the future.")
from celery.signals import worker_ready, worker_shutting_down, worker_process_init, worker_process_shutdown
from kombu import Exchange, Queue
from typing import Dict, Any, Optional
import asyncio

from config.settings import get_settings
from models.schemas import TaskRequest
from services.monitoring_service import monitoring_service
from services.database_persistence_service import db_persistence
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

celery_app = Celery(
    "ai_agent_background",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["services.celery_app"]  
)

default_exchange = Exchange('ai_agent', type='topic')

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_pool_limit=10,
    
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,

    task_default_retry_delay=60,  
    task_max_retries=3,
    task_soft_time_limit=1500,    
    task_time_limit=1800,         
    task_default_exchange='ai_agent',
    task_default_exchange_type='topic',
    task_default_routing_key='task.default',
    task_create_missing_queues=True,
    
    task_queues=[
        Queue('webhooks',
            exchange=default_exchange,
            routing_key='webhook.*',
            queue_arguments={
                'x-max-priority': 10,
                'x-message-ttl': 900000,  
                'x-dead-letter-exchange': 'ai_agent',
                'x-dead-letter-routing-key': 'dead_letter.webhook'
            }),
        
        Queue('workflows',
            exchange=default_exchange,
            routing_key='workflow.*',
            queue_arguments={
                'x-max-priority': 5,
                'x-message-ttl': 3600000,  
                'x-dead-letter-exchange': 'ai_agent',
                'x-dead-letter-routing-key': 'dead_letter.workflow'
            }),
        
        Queue('ai_generation',
            exchange=default_exchange,
            routing_key='ai.*',
            queue_arguments={
                'x-max-priority': 7,
                'x-message-ttl': 1800000,  
                'x-dead-letter-exchange': 'ai_agent',
                'x-dead-letter-routing-key': 'dead_letter.ai'
            }),
        
        Queue('tests',
            exchange=default_exchange,
            routing_key='test.*',
            queue_arguments={
                'x-max-priority': 3,
                'x-message-ttl': 1200000,  
                'x-dead-letter-exchange': 'ai_agent',
                'x-dead-letter-routing-key': 'dead_letter.test'
            }),
        
        # Dead Letter Queue pour les tâches échouées
        Queue('dlq',
            exchange=default_exchange,
            routing_key='dead_letter.*',
            queue_arguments={
                'x-message-ttl': 86400000,  
            }),
    ],
    
    task_routes={
        "ai_agent_background.process_monday_webhook": {
            "queue": "webhooks",
            "routing_key": "webhook.monday",
            "priority": 9
        },
        "ai_agent_background.execute_workflow": {
            "queue": "workflows", 
            "routing_key": "workflow.langgraph",
            "priority": 5
        },
        "ai_agent_background.generate_code": {
            "queue": "ai_generation",
            "routing_key": "ai.generate.code",
            "priority": 7
        },
        "ai_agent_background.run_tests": {
            "queue": "tests",
            "routing_key": "test.execute",
            "priority": 3
        },
        "ai_agent_background.handle_dead_letter": {
            "queue": "dlq",
            "routing_key": "dead_letter.handler",
            "priority": 1
        }
    },
    
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    worker_disable_rate_limits=True,
    task_compression='gzip',
    result_compression='gzip',
    result_expires=3600,  
)


# ❌ ANCIEN SYSTÈME SUPPRIMÉ - Instance webhook_service non utilisée
# ✅ NOUVEAU SYSTÈME: Utilise directement webhook_persistence_service dans les tasks


@celery_app.task(
    bind=True, 
    name="ai_agent_background.process_monday_webhook",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    priority=9
)
def process_monday_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None):
    """
    Tâche Celery principale pour traiter les webhooks Monday.com.
    
    Avec gestion automatique des échecs vers Dead Letter Queue.
    """
    task_id = self.request.id
    
    monday_item_id = payload.get('event', {}).get('pulseId', 'unknown')
    
    if str(monday_item_id).startswith('test_connection'):
        logger.info(f"🧪 Traitement item de test {monday_item_id}",
                    task_id=task_id,
                    queue="webhooks")
    else:
        logger.info("🚀 Démarrage traitement webhook Celery",
                    task_id=task_id,
                    monday_item_id=monday_item_id,
                    queue="webhooks",
                    routing_key="webhook.monday")
    
    try:
        if "_persistence_result" in payload:
            logger.info("✅ Utilisation résultat de persistence pré-calculé par FastAPI")
            result = payload["_persistence_result"]
            logger.info(f"🔍 DEBUG result keys: {list(result.keys())}")
            logger.info(f"🔍 DEBUG result.run_id: {result.get('run_id')}")
            logger.info(f"🔍 DEBUG result.is_reactivation: {result.get('is_reactivation')}")
        else:
            logger.info("⚠️ Résultat non pré-calculé - traitement du webhook avec nouveau système")
            
            from services.webhook_persistence_service import webhook_persistence
            result = asyncio.run(
                webhook_persistence.process_monday_webhook(
                    payload,
                    {},  
                    signature
                )
            )
        
        if result.get('success') and result.get('task_id'):
            is_reactivation = result.get('is_reactivation', False)
            task_exists = result.get('task_exists', False)
            is_new_task = result.get('existing', True) == False
            
            logger.info(f"🔍 Analyse déclenchement workflow: task_id={result['task_id']}, task_exists={task_exists}, is_reactivation={is_reactivation}, is_new_task={is_new_task}")
            
            if task_exists and not is_reactivation and not is_new_task:
                logger.info(f"⚠️ Tâche {result['task_id']} existe déjà et PAS de réactivation - pas de lancement de workflow")
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "result": result,
                    "webhook_payload": payload,
                    "queue": "webhooks",
                    "workflow_skipped": "task_exists"
                }
            
            from models.schemas import TaskRequest
            
            if is_reactivation:
                logger.info(f"🚀 🔔 LANCEMENT WORKFLOW DE RÉACTIVATION pour tâche {result['task_id']}")
            else:
                logger.info(f"🚀 Lancement workflow NOUVEAU pour tâche {result['task_id']}")
            
            task_db_id = result['task_id']
            
            def load_task_from_db_sync(task_id: int) -> Dict[str, Any]:
                """Charge les données complètes de la tâche depuis la base de données (version synchrone pour Celery)."""
                import asyncpg
                loop = None
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def _load():
                        conn = None
                        try:
                            conn = await asyncpg.connect(get_settings().database_url, timeout=30)
                            
                            task_data = await conn.fetchrow("""
                                SELECT tasks_id, monday_item_id, monday_board_id, title, description,
                                    priority, repository_url, repository_name, default_branch,
                                    monday_status, internal_status
                                FROM tasks
                                WHERE tasks_id = $1
                            """, task_id)
                            
                            if not task_data:
                                raise ValueError(f"Tâche {task_id} non trouvée dans la DB")
                            
                            return dict(task_data)
                        finally:
                            if conn:
                                try:
                                    await conn.close()
                                except Exception as e:
                                    logger.debug(f"Erreur fermeture connexion: {e}")
                    
                    return loop.run_until_complete(_load())
                except Exception as e:
                    logger.error(f"Erreur load_task_from_db_sync: {e}")
                    raise
                finally:
                    if loop and not loop.is_closed():
                        try:
                            pending = asyncio.all_tasks(loop)
                            if pending:
                                for task in pending:
                                    task.cancel()
                                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                            loop.close()
                            asyncio.set_event_loop(None)
                        except Exception as e:
                            logger.debug(f"Erreur fermeture loop: {e}")
                            try:
                                asyncio.set_event_loop(None)
                            except:
                                pass
            
            try:
                task_data = load_task_from_db_sync(task_db_id)
                
                logger.info(f"✅ Données tâche chargées depuis DB: {task_data['title']}")
                logger.info(f"📄 Description: {task_data['description'][:100] if task_data['description'] else 'N/A'}...")
                logger.info(f"🔗 Repository URL: {task_data['repository_url'] or 'N/A'}")

                is_reactivation = result.get('is_reactivation', False)
                reactivation_data = result.get('reactivation_data', {})
                reactivation_count = result.get('reactivation_count', 0)
                source_branch = result.get('source_branch', 'main')
                update_text = result.get('update_text', '')  
                
                logger.info(f"🔍 DEBUG extracted values (main block):")
                logger.info(f"   • reactivation_count: {reactivation_count}")
                logger.info(f"   • source_branch: {source_branch}")
                logger.info(f"   • update_text: '{update_text[:100] if update_text else 'VIDE'}...'")
                logger.info(f"   • run_id from result: {result.get('run_id')}")
                
                if is_reactivation:
                    logger.info(f"🔔 Configuration TaskRequest pour RÉACTIVATION #{reactivation_count}")
                    logger.info(f"📝 Contexte réactivation: {update_text[:100] if update_text else 'VIDE'}...")
                    logger.info(f"🌿 Clone depuis: {source_branch}")
                    
                    effective_reactivation_count = max(reactivation_count, 1) if is_reactivation else reactivation_count
                    
                    combined_description = f"""🔄 RÉACTIVATION #{effective_reactivation_count}

{update_text}

📌 Note: Ceci est une NOUVELLE demande suite à la réactivation. Traiter UNIQUEMENT cette demande, PAS la tâche précédente.
"""
                    new_title_base = update_text[:80].strip() if update_text else task_data['title']
                    updated_title = f"[Réactivation {effective_reactivation_count}] {new_title_base}"
                    
                    logger.info("="*80)
                    logger.info("📝 DESCRIPTION MISE À JOUR POUR LA RÉACTIVATION")
                    logger.info("="*80)
                    logger.info(f"🆕 Nouveau commentaire: {update_text}")
                    logger.info(f"📋 Titre réactivation: {updated_title}")
                    logger.info("="*80)
                else:
                    combined_description = task_data['description'] or ''
                    updated_title = task_data['title']
                
                queue_id = payload.get('_queue_id')
                
                task_request = TaskRequest(
                    task_id=str(task_data['monday_item_id'] or task_db_id),
                    title=updated_title,  
                    description=combined_description,  
                    priority=task_data['priority'] or 'medium',
                    repository_url=task_data['repository_url'] or '',
                    branch_name=task_data['default_branch'] or 'main',
                    monday_item_id=task_data['monday_item_id'],
                    board_id=task_data['monday_board_id'],
                    task_db_id=task_db_id,
                    is_reactivation=is_reactivation,  
                    reactivation_context=update_text if is_reactivation else None,  
                    reactivation_count=effective_reactivation_count if is_reactivation else 0,
                    source_branch=source_branch if is_reactivation else 'main',
                    run_id=result.get('run_id') if is_reactivation else None,
                    queue_id=queue_id
                )
                
                if is_reactivation:
                    logger.info(f"✅ TaskRequest créé pour RÉACTIVATION #{reactivation_count} - clone depuis {source_branch}")
                else:
                    logger.info(f"✅ TaskRequest créé pour PREMIER WORKFLOW")
            except Exception as e:
                logger.error(f"❌ Erreur chargement tâche depuis DB: {e}")
                task_info = payload.get('event', {})
                is_reactivation = result.get('is_reactivation', False)
                reactivation_count = result.get('reactivation_count', 0)
                source_branch = result.get('source_branch', 'main')
                update_text = result.get('update_text', '')
                
                logger.info(f"🔍 DEBUG extracted values (main block):")
                logger.info(f"   • reactivation_count: {reactivation_count}")
                logger.info(f"   • source_branch: {source_branch}")
                logger.info(f"   • update_text: '{update_text[:100] if update_text else 'VIDE'}...'")
                logger.info(f"   • run_id from result: {result.get('run_id')}")
                
                effective_reactivation_count = max(reactivation_count, 1) if is_reactivation else reactivation_count
                if is_reactivation and update_text:
                    new_title_base = update_text[:80].strip()
                    fallback_title = f"[Réactivation {effective_reactivation_count}] {new_title_base}"
                elif is_reactivation:
                    fallback_title = f"[Réactivation {effective_reactivation_count}] {task_info.get('pulseName', 'Tâche Monday.com')}"
                else:
                    fallback_title = task_info.get('pulseName', 'Tâche Monday.com')
                
                task_request = TaskRequest(
                    task_id=str(task_db_id),
                    title=fallback_title,
                    description=task_info.get('description', ''),
                    priority=task_info.get('priority', 'medium'),
                    monday_item_id=task_info.get('pulseId'),
                    board_id=task_info.get('boardId'),
                    task_db_id=task_db_id,
                    is_reactivation=is_reactivation,
                    reactivation_context=update_text if is_reactivation else None,
                    reactivation_count=effective_reactivation_count if is_reactivation else 0,
                    source_branch=source_branch if is_reactivation else 'main',
                    run_id=result.get('run_id') if is_reactivation else None
                )
            
            workflow_task = execute_workflow.apply_async(
                args=[task_request.model_dump()],
                priority=5,
                countdown=2 if str(monday_item_id).startswith('test_connection') else 0
            )
            
            result['workflow_task_id'] = workflow_task.id
            logger.info(f"✅ Workflow lancé - Task ID: {workflow_task.id}")
        else:
            if result.get('task_exists', False):
                logger.info(f"ℹ️ Workflow non lancé - tâche existante: {result.get('task_id', 'unknown')}")
            else:
                logger.warning(f"⚠️ Workflow non lancé - pas de task_id: {result}")
        
        return {
            "task_id": task_id,
            "status": "completed",
            "result": result,
            "webhook_payload": payload,
            "queue": "webhooks"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur traitement webhook", 
                    task_id=task_id, 
                    monday_item_id=monday_item_id,
                    error=str(exc))

        
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retry {self.request.retries + 1}/{self.max_retries}", task_id=task_id)
            raise self.retry(countdown=60, exc=exc)
        else:
            handle_dead_letter.delay({
                "original_task": "process_monday_webhook",
                "task_id": task_id,
                "payload": payload,
                "signature": signature,
                "error": str(exc),
                "retries_exhausted": True,
                "timestamp": task_id  
            })
            
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
                "retries_exhausted": True,
                "sent_to_dlq": True
            }


@celery_app.task(
    bind=True, 
    name="ai_agent_background.execute_workflow",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 120},
    priority=5,
    acks_late=True,
    reject_on_worker_lost=True
)
def execute_workflow(self, task_request_dict: Dict[str, Any]):
    """
    Tâche Celery pour exécuter un workflow LangGraph complet.
    
    Permet la parallélisation de plusieurs workflows.
    """
    task_id = self.request.id
    workflow_id = f"celery_{task_id}"
    
    logger.info(f"📦 Task request dict reçu: {task_request_dict.keys()}")
    logger.info(f"🔄 is_reactivation: {task_request_dict.get('is_reactivation', False)}")
    logger.info(f"🔢 reactivation_count: {task_request_dict.get('reactivation_count', 0)}")
    logger.info(f"🌿 source_branch: {task_request_dict.get('source_branch', 'main')}")
    logger.info(f"🔗 repository_url: {task_request_dict.get('repository_url', 'NON DÉFINI')}")
    
    try:
        task_request = TaskRequest(**task_request_dict)
        logger.info(f"✅ TaskRequest créé: is_reactivation={task_request.is_reactivation}, reactivation_count={task_request.reactivation_count}")
    except Exception as e:
        logger.error(f"❌ Erreur création TaskRequest: {e}")
        logger.error(f"📦 Dict problématique: {task_request_dict}")
        raise
    
    if hasattr(task_request, 'task_db_id') and task_request.task_db_id:
        try:
            import asyncpg
            
            def check_if_completed_sync(task_id: int) -> bool:
                """Vérifie si la tâche est déjà completed (version synchrone pour Celery)."""
                loop = None
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def _check():
                        conn = None
                        try:
                            conn = await asyncpg.connect(get_settings().database_url, timeout=30)
                            result = await conn.fetchrow("""
                                SELECT 
                                    t.internal_status,
                                    (SELECT COUNT(*) FROM task_runs WHERE task_id = t.tasks_id) as task_runs_count
                                FROM tasks t
                                WHERE t.tasks_id = $1
                            """, task_id)
                            
                            if result:      
                                if result['internal_status'] == 'completed' and result['task_runs_count'] > 0:
                                    return True
                            return False
                        except Exception as e:
                            logger.debug(f"Erreur vérification statut completed: {e}")
                            return False
                        finally:
                            if conn:
                                try:
                                    await conn.close()
                                except Exception:
                                    pass
                    
                    return loop.run_until_complete(_check())
                except Exception as e:
                    logger.debug(f"Erreur check_if_completed_sync: {e}")
                    return False
                finally:
                    if loop and not loop.is_closed():
                        try:
                            pending = asyncio.all_tasks(loop)
                            if pending:
                                for task in pending:
                                    task.cancel()
                                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                            loop.close()
                            asyncio.set_event_loop(None)
                        except Exception:
                            try:
                                asyncio.set_event_loop(None)
                            except:
                                pass
            
            is_completed = check_if_completed_sync(task_request.task_db_id)
            
            is_reactivation = getattr(task_request, 'is_reactivation', False)
            
            if is_completed and not is_reactivation:
                logger.warning(f"⚠️ Workflow déjà completed pour tâche {task_request.task_db_id} - abandon du re-démarrage")
                return {
                    "task_id": task_id,
                    "workflow_id": workflow_id,
                    "status": "skipped",
                    "message": "Workflow déjà completed - évite le re-démarrage après SIGSEGV",
                    "queue": "workflows"
                }
            elif is_completed and is_reactivation:
                logger.info(f"🔄 Workflow completed mais réactivation demandée pour tâche {task_request.task_db_id} - redémarrage autorisé")
        except Exception as check_error:
            logger.warning(f"⚠️ Impossible de vérifier le statut completed: {check_error}")
    
    if hasattr(task_request, 'task_id') and task_request.task_id and (
        task_request.task_id == "test_connection_123" or 
        str(task_request.task_id).startswith("test_")
    ):
        logger.warning(f"🚫 Tâche de test dev bloquée: {task_request.title} (ID: {task_request.task_id})")
        return {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "status": "blocked",
            "message": "Tâche de test de développement bloquée",
            "queue": "workflows"
        }
    
    if hasattr(task_request, 'task_id') and task_request.task_id and task_request.task_id != "test_connection_123":
        from tools.monday_tool import MondayTool
        monday_tool = MondayTool()
        if not hasattr(monday_tool, 'api_token') or not monday_tool.api_token:
            logger.warning(f"🚫 Workflow bloqué - Monday.com non configuré: {task_request.title}")
            return {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": "blocked",
                "message": "Workflow bloqué - Configurez MONDAY_API_TOKEN dans votre .env",
                "queue": "workflows"
            }
    
    logger.info("🔄 Démarrage workflow LangGraph",
                task_id=task_id,
                workflow_title=task_request.title,
                queue="workflows")
    
    try:
        import sys
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        async def execute_workflow_async():
            result = None
            try:
                try:
                    await monitoring_service.start_workflow_monitoring(workflow_id, task_request_dict)
                except Exception as e:
                    logger.warning(f"⚠️ Erreur démarrage monitoring: {e}")
                
                from graph.workflow_graph import run_workflow
                result = await run_workflow(task_request)
                
                try:
                    await monitoring_service.complete_workflow(workflow_id, result.get('success', False), result)
                except Exception as e:
                    logger.debug(f"Erreur non-critique finalisation monitoring: {e}")
                    
                return result
                
            except Exception as e:
                logger.error(f"❌ Erreur dans execute_workflow_async: {e}", exc_info=True)
                if result is None:
                    result = {
                        'success': False,
                        'error': str(e),
                        'status': 'failed'
                    }
                return result

        result = asyncio.run(execute_workflow_async())
        
        logger.info("✅ Workflow terminé", 
                    task_id=task_id,
                    success=result.get('success', False),
                    duration=result.get('duration', 0))
        
        return {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "status": "completed",
            "result": result,
            "queue": "workflows"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur workflow", 
                    task_id=task_id, 
                    error=str(exc), 
                    exc_info=True)
        
        try:
            asyncio.run(monitoring_service.complete_workflow(workflow_id, False))
        except Exception as e:
            logger.debug(f"Erreur non-critique finalisation monitoring erreur: {e}")
        
        exc_str = str(exc).lower()
        should_retry = (
            "connection" in exc_str or 
            "timeout" in exc_str or
            "network" in exc_str or
            "database" in exc_str or
            "529" in exc_str or
            "overloaded" in exc_str or
            "rate limit" in exc_str
        )
        
        if should_retry and self.request.retries < self.max_retries:
            if "529" in exc_str or "overloaded" in exc_str:
                countdown_time = min(300, 60 * (self.request.retries + 1))  # 1, 2, 5 minutes max
                logger.info(f"🔄 Retry workflow {self.request.retries + 1}/{self.max_retries} (Claude surchargé, attente {countdown_time}s)", task_id=task_id)
                raise self.retry(countdown=countdown_time, exc=exc)
            else:
                logger.info(f"🔄 Retry workflow {self.request.retries + 1}/{self.max_retries} (erreur infrastructure)", task_id=task_id)
                raise self.retry(countdown=120, exc=exc)  # 2 minutes entre retries
        else:
            if "529" in exc_str or "overloaded" in exc_str:
                logger.warning(f"⚠️ Workflow suspendu temporairement à cause de la surcharge Claude", task_id=task_id)

                execute_workflow.apply_async(
                    args=[task_request_dict],
                    countdown=3600,  
                    priority=1  
                )
                
                return {
                    "task_id": task_id,
                    "workflow_id": workflow_id,
                    "status": "suspended",
                    "error": "Claude API surchargée - reprogrammé dans 1h",
                    "retries_exhausted": True,
                    "rescheduled": True
                }
            
            if not should_retry:
                logger.info(f"⏹️ Pas de retry - échec métier (tests/QA): {str(exc)[:100]}", task_id=task_id)
            
            handle_dead_letter.delay({
                "original_task": "execute_workflow", 
                "task_id": task_id,
                "task_request": task_request_dict,
                "workflow_id": workflow_id,
                "error": str(exc),
                "retries_exhausted": True
            })
            
            return {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(exc),
                "retries_exhausted": True,
                "sent_to_dlq": True
            }


@celery_app.task(
    bind=True, 
    name="ai_agent_background.generate_code",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    priority=7
)
def generate_code_task(self, prompt: str, provider: str = "claude", context: Dict[str, Any] = None):
    """
    Tâche Celery pour la génération de code IA.
    
    Permet d'isoler les appels IA et de les paralléliser.
    """
    task_id = self.request.id
    
    from tools.ai_engine_hub import AIEngineHub
    
    logger.info("🤖 Génération code IA", 
                task_id=task_id, 
                provider=provider,
                queue="ai_generation")
    
    ai_hub = AIEngineHub()
    
    try:
        result = asyncio.run(
            ai_hub.generate_code(prompt, provider, context or {})
        )
        
        logger.info("✅ Code généré", 
                    task_id=task_id,
                    provider=provider,
                    tokens_used=result.get('tokens_used', 0))
        
        return {
            "task_id": task_id,
            "status": "completed",
            "provider": provider,
            "result": result,
            "queue": "ai_generation"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur génération code", 
                    task_id=task_id, 
                    provider=provider,
                    error=str(exc), 
                    exc_info=True)
        
        if self.request.retries < self.max_retries:
            alt_provider = "openai" if provider == "claude" else "claude"
            logger.info(f"🔄 Retry avec {alt_provider}", task_id=task_id)
            
            return generate_code_task.retry(
                countdown=30,
                exc=exc,
                args=[prompt, alt_provider, context]
            )
        else:
            handle_dead_letter.delay({
                "original_task": "generate_code",
                "task_id": task_id,
                "prompt": prompt,
                "provider": provider,
                "context": context,
                "error": str(exc),
                "retries_exhausted": True
            })
            
            return {
                "task_id": task_id,
                "status": "failed",
                "provider": provider,
                "error": str(exc),
                "retries_exhausted": True,
                "sent_to_dlq": True
            }


@celery_app.task(
    bind=True, 
    name="ai_agent_background.run_tests",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    priority=3
)
def run_tests_task(self, workflow_id: str, code_changes: Dict[str, str], test_types: list = None):
    """
    Tâche Celery pour exécuter les tests de manière asynchrone.
    """
    task_id = self.request.id
    test_types = test_types or ["unit", "integration", "security"]
    
    from tools.testing_engine import TestingEngine
    
    logger.info("🧪 Exécution tests", 
                task_id=task_id,
                workflow_id=workflow_id,
                test_types=test_types,
                queue="tests")
    
    testing_engine = TestingEngine()
    
    try:
        results = asyncio.run(
            testing_engine.run_comprehensive_tests(code_changes, test_types)
        )
        
        total_tests = sum(len(result.get('results', [])) for result in results.values())
        passed_tests = sum(
            len([r for r in result.get('results', []) if r.get('passed', False)]) 
            for result in results.values()
        )
        
        logger.info("✅ Tests terminés", 
                    task_id=task_id,
                    total_tests=total_tests,
                    passed_tests=passed_tests,
                    success_rate=f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%")
        
        return {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "status": "completed",
            "results": results,
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": (passed_tests/total_tests*100) if total_tests > 0 else 0
            },
            "queue": "tests"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur tests", 
                    task_id=task_id,
                    error=str(exc), 
                    exc_info=True)
        
        if self.request.retries < 2:  
            logger.info(f"🔄 Retry tests {self.request.retries + 1}/2", task_id=task_id)
            raise self.retry(countdown=30, exc=exc)
        else:
            handle_dead_letter.delay({
                "original_task": "run_tests",
                "task_id": task_id,
                "workflow_id": workflow_id,
                "code_changes": code_changes,
                "test_types": test_types,
                "error": str(exc),
                "retries_exhausted": True
            })
            
            return {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(exc),
                "retries_exhausted": True,
                "sent_to_dlq": True
            }


@celery_app.task(name="ai_agent_background.handle_dead_letter", priority=1)
def handle_dead_letter(failed_task_data: Dict[str, Any]):
    """
    Gestionnaire de Dead Letter Queue pour les tâches échouées.
    
    Logs, notifie les admins et stocke les informations d'échec.
    """
    try:
        task_id = failed_task_data.get("task_id", "unknown")
        original_task = failed_task_data.get("original_task", "unknown")
        error = failed_task_data.get("error", "Unknown error")
        
        logger.error("💀 Tâche en Dead Letter Queue", 
                    dlq_task_id=task_id,
                    original_task=original_task,
                    error=error,
                    queue="dlq")
        
        return {
            "dlq_processed": True,
            "original_task": original_task,
            "task_id": task_id,
            "timestamp": failed_task_data.get("timestamp"),
            "action": "logged_and_stored"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur traitement DLQ", error=str(exc))
        return {
            "dlq_processed": False,
            "error": str(exc)
        }


@celery_app.task(name="ai_agent_background.cleanup_old_tasks")
def cleanup_old_tasks():
    """Tâche périodique de nettoyage des anciennes tâches."""
    try:
        from datetime import datetime
        
        logger.info("🧹 Nettoyage des anciennes tâches Celery")
        
        celery_app.backend.cleanup()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            pass
        finally:
            loop.close()
            
        logger.info("✅ Nettoyage terminé")
        return {"status": "completed", "timestamp": datetime.now().isoformat()}
        
    except Exception as exc:
        logger.error("❌ Erreur nettoyage", error=str(exc))
        return {"status": "failed", "error": str(exc)}


celery_app.conf.beat_schedule = {
    "cleanup-old-tasks": {
        "task": "ai_agent_background.cleanup_old_tasks",
        "schedule": 24 * 60 * 60,  # Tous les jours
    },
}

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Signal émis quand un worker Celery est prêt (processus parent)."""
    logger.info("🚀 Celery worker prêt (parent)", 
                worker=sender,
                broker="RabbitMQ",
                backend="PostgreSQL")
    
    try:
        from services.logging_service import logging_service
        if logging_service.setup_logging():
            logger.info("✅ Logging Celery configuré de manière robuste")
            logs_info = logging_service.get_logs_info()
            logger.info(f"📊 Logs: {logs_info['logs_directory']} ({logs_info['environment']})")
        else:
            logger.warning("⚠️ Configuration logging basique appliquée")
    except Exception as e:
        logger.error(f"❌ Erreur configuration logging: {e}")


@worker_process_init.connect
def worker_process_init_handler(**kwargs):
    """
    Signal émis quand un worker process Celery est initialisé (après fork).
    """
    import os
    import sys
    
    pid = os.getpid()
    
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
        logger.info(f"✅ PYTHONPATH ajouté pour worker PID={pid}: {PROJECT_ROOT}")
    
    logger.info(f"🔄 Initialisation worker process PID={pid}")
    
    try:
        from utils.database_manager import db_manager
        
        if db_manager.pool:
            logger.debug(f"🔒 Reset flags pool hérité dans worker PID={pid}")
            db_manager._is_initialized = False
            db_manager.pool = None
        
        logger.info(f"✅ Worker PID={pid} prêt (pool sera créé à la demande)")
    except Exception as e:
        logger.error(f"❌ Erreur initialisation worker PID={pid}: {e}")


@worker_process_shutdown.connect
def worker_process_shutdown_handler(**kwargs):
    """
    Signal émis quand un worker process se termine (avant la fin du fork).
    
    """
    import os
    pid = os.getpid()
    logger.info(f"🔒 Arrêt worker process PID={pid}")
    
    try:
        from utils.database_manager import db_manager
        
        if db_manager.pool:
            db_manager._is_initialized = False
            db_manager.pool = None
            logger.debug(f"✅ Flags pool réinitialisés pour worker PID={pid}")
                
    except Exception as e:
        logger.debug(f"Erreur non-critique shutdown worker PID={pid}: {e}")


@worker_shutting_down.connect
def worker_shutting_down_handler(sender=None, **kwargs):
    """Signal émis quand un worker Celery s'arrête (processus parent)."""
    logger.info("🔄 Celery worker arrêt (parent)", worker=sender)


def submit_task(task_name: str, *args, **kwargs):
    """
    Fonction utilitaire pour soumettre des tâches Celery avec monitoring.
    """
    try:
        task_options = {}
        if 'priority' in kwargs:
            task_options['priority'] = kwargs.pop('priority')
            
        task = celery_app.send_task(task_name, args=args, kwargs=kwargs, **task_options)
        logger.info("📨 Tâche soumise", 
                    task_name=task_name, 
                    task_id=task.id,
                    broker="RabbitMQ")
        return task
    except Exception as exc:
        logger.error("❌ Erreur soumission tâche", 
                    task_name=task_name, 
                    error=str(exc))
        raise


if __name__ == "__main__":
    celery_app.start() 