"""Service de réception et traitement des webhooks Monday.com."""

import hashlib
import hmac
import json
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import time

from models.schemas import TaskRequest, WebhookPayload
from tools.monday_tool import MondayTool
from utils.logger import get_logger
from config.settings import get_settings
from admin.backend.database import get_db_connection
from utils.github_parser import enrich_task_with_description_info

logger = get_logger(__name__)

class WebhookService:
    """Service de gestion des webhooks Monday.com."""

    def __init__(self):
        self.settings = get_settings()
        self.monday_tool = MondayTool()

        self._webhook_cache = {}
        self._cache_expiry = 300  
        self._processing_locks = {}  

    async def process_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        """
        Traite un webhook Monday.com avec déduplication renforcée.
        """
        try:
            webhook_signature = self._create_webhook_signature(payload)

            current_time = time.time()

            self._cleanup_webhook_cache(current_time)

            if webhook_signature in self._webhook_cache:
                cached_data = self._webhook_cache[webhook_signature]
                logger.warning(f"🚫 Webhook déjà traité il y a {current_time - cached_data['timestamp']:.1f}s")
                logger.warning(f"   Signature: {webhook_signature}")
                logger.warning(f"   Task ID: {cached_data.get('task_id', 'unknown')}")
                return {
                    "success": True,
                    "task_id": cached_data.get('task_id'),
                    "task_exists": True,
                    "message": "Webhook déjà traité (déduplication)",
                    "deduplicated": True
                }

            # ✅ NOUVEAU: Acquérir un verrou pour ce webhook
            if webhook_signature in self._processing_locks:
                logger.warning("🔒 Webhook en cours de traitement - attente...")
                # Attendre maximum 30 secondes
                for _ in range(30):
                    await asyncio.sleep(1)
                    if webhook_signature not in self._processing_locks:
                        break
                else:
                    logger.error("❌ Timeout - webhook toujours en cours de traitement")
                    return {
                        "success": False,
                        "error": "Webhook timeout - traitement parallèle détecté"
                    }

            # Marquer comme en cours de traitement
            self._processing_locks[webhook_signature] = current_time

            try:
                # Marquer dans le cache immédiatement
                self._webhook_cache[webhook_signature] = {
                    "timestamp": current_time,
                    "status": "processing"
                }

                logger.info("📨 Réception d'un webhook Monday.com")

                # 1. Sauvegarder le webhook en base
                webhook_id = await self._save_webhook_event(payload, signature)

                # 2. Valider la signature si fournie
                if signature and not self._validate_signature(payload, signature):
                    logger.warning("❌ Signature webhook invalide")
                    await self._update_webhook_status(webhook_id, 'failed', 'Signature invalide')
                    return {
                        "success": False,
                        "error": "Signature webhook invalide",
                        "status_code": 401
                    }

                # 3. Parser le payload
                webhook_data = WebhookPayload(**payload)

                # 4. Vérifier si c'est un challenge de validation
                if webhook_data.challenge:
                    logger.info("✅ Challenge webhook reçu")
                    await self._update_webhook_status(webhook_id, 'processed')
                    return {
                        "success": True,
                        "challenge": webhook_data.challenge,
                        "status_code": 200
                    }

                # 5. Traiter l'événement
                if not webhook_data.event:
                    logger.warning("⚠️ Webhook sans événement")
                    await self._update_webhook_status(webhook_id, 'ignored', 'Aucun événement')
                    return {
                        "success": False,
                        "error": "Aucun événement dans le webhook",
                        "status_code": 400
                    }

                # 6. Vérifier les webhooks en doublon (protection contre les multiples envois Monday.com)
                duplicate_check = await self._check_duplicate_webhook(payload)
                if duplicate_check:
                    logger.warning("⚠️ Webhook en doublon détecté:")
                    logger.warning(f"   Webhook similaire traité: {duplicate_check['webhook_events_id']} à {duplicate_check['processed_at']}")
                    logger.warning("   🛑 Webhook ignoré pour éviter la duplication")
                    await self._update_webhook_status(webhook_id, 'processed', 'Doublon ignoré')
                    return {
                        "success": True,
                        "message": "Webhook doublon ignoré",
                        "status_code": 200
                    }

                # 7. Extraire les informations de la tâche
                task_info = self.monday_tool.parse_monday_webhook(payload)

                if not task_info:
                    logger.info("ℹ️ Webhook ignoré - pas pertinent pour notre workflow")
                    await self._update_webhook_status(webhook_id, 'ignored', 'Pas pertinent')
                    return {
                        "success": True,
                        "message": "Webhook ignoré",
                        "status_code": 200
                    }

                # 7. Créer une requête de tâche
                task_request = await self._create_task_request(task_info)

                if not task_request:
                    logger.warning("❌ Impossible de créer la requête de tâche")
                    await self._update_webhook_status(webhook_id, 'failed', 'Impossible de créer la requête')
                    return {
                        "success": False,
                        "error": "Impossible de créer la requête de tâche",
                        "status_code": 400
                    }

                # 8. Sauvegarder la tâche en base (seulement si elle n'existe pas)
                task_id = await self._save_task(task_request)

                # ✅ CORRECTION: Ne plus créer le run ici - il sera créé par le workflow lui-même
                # Évite la duplication et les conflits de statut
                # run_id = await self._save_task_run(task_id, task_request)

                # Note : Le statut de la tâche sera mis à jour par le workflow via les triggers

                # 10. Mettre à jour le webhook avec la tâche liée
                await self._update_webhook_status(webhook_id, 'processed', related_task_id=task_id)

                # 11. ✅ Tâche créée et prête - le workflow sera lancé par celery_app
                logger.info(f"📋 Tâche créée et prête pour workflow: {task_request.title} (ID: {task_id})")

                # Retourner le succès - le workflow sera géré par celery_app.process_monday_webhook
                return {
                    "success": True,
                    "message": "Tâche créée avec succès - workflow géré par Celery",
                    "task_id": task_id,  # ✅ Retourner le tasks_id de la BD
                    "status": "created",
                    "status_code": 201  # Created
                }

                # ANCIEN CODE SUPPRIMÉ pour éviter le double lancement :
                # - celery_app.send_task("ai_agent_background.execute_workflow")
                # Ce workflow est maintenant géré directement par main.py

            except Exception as wf_err:
                err_msg = str(wf_err)
                logger.error(f"❌ Erreur lors de la création de la tâche: {err_msg}")

                # ✅ CORRECTION: Ne pas modifier le statut ici - laisser le workflow gérer
                # Le workflow mettra à jour le statut correctement selon son exécution
                
                # Gestion spéciale pour les transitions de statut (ne devrait plus arriver)
                if "Invalid status transition" in err_msg:
                    logger.warning(f"⚠️ Transition de statut détectée (ignorée): {err_msg}")
                    return {
                        "success": True,
                        "message": "Tâche créée avec avertissement (transition ignorée)",
                        "task_id": getattr(task_request, 'task_id', 'unknown'),
                        "warning": err_msg,
                        "status_code": 200
                    }

                # Relancer l'exception pour le gestionnaire global
                raise

            except Exception as e:
                error_msg = f"Erreur lors du traitement du webhook: {str(e)}"
                logger.error(error_msg, exc_info=True)

                # Gestion spéciale pour les transitions de statut identiques
                if "Invalid status transition" in str(e):
                    logger.warning(f"⚠️ Transition de statut identique détectée (webhook traité quand même): {str(e)}")
                    await self._update_webhook_status(webhook_id, 'processed')
                    return {
                        "success": True,
                        "message": "Webhook traité (transition de statut identique ignorée)",
                        "warning": str(e),
                        "status_code": 200
                    }

                await self._update_webhook_status(webhook_id, 'failed', error_msg)

                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": 500
                }
            finally:
                # ✅ NOUVEAU: Libérer le verrou après le traitement
                if webhook_signature in self._processing_locks:
                    del self._processing_locks[webhook_signature]
                    logger.debug(f"🔓 Libération du verrou pour signature: {webhook_signature}")
        except Exception as e:
            logger.error(f"Erreur générale lors du traitement du webhook: {e}", exc_info=True)
            return {"success": False, "error": str(e), "status_code": 500}

    def _create_webhook_signature(self, payload: Dict[str, Any]) -> str:
        """Crée une signature unique pour un webhook."""
        payload_str = json.dumps(payload, sort_keys=True).encode('utf-8')
        return hashlib.sha256(payload_str).hexdigest()

    def _cleanup_webhook_cache(self, current_time: float):
        """Nettoie le cache des webhooks qui ont expiré."""
        expired_keys = [
            k for k, v in self._webhook_cache.items()
            if current_time - v['timestamp'] > self._cache_expiry
        ]
        for key in expired_keys:
            logger.debug(f"🧹 Nettoyage du cache webhook: {key}")
            del self._webhook_cache[key]

    def _validate_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """Valide la signature du webhook Monday.com."""

        try:
            # Monday.com utilise HMAC-SHA256
            payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')

            expected_signature = hmac.new(
                self.settings.webhook_secret.encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()

            # Comparer en toute sécurité
            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Erreur lors de la validation de signature: {e}")
            return False

    async def _save_webhook_event(self, payload: Dict[str, Any], signature: Optional[str] = None) -> int:
        """Sauvegarde le webhook en base de données."""
        try:
            conn = await get_db_connection()
            logger.debug("Connexion DB établie pour sauvegarde webhook")

            result = await conn.fetchrow("""
                INSERT INTO webhook_events (source, event_type, payload, signature, processed, processing_status)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING webhook_events_id
            """,
                'monday',
                payload.get('event', {}).get('type'),
                json.dumps(payload),
                signature,
                False,
                'pending'
            )
            return result['webhook_events_id']
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde webhook en base: {e}")
            # Retourner un ID temporaire pour continuer le traitement
            return -1
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _save_task(self, task_request: TaskRequest) -> int:
        """Sauvegarde la tâche en base de données avec gestion des doublons améliorée."""
        try:
            conn = await get_db_connection()
            logger.debug("Connexion DB établie pour sauvegarde tâche")

            # 1. Vérifier si la tâche existe déjà par monday_item_id
            existing_task = await conn.fetchrow("""
                SELECT tasks_id, internal_status, description, repository_url FROM tasks
                WHERE monday_item_id = $1
            """, int(task_request.task_id))

            if existing_task:
                logger.info(f"📋 Tâche existante trouvée par ID: {existing_task['tasks_id']}, statut: {existing_task['internal_status']}")
                
                # ✅ CORRECTION CRITIQUE: TOUJOURS mettre à jour la description si elle a changé
                # (pour capturer les updates/commentaires Monday.com enrichis)
                needs_update = False
                updates = []
                params = []
                param_idx = 1
                
                # Mettre à jour la description si:
                # 1. Elle est vide dans la DB ET on en a une nouvelle
                # 2. La nouvelle est PLUS LONGUE (enrichie avec updates)
                # ⚠️ PROTECTION: Ne JAMAIS écraser une longue description par une plus courte
                if task_request.description and (
                    not existing_task['description'] or  # Cas 1: vide en DB
                    len(task_request.description) > len(existing_task['description'] or '')  # Cas 2: enrichie (plus longue)
                ):
                    updates.append(f"description = ${param_idx}")
                    params.append(task_request.description)
                    param_idx += 1
                    needs_update = True
                    logger.info(f"✅ Mise à jour de la description (ancienne: {len(existing_task['description'] or '')} chars → nouvelle: {len(task_request.description)} chars)")
                    if "--- Commentaires et précisions additionnelles ---" in task_request.description:
                        logger.info("📝 Description enrichie avec des updates Monday.com détectée")
                
                if not existing_task['repository_url'] and task_request.repository_url:
                    updates.append(f"repository_url = ${param_idx}")
                    params.append(task_request.repository_url)
                    param_idx += 1
                    needs_update = True
                    logger.info(f"✅ Mise à jour de l'URL du repository: {task_request.repository_url}")
                
                if needs_update:
                    params.append(existing_task['tasks_id'])
                    update_query = f"""
                        UPDATE tasks 
                        SET {', '.join(updates)}, updated_at = NOW()
                        WHERE tasks_id = ${param_idx}
                    """
                    await conn.execute(update_query, *params)
                    logger.info(f"📝 Tâche {existing_task['tasks_id']} mise à jour avec les nouvelles données")
                
                return existing_task['tasks_id']

            # 2. Vérifier les doublons par titre + créé dans les 5 dernières minutes
            # (protection contre les webhooks multiples de Monday.com)
            similar_task = await conn.fetchrow("""
                SELECT tasks_id, monday_item_id, internal_status
                FROM tasks
                WHERE title = $1
                AND created_at >= NOW() - INTERVAL '5 minutes'
                AND internal_status IN ('pending', 'processing')
                ORDER BY created_at DESC
                LIMIT 1
            """, task_request.title)

            if similar_task:
                logger.warning("⚠️ Tâche similaire détectée dans les 5 dernières minutes:")
                logger.warning(f"   Existante: ID {similar_task['tasks_id']}, Monday ID {similar_task['monday_item_id']}")
                logger.warning(f"   Nouvelle: Monday ID {task_request.task_id}")
                logger.warning(f"   Titre: {task_request.title}")
                logger.warning("   🛑 Duplication probable détectée - utilisation de la tâche existante")
                return similar_task['tasks_id']

            # Créer une nouvelle tâche
            result = await conn.fetchrow("""
                INSERT INTO tasks (
                    monday_item_id, monday_board_id, title, description, priority,
                    repository_url, repository_name, default_branch, internal_status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING tasks_id
            """,
                int(task_request.task_id),
                None,
                task_request.title,
                task_request.description,
                task_request.priority.value,
                task_request.repository_url or '',
                None,
                task_request.base_branch,
                'pending'  # Statut initial
            )
            logger.info(f"📋 Nouvelle tâche créée: ID {result['tasks_id']}")
            return result['tasks_id']
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde tâche en base: {e}")
            raise
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _save_task_run(self, task_id: int, task_request: TaskRequest) -> int:
        """Sauvegarde le run en base de données avec gestion des doublons."""
        try:
            conn = await get_db_connection()

            # Vérifier s'il y a déjà un run actif pour cette tâche
            existing_run = await conn.fetchrow("""
                SELECT tasks_runs_id, status FROM task_runs
                WHERE task_id = $1 AND status IN ('started', 'running', 'pending')
                ORDER BY started_at DESC
                LIMIT 1
            """, task_id)

            if existing_run:
                logger.info(f"📊 Run existant trouvé: ID {existing_run['tasks_runs_id']}, statut: {existing_run['status']}")
                return existing_run['tasks_runs_id']

            # Créer un nouveau run
            # ✅ CORRECTION CRITIQUE: Ajouter run_number, is_reactivation et reactivation_count
            # Obtenir le prochain run_number
            run_number = await conn.fetchval("""
                SELECT COALESCE(MAX(run_number), 0) + 1
                FROM task_runs
                WHERE task_id = $1
            """, task_id)
            
            # Déterminer si c'est une réactivation depuis task_request
            is_reactivation = getattr(task_request, 'is_reactivation', False)
            reactivation_count = getattr(task_request, 'reactivation_count', 0)
            
            result = await conn.fetchrow("""
                INSERT INTO task_runs (
                    task_id, 
                    run_number,
                    status, 
                    git_branch_name, 
                    ai_provider,
                    is_reactivation,
                    reactivation_count
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING tasks_runs_id
            """,
                task_id,
                run_number,
                'started',  # Statut 'started' au lieu de 'pending'
                task_request.branch_name,
                'claude',
                is_reactivation,
                reactivation_count
            )
            logger.info(f"📊 Nouveau run créé: ID {result['tasks_runs_id']}, run_number={run_number}, is_reactivation={is_reactivation}")
            return result['tasks_runs_id']
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde run en base: {e}")
            raise
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _update_task_status(self, task_db_id: int, new_status: str):
        """Met à jour le statut d'une tâche de manière idempotente."""
        try:
            conn = await get_db_connection()

            # Vérifier le statut actuel
            row = await conn.fetchrow("SELECT internal_status FROM tasks WHERE tasks_id=$1", task_db_id)

            if row and row["internal_status"] != new_status:
                await conn.execute(
                    "UPDATE tasks SET internal_status=$1, updated_at=NOW() WHERE tasks_id=$2",
                    new_status, task_db_id
                )
                logger.info(f"📊 Statut tâche {task_db_id} mis à jour: {row['internal_status']} → {new_status}")
            else:
                logger.debug(f"📊 Statut identique pour tâche {task_db_id}: {new_status}")
                # C'est normal - ne pas lever d'exception

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour statut tâche {task_db_id}: {e}")
            # Ne pas relancer l'exception pour éviter de faire échouer le traitement
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _update_webhook_status(self, webhook_id: int, status: str, error_message: Optional[str] = None, related_task_id: Optional[int] = None):
        """Met à jour le statut du webhook."""
        try:
            conn = await get_db_connection()

            await conn.execute("""
                UPDATE webhook_events
                SET processing_status = $1,
                    error_message = $2,
                    related_task_id = $3,
                    processed = $4,
                    processed_at = CASE WHEN $4 THEN NOW() ELSE processed_at END
                WHERE webhook_events_id = $5
            """, status, error_message, related_task_id, status == 'processed', webhook_id)

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour webhook {webhook_id}: {e}")
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _create_task_request(self, task_info: Dict[str, Any]) -> Optional[TaskRequest]:
        """Crée une TaskRequest à partir des informations d'une tâche Monday.com."""

        try:
            item_id = task_info.get("task_id", "")

            # ✅ AMÉLIORATION: Vérification précoce des items de test
            if self._is_test_item(item_id):
                logger.info(f"⚠️ Item de test détecté ({item_id}) - Traitement simplifié")
                return self._create_test_task_request(task_info)

            # Récupérer les informations détaillées de l'item depuis Monday.com
            logger.info(f"📥 Récupération des détails pour l'item Monday.com: {item_id}")

            # ✅ CORRECTION: Utiliser _arun au lieu d'appeler directement _get_item_info
            item_data = await self.monday_tool._arun(action="get_item_info", item_id=item_id)

            if not item_data.get("success"):
                error_msg = item_data.get("error", "Erreur inconnue")
                logger.error(f"❌ Impossible de récupérer les détails de l'item {item_id}: {error_msg}")

                # ✅ AMÉLIORATION: Gestion différentielle selon le type d'erreur
                if "non trouvé" in error_msg or "supprimé" in error_msg:
                    # L'item a probablement été supprimé entre l'envoi du webhook et le traitement
                    logger.warning(f"⚠️ Item {item_id} supprimé après envoi du webhook - Ceci peut arriver lors de suppressions rapides")
                    # Créer une tâche minimale pour éviter l'arrêt complet du workflow
                    return self._create_fallback_task_request(task_info, f"Item supprimé: {error_msg}")
                else:
                    # Autres erreurs (permissions, API down, etc.)
                    raise ValueError(f"Item Monday.com {item_id} inaccessible: {error_msg}")

            # Extraire les informations nécessaires
            title = item_data.get("name", task_info.get("title", "Tâche sans titre"))

            # ✅ AMÉLIORATION: Extraction de description plus robuste
            description = None

            # Fonction helper pour extraire texte sécurisé
            def safe_extract_column_text(column: Dict[str, Any]) -> str:
                """Extrait le texte d'une colonne Monday.com de manière sécurisée."""
                if not isinstance(column, dict):
                    return ""

                # Essayer plusieurs propriétés possibles dans l'ordre de priorité
                text_value = (
                    column.get("text") or
                    column.get("value") or
                    (column.get("display_value") if column.get("display_value") else "") or
                    ""
                ).strip()

                # Si c'est un dict dans value, essayer d'extraire le texte
                if not text_value and isinstance(column.get("value"), dict):
                    value_dict = column.get("value", {})
                    text_value = (
                        value_dict.get("text") or
                        value_dict.get("value") or
                        str(value_dict.get("display_value", ""))
                    ).strip()

                return text_value

            # DEBUG: Afficher toutes les colonnes disponibles
            if "column_values" in item_data:
                # ✅ PROTECTION: Normaliser column_values en liste pour le traitement
                column_values_raw = item_data["column_values"]
                column_values = []
                
                if isinstance(column_values_raw, dict):
                    # Cas dict: transformer en liste en préservant les IDs des colonnes
                    logger.debug(f"🔧 column_values reçu comme dict, conversion en liste ({len(column_values_raw)} colonnes)")
                    for col_id, col_data in column_values_raw.items():
                        if isinstance(col_data, dict):
                            # Ajouter l'ID à l'objet colonne s'il n'existe pas déjà
                            if "id" not in col_data:
                                col_data["id"] = col_id
                            column_values.append(col_data)
                        else:
                            # Format inattendu: créer un objet colonne basique
                            column_values.append({"id": col_id, "text": str(col_data), "value": col_data})
                elif isinstance(column_values_raw, list):
                    # Cas liste: utiliser directement
                    column_values = column_values_raw
                else:
                    # Cas anormal : type inattendu
                    logger.warning(f"⚠️ column_values type inattendu: {type(column_values_raw)}, fallback vers liste vide")
                    column_values = []

                # Afficher les colonnes pour debug
                column_names = [col.get("id", "no_id") for col in column_values if isinstance(col, dict)]
                logger.info(f"🔍 DEBUG - Colonnes disponibles dans Monday.com: {column_names}")
                
                # Log détaillé des colonnes pour debugging
                if column_names:
                    logger.info(f"📋 {len(column_names)} colonnes trouvées: {', '.join(column_names[:10])}{'...' if len(column_names) > 10 else ''}")
                
                # ✅ VALIDATION: Vérifier les colonnes importantes (pas bloquant)
                # On cherche des colonnes utiles mais ce n'est pas obligatoire car on peut
                # récupérer les infos depuis les updates Monday.com
                important_columns = {
                    "link": "Repository URL (configuré)",
                    "monday_doc_v2": "Documentation",
                    "task_owner": "Propriétaire",
                    "task_status": "Statut"
                }
                
                found_important = []
                for col_id, description in important_columns.items():
                    if col_id in column_names:
                        found_important.append(f"{description} ({col_id})")
                
                if found_important:
                    logger.info(f"✅ Colonnes utiles disponibles: {', '.join(found_important[:3])}")
                
                # Note: Les descriptions viennent des updates Monday.com, pas des colonnes

                # ✅ AMÉLIORATION: Chercher la description avec plus de flexibilité
                description_candidates = []

                for col in column_values:
                    col_id = col.get("id", "").lower()
                    col_title = col.get("title", "").lower()
                    col_text = safe_extract_column_text(col)

                    # Logger les colonnes potentielles pour debug
                    if any(keyword in col_id for keyword in ["desc", "detail", "note", "comment", "text", "sujet"]) or \
                       any(keyword in col_title for keyword in ["desc", "detail", "note", "comment", "text", "sujet"]):
                        logger.info(f"🔍 DEBUG - Colonne potentielle: id='{col.get('id')}', title='{col.get('title')}', text='{col_text[:50]}...'")

                        if col_text and len(col_text) > 10:  # Priorité aux descriptions substantielles
                            description_candidates.append((col_text, len(col_text), col.get("id")))

                # Choisir la meilleure description (la plus longue)
                if description_candidates:
                    description_candidates.sort(key=lambda x: x[1], reverse=True)  # Trier par longueur
                    description = description_candidates[0][0]
                    source_column = description_candidates[0][2]
                    logger.info(f"📝 Description sélectionnée depuis colonne '{source_column}': {description[:100]}...")

            # ✅ AMÉLIORATION CRITIQUE: TOUJOURS récupérer les updates/commentaires Monday.com
            # pour enrichir la description avec les précisions de l'utilisateur
            additional_context = []
            vydata_update_creator_name = None  # ✅ NOUVEAU: Capturer le vrai créateur de l'update @vydata
            vydata_update_creator_id = None
            logger.info("🔍 Récupération des updates Monday.com pour enrichir le contexte...")
            try:
                # ✅ CORRECTION: Vérifier la configuration Monday.com avant l'appel
                if not hasattr(self.monday_tool, 'api_token') or not self.monday_tool.api_token:
                    logger.info("💡 Monday.com non configuré - skip des updates")
                else:
                    updates_result = await self.monday_tool._arun(
                        action="get_item_updates",
                        item_id=task_info["task_id"]
                    )

                    if updates_result.get("success") and updates_result.get("updates"):
                        import re
                        # Récupérer TOUTES les updates pertinentes (pas seulement la première)
                        for update in updates_result["updates"][:10]:  # Maximum 10 updates récentes
                            update_body = update.get("body", "").strip()
                            if update_body and len(update_body) > 15:  # Filtrer les updates trop courtes
                                # Nettoyer le HTML si présent
                                clean_body = re.sub(r'<[^>]+>', '', update_body).strip()
                                if clean_body and len(clean_body) > 15:
                                    # Ajouter le créateur si disponible
                                    update_creator = update.get("creator", {})
                                    creator_name = update_creator.get("name", "Utilisateur")
                                    
                                    # ✅ NOUVEAU: Capturer le créateur de l'update @vydata
                                    if "@vydata" in clean_body.lower() and vydata_update_creator_name is None:
                                        vydata_update_creator_name = creator_name
                                        vydata_update_creator_id = update_creator.get("id")
                                        logger.info(f"👤 ✅ CRÉATEUR UPDATE @VYDATA IDENTIFIÉ: {creator_name} (ID: {vydata_update_creator_id})")
                                    
                                    additional_context.append(f"[{creator_name}]: {clean_body}")
                                    logger.info(f"📝 Update récupérée de {creator_name}: {clean_body[:80]}...")
                        
                        if additional_context:
                            logger.info(f"✅ {len(additional_context)} update(s) récupérée(s) depuis Monday.com")
                    else:
                        logger.info("ℹ️ Aucune update trouvée dans Monday.com")
            except Exception as e:
                logger.warning(f"⚠️ Erreur récupération updates: {e}")

            # ✅ FALLBACK 1: Si pas de description de base, utiliser la première update
            if not description and additional_context:
                description = additional_context[0]
                additional_context = additional_context[1:]  # Retirer la première qu'on a utilisée
                logger.info(f"📝 Description générée depuis première update: {description[:100]}...")

            # ✅ FALLBACK 2: Utiliser le titre de la tâche comme description minimale
            if not description and title:
                description = f"Tâche: {title}"
                logger.info(f"📝 Description générée depuis le titre: {description}")

            # ✅ VALIDATION: S'assurer qu'on a au moins quelque chose
            if not description:
                description = "Description non disponible - Veuillez ajouter plus de détails dans Monday.com"
                logger.warning("⚠️ Aucune description trouvée dans Monday.com après toutes les tentatives")

            # ✅ ENRICHISSEMENT FINAL: Ajouter les commentaires/updates à la description
            if additional_context:
                # Ajouter une section séparée pour les commentaires
                description += "\n\n--- Commentaires et précisions additionnelles ---\n"
                description += "\n".join(additional_context)
                logger.info(f"✅ Description enrichie avec {len(additional_context)} commentaire(s) Monday.com")

            logger.info(f"📄 Description finale: {description[:100]}{'...' if len(description) > 100 else ''}")

            # Rechercher la branche Git
            git_branch = self._extract_column_value(item_data, "branche_git", "text")
            if not git_branch:
                git_branch = self._generate_branch_name(title)

            # Autres informations
            assignee = self._extract_column_value(item_data, "personne", "name")
            priority = self._extract_column_value(item_data, "priorite", "text", "medium")
            
            # ✅ CORRECTION MAJEURE: Utiliser le créateur de l'update @vydata, PAS le créateur de l'item
            creator_name = None
            creator_id = None
            
            if vydata_update_creator_name:
                # ✅ PRIORITÉ 1: Créateur de l'update @vydata (le vrai utilisateur qui demande la tâche)
                creator_name = vydata_update_creator_name
                creator_id = vydata_update_creator_id
                logger.info(f"👤 ✅ Créateur identifié (update @vydata): {creator_name} (ID: {creator_id})")
            else:
                # ❌ FALLBACK: Créateur de l'item (owner du board, moins précis)
                creator_name = item_data.get("creator_name")
                creator_id = item_data.get("creator_id")
                if creator_name:
                    logger.warning(f"⚠️ Fallback - Créateur depuis item (owner): {creator_name} (ID: {creator_id})")
                else:
                    logger.debug("ℹ️  Créateur non disponible")
            
            # ✅ NOUVEAU: Récupérer base_branch depuis Monday.com (si spécifiée)
            monday_base_branch = item_data.get("base_branch")
            if monday_base_branch:
                logger.info(f"🌿 Branche de base depuis Monday.com: {monday_base_branch}")
            else:
                logger.debug("ℹ️  Branche de base non spécifiée dans Monday.com - sera résolue intelligemment")
            
            # ✅ CORRECTION: Lire la colonne Repository URL configurée
            from config.settings import get_settings
            settings = get_settings()
            repository_url = ""
            
            # Essayer d'abord avec l'ID de colonne configuré
            if settings.monday_repository_url_column_id:
                # Pour une colonne de type "link", essayer "url" et "text"
                repository_url = (
                    self._extract_column_value(item_data, settings.monday_repository_url_column_id, "url") or
                    self._extract_column_value(item_data, settings.monday_repository_url_column_id, "text") or
                    ""
                )
                if repository_url:
                    logger.info(f"🔗 URL repository trouvée dans colonne configurée ({settings.monday_repository_url_column_id}): {repository_url}")
            
            # Fallback: essayer avec le nom générique
            if not repository_url:
                repository_url = self._extract_column_value(item_data, "repo_url", "text") or ""
                if repository_url:
                    logger.info(f"🔗 URL repository trouvée dans colonne 'repo_url': {repository_url}")

            # Préparer les données de base de la tâche
            base_task_data = {
                "task_id": task_info["task_id"],
                "title": title,
                "description": description,
                "branch_name": git_branch,
                "repository_url": repository_url,
                "priority": priority,
                "assignee": assignee
            }

            # Enrichir avec les informations extraites de la description
            logger.info(f"📝 Analyse de la description pour enrichissement: {description[:100]}...")
            logger.info(f"🔗 URL de base (avant enrichissement): {repository_url}")

            enriched_data = enrich_task_with_description_info(base_task_data, description)

            final_url = enriched_data.get("repository_url", "")
            if final_url != repository_url:
                logger.info(f"🎯 URL GitHub finale (après enrichissement): {final_url}")
            else:
                logger.info(f"📝 URL GitHub finale (inchangée): {final_url}")

            # Validation critique: URL GitHub obligatoire
            if not final_url or not final_url.strip():
                error_msg = "❌ ERREUR CRITIQUE: Aucune URL GitHub trouvée dans la description ni dans les colonnes Monday.com"
                logger.error(error_msg)
                logger.error("💡 SOLUTION: Ajoutez l'URL GitHub dans la description de la tâche Monday.com")
                logger.error("📝 EXEMPLE: 'Implémente login JWT pour: https://github.com/user/repo'")

                raise ValueError(
                    "URL GitHub manquante. "
                    "Veuillez spécifier l'URL GitHub dans la description de la tâche Monday.com. "
                    "Exemple: 'Implémente login pour: https://github.com/user/repo'"
                )

            # ✅ CORRECTION CRITIQUE: Ne PAS bloquer les réactivations
            # La déduplication doit se faire au niveau de la BDD, pas ici
            # Car une tâche terminée peut être réactivée légitimement
            task_id = enriched_data["task_id"]
            
            # Note: La déduplication est désormais gérée par:
            # 1. Le système de détection de doublons dans webhook_persistence_service
            # 2. La vérification du statut de la tâche en BDD
            # On ne bloque PLUS les tâches ici pour permettre les réactivations

            # Créer la requête de tâche avec les données enrichies
            task_request = TaskRequest(
                task_id=enriched_data["task_id"],
                title=enriched_data["title"],
                description=enriched_data["description"],
                branch_name=enriched_data["branch_name"],
                repository_url=enriched_data["repository_url"],
                priority=enriched_data["priority"],
                files_to_modify=enriched_data.get("files_to_modify"),
                creator_name=creator_name,
                creator_id=int(creator_id) if creator_id else None,
                base_branch=monday_base_branch  # ✅ NOUVEAU: Branche de base (sera résolue intelligemment si None)
            )

            logger.info(f"📋 Tâche créée: {task_request.title} (Branche: {task_request.branch_name})")

            # ✅ AJOUT: Programmer le nettoyage de la tâche après un délai
            # Cela évite les fuites mémoire et permet de refaire la tâche plus tard si nécessaire
            import asyncio
            asyncio.create_task(self._cleanup_task_later(task_id, delay_minutes=10))

            return task_request

        except Exception as e:
            logger.error(f"Erreur lors de la création de la requête de tâche: {e}")
            return None

    async def _cleanup_task_later(self, task_id: str, delay_minutes: int = 10):
        """Nettoie une tâche de la liste des tâches actives après un délai."""
        import asyncio
        await asyncio.sleep(delay_minutes * 60)  # Attendre le délai en secondes

        if hasattr(self, '_active_tasks') and task_id in self._active_tasks:
            self._active_tasks.discard(task_id)
            logger.info(f"🧹 Nettoyage tâche {task_id} de la liste des tâches actives")

    def _extract_column_value(self, item_data: Dict[str, Any], column_name: str,
                            value_type: str = "text", default: Any = None) -> Any:
        """Extrait une valeur de colonne Monday.com."""

        try:
            column_values = item_data.get("column_values", [])

            # ✅ PROTECTION: Normaliser column_values en liste
            if isinstance(column_values, dict):
                # Format dict normal de l'API Monday.com
                logger.debug(f"🔧 _extract_column_value: Conversion dict → liste ({len(column_values)} colonnes)")
                column_values = list(column_values.values())
            elif not isinstance(column_values, list):
                # Type inattendu
                logger.warning(f"⚠️ _extract_column_value: Type column_values inattendu: {type(column_values)}")
                column_values = []

            for column in column_values:
                if (column.get("id", "").lower() == column_name.lower() or
                    column_name.lower() in column.get("id", "").lower()):

                    if value_type == "text":
                        return column.get("text", default)
                    elif value_type == "value":
                        return column.get("value", default)
                    elif value_type == "name":
                        value = column.get("value")
                        if value and isinstance(value, dict):
                            return value.get("name", default)
                        return default

            return default

        except Exception as e:
            logger.warning(f"Erreur extraction colonne {column_name}: {e}")
            return default

    def _generate_branch_name(self, title: str) -> str:
        """Génère un nom de branche Git à partir du titre de la tâche."""

        import re

        clean_title = re.sub(r'[^\w\s-]', '', title.lower())
        clean_title = re.sub(r'\s+', '-', clean_title.strip())

        if len(clean_title) > 50:
            clean_title = clean_title[:50].rstrip('-')

        branch_name = f"feature/{clean_title}"
        timestamp = datetime.now().strftime("%m%d")
        branch_name += f"-{timestamp}"

        return branch_name

    def _is_test_item(self, item_id: str) -> bool:
        """Vérifie si l'item est un item de test (par exemple, un item avec un ID spécifique)."""
        # Ajoutez ici les conditions pour détecter les items de test
        # Par exemple, si l'ID de l'item contient "test" ou "sandbox"
        return "test" in item_id.lower() or "sandbox" in item_id.lower()

    def _create_test_task_request(self, task_info: Dict[str, Any]) -> Optional[TaskRequest]:
        """Crée une requête de tâche pour un item de test."""
        logger.warning(f"🧪 Création d'une requête de tâche pour un item de test: {task_info.get('item_id')}")

        title = f"Test Task - {task_info.get('item_id', 'N/A')}"
        description = f"This is a test task created for item ID: {task_info.get('item_id', 'N/A')}. Please ignore."
        git_branch = self._generate_branch_name(title)
        repository_url = "" # Pas d'URL GitHub pour les items de test
        priority = "medium"
        assignee = None

        task_request = TaskRequest(
            task_id=task_info["task_id"],
            title=title,
            description=description,
            branch_name=git_branch,
            repository_url=repository_url,
            priority=priority,
            files_to_modify=[]
        )
        logger.info(f"📋 Requête de tâche de test créée: {task_request.title}")
        return task_request

    def _create_fallback_task_request(self, task_info: Dict[str, Any], error_reason: str) -> TaskRequest:
        """Crée une TaskRequest de fallback pour des items inaccessibles."""

        item_id = task_info.get("task_id", "unknown")
        title = task_info.get("title", f"Tâche {item_id}")

        logger.info(f"🔄 Création tâche fallback pour item {item_id}: {error_reason}")

        # Créer une tâche minimale mais fonctionnelle
        fallback_task = TaskRequest(
            task_id=item_id,
            title=f"[ITEM INACCESSIBLE] {title}",
            description=f"""⚠️ **Item Monday.com inaccessible**

**Raison**: {error_reason}

**Action**: Cette tâche a été créée automatiquement car l'item Monday.com original n'était plus accessible lors du traitement du webhook.

**Informations disponibles du webhook**:
- ID Item: {item_id}
- Titre: {title}
- Type: {task_info.get('task_type', 'N/A')}
- Priorité: {task_info.get('priority', 'N/A')}

**Recommandation**: Vérifiez l'état de l'item dans Monday.com et relancez manuellement si nécessaire.""",
            branch_name=self._generate_branch_name(f"fallback-{item_id}"),
            repository_url=getattr(self.settings, "default_repo_url", "") or "",
            priority=task_info.get("priority", "low"),  # Priorité basse pour les fallbacks
            task_type="analysis"  # Utiliser un type valide pour les fallbacks
        )

        return fallback_task

    async def handle_task_completion(self, task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Gère la completion d'une tâche."""

        try:
            success = result.get("success", False)
            pr_url = result.get("pr_url")

            if success and pr_url:
                update_result = await self.monday_tool._arun(
                    action="complete_task",
                    item_id=task_id,
                    pr_url=pr_url
                )
            else:
                status = "Bloqué" if not success else "À vérifier"

                error_summary = ""
                if result.get("error_summary"):
                    error_summary = " | ".join(result["error_summary"][:3])

                comment = f"""❌ **Implémentation automatique échouée**

Erreurs rencontrées: {error_summary}

Intervention manuelle requise."""

                status_result = await self.monday_tool._arun(
                    action="update_item_status",
                    item_id=task_id,
                    status=status
                )

                comment_result = await self.monday_tool._arun(
                    action="add_comment",
                    item_id=task_id,
                    comment=comment
                )

                update_result = {
                    "success": status_result.get("success", False) and comment_result.get("success", False)
                }

            return update_result

        except Exception as e:
            logger.error(f"Erreur lors de la gestion de completion: {e}")
            return {"success": False, "error": str(e)}

    async def cleanup_stuck_tasks(self):
        """Nettoie les tâches restées en processing trop longtemps."""
        try:
            conn = await get_db_connection()

            result = await conn.execute("""
                UPDATE tasks
                SET internal_status = 'failed',
                    updated_at = NOW()
                WHERE internal_status = 'processing'
                AND updated_at < NOW() - INTERVAL '1 hour'
            """)

            logger.info(f"🧹 Tâches bloquées nettoyées: {result}")

        except Exception as e:
            logger.error(f"❌ Erreur lors du cleanup des tâches: {e}")
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _check_duplicate_webhook(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Vérifie si un webhook IDENTIQUE a déjà été traité récemment.
        
        ✅ CORRECTION CRITIQUE: Ne bloque que les webhooks vraiment identiques
        (même type + même valeur), pas tous les webhooks du même item.
        Cela permet les réactivations manuelles via changement de statut.
        """
        try:
            # Extraire l'identifiant de la tâche du payload
            if 'event' not in payload:
                return None

            event = payload['event']
            pulse_id = event.get('pulseId')
            event_type = event.get('type')
            trigger_uuid = event.get('triggerUuid')

            if not pulse_id or not event_type:
                return None

            conn = await get_db_connection()

            # ✅ CORRECTION: Vérifier le triggerUuid pour détecter les VRAIS doublons
            # Monday.com envoie le même triggerUuid pour les webhooks en doublon
            # Fenêtre de 2 minutes pour éviter les doublons immédiats uniquement
            similar_webhook = await conn.fetchrow("""
                SELECT
                    webhook_events_id,
                    processed_at,
                    processing_status
                FROM webhook_events
                WHERE processing_status = 'processed'
                AND received_at >= NOW() - INTERVAL '2 minutes'
                AND payload::jsonb -> 'event' ->> 'pulseId' = $1
                AND payload::jsonb -> 'event' ->> 'type' = $2
                AND payload::jsonb -> 'event' ->> 'triggerUuid' = $3
                ORDER BY received_at DESC
                LIMIT 1
            """, str(pulse_id), event_type, trigger_uuid)

            await conn.close()

            return similar_webhook

        except Exception as e:
            logger.error(f"❌ Erreur vérification doublon webhook: {e}")
            return None
    
    async def process_monday_update(
        self,
        payload: Dict[str, Any],
        signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Traite spécifiquement les updates Monday.com (type 'update_update' ou 'column_value_changed')
        avec validations et protections contre les race conditions.
        
        Args:
            payload: Payload du webhook Monday.com
            signature: Signature du webhook pour validation
            
        Returns:
            Résultat du traitement avec succès/erreur
        """
        from services.workflow_lock_manager import workflow_lock_manager
        from services.cooldown_manager import cooldown_manager
        from services.update_debouncer import update_debouncer
        from services.reactivation_service import reactivation_service
        
        try:
            logger.info("📨 Traitement d'un update Monday.com")
            
            # 1. Valider le payload
            if 'event' not in payload:
                return {'success': False, 'error': 'Payload invalide - pas d\'événement'}
            
            event = payload['event']
            pulse_id = event.get('pulseId')
            
            if not pulse_id:
                return {'success': False, 'error': 'Pulse ID manquant'}
            
            # 2. Récupérer la tâche correspondante
            conn = await get_db_connection()
            try:
                task = await conn.fetchrow("""
                    SELECT 
                        tasks_id,
                        internal_status,
                        is_locked,
                        locked_by,
                        cooldown_until,
                        reactivation_count
                    FROM tasks
                    WHERE monday_item_id = $1
                """, int(pulse_id))
                
                if not task:
                    logger.info(f"ℹ️ Aucune tâche trouvée pour pulse_id {pulse_id}")
                    return {
                        'success': True,
                        'message': 'Tâche non trouvée - ignoré',
                        'status_code': 200
                    }
                
                task_id = task['tasks_id']
                
                # CORRECTION ERREUR #2 : Valider l'état du workflow
                reactivable_statuses = ['completed', 'failed', 'quality_check']
                if task['internal_status'] not in reactivable_statuses:
                    logger.info(
                        f"ℹ️ Tâche {task_id} dans un état non réactivable: {task['internal_status']}"
                    )
                    return {
                        'success': False,
                        'message': f'État non réactivable: {task["internal_status"]}',
                        'status_code': 200
                    }
                
                # Vérifier si déjà en traitement
                if task['is_locked']:
                    logger.info(f"⚠️ Tâche {task_id} déjà verrouillée par {task['locked_by']}")
                    return {
                        'success': False,
                        'message': 'Tâche déjà en traitement',
                        'status_code': 200
                    }
                
                # CORRECTION ERREUR #3 : Utiliser un verrou pour éviter la race condition
                async with workflow_lock_manager.acquire_update_lock(task_id, timeout=5) as lock_acquired:
                    if not lock_acquired:
                        logger.warning(f"⚠️ Impossible d'acquérir le verrou pour tâche {task_id}")
                        return {
                            'success': False,
                            'message': 'Un autre update est en cours de traitement',
                            'status_code': 200
                        }
                    
                    # Re-vérifier le cooldown dans le verrou
                    in_cooldown, cooldown_until = await cooldown_manager.is_in_cooldown(task_id)
                    
                    if in_cooldown:
                        cooldown_info = await cooldown_manager.get_cooldown_info(task_id)
                        logger.info(f"⏱️ Tâche {task_id} en cooldown")
                        return {
                            'success': False,
                            'message': 'Tâche en cooldown',
                            'cooldown_info': cooldown_info,
                            'status_code': 200
                        }
                    
                    # Extraire le texte de l'update
                    update_text = self._extract_update_text(event)
                    
                    # Analyser l'update pour déterminer si réactivation nécessaire
                    task_context = {
                        'task_id': task_id,
                        'task_title': event.get('pulseName', ''),
                        'internal_status': task['internal_status']
                    }
                    
                    update_analysis = await reactivation_service.analyze_update_for_reactivation(
                        update_text,
                        task_context
                    )
                    
                    if not update_analysis.requires_reactivation:
                        logger.info(
                            f"ℹ️ Update ne nécessite pas de réactivation (confiance: {update_analysis.confidence:.2f})"
                        )
                        return {
                            'success': True,
                            'message': 'Update analysé - pas de réactivation nécessaire',
                            'analysis': {
                                'requires_reactivation': False,
                                'confidence': update_analysis.confidence,
                                'reasoning': update_analysis.reasoning
                            },
                            'status_code': 200
                        }
                    
                    # Réactiver la tâche
                    logger.info(f"🔄 Réactivation de la tâche {task_id} suite à l'update")
                    reactivation_result = await reactivation_service.reactivate_task(
                        task_id=task_id,
                        monday_item_id=str(pulse_id),
                        update_analysis=update_analysis,
                        update_text=update_text
                    )
                    
                    return {
                        'success': reactivation_result.get('success', False),
                        'message': 'Tâche réactivée avec succès' if reactivation_result.get('success') else 'Échec de réactivation',
                        'reactivation_result': reactivation_result,
                        'status_code': 200 if reactivation_result.get('success') else 500
                    }
                    
            finally:
                await conn.close()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement de l'update Monday.com: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'status_code': 500
            }
    
    def _extract_update_text(self, event: Dict[str, Any]) -> str:
        """
        Extrait le texte pertinent d'un événement d'update Monday.com.
        
        Args:
            event: Événement Monday.com
            
        Returns:
            Texte de l'update
        """
        # Essayer différentes sources de texte
        update_text = ""
        
        # 1. Chercher dans les nouvelles valeurs de colonnes
        if 'newColumnValues' in event and event['newColumnValues']:
            for col_name, col_value in event['newColumnValues'].items():
                if isinstance(col_value, dict):
                    text = col_value.get('text', '')
                    if text:
                        update_text += f"{text} "
        
        # 2. Chercher dans les valeurs de colonnes (pour les comments)
        if 'columnValues' in event and event['columnValues']:
            for col_name, col_value in event['columnValues'].items():
                if 'comment' in col_name.lower() or 'update' in col_name.lower():
                    if isinstance(col_value, dict):
                        text = col_value.get('text', '')
                        if text:
                            update_text += f"{text} "
        
        # 3. Fallback : utiliser le nom de la tâche
        if not update_text.strip():
            update_text = event.get('pulseName', 'Update sans texte')
        
        return update_text.strip()