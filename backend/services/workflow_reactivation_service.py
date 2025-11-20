"""
Service de réactivation de workflow qui crée de NOUVEAUX WorkflowRuns.

DIFFÉRENCE CLÉ avec ReactivationService:
- ReactivationService : Reprend un workflow existant où il s'est arrêté
- WorkflowReactivationService : Crée un NOUVEAU workflow qui repart de zéro depuis MAIN
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass

from utils.logger import get_logger
from services.database_persistence_service import db_persistence
from services.workflow_lock_manager import workflow_lock_manager
from services.cooldown_manager import cooldown_manager
from services.reactivation_service import UpdateAnalysis

logger = get_logger(__name__)


class WorkflowReactivationService:
    """
    Service pour créer de nouveaux workflows à partir d'updates Monday.com.
    
    Ce service crée un NOUVEAU workflow run qui:
    1. Clone le repository depuis MAIN (dernière version)
    2. Crée une NOUVELLE branche (feature/xxx-reactivation-N)
    3. Réexécute tous les nœuds depuis le début
    4. Crée une NOUVELLE Pull Request avec "[Réactivation N]" dans le titre
    """
    
    def __init__(self):
        self.cooldown_duration = 0  
    
    async def create_new_workflow_run_from_update(
        self,
        task_id: int,
        monday_item_id: str,
        update_analysis: UpdateAnalysis,
        update_text: str,
        board_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        task_context: Optional[Dict[str, Any]] = None  
    ) -> Dict[str, Any]:
        """
        Crée un NOUVEAU workflow run à partir d'un update Monday.com.
        
        Args:
            task_id: ID de la tâche en base (tasks_id)
            monday_item_id: ID de l'item Monday.com
            update_analysis: Résultat de l'analyse de l'update
            update_text: Texte original de l'update
            board_id: ID du board Monday.com
            metadata: Métadonnées additionnelles
            task_context: Contexte de la tâche (incluant user_language, project_language)
            
        Returns:
            Dict contenant:
                - success: bool
                - run_id: int (nouveau task_run_id créé)
                - workflow_id: int
                - is_reactivation: True
                - task_context: Dict (contexte avec langues)
                - error: str (si échec)
        """
        logger.info(f"🔄 Création nouveau workflow run depuis update - Tâche {task_id}")
        
        try:
            in_cooldown, cooldown_until = await cooldown_manager.is_in_cooldown(task_id)
            if in_cooldown:
                remaining = (cooldown_until - datetime.utcnow()).total_seconds()
                logger.error("="*80)
                logger.error("❌ RÉACTIVATION BLOQUÉE - COOLDOWN ACTIF")
                logger.error("="*80)
                logger.error(f"🆔 Task ID: {task_id}")
                logger.error(f"⏱️  Temps restant: {int(remaining)}s")
                logger.error(f"🕐 Cooldown jusqu'à: {cooldown_until.isoformat()}")
                logger.error("="*80)
                return {
                    'success': False,
                    'error': f'Tâche en cooldown (reste {int(remaining)}s)',
                    'in_cooldown': True,
                    'cooldown_until': cooldown_until.isoformat()
                }
            
            can_reactivate, reason = await workflow_lock_manager.can_reactivate_workflow(task_id)
            if not can_reactivate:
                logger.error("="*80)
                logger.error("❌ RÉACTIVATION BLOQUÉE - ÉTAT DE LA TÂCHE")
                logger.error("="*80)
                logger.error(f"🆔 Task ID: {task_id}")
                logger.error(f"❌ Raison: {reason}")
                logger.error("="*80)
                return {
                    'success': False,
                    'error': reason,
                    'can_reactivate': False
                }
            
            reactivation_count = await self._get_reactivation_count(task_id)
            logger.info(f"🔢 Nombre de réactivations actuel: {reactivation_count}")
            
            task_info = await self._get_task_info(task_id)
            if not task_info:
                return {
                    'success': False,
                    'error': f'Tâche {task_id} introuvable'
                }
            
            logger.info(f"📋 Tâche trouvée: {task_info['title']}")
            logger.info(f"🔄 Nombre de réactivations précédentes: {reactivation_count}")
            
            try:
                await self._add_update_to_task_description(task_id, update_text)
                logger.info(f"✅ Update ajouté à la description de la tâche {task_id}")
            except Exception as desc_error:
                logger.warning(f"⚠️ Erreur ajout update à description (non-bloquant): {desc_error}")
            
            update_data = {
                'update_text': update_text,
                'confidence': update_analysis.confidence,
                'reasoning': update_analysis.reasoning,
                'monday_item_id': monday_item_id,
                'board_id': board_id
            }
            
            if metadata:
                update_data.update(metadata)
            
            reactivation_id = await self._log_reactivation_attempt(
                task_id=task_id,
                trigger_type='update',
                update_data=update_data
            )
            
            logger.info(f"📝 Réactivation enregistrée: ID={reactivation_id}")
            
            new_run_id = None
            try:
                new_run_id = await self._create_new_task_run(
                    task_id=task_id,
                    is_reactivation=True,
                    reactivation_count=reactivation_count + 1,
                    parent_run_id=task_info.get('last_run_id')
                )
            except Exception as create_run_error:
                logger.error(f"❌ Erreur création task_run: {create_run_error}", exc_info=True)
                try:
                    await self._update_reactivation_status(reactivation_id, 'failed', str(create_run_error))
                except:
                    pass
                return {
                    'success': False,
                    'error': f'Échec création task_run: {str(create_run_error)}'
                }
            
            logger.info(f"✅ Nouveau workflow run créé: run_id={new_run_id}")
            
            if not new_run_id or new_run_id <= 0:
                logger.error("="*80)
                logger.error("❌ ÉCHEC CRITIQUE - RUN_ID INVALIDE")
                logger.error("="*80)
                logger.error(f"🆔 Task ID: {task_id}")
                logger.error(f"❌ Run ID: {new_run_id}")
                logger.error("="*80)
                return {
                    'success': False,
                    'error': f'Échec création task_run - run_id invalide: {new_run_id}'
                }
            
            await self._update_reactivation_with_run_id(reactivation_id, new_run_id)
            
            await workflow_lock_manager.mark_task_reactivated(task_id)
            
            logger.info(f"🎯 Workflow run créé avec succès: run_id={new_run_id}")
            
            result = {
                'success': True,
                'run_id': new_run_id,
                'task_id': task_id,  
                'is_reactivation': True,
                'reactivation_count': reactivation_count + 1,
                'reactivation_id': reactivation_id,
                'update_text': update_text,
                'confidence': update_analysis.confidence,
                'task_context': task_context  
            }
            
            if metadata:
                result['metadata'] = metadata
                logger.info(f"✅ Metadata ajoutées au workflow: {list(metadata.keys())}")
            
            if task_context and ('user_language' in task_context or 'project_language' in task_context):
                logger.info(f"🌍 Langues ajoutées au workflow: user={task_context.get('user_language', 'en')}, project={task_context.get('project_language', 'en')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur création nouveau workflow run: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Erreur interne: {str(e)}'
            }
    
    async def _get_reactivation_count(self, task_id: int) -> int:
        """
        Récupère le nombre de réactivations d'une tâche.
        
        ✅ CORRECTION CRITIQUE: Calculer depuis task_runs, pas depuis tasks.reactivation_count
        qui peut ne pas exister ou être obsolète.
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                count = await conn.fetchval("""
                    SELECT COUNT(*) 
                    FROM task_runs 
                    WHERE task_id = $1 AND is_reactivation = TRUE
                """, task_id)
                return count or 0
        except Exception as e:
            logger.error(f"❌ Erreur récupération compteur réactivations: {e}")
            return 0
    
    async def _get_task_info(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'une tâche."""
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        tasks_id,
                        monday_item_id,
                        monday_board_id,
                        title,
                        description,
                        repository_url,
                        default_branch,
                        internal_status,
                        last_run_id,
                        reactivation_count
                    FROM tasks
                    WHERE tasks_id = $1
                """, task_id)
                
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"❌ Erreur récupération informations tâche: {e}")
            return None
    
    async def _log_reactivation_attempt(
        self,
        task_id: int,
        trigger_type: str,
        update_data: Dict[str, Any]
    ) -> int:
        """Enregistre une tentative de réactivation dans workflow_reactivations."""
        try:
            import json
            async with db_persistence.db_manager.get_connection() as conn:
                reactivation_id = await conn.fetchval("""
                    INSERT INTO workflow_reactivations (
                        workflow_id,
                        trigger_type,
                        update_data,
                        status,
                        created_at
                    ) VALUES ($1, $2, $3, 'pending', NOW())
                    RETURNING id
                """, task_id, trigger_type, json.dumps(update_data))
                
                logger.info(f"📝 Réactivation enregistrée: ID={reactivation_id}")
                return reactivation_id
        except Exception as e:
            logger.error(f"❌ Erreur enregistrement réactivation: {e}")
            return -1
    
    async def _update_reactivation_with_run_id(self, reactivation_id: int, run_id: int):
        """Met à jour l'enregistrement de réactivation avec le run_id créé."""
        if reactivation_id <= 0:
            return
        
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE workflow_reactivations
                    SET task_id = $1,
                        status = 'processing',
                        updated_at = NOW()
                    WHERE id = $2
                """, str(run_id), reactivation_id)
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour réactivation: {e}")
    
    async def _create_new_task_run(
        self,
        task_id: int,
        is_reactivation: bool,
        reactivation_count: int,
        parent_run_id: Optional[int] = None
    ) -> int:
        """
        Crée un NOUVEAU task_run pour la réactivation.
        
        Args:
            task_id: ID de la tâche
            is_reactivation: True pour marquer comme réactivation
            reactivation_count: Numéro de la réactivation
            parent_run_id: ID du run parent (optionnel)
            
        Returns:
            ID du nouveau task_run créé
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                max_run_number = await conn.fetchval("""
                    SELECT COALESCE(MAX(run_number), 0)
                    FROM task_runs
                    WHERE task_id = $1
                """, task_id)
                
                new_run_number = (max_run_number or 0) + 1
                
                new_run_id = await conn.fetchval("""
                    INSERT INTO task_runs (
                        task_id,
                        run_number,
                        status,
                        is_reactivation,
                        reactivation_count,
                        parent_run_id,
                        started_at
                    ) VALUES ($1, $2, 'started', $3, $4, $5, NOW())
                    RETURNING tasks_runs_id
                """, task_id, new_run_number, is_reactivation, reactivation_count, parent_run_id)
                
                await conn.execute("""
                    UPDATE tasks
                    SET last_run_id = $1,
                        updated_at = NOW()
                    WHERE tasks_id = $2
                """, new_run_id, task_id)
                
                logger.info(f"✅ Nouveau task_run créé: ID={new_run_id}, run_number={new_run_number}")
                
                return new_run_id
                
        except Exception as e:
            logger.error(f"❌ Erreur création task_run: {e}", exc_info=True)
            raise
    
    async def _update_reactivation_status(self, reactivation_id: int, status: str, error_message: Optional[str] = None):
        """
        Met à jour le statut d'une réactivation.
        
        Args:
            reactivation_id: ID de la réactivation
            status: Nouveau statut ('pending', 'processing', 'completed', 'failed')
            error_message: Message d'erreur optionnel
        """
        if not reactivation_id or reactivation_id <= 0:
            return
        
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE workflow_reactivations
                    SET status = $1,
                        error_message = $2,
                        updated_at = NOW()
                    WHERE id = $3
                """, status, error_message, reactivation_id)
                
                logger.info(f"✅ Réactivation {reactivation_id} marquée comme {status}")
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour statut réactivation: {e}")
    
    async def mark_reactivation_completed(self, reactivation_id: int, success: bool, error_message: Optional[str] = None):
        """Marque une réactivation comme terminée."""
        if reactivation_id <= 0:
            return
        
        try:
            status = 'completed' if success else 'failed'
            async with db_persistence.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE workflow_reactivations
                    SET status = $1,
                        error_message = $2,
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $3
                """, status, error_message, reactivation_id)
                
                logger.info(f"✅ Réactivation {reactivation_id} marquée comme {status}")
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour statut réactivation: {e}")
    
    async def _add_update_to_task_description(self, task_id: int, update_text: str):
        """
        Ajoute l'update à la description de la tâche pour traçabilité.
        ✅ CORRECTION: Enregistrer les updates dans la DB pour historique.
        ✅ NOUVEAU: Mettre à jour aussi le titre pour refléter la nouvelle demande
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                current_task = await conn.fetchrow("""
                    SELECT description, title FROM tasks WHERE tasks_id = $1
                """, task_id)
                
                if not current_task:
                    logger.error(f"❌ Tâche {task_id} non trouvée pour mise à jour description")
                    return
                
                original_description = current_task['description'] or ""
                original_title = current_task['title'] or ""
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                update_section = f"\n\n--- UPDATE {timestamp} ---\n{update_text[:500]}"

                if "--- UPDATES ---" in original_description:
                    updated_description = original_description + update_section
                else:
                    updated_description = original_description + "\n\n--- UPDATES ---" + update_section
                
                if len(updated_description) > 5000:
                    parts = updated_description.split("--- UPDATE ")
                    if len(parts) > 4:  
                        updated_description = parts[0] + "--- UPDATE " + "--- UPDATE ".join(parts[-3:])
                
                new_title_base = update_text[:100].strip()
                if original_title.startswith("[Réactivation"):
                    import re
                    match = re.match(r'\[Réactivation (\d+)\]', original_title)
                    if match:
                        reactivation_num = match.group(1)
                        updated_title = f"[Réactivation {reactivation_num}] {new_title_base}"
                    else:
                        updated_title = f"{new_title_base}"
                else:
                    updated_title = f"{new_title_base}"
                
                await conn.execute("""
                    UPDATE tasks 
                    SET description = $1, title = $2, updated_at = NOW()
                    WHERE tasks_id = $3
                """, updated_description, updated_title, task_id)
                
                logger.info(f"📝 Description et titre mis à jour pour tâche {task_id}")
                logger.info(f"   • Nouveau titre: {updated_title}")
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour description tâche {task_id}: {e}", exc_info=True)

workflow_reactivation_service = WorkflowReactivationService()