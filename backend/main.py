"""Point d'entrée principal de l'Agent d'Automatisation IA."""
import sys
import warnings
from typing import Dict, Optional

# ✅ SUPPRESSION des warnings LangChain Beta pour nettoyer les logs
try:
    from langchain_core._api.beta_decorator import LangChainBetaWarning
    warnings.simplefilter("ignore", LangChainBetaWarning)
except ImportError:
    # Fallback si l'import échoue
    warnings.filterwarnings("ignore", message="This API is in beta and may change in the future.")
from models.schemas import MondayColumnValue, MondayEvent, TaskRequest, WebhookPayload
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
# ❌ ANCIEN SYSTÈME SUPPRIMÉ: from services.webhook_service import WebhookService
from services.webhook_persistence_service import webhook_persistence
from services.celery_app import celery_app, submit_task
from config.settings import get_settings
from utils.logger import get_logger

# ✅ NOUVEAU: Imports pour l'évaluation de l'agent
# DEPRECATED: Ces imports ne sont plus utilisés après simplification du Golden Dataset
# from services.evaluation.agent_evaluation_service import AgentEvaluationService
# from models.evaluation_models import DatasetType, AgentEvaluationConfig

# ✅ NOUVEAU: Importer le registry des routers orientés objet
from admin.backend.routes.router_registry import RouterRegistry

# ✅ OPTIMISATION: Importer les services de pool et cache
from admin.backend.init_pools import initialize_services, shutdown_services

# ✅ MONITORING: Importer le service de monitoring
from services.monitoring_service import monitoring_service

print("🔴 DEBUG: main.py est exécuté !")
print(f"🔴 DEBUG: Python path: {sys.path}")

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    logger.info("🚀 Démarrage de l'Agent d'Automatisation IA")
    
    # Récupérer les settings
    settings = get_settings()
    
    # ✅ OPTIMISATION: Initialiser les pools de connexions et le cache
    try:
        await initialize_services()
        logger.info("✅ Services optimisés initialisés (Pool PostgreSQL + Cache Redis)")
    except Exception as e:
        logger.error(f"❌ Erreur initialisation services optimisés: {e}")
    
    # ✅ AUTHENTIFICATION: Initialiser le service d'authentification
    try:
        import asyncpg
        from services.auth_service import AuthService
        
        db_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10
        )
        app.state.auth_db_pool = db_pool
        app.state.auth_service = AuthService(db_pool)
        logger.info("✅ Service d'authentification initialisé")
    except Exception as e:
        logger.error(f"❌ Erreur initialisation service d'authentification: {e}")
        # Continuer même si l'auth échoue pour ne pas bloquer l'app
        import traceback
        logger.error(f"Traceback complet: {traceback.format_exc()}")
    
    # Démarrer le monitoring en arrière-plan
    try:
        await monitoring_service.start_monitoring()
        logger.info("✅ Service de monitoring démarré")
    except Exception as e:
        logger.error(f"❌ Erreur démarrage monitoring: {e}")
    
    yield
    
    # Arrêter proprement les services
    logger.info("🛑 Arrêt de l'Agent d'Automatisation IA")
    
    # ✅ AUTHENTIFICATION: Fermer le pool d'authentification
    try:
        if hasattr(app.state, 'auth_db_pool'):
            await app.state.auth_db_pool.close()
            logger.info("✅ Pool d'authentification fermé")
    except Exception as e:
        logger.error(f"❌ Erreur fermeture pool d'authentification: {e}")
    
    # ✅ OPTIMISATION: Fermer les pools et le cache
    try:
        await shutdown_services()
        logger.info("✅ Services optimisés arrêtés proprement")
    except Exception as e:
        logger.error(f"❌ Erreur arrêt services optimisés: {e}")
    
    try:
        await monitoring_service.stop_monitoring()
        logger.info("✅ Service de monitoring arrêté")
    except Exception as e:
        logger.error(f"❌ Erreur arrêt monitoring: {e}")


# Initialiser l'application FastAPI
app = FastAPI(
    title="Agent d'Automatisation IA",
    description="Automatisation complète du cycle de développement avec IA",
    version="2.0.0",
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:3000"],  # En production, spécifier les domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ OPTIMISATION: Compression GZIP pour réduire la taille des réponses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ✅ NOUVEAU: Enregistrer tous les routers orientés objet pour l'API Admin
RouterRegistry.register_all_routers(app, prefix="/api")

# ✅ NOUVEAU: Middleware pour logger TOUTES les requêtes
@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    """Log toutes les requêtes HTTP pour debugging."""
    print(f"\n{'='*80}")
    print(f"🌐 REQUÊTE HTTP REÇUE: {request.method} {request.url.path}")
    print(f"{'='*80}")
    logger.info(f"🌐 REQUÊTE: {request.method} {request.url.path}")
    
    # Si c'est un webhook Monday
    if "/webhook/monday" in str(request.url.path):
        print("🔔 C'EST UN WEBHOOK MONDAY.COM !")
        logger.info("🔔 C'EST UN WEBHOOK MONDAY.COM !")
    
    response = await call_next(request)
    
    print(f"✅ RÉPONSE: Status {response.status_code}")
    logger.info(f"✅ RÉPONSE: Status {response.status_code}")
    
    return response

# Initialiser les services
settings = get_settings()
# ❌ ANCIEN SYSTÈME SUPPRIMÉ: webhook_service = WebhookService()

# ✅ NOUVEAU: Importer le gestionnaire de queue de workflows
from services.workflow_queue_manager import workflow_queue_manager


@app.get("/")
async def root():
    """Point d'entree racine de l'API."""
    return {
        "message": "Agent d'Automatisation IA",
        "version": "2.0.0",
        "status": "running",
        "background_processing": "Celery",
        "documentation": "/docs"
    }


@app.get("/health")
async def health_check():
    """Verification de santé de l'application."""
    import asyncpg
    import aio_pika
    from redis import asyncio as aioredis
    
    health_status = {
        "status": "healthy",
        "celery_workers": 0,
        "celery_healthy": False,
        "rabbitmq_status": "down",
        "postgres_status": "down",
        "redis_status": "down",
        "version": "2.0.0"
    }
    
    # 1. Vérifier Celery
    try:
        celery_status = celery_app.control.inspect().ping()
        health_status["celery_healthy"] = bool(celery_status)
        health_status["celery_workers"] = len(celery_status) if celery_status else 0
    except Exception as e:
        logger.warning(f"Celery check failed: {e}")
    
    # 2. Vérifier PostgreSQL
    try:
        conn = await asyncpg.connect(settings.database_url)
        await conn.fetchval("SELECT 1")
        await conn.close()
        health_status["postgres_status"] = "up"
    except Exception as e:
        logger.warning(f"PostgreSQL check failed: {e}")
    
    # 3. Vérifier RabbitMQ
    try:
        connection = await aio_pika.connect_robust(settings.celery_broker_url)
        await connection.close()
        health_status["rabbitmq_status"] = "up"
    except Exception as e:
        logger.warning(f"RabbitMQ check failed: {e}")
    
    # 4. Vérifier Redis
    try:
        redis_client = await aioredis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()
        health_status["redis_status"] = "up"
    except Exception as e:
        logger.warning(f"Redis check failed: {e}")
    
    # Déterminer le statut global
    if health_status["postgres_status"] == "up":
        if health_status["celery_healthy"]:
            health_status["status"] = "healthy"
        else:
            health_status["status"] = "degraded"
    else:
        health_status["status"] = "unhealthy"
    
    return health_status


@app.get("/webhook/monday")
async def validate_monday_webhook(request: Request):
    """
    Endpoint GET pour la validation des webhooks Monday.com.
    Monday.com utilise cet endpoint pour vérifier que l'URL est valide.
    """
    try:
        # Monday.com envoie un paramètre 'challenge' pour validation
        challenge = request.query_params.get("challenge")
        
        if challenge:
            logger.info(f"✅ Challenge webhook reçu: {challenge}")
            return JSONResponse(
                content={"challenge": challenge},
                status_code=200,
                headers={"Content-Type": "application/json"}
            )
        else:
            logger.info("ℹ️ Webhook GET sans challenge - endpoint actif")
            return JSONResponse(
                content={"message": "Webhook endpoint actif", "status": "ready"},
                status_code=200,
                headers={"Content-Type": "application/json"}
            )
        
    except Exception as e:
        logger.error(f"❌ Erreur validation webhook: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "Erreur lors de la validation du webhook"},
            status_code=500,
            headers={"Content-Type": "application/json"}
        )
        

@app.post("/webhook/monday")
async def receive_monday_webhook(request: Request):
    """
    Endpoint pour recevoir les webhooks Monday.com.
    """
    try:
        # 🔔 LOG DEBUG: Webhook reçu - AFFICHER TOUT
        print("="*80)
        print("📨 WEBHOOK MONDAY.COM REÇU")
        print("="*80)
        logger.info("="*80)
        logger.info("📨 WEBHOOK MONDAY.COM REÇU")
        logger.info("="*80)
        logger.info(f"🌐 URL: {request.url}")
        logger.info(f"📋 Method: {request.method}")
        logger.info(f"🔑 Headers: {dict(request.headers)}")
        
        # 🔥 AJOUTEZ CE CODE EN TOUT PREMIER
        # Gestion spéciale pour le challenge de validation Monday.com
        try:
            # Lire le body brut pour inspection
            body_bytes = await request.body()
            body_str = body_bytes.decode('utf-8')
            
            # 🔔 LOG DEBUG: Contenu brut du webhook
            logger.debug(f"📦 Body brut reçu (100 premiers caractères): {body_str[:100]}...")
            
            # Vérifier si c'est un simple challenge
            if '"challenge"' in body_str and '"event"' not in body_str:
                import json
                try:
                    payload = json.loads(body_str)
                    if "challenge" in payload and not payload.get("event"):
                        challenge = payload["challenge"]
                        logger.info(f"🎯 Challenge POST reçu: {challenge}")
                        return JSONResponse(content={"challenge": challenge}, status_code=200)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.warning(f"⚠️ Erreur lecture body: {e}")
        
        # Continuer avec le traitement normal
        payload_raw = await request.json()
        
        # ✅ CORRECTION: Logger le payload brut COMPLET pour debugging
        print(f"📦 PAYLOAD BRUT COMPLET:")
        print(f"{payload_raw}")
        logger.info(f"📦 PAYLOAD BRUT COMPLET: {payload_raw}")
        logger.info(f"📦 Payload type: {payload_raw.get('type', 'unknown')}")
        logger.info(f"📦 Payload keys: {list(payload_raw.keys())}")
        if payload_raw.get('event'):
            logger.info(f"📦 Event type: {payload_raw['event'].get('type', 'unknown')}")
            logger.info(f"📦 Event keys: {list(payload_raw['event'].keys())}")
        
        # Validation du payload avec le nouveau schéma
        try:
            webhook_payload = WebhookPayload(**payload_raw)
        except Exception as validation_error:
            logger.error("="*80)
            logger.error("❌ PAYLOAD WEBHOOK MALFORMÉ")
            logger.error("="*80)
            logger.error(f"Erreur: {str(validation_error)}")
            logger.error(f"Payload keys: {list(payload_raw.keys()) if isinstance(payload_raw, dict) else 'non-dict'}")
            logger.error(f"Payload complet: {payload_raw}")
            logger.error("="*80)
            
            # Vérifier si c'est quand même un challenge valide
            if "challenge" in payload_raw and not payload_raw.get("event"):
                challenge = payload_raw["challenge"] 
                logger.info(f"✅ Challenge webhook reçu (payload non-standard): {challenge}")
                return JSONResponse(content={"challenge": challenge}, status_code=200)
            
            # ✅ CORRECTION: Essayer de traiter quand même si c'est un événement valide
            if "event" in payload_raw and isinstance(payload_raw["event"], dict):
                logger.warning("⚠️ Tentative de traitement malgré l'erreur de validation...")
                # Passer directement au service de persistence qui est plus tolérant
                try:
                    persistence_result = await webhook_persistence.process_monday_webhook(
                        payload_raw,
                        dict(request.headers),
                        request.headers.get("X-Monday-Signature")
                    )
                    logger.info(f"✅ Traité malgré erreur de validation: {persistence_result}")
                    return JSONResponse(content={"success": True, "message": "Traité avec tolérance"}, status_code=200)
                except Exception as e2:
                    logger.error(f"❌ Échec même avec tolérance: {e2}")
            
            raise HTTPException(
                status_code=400, 
                detail=f"Format de payload invalide: {str(validation_error)}"
            )
        
        # Vérifier si c'est un challenge de validation Monday.com
        if webhook_payload.challenge and not webhook_payload.event:
            challenge = webhook_payload.challenge
            logger.info(f"✅ Challenge webhook reçu via POST: {challenge}")
            return JSONResponse(content={"challenge": challenge}, status_code=200)
        
        # Vérifier qu'on a bien un événement à traiter
        if not webhook_payload.event:
            logger.warning("⚠️ Webhook reçu sans événement")
            return JSONResponse(
                content={
                    "message": "Webhook reçu mais aucun événement à traiter",
                    "status": "ignored"
                },
                status_code=200
            )
        
        # Extraire les informations de la tâche
        task_info = webhook_payload.extract_task_info()
        if not task_info:
            logger.info("ℹ️ Webhook ignoré - pas de tâche extractable")
            return JSONResponse(
                content={
                    "message": "Webhook reçu mais pas de tâche à traiter",
                    "status": "ignored"
                },
                status_code=200
            )
        
        # Récupérer la signature pour validation sécurisée
        signature = request.headers.get("X-Monday-Signature")
        
        # 🔔 LOG DEBUG: Informations du webhook
        logger.info(f"📋 Type d'événement: {webhook_payload.type}")
        logger.info(f"📌 Pulse ID: {webhook_payload.event.pulseId}")
        logger.info(f"📊 Board ID: {webhook_payload.event.boardId}")
        
        # ✅ PERSISTENCE: Traiter et enregistrer le webhook en temps réel
        persistence_result = await webhook_persistence.process_monday_webhook(
            payload_raw, 
            dict(request.headers), 
            signature
        )
        
        # 🔔 LOG DEBUG: Résultat de la persistence
        logger.info("="*80)
        logger.info("📊 RÉSULTAT DE LA PERSISTENCE")
        logger.info("="*80)
        logger.info(f"✅ Webhook ID: {persistence_result.get('webhook_id')}")
        logger.info(f"📝 Task ID: {persistence_result.get('task_id')}")
        logger.info(f"🔄 Est une réactivation: {persistence_result.get('is_reactivation', False)}")
        logger.info(f"💬 Message: {persistence_result.get('message', 'N/A')}")
        
        # Logs détaillés du webhook reçu avec persistence
        logger.info("📨 Webhook Monday.com reçu et persisté", 
                   pulse_id=webhook_payload.event.pulseId,
                   board_id=webhook_payload.event.boardId,
                   event_type=webhook_payload.type,
                   task_title=task_info.get("title", "N/A"),
                   task_type=task_info.get("task_type", "N/A"),
                   priority=task_info.get("priority", "N/A"),
                   webhook_id=persistence_result.get("webhook_id"),
                   db_task_id=persistence_result.get("task_id"))
        
        # ✅ CORRECTION: Vérifier si la tâche existe déjà pour éviter la duplication
        if persistence_result.get("task_exists", False):
            # ✅ NOUVEAU: Vérifier si c'est une réactivation
            is_reactivation = persistence_result.get("is_reactivation", False)
            
            if is_reactivation:
                logger.info("="*80)
                logger.info("🚀 TENTATIVE DE LANCEMENT DU WORKFLOW RÉACTIVÉ")
                logger.info("="*80)
                
                task_id = persistence_result.get("task_id")
                reactivation_data = persistence_result.get("reactivation_data", {})
                
                # ✅ CORRECTION: run_id peut être dans reactivation_data OU au niveau supérieur
                run_id = reactivation_data.get("run_id") or persistence_result.get("run_id")
                
                logger.info(f"🔍 DEBUG Réactivation:")
                logger.info(f"   • task_id: {task_id}")
                logger.info(f"   • run_id: {run_id}")
                logger.info(f"   • reactivation_data keys: {reactivation_data.keys() if reactivation_data else 'None'}")
                
                # ✅ CORRECTION CRITIQUE: Vérifier que la réactivation a bien réussi
                if not run_id or not task_id:
                    error_msg = persistence_result.get("message", "Erreur inconnue lors de la réactivation")
                    logger.error("="*80)
                    logger.error("❌ ÉCHEC DU LANCEMENT DU WORKFLOW RÉACTIVÉ")
                    logger.error("="*80)
                    logger.error(f"🆔 Task ID: {task_id}")
                    logger.error(f"🔄 Run ID: {run_id}")
                    logger.error(f"❌ Erreur: {error_msg}")
                    logger.error(f"📦 Données de réactivation: {reactivation_data}")
                    logger.error("="*80)
                    
                    return JSONResponse(
                        content={
                            "success": False,
                            "message": f"Échec de la réactivation: {error_msg}",
                            "task_id": task_id,
                            "error": error_msg,
                            "status": "reactivation_failed",
                            "status_code": 400
                        },
                        status_code=400
                    )
                
                logger.info(f"📝 Task ID: {task_id}")
                logger.info(f"🔄 Run ID: {run_id}")
                logger.info(f"💪 Confidence: {reactivation_data.get('confidence')}")
                
                # ✅ CORRECTION CRITIQUE: Récupérer les informations de la tâche depuis la BDD
                from services.database_persistence_service import db_persistence
                
                task_details = None
                repository_url = ""
                task_title = ""
                task_description = ""
                
                try:
                    # ✅ CORRECTION: Utiliser le gestionnaire centralisé
                    async with db_persistence.db_manager.get_connection() as conn:
                        task_details = await conn.fetchrow("""
                            SELECT 
                                tasks_id,
                                monday_item_id,
                                title,
                                description,
                                repository_url,
                                priority
                            FROM tasks 
                            WHERE tasks_id = $1
                        """, task_id)
                    
                    if task_details:
                        repository_url = task_details['repository_url'] or ""
                        task_title = task_details['title'] or ""
                        task_description = task_details['description'] or ""
                        
                        logger.info(f"✅ Informations tâche récupérées depuis BDD")
                        logger.info(f"🔗 Repository URL: {repository_url}")
                        logger.info(f"📝 Title: {task_title}")
                    else:
                        logger.warning(f"⚠️ Impossible de récupérer les détails de la tâche {task_id}")
                        
                except Exception as e:
                    logger.error(f"❌ Erreur récupération détails tâche: {e}")
                
                # Déclencher le workflow via Celery
                from services.celery_app import execute_workflow
                
                # ✅ CORRECTION: Extraire reactivation_count et le nouveau commentaire
                reactivation_count = reactivation_data.get('reactivation_count', 1)
                update_text = reactivation_data.get('update_text', '')
                
                # ✅ CORRECTION MAJEURE: Créer une NOUVELLE description avec le NOUVEAU commentaire
                combined_description = f"""🔄 RÉACTIVATION #{reactivation_count} - Nouvelle demande:
{update_text}

📋 Description originale:
{task_description or 'N/A'}
"""
                
                # Titre mis à jour pour indiquer la réactivation
                reactivation_title = f"[Réactivation {reactivation_count}] {task_title}"
                
                logger.info("="*80)
                logger.info("📝 NOUVELLE DESCRIPTION POUR LA RÉACTIVATION")
                logger.info("="*80)
                logger.info(f"🆕 Nouveau commentaire: {update_text}")
                logger.info(f"📋 Titre réactivation: {reactivation_title}")
                logger.info(f"📄 Description combinée créée")
                logger.info("="*80)
                
                # ✅ NOUVEAU: Récupérer task_context avec langues depuis reactivation_data
                # Le task_context est dans reactivation_data['reactivation_data'] (double imbrication)
                inner_reactivation_data = reactivation_data.get("reactivation_data", {})
                task_context = inner_reactivation_data.get("task_context", {})
                
                # ✅ CORRECTION CRITIQUE: Construire task_request_dict avec la NOUVELLE description ET task_context
                task_request_dict = {
                    "task_id": str(task_id) if task_id else f"task_{run_id}",
                    "task_db_id": task_id,
                    "run_id": run_id,
                    "monday_item_id": reactivation_data.get("monday_item_id"),
                    "title": reactivation_title,  # ✅ NOUVEAU: Titre avec [Réactivation N]
                    "description": combined_description,  # ✅ NOUVEAU: Description avec nouveau commentaire
                    "task_type": "feature",
                    "priority": task_details.get('priority', 'medium') if task_details else "medium",
                    "repository_url": repository_url or "",
                    "is_reactivation": True,
                    "reactivation_count": reactivation_count,
                    "source_branch": "main",
                    "reactivation_context": update_text,  # Le nouveau commentaire
                    "new_requirements": update_text,  # ✅ NOUVEAU: Exigences spécifiques de réactivation
                    "task_context": task_context  # ✅ NOUVEAU: Contexte avec user_language et project_language
                }
                
                # ✅ LOG DEBUG: Afficher le dict complet avant envoi
                logger.info(f"📦 Task request dict envoyé à Celery:")
                logger.info(f"   • task_id: {task_request_dict.get('task_id')}")
                logger.info(f"   • task_db_id: {task_request_dict.get('task_db_id')}")
                logger.info(f"   • run_id: {task_request_dict.get('run_id')}")
                logger.info(f"   • is_reactivation: {task_request_dict.get('is_reactivation')}")
                logger.info(f"   • reactivation_count: {task_request_dict.get('reactivation_count')}")
                logger.info(f"   • source_branch: {task_request_dict.get('source_branch')}")
                logger.info(f"   • repository_url: {task_request_dict.get('repository_url')}")
                logger.info(f"   • title: {task_request_dict.get('title')}")
                
                celery_task = execute_workflow.delay(task_request_dict)
                
                logger.info(f"🎉 Workflow réactivé lancé avec Celery task: {celery_task.id}")
                logger.info("="*80)
                
                return JSONResponse(
                    content={
                        "success": True,
                        "message": "Workflow réactivé et lancé avec succès",
                        "task_id": task_id,
                        "run_id": run_id,
                        "celery_task_id": celery_task.id,
                        "is_reactivation": True,
                        "status": "reactivated",
                        "status_code": 200
                    },
                    status_code=200
                )
            else:
                logger.info("⚠️ Tâche déjà existante - pas de traitement Celery", 
                           task_id=persistence_result.get("task_id"),
                           pulse_id=webhook_payload.event.pulseId)
                return JSONResponse(
                    content={
                        "success": True,
                        "message": "Tâche déjà existante - mise à jour uniquement",
                        "task_id": persistence_result.get("task_id"),
                        "status": "updated",
                        "status_code": 200
                    },
                    status_code=200
                )
        
        # ✅ CORRECTION: Ne lancer le workflow Celery que pour les nouvelles tâches
        if not persistence_result.get("success") or not persistence_result.get("task_id"):
            logger.warning("❌ Erreur de persistence - pas de lancement Celery")
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Erreur lors de la création de la tâche",
                    "status_code": 400
                },
                status_code=400
            )
        
        # 🚀 Calculer la priorité AVANT de l'utiliser dans la queue
        priority_map = {
            "urgent": 9,
            "high": 7, 
            "medium": 5,
            "low": 3
        }
        task_priority = priority_map.get(task_info.get("priority", "medium").lower(), 5)
        
        # ✅ NOUVEAU: Ajouter à la queue de workflows pour éviter les conflits
        monday_item_id = webhook_payload.event.pulseId
        queue_id = await workflow_queue_manager.enqueue_workflow(
            monday_item_id=monday_item_id,
            payload=payload_raw,
            task_db_id=persistence_result.get("task_id"),
            priority=task_priority
        )
        
        persistence_result["queue_id"] = queue_id
        
        # ✅ NOUVEAU: Vérifier si on peut exécuter immédiatement ou attendre
        can_execute_now = await workflow_queue_manager.should_execute_now(monday_item_id, queue_id)
        
        if not can_execute_now:
            # Un workflow est déjà en cours ou en attente de validation
            queue_status = await workflow_queue_manager.get_queue_status(monday_item_id)
            
            logger.info(
                f"⏳ Workflow mis en queue pour item {monday_item_id}",
                queue_id=queue_id,
                queue_position=len(queue_status["pending_workflows"]) + (1 if queue_status["running_workflow"] else 0),
                running_workflow=queue_status["running_workflow"]
            )
            
            return JSONResponse(
                content={
                    "message": "Workflow mis en queue - un autre workflow est en cours",
                    "task_id": None,  # Pas encore de task Celery
                    "status": "queued",
                    "processing": "queued_for_sequential_processing",
                    "queue_info": {
                        "queue_id": queue_id,
                        "position": len(queue_status["pending_workflows"]) + (1 if queue_status["running_workflow"] else 0),
                        "running_workflow_id": queue_status["running_workflow"]["queue_id"] if queue_status["running_workflow"] else None,
                        "estimated_wait_time": "Dépend du workflow en cours"
                    },
                    "webhook_info": {
                        "pulse_id": webhook_payload.event.pulseId,
                        "task_title": task_info.get("title", ""),
                        "priority_level": task_priority
                    },
                    "persistence_info": {
                        "webhook_id": persistence_result.get("webhook_id"),
                        "db_task_id": persistence_result.get("task_id"),
                        "persistence_success": persistence_result.get("success", False)
                    }
                },
                status_code=202
            )
        
        # ✅ CORRECTION CRITIQUE: Transmettre le résultat avec is_reactivation à Celery
        celery_payload = {
            **payload_raw,  # Payload original
            "_persistence_result": persistence_result,  # ✅ CORRIGÉ: persistence_result au lieu de task_info !
            "_queue_id": queue_id  # ✅ NOUVEAU: Transmettre le queue_id pour traçabilité
        }
        
        # ✅ NOUVEAU: Le workflow peut être lancé immédiatement
        task = submit_task(
            "ai_agent_background.process_monday_webhook",
            celery_payload,  # ✅ Payload enrichi avec résultat de persistence
            signature,
            priority=task_priority
        )
        
        # ✅ NOUVEAU: Marquer le workflow comme en cours dans la queue
        await workflow_queue_manager.mark_as_running(monday_item_id, queue_id, task.id)
        
        logger.info("📨 Webhook envoyé à RabbitMQ", 
                   task_id=task.id,
                   webhook_type=webhook_payload.type,
                   queue="webhooks",
                   priority=task_priority,
                   routing_key="webhook.monday",
                   is_reactivation=persistence_result.get("is_reactivation", False),  # ✅ CORRIGÉ
                   task_db_id=persistence_result.get("task_id"))  # ✅ Ajouter le vrai task_id DB
        
        # Réponse enrichie avec informations extraites et persistence
        return JSONResponse(
            content={
                "message": "Webhook reçu, persiste et traite par RabbitMQ",
                "task_id": task.id,
                "status": "accepted",
                "processing": "rabbitmq_celery",
                "queue_info": {
                    "queue_id": queue_id,
                    "position": 1,  # En cours d'exécution
                    "status": "running"
                },
                "webhook_info": {
                    "pulse_id": webhook_payload.event.pulseId,
                    "task_title": task_info.get("title", ""),
                    "task_type": task_info.get("task_type", ""),
                    "priority": task_info.get("priority", ""),
                    "queue": "webhooks",
                    "priority_level": task_priority
                },
                "persistence_info": {
                    "webhook_id": persistence_result.get("webhook_id"),
                    "db_task_id": persistence_result.get("task_id"),
                    "persistence_success": persistence_result.get("success", False)
                },
                "estimated_processing_time": "2-10 minutes"
            },
            status_code=202
        )
        
    except HTTPException:
        # Re-lever les HTTPExceptions (erreurs de validation, etc.)
        raise
    except Exception as e:
        logger.error("❌ Erreur lors de la reception du webhook", 
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur interne lors du traitement du webhook: {str(e)}"
        )


@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """
    Endpoint pour suivre le statut d'une tâche Celery.
    
    Permet de vérifier l'avancement des workflows en temps réel.
    """
    try:
        # Récupérer le résultat de la tâche Celery
        task_result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": task_result.status,
            "ready": task_result.ready(),
            "successful": task_result.successful() if task_result.ready() else None,
            "failed": task_result.failed() if task_result.ready() else None,
        }
        
        # Ajouter le résultat si disponible
        if task_result.ready():
            if task_result.successful():
                response["result"] = task_result.result
            elif task_result.failed():
                response["error"] = str(task_result.info)
                response["traceback"] = task_result.traceback
        else:
            # Tâche en cours - essayer de récupérer des infos
            response["info"] = task_result.info
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur recuperation statut tache {task_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la recuperation du statut de la tache"
        )


# ================================================================
# ✅ NOUVEAUX ENDPOINTS: Webhooks Monday.com pour Notifications Slack
# ================================================================

@app.post("/webhook/monday/update-created")
async def monday_update_created_webhook(request: Request):
    """
    Webhook déclenché par Monday.com quand une update est créée.
    
    Utilisé pour envoyer des notifications Slack d'attente de validation.
    
    Configuration Monday.com:
    - Event: "create_update"
    - URL: https://votre-domaine.com/webhook/monday/update-created
    """
    try:
        from services.monday_slack_webhook_service import monday_slack_webhook_service
        
        payload = await request.json()
        
        logger.info("📥 Webhook Monday.com reçu: Update créée")
        logger.debug(f"Payload: {payload}")
        
        # Traiter le webhook
        result = await monday_slack_webhook_service.handle_update_created(payload)
        
        logger.info(f"✅ Webhook traité: {result.get('status')}")
        
        return JSONResponse(
            content={
                "success": True,
                "status": result.get("status"),
                "message": "Webhook traité avec succès"
            },
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"❌ Erreur traitement webhook update-created: {e}", exc_info=True)
        return JSONResponse(
            content={
                "success": False,
                "error": str(e)
            },
            status_code=500
        )


@app.post("/webhook/monday/status-changed")
async def monday_status_changed_webhook(request: Request):
    """
    Webhook déclenché par Monday.com quand un statut change.
    
    Utilisé pour envoyer des notifications Slack de succès de tâche.
    
    Configuration Monday.com:
    - Event: "change_column_value"
    - Column: Status column
    - URL: https://votre-domaine.com/webhook/monday/status-changed
    """
    try:
        from services.monday_slack_webhook_service import monday_slack_webhook_service
        
        payload = await request.json()
        
        logger.info("📥 Webhook Monday.com reçu: Statut changé")
        logger.debug(f"Payload: {payload}")
        
        # Traiter le webhook
        result = await monday_slack_webhook_service.handle_status_changed(payload)
        
        logger.info(f"✅ Webhook traité: {result.get('status')}")
        
        return JSONResponse(
            content={
                "success": True,
                "status": result.get("status"),
                "message": "Webhook traité avec succès"
            },
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"❌ Erreur traitement webhook status-changed: {e}", exc_info=True)
        return JSONResponse(
            content={
                "success": False,
                "error": str(e)
            },
            status_code=500
        )


@app.post("/workflows/execute")
async def execute_workflow_directly(task_request: TaskRequest):
    """
    Endpoint pour lancer un workflow directement (sans passer par Monday.com).
    
    Utile pour les tests et l'execution manuelle.
    """
    try:
        logger.info(f"🎯 Exécution workflow directe: {task_request.title}")
        
        # Soumettre à Celery
        task = submit_task(
            "ai_agent_background.execute_workflow",
            task_request.dict()
        )
        
        return {
            "message": "Workflow soumis à Celery",
            "task_id": task.id,
            "workflow_title": task_request.title,
            "status_url": f"/tasks/{task.id}/status"
        }
        
    except Exception as e:
        logger.error(f"Erreur execution workflow: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'exécution du workflow"
        )


@app.get("/costs/{period}")
async def get_costs_summary(period: str = "today"):
    """Recupere le resume des couts IA."""
    try:
        from services.monitoring_service import monitoring_dashboard
        
        valid_periods = ["today", "week", "month", "all"]
        if period not in valid_periods:
            raise HTTPException(
                status_code=400, 
                detail=f"Période invalide. Valides: {valid_periods}"
            )
        
        summary = await monitoring_dashboard.get_costs_summary(period)
        
        if "error" in summary:
            raise HTTPException(status_code=500, detail=summary["error"])
            
        return summary
        
    except Exception as e:
        logger.error(f"❌ Erreur recuperation couts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/celery/status")
async def get_celery_status():
    """
    Endpoint pour verifier le statut des workers Celery.
    """
    try:
        # Inspection des workers
        inspect = celery_app.control.inspect()
        
        # Workers actifs
        active_workers = inspect.ping() or {}
        
        # Tâches actives
        active_tasks = inspect.active() or {}
        
        # Tâches en attente
        reserved_tasks = inspect.reserved() or {}
        
        # Statistiques
        stats = inspect.stats() or {}
        
        total_active_tasks = sum(len(tasks) for tasks in active_tasks.values())
        total_reserved_tasks = sum(len(tasks) for tasks in reserved_tasks.values())
        
        return {
            "workers_count": len(active_workers),
            "workers": list(active_workers.keys()),
            "active_tasks": total_active_tasks,
            "reserved_tasks": total_reserved_tasks,
            "workers_stats": stats,
            "queues": ["webhooks", "workflows", "tests", "ai_generation"]
        }
        
    except Exception as e:
        logger.error(f"Erreur statut Celery: {e}")
        return {
            "error": str(e),
            "workers_count": 0,
            "status": "unavailable"
        }


# Endpoint pour déclencher des tâches de maintenance
@app.post("/admin/cleanup")
async def trigger_cleanup():
    """
    Endpoint admin pour declencher le nettoyage manuel.
    """
    try:
        task = submit_task("ai_agent_background.cleanup_old_tasks")
        
        return {
            "message": "Nettoyage déclenché",
            "task_id": task.id,
            "status_url": f"/tasks/{task.id}/status"
        }
        
    except Exception as e:
        logger.error(f"Erreur déclenchement nettoyage: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du déclenchement du nettoyage"
        )


# ============================================================================
# 📊 ÉVALUATION DE L'AGENT IA (GOLDEN DATASETS + LLM JUDGE)
# ============================================================================

# DEPRECATED: Cette route utilisait l'ancien système d'évaluation complexe
# Pour utiliser le nouveau système simplifié, exécutez:
#   python scripts/evaluation_semantique_golden_set.py
#
# @app.post("/evaluation/run")
# async def run_evaluation(
#     background_tasks: BackgroundTasks,
#     dataset_type: Optional[str] = None,
#     run_in_background: bool = True
# ):
#     """
#     Déclenche l'évaluation de l'agent sur un Golden Dataset.
#     
#     Args:
#         dataset_type: Type de dataset ("questions" ou "commands"). 
#                      Si None, évalue les deux.
#         run_in_background: Exécuter en arrière-plan (recommandé)
#         
#     Returns:
#         Status de l'évaluation
#         
#     Examples:
#         POST /evaluation/run?dataset_type=questions
#         POST /evaluation/run  (évalue tous les datasets)
#     """
#     logger.info("=" * 80)
#     logger.info("📊 DEMANDE D'ÉVALUATION DE L'AGENT")
#     logger.info("=" * 80)
#     
#     # Valider le dataset_type
#     valid_types = ["questions", "commands", None]
#     if dataset_type and dataset_type not in ["questions", "commands"]:
#         raise HTTPException(
#             status_code=400,
#             detail=f"dataset_type invalide. Attendu: questions, commands ou null"
#         )
#     
#     # Créer le service d'évaluation
#     config = AgentEvaluationConfig()
#     evaluation_service = AgentEvaluationService(config=config)
#     
#     async def run_evaluation_task():
#         """Tâche d'évaluation à exécuter."""
#         try:
#             if dataset_type:
#                 # Évaluer un seul dataset
#                 dataset_enum = DatasetType(dataset_type)
#                 report = await evaluation_service.evaluate_dataset(
#                     dataset_type=dataset_enum,
#                     save_report=True
#                 )
#                 
#                 logger.info(
#                     f"✅ Évaluation {dataset_type} terminée: "
#                     f"{report.reliability_score}/100 ({report.reliability_status})"
#                 )
#             else:
#                 # Évaluer les deux datasets
#                 reports = []
#                 
#                 for dt in DatasetType:
#                     try:
#                         report = await evaluation_service.evaluate_dataset(
#                             dataset_type=dt,
#                             save_report=True
#                         )
#                         reports.append(report)
#                         logger.info(
#                             f"✅ Dataset {dt.value}: {report.reliability_score}/100"
#                         )
#                     except FileNotFoundError:
#                         logger.warning(f"⚠️ Dataset {dt.value} non trouvé, ignoré")
#                 
#                 logger.info(f"✅ Évaluation complète terminée: {len(reports)} datasets")
#         
#         except Exception as e:
#             logger.error(f"❌ Erreur durant l'évaluation: {e}", exc_info=True)
#     
#     if run_in_background:
#         # Exécuter en arrière-plan
#         background_tasks.add_task(run_evaluation_task)
#         
#         return {
#             "status": "started",
#             "message": "Évaluation lancée en arrière-plan",
#             "dataset_type": dataset_type or "all",
#             "note": "Consultez les logs pour suivre la progression"
#         }
#     else:
#         # Exécuter immédiatement (bloquant)
#         await run_evaluation_task()
#         
#         return {
#             "status": "completed",
#             "message": "Évaluation terminée",
#             "dataset_type": dataset_type or "all"
#         }


@app.get("/evaluation/reports")
async def list_evaluation_reports():
    """
    Liste tous les rapports d'évaluation disponibles.
    
    Returns:
        Liste des rapports avec métadonnées (score, status, date, etc.)
        
    Example:
        GET /evaluation/reports
    """
    try:
        import json
        from pathlib import Path
        
        reports_dir = Path(__file__).parent / "data" / "evaluation_reports"
        
        if not reports_dir.exists():
            return {"reports": [], "total": 0}
        
        reports_list = []
        
        for report_file in sorted(reports_dir.glob("evaluation_*.json"), reverse=True):
            try:
                with open(report_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                reports_list.append({
                    "filename": report_file.name,
                    "report_id": data.get("report_id"),
                    "dataset_name": data.get("dataset_name"),
                    "dataset_type": data.get("dataset_type"),
                    "reliability_score": data.get("reliability_score"),
                    "reliability_status": data.get("reliability_status"),
                    "total_tests": data.get("total_tests"),
                    "tests_passed": data.get("tests_passed"),
                    "tests_failed": data.get("tests_failed"),
                    "average_score": data.get("average_score"),
                    "evaluated_at": data.get("evaluation_started_at"),
                    "duration_seconds": data.get("total_duration_seconds")
                })
            
            except Exception as e:
                logger.warning(f"⚠️ Erreur lecture rapport {report_file.name}: {e}")
        
        return {
            "reports": reports_list,
            "total": len(reports_list)
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur listing rapports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/evaluation/reports/{report_id}")
async def get_evaluation_report(report_id: str):
    """
    Récupère un rapport d'évaluation spécifique.
    
    Args:
        report_id: ID du rapport (UUID)
        
    Returns:
        Rapport d'évaluation complet avec tous les détails
        
    Example:
        GET /evaluation/reports/123e4567-e89b-12d3-a456-426614174000
    """
    try:
        import json
        from pathlib import Path
        
        reports_dir = Path(__file__).parent / "data" / "evaluation_reports"
        
        # Chercher le fichier correspondant
        for report_file in reports_dir.glob("evaluation_*.json"):
            with open(report_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if data.get("report_id") == report_id:
                return data
        
        raise HTTPException(status_code=404, detail=f"Rapport {report_id} non trouvé")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur récupération rapport: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.debug else False,
        log_level=settings.log_level.lower()
    )