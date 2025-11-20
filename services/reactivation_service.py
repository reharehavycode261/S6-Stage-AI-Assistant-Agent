"""Service de réactivation des tâches terminées via Monday.com updates."""

import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from utils.logger import get_logger
from services.database_persistence_service import db_persistence
from services.workflow_lock_manager import workflow_lock_manager
from services.cooldown_manager import cooldown_manager
from services.celery_task_manager import celery_task_manager
from tools.monday_tool import MondayTool

logger = get_logger(__name__)


@dataclass
class UpdateAnalysis:
    """Résultat de l'analyse d'un update Monday.com."""
    requires_reactivation: bool
    confidence: float
    reasoning: str
    extracted_requirements: Optional[str] = None
    is_from_agent: bool = False


class ReactivationService:
    """Service pour gérer la réactivation des tâches terminées."""
    
    def __init__(self):
        self.monday_tool = MondayTool()
        
        self.reactivation_patterns = {
            'explicit_request': [
                r'\b(ajoute|ajout|add|nouveau|nouvelle|créer?|créé|create|faire|développer?|dev)\b',
                r'\b(modifi[eé]r?|change[mr]?|update|mettre à jour)\b',
                r'\b(implément[eé]r?|implement|développer?|dev|build|construire)\b',
                r'\b(corriger?|correction|fix|réparer?)\b',
                r'\b(améliorer?|amélioration|improve|enhancement|optimiser?)\b',
                r'\b(api|rest|graphql|interface|service|module|système)\b'
            ],
            'question_request': [
                r'\b(peux-tu|pouvez-vous|can you|pourrait[s]?-tu|pourrais-tu)\b',
                r'\b(il faut|il faudrait|we need|il serait bien|ajouter?)\b',
                r'\b(comment|how|que faire|what about)\b'
            ],
            'agent_exclusions': [
                r'🤖\s*AI-AGENT\s*🤖',
                r'<!--\s*AI_AGENT_SIGNATURE.*?-->',
                r'✅.*pull request.*créée',
                r'🎯.*workflow.*terminé',
                r'📋.*mise à jour.*statut',
                r'🔧.*correction.*appliquée',
                r'validation humaine',
                r'human validation',
                r'🚀.*workflow.*complété',
                r'📊.*résultats.*tests',
                r'🔍.*analyse.*code',
                r'^[🎯📋✅❌🚀🔧📊🔍🤖]',
                r'workflow\s+(completed|terminé|finished)',
                r'task\s+(completed|terminée|finished)'
            ]
        }
        
        self._recent_updates_cache = {}
        self._cache_duration = 300
    
    async def analyze_update_for_reactivation(
        self, 
        update_text: str, 
        task_context: Dict[str, Any]
    ) -> UpdateAnalysis:
        """
        Analyse un update Monday.com pour déterminer s'il nécessite une réactivation.
        
        Args:
            update_text: Texte de l'update/commentaire
            task_context: Contexte de la tâche (titre, statut, etc.)
            
        Returns:
            UpdateAnalysis avec la décision et la confiance
        """
        logger.info(f"🔍 Analyse update pour réactivation: '{update_text[:100]}...'")
        
        clean_text = update_text.lower().strip()
        task_id = task_context.get('task_id') or task_context.get('task_title', 'unknown')
        
        cache_key = f"{task_id}_{hash(clean_text) % 10000}"
        current_time = datetime.now().timestamp()
        
        if cache_key in self._recent_updates_cache:
            last_analysis_time = self._recent_updates_cache[cache_key]
            if current_time - last_analysis_time < self._cache_duration:
                logger.info(f"⏱️ Update récent déjà analysé - ignoré (cache: {cache_key})")
                return UpdateAnalysis(
                    requires_reactivation=False,
                    confidence=0.95,
                    reasoning="Update récent déjà analysé - protection anti-spam",
                    is_from_agent=False
                )
        
        self._recent_updates_cache[cache_key] = current_time
        
        self._cleanup_cache(current_time)
        
        is_from_agent = self._is_agent_message(clean_text)
        if is_from_agent:
            return UpdateAnalysis(
                requires_reactivation=False,
                confidence=0.9,
                reasoning="Message généré par l'agent - pas de réactivation",
                is_from_agent=True
            )
        
        explicit_score = self._calculate_pattern_score(clean_text, self.reactivation_patterns['explicit_request'])
        question_score = self._calculate_pattern_score(clean_text, self.reactivation_patterns['question_request'])

        context_bonus = self._calculate_context_bonus(clean_text, task_context)
        
        total_score = explicit_score + question_score + context_bonus

        requires_reactivation = total_score >= 0.1
        confidence = min(total_score, 0.95)
        
        extracted_requirements = None
        if requires_reactivation:
            extracted_requirements = self._extract_requirements(update_text)
        
        reasoning = self._build_reasoning(explicit_score, question_score, context_bonus, total_score)
        
        logger.info(f"📊 Résultat analyse: requires_reactivation={requires_reactivation}, "
                   f"confidence={confidence:.2f}, score_total={total_score:.2f}")
        
        return UpdateAnalysis(
            requires_reactivation=requires_reactivation,
            confidence=confidence,
            reasoning=reasoning,
            extracted_requirements=extracted_requirements
        )
    
    def _cleanup_cache(self, current_time: float):
        """Nettoie le cache des entrées expirées."""
        expired_keys = [
            key for key, timestamp in self._recent_updates_cache.items()
            if current_time - timestamp > self._cache_duration
        ]
        
        for key in expired_keys:
            del self._recent_updates_cache[key]
        
        if expired_keys:
            logger.debug(f"🧹 Cache nettoyé: {len(expired_keys)} entrées expirées supprimées")
    
    def _is_agent_message(self, text: str) -> bool:
        """Vérifie si le message provient de l'agent."""
        from utils.monday_comment_formatter import monday_formatter
        
        if monday_formatter.is_agent_comment(text):
            return True
        
        for pattern in self.reactivation_patterns['agent_exclusions']:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _calculate_pattern_score(self, text: str, patterns: list) -> float:
        """Calcule un score basé sur les patterns trouvés."""
        matches = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
        
        return min(matches * 0.2, 0.4)
    
    def _calculate_context_bonus(self, text: str, context: Dict[str, Any]) -> float:
        """Calcule un bonus basé sur le contexte."""
        bonus = 0.0
        
        if len(text.strip()) > 10:
            bonus += 0.1
        
        technical_words = ['feature', 'bug', 'api', 'backend', 'frontend', 'database', 'ui', 'ux']
        for word in technical_words:
            if word in text:
                bonus += 0.05
                
        return min(bonus, 0.2)
    
    def _extract_requirements(self, text: str) -> str:
        """Extrait les exigences du texte."""
        lines = text.strip().split('\n')
        relevant_lines = [line.strip() for line in lines if len(line.strip()) > 10]
        return '\n'.join(relevant_lines[:3])
    
    def _build_reasoning(self, explicit: float, question: float, context: float, total: float) -> str:
        """Construit l'explication du raisonnement."""
        parts = []
        if explicit > 0:
            parts.append(f"Demande explicite détectée (score: {explicit:.2f})")
        if question > 0:
            parts.append(f"Question/demande implicite (score: {question:.2f})")
        if context > 0:
            parts.append(f"Contexte favorable (score: {context:.2f})")
        
        reasoning = " + ".join(parts) if parts else "Aucun pattern de réactivation détecté"
        reasoning += f" = Score total: {total:.2f}"
        
        return reasoning
    
    async def reactivate_task(
        self, 
        task_id: int, 
        monday_item_id: str, 
        update_analysis: UpdateAnalysis,
        update_text: str
    ) -> Dict[str, Any]:
        """
        Réactive une tâche terminée avec protections contre les doublons.
        
        Args:
            task_id: ID de la tâche en base
            monday_item_id: ID de l'item Monday.com
            update_analysis: Résultat de l'analyse
            update_text: Texte original de l'update
            
        Returns:
            Résultat de la réactivation
        """
        logger.info(f"🔄 Réactivation de la tâche {task_id} (Monday: {monday_item_id})")
        
        lock_id = f"reactivation_{task_id}_{datetime.utcnow().timestamp()}"
        
        try:
            in_cooldown, cooldown_until = await cooldown_manager.is_in_cooldown(task_id)
            if in_cooldown:
                remaining = (cooldown_until - datetime.utcnow()).total_seconds()
                logger.warning(f"⏱️ Tâche {task_id} en cooldown (reste {int(remaining)}s)")
                await cooldown_manager.increment_failed_attempt(task_id)
                return {
                    'success': False,
                    'error': f'Tâche en cooldown (reste {int(remaining)}s)',
                    'in_cooldown': True,
                    'cooldown_until': cooldown_until.isoformat()
                }
            
            can_reactivate, reason = await workflow_lock_manager.can_reactivate_workflow(task_id)
            if not can_reactivate:
                logger.warning(f"⚠️ Réactivation impossible pour tâche {task_id}: {reason}")
                await cooldown_manager.increment_failed_attempt(task_id)
                return {
                    'success': False,
                    'error': reason,
                    'can_reactivate': False
                }
            
            if not await workflow_lock_manager.acquire_workflow_lock(task_id, lock_id):
                logger.error(f"❌ Impossible d'acquérir le verrou pour tâche {task_id}")
                await cooldown_manager.increment_failed_attempt(task_id)
                return {
                    'success': False,
                    'error': 'Impossible d\'acquérir le verrou sur la tâche',
                    'locked': True
                }
            
            try:
                revoked_tasks = []
                last_run_id = None
                async with db_persistence.db_manager.get_connection() as conn:
                    last_run_id = await conn.fetchval("""
                        SELECT tasks_runs_id
                        FROM task_runs
                        WHERE task_id = $1
                          AND status IN ('started', 'running')
                        ORDER BY started_at DESC
                        LIMIT 1
                    """, task_id)
                if last_run_id:
                    logger.info(f"🔄 Révocation des tâches actives pour run {last_run_id}")
                    revoked_tasks = await celery_task_manager.revoke_workflow_tasks(
                        last_run_id,
                        terminate=True
                    )
                    if revoked_tasks:
                        logger.info(f"✅ {len(revoked_tasks)} tâche(s) Celery révoquée(s): {revoked_tasks}")
                
                monday_success = False
                try:
                    monday_result = await self._update_monday_status(monday_item_id, "Working on it")
                    if monday_result.get('success', False):
                        monday_success = True
                        logger.info(f"✅ Statut Monday.com mis à jour: Working on it")
                    else:
                        logger.warning(f"⚠️ Échec mise à jour statut Monday (non-bloquant): {monday_result.get('error')}")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur Monday.com (non-bloquant): {e}")
                
                reactivation_id = await self._create_workflow_reactivation(
                    task_id=task_id,
                    trigger_type='update',
                    update_data={'update_text': update_text, 'confidence': update_analysis.confidence},
                    status='pending'
                )
                
                await self._update_internal_status(task_id, 'processing')
                await workflow_lock_manager.mark_task_reactivated(task_id)
                
                await self._add_update_to_task_description(task_id, update_text)
                
                run_id = await self._create_reactivation_run(task_id, update_analysis, update_text)
                
                await self._update_workflow_reactivation(reactivation_id, task_id=str(run_id), status='processing')
                
                await self._post_reactivation_acknowledgment(monday_item_id, update_text)
                
                await cooldown_manager.set_cooldown(task_id, 'normal')
                
                await cooldown_manager.reset_failed_attempts(task_id)
                
                await self._update_workflow_reactivation(reactivation_id, status='completed')
                
                await db_persistence.log_application_event(
                    task_id=task_id,
                    level="INFO",
                    source_component="reactivation_service",
                    action="task_reactivated",
                    message=f"Tâche réactivée suite à update Monday.com avec protections",
                    metadata={
                        "monday_item_id": monday_item_id,
                        "update_text": update_text[:200],
                        "confidence": update_analysis.confidence,
                        "reasoning": update_analysis.reasoning,
                        "new_run_id": run_id,
                        "revoked_tasks": len(revoked_tasks) if last_run_id else 0,
                        "lock_id": lock_id,
                        "reactivation_id": reactivation_id
                    }
                )
                
                logger.info(f"✅ Tâche {task_id} réactivée avec succès (run_id: {run_id}, reactivation_id: {reactivation_id})")
                
                return {
                    'success': True,
                    'task_id': task_id,
                    'run_id': run_id,
                    'reactivation_id': reactivation_id,
                    'monday_status_updated': monday_success,
                    'internal_status_updated': True,
                    'previous_tasks_revoked': len(revoked_tasks) if last_run_id else 0
                }
                
            finally:
                await workflow_lock_manager.release_workflow_lock(task_id, lock_id)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la réactivation: {e}", exc_info=True)
            
            if 'reactivation_id' in locals():
                try:
                    await self._update_workflow_reactivation(
                        reactivation_id, 
                        status='failed', 
                        error_message=str(e)
                    )
                except Exception as update_err:
                    logger.error(f"❌ Erreur lors de la mise à jour de la réactivation: {update_err}")
                
            await cooldown_manager.increment_failed_attempt(task_id)
            
            await workflow_lock_manager.release_workflow_lock(task_id, lock_id)
            
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _update_monday_status(self, item_id: str, status: str) -> Dict[str, Any]:
        """Met à jour le statut Monday.com avec vérification renforcée."""
        try:
            logger.info(f"🔄 Mise à jour statut Monday.com: {item_id} → {status}")
            
            result = await self.monday_tool._arun(
                action="update_item_status",
                item_id=item_id,
                status=status
            )
            
            if isinstance(result, dict) and result.get('success', False):
                logger.info(f"✅ Statut Monday.com mis à jour: {item_id} → {status}")
                return result
            else:
                logger.error(f"❌ Échec mise à jour statut Monday: {result}")
                return {'success': False, 'error': f'Résultat inattendu: {result}'}
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour Monday: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _update_internal_status(self, task_id: int, status: str):
        """Met à jour le statut interne de la tâche."""
        async with db_persistence.db_manager.get_connection() as conn:
            await conn.execute("SET session_replication_role = replica;")
            
            try:
                await conn.execute("""
                    UPDATE tasks 
                    SET internal_status = $1, 
                        monday_status = 'Working on it',
                        updated_at = NOW()
                    WHERE tasks_id = $2
                """, status, task_id)
                logger.info(f"✅ Statut tâche {task_id} mis à jour: {status} (réactivation - bypass trigger DB)")
            finally:
                await conn.execute("SET session_replication_role = DEFAULT;")
    
    async def _create_reactivation_run(
        self, 
        task_id: int, 
        update_analysis: UpdateAnalysis,
        update_text: str
    ) -> int:
        """Crée un nouveau task_run pour la réactivation."""
        async with db_persistence.db_manager.get_connection() as conn:
            last_run_info = await conn.fetchrow("""
                SELECT tasks_runs_id, reactivation_count
                FROM task_runs
                WHERE task_id = $1
                ORDER BY started_at DESC
                LIMIT 1
            """, task_id)
            
            parent_run_id = last_run_info['tasks_runs_id'] if last_run_info else None
            current_reactivation_count = last_run_info['reactivation_count'] if last_run_info else 0
            new_reactivation_count = current_reactivation_count + 1
            
            run_number = await conn.fetchval("""
                SELECT COALESCE(MAX(run_number), 0) + 1
                FROM task_runs
                WHERE task_id = $1
            """, task_id)
            
            run_id = await conn.fetchval("""
                INSERT INTO task_runs (
                    task_id, 
                    run_number,
                    status,
                    is_reactivation,
                    reactivation_count,
                    parent_run_id,
                    started_at
                ) VALUES (
                    $1, $2, 'started', TRUE, $3, $4, NOW()
                ) RETURNING tasks_runs_id
            """, task_id, run_number, new_reactivation_count, parent_run_id)
            
            await conn.execute("""
                UPDATE tasks 
                SET last_run_id = $1, updated_at = NOW()
                WHERE tasks_id = $2
            """, run_id, task_id)
            
            logger.info(f"✅ Run de réactivation créé: ID={run_id}, reactivation_count={new_reactivation_count}, parent={parent_run_id}")
            
            return run_id
    
    async def _add_update_to_task_description(self, task_id: int, update_text: str):
        """Ajoute l'update à la description de la tâche pour traçabilité."""
        try:
            async with db_persistence.db_manager.get_connection() as conn:  
                current_task = await conn.fetchrow("""
                    SELECT description FROM tasks WHERE tasks_id = $1
                """, task_id)
                
                if not current_task:
                    logger.error(f"❌ Tâche {task_id} non trouvée pour mise à jour description")
                    return
                
                original_description = current_task['description'] or ""
                
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
                
                await conn.execute("""
                    UPDATE tasks 
                    SET description = $1, updated_at = NOW()
                    WHERE tasks_id = $2
                """, updated_description, task_id)
                
                logger.info(f"📝 Description mise à jour pour tâche {task_id} (update ajouté)")
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour description tâche {task_id}: {e}", exc_info=True)
    
    async def _post_reactivation_acknowledgment(self, monday_item_id: str, original_update: str):
        """Poste un commentaire de confirmation de réactivation."""
        try:
            from utils.monday_comment_formatter import monday_formatter
            
            creator_name = None
            try:
                item_info = await self.monday_tool._arun(
                    action="get_item_info",
                    item_id=monday_item_id
                )
                if item_info and item_info.get("success"):
                    creator_name = item_info.get("creator_name")
                    if creator_name:
                        logger.debug(f"👤 Créateur du ticket récupéré: {creator_name}")
            except Exception as e:
                logger.debug(f"⚠️ Impossible de récupérer le créateur: {e}")
            
            comment = monday_formatter.format_reactivation_acknowledgment(original_update, creator_name)
            
            result = await self.monday_tool._arun(
                action="add_comment",
                item_id=monday_item_id,
                comment=comment
            )
            
            if result.get('success', False):
                logger.info(f"✅ Commentaire de réactivation posté sur Monday item {monday_item_id}")
            else:
                logger.warning(f"⚠️ Échec posting commentaire de réactivation: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Erreur posting commentaire de réactivation: {e}", exc_info=True)
    
    async def _create_workflow_reactivation(
        self,
        task_id: int,
        trigger_type: str,
        update_data: Dict[str, Any],
        status: str = 'pending'
    ) -> int:
        """
        Crée un enregistrement de réactivation de workflow.
        
        Args:
            task_id: ID de la tâche réactivée
            trigger_type: Type de déclencheur ('update', 'manual', 'automatic')
            update_data: Données de l'update
            status: Statut initial
            
        Returns:
            ID de l'enregistrement de réactivation créé
        """
        try:
            import json
            async with db_persistence.db_manager.get_connection() as conn:
                reactivation_id = await conn.fetchval("""
                    INSERT INTO workflow_reactivations (
                        workflow_id,
                        trigger_type,
                        update_data,
                        status,
                        reactivated_at
                    ) VALUES ($1, $2, $3, $4, NOW())
                    RETURNING id
                """, task_id, trigger_type, json.dumps(update_data), status)
                
                logger.info(f"✅ Enregistrement de réactivation créé: ID {reactivation_id} pour tâche {task_id}")
                return reactivation_id
                
        except Exception as e:
            logger.error(f"❌ Erreur création enregistrement réactivation: {e}", exc_info=True)
            return -1
    
    async def _update_workflow_reactivation(
        self,
        reactivation_id: int,
        task_id: Optional[str] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """
        Met à jour un enregistrement de réactivation.
        
        Args:
            reactivation_id: ID de l'enregistrement à mettre à jour
            task_id: ID de la tâche Celery (optionnel)
            status: Nouveau statut (optionnel)
            error_message: Message d'erreur (optionnel)
        """
        try:
            if reactivation_id <= 0:
                return
                
            async with db_persistence.db_manager.get_connection() as conn:
                updates = []
                params = []
                param_idx = 1
                
                if task_id is not None:
                    updates.append(f"task_id = ${param_idx}")
                    params.append(task_id)
                    param_idx += 1
                
                if status is not None:
                    updates.append(f"status = ${param_idx}")
                    params.append(status)
                    param_idx += 1
                    
                    if status in ['completed', 'failed']:
                        updates.append("completed_at = NOW()")
                
                if error_message is not None:
                    updates.append(f"error_message = ${param_idx}")
                    params.append(error_message)
                    param_idx += 1
                
                if not updates:
                    return
                
                params.append(reactivation_id)
                
                query = f"""
                    UPDATE workflow_reactivations
                    SET {', '.join(updates)}
                    WHERE id = ${param_idx}
                """
                
                await conn.execute(query, *params)
                logger.debug(f"✅ Enregistrement de réactivation {reactivation_id} mis à jour")
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour enregistrement réactivation {reactivation_id}: {e}", exc_info=True)


reactivation_service = ReactivationService()
