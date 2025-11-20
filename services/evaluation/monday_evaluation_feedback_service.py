"""
Monday Evaluation Feedback Service - Service pour renvoyer les scores d'évaluation dans Monday.

Implémentation de la boucle de rétroaction:
Update Monday → Agent → Output → LLM Judge + Validation Humaine → 🔁 Retour Monday

Permet de:
1. Poster les scores LLM dans Monday
2. Poster les validations humaines dans Monday
3. Mettre à jour les colonnes Monday avec les métriques
4. Créer des updates de feedback
"""

from typing import Dict, Any, Optional
from datetime import datetime
from tools.monday_tool import MondayTool
from utils.monday_comment_formatter import format_for_monday
from utils.logger import get_logger

logger = get_logger(__name__)


class MondayEvaluationFeedbackService:
    """
    Service pour renvoyer les résultats d'évaluation dans Monday.com.
    """
    
    def __init__(self):
        """Initialise le service avec le MondayTool."""
        self.monday_tool = MondayTool()
        logger.info("✅ MondayEvaluationFeedbackService initialisé")
    
    async def post_llm_evaluation_result(
        self,
        item_id: str,
        evaluation_result: Dict[str, Any],
        tag_user: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Poste le résultat de l'évaluation LLM dans Monday.
        
        Args:
            item_id: ID de l'item Monday.
            evaluation_result: Résultat de l'évaluation (de VyDataEvaluator).
            tag_user: Nom d'utilisateur à taguer (optionnel).
            
        Returns:
            Résultat de la création de l'update.
        """
        try:
            logger.info(f"📤 Envoi résultat évaluation LLM vers Monday (item {item_id})...")
            
            score = evaluation_result['llm_score']
            status = evaluation_result['status']
            test_id = evaluation_result.get('test_id', 'N/A')
            reasoning = evaluation_result.get('llm_reasoning', 'N/A')
            duration = evaluation_result.get('duration_seconds', 0)
            
            score_emoji = self._get_score_emoji(score)
            status_emoji = "✅" if status == "PASS" else "❌"
            
            message = f"""
🤖 **Évaluation Automatique LLM Judge**

{status_emoji} **Statut**: {status}
{score_emoji} **Score Global**: {score}/100
🧪 **Test ID**: {test_id}
⏱️ **Durée**: {duration}s

📋 **Scores par Critère**:
"""
            
            criteria_scores = evaluation_result.get('criteria_scores', {})
            if criteria_scores:
                for criterion, crit_score in criteria_scores.items():
                    crit_emoji = self._get_score_emoji(crit_score)
                    message += f"{crit_emoji} {criterion.capitalize()}: {crit_score}/100\n"
            
            message += f"""
💬 **Justification**:
{reasoning}

---
⏳ **En attente de validation humaine pour score final**
"""
            
            formatted_message = format_for_monday(message, tag_user=tag_user)
            
            result = await self.monday_tool.create_update(
                item_id=item_id,
                update_body=formatted_message
            )
            
            if result.get("success"):
                logger.info(f"✅ Évaluation LLM postée dans Monday (item {item_id})")
                return {
                    "success": True,
                    "update_id": result.get("update_id"),
                    "message": "Évaluation LLM postée avec succès"
                }
            else:
                logger.error(f"❌ Échec post évaluation LLM: {result.get('error')}")
                return {
                    "success": False,
                    "error": result.get("error")
                }
        
        except Exception as e:
            logger.error(f"❌ Erreur post évaluation LLM dans Monday: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def post_human_validation_result(
        self,
        item_id: str,
        evaluation_result: Dict[str, Any],
        tag_user: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Poste le résultat de la validation humaine dans Monday.
        
        Args:
            item_id: ID de l'item Monday.
            evaluation_result: Résultat complet avec validation humaine.
            tag_user: Nom d'utilisateur à taguer.
            
        Returns:
            Résultat de la création de l'update.
        """
        try:
            logger.info(f"📤 Envoi validation humaine vers Monday (item {item_id})...")
            
            llm_score = evaluation_result['llm_score']
            human_score = evaluation_result.get('human_score', 0)
            final_score = evaluation_result['final_score']
            status = evaluation_result['status']
            human_feedback = evaluation_result.get('human_feedback', 'Aucun commentaire')
            test_id = evaluation_result.get('test_id', 'N/A')
            
            final_emoji = self._get_score_emoji(final_score)
            status_emoji = "✅" if status == "PASS" else "❌"
            
            message = f"""
👤 **Validation Humaine Complétée**

{status_emoji} **Statut Final**: {status}
{final_emoji} **Score Final**: {final_score}/100
🧪 **Test ID**: {test_id}

📊 **Détails des Scores**:
🤖 Score LLM: {llm_score}/100
👤 Score Humain: {human_score}/100
🎯 Score Final (60% LLM + 40% Humain): {final_score}/100

💬 **Feedback Humain**:
{human_feedback}

---
✅ **Évaluation complète et validée**
"""
            
            formatted_message = format_for_monday(message, tag_user=tag_user)
            
            result = await self.monday_tool.create_update(
                item_id=item_id,
                update_body=formatted_message
            )
            
            if result.get("success"):
                logger.info(f"✅ Validation humaine postée dans Monday (item {item_id})")
                return {
                    "success": True,
                    "update_id": result.get("update_id"),
                    "message": "Validation humaine postée avec succès"
                }
            else:
                logger.error(f"❌ Échec post validation humaine: {result.get('error')}")
                return {
                    "success": False,
                    "error": result.get("error")
                }
        
        except Exception as e:
            logger.error(f"❌ Erreur post validation humaine dans Monday: {e}", exc_info=True)
            return {
                    "success": False,
                "error": str(e)
            }
    
    async def request_human_validation(
        self,
        item_id: str,
        evaluation_result: Dict[str, Any],
        assigned_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Demande une validation humaine dans Monday.
        
        Args:
            item_id: ID de l'item Monday.
            evaluation_result: Résultat de l'évaluation LLM.
            assigned_to: Utilisateur assigné pour la validation.
            
        Returns:
            Résultat de la création de la demande.
        """
        try:
            logger.info(f"🙋 Demande de validation humaine (item {item_id})...")
            
            score = evaluation_result['llm_score']
            test_id = evaluation_result.get('test_id', 'N/A')
            agent_output = evaluation_result.get('agent_output', '')[:200]  
            
            message = f"""
🙋 **Validation Humaine Requise**

🤖 **Score LLM préliminaire**: {score}/100
🧪 **Test ID**: {test_id}

📝 **Aperçu de la réponse de l'agent**:
{agent_output}...

---
👉 **Action requise**: Veuillez évaluer cette réponse et fournir:
1. Un score humain (0-100)
2. Vos commentaires/feedback
3. Validation (approve/reject)

⏰ Le score final sera calculé automatiquement (60% LLM + 40% Humain)
"""
            
            formatted_message = format_for_monday(message, tag_user=assigned_to)
            
            result = await self.monday_tool.create_update(
                item_id=item_id,
                update_body=formatted_message
            )
            
            if result.get("success"):
                logger.info(f"✅ Demande de validation postée (item {item_id})")
                return {
                    "success": True,
                    "update_id": result.get("update_id"),
                    "message": "Demande de validation postée"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error")
                }
        
        except Exception as e:
            logger.error(f"❌ Erreur demande validation: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def post_performance_summary(
        self,
        item_id: str,
        metrics: Dict[str, Any],
        tag_user: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Poste un résumé des métriques de performance dans Monday.
        
        Args:
            item_id: ID de l'item Monday.
            metrics: Métriques de performance (de GoldenDatasetManager).
            tag_user: Utilisateur à taguer.
            
        Returns:
            Résultat de la création de l'update.
        """
        try:
            logger.info(f"📊 Envoi résumé performance vers Monday (item {item_id})...")
            
            total_tests = metrics.get('total_tests_run', 0)
            pass_rate = metrics.get('pass_rate_percent', 0)
            avg_score = metrics.get('avg_final_score', 0)
            reliability = metrics.get('reliability_status', 'unknown')
            date = metrics.get('metric_date', datetime.now().strftime("%Y-%m-%d"))
            
            reliability_emoji = {
                'excellent': '🟢',
                'good': '🟡',
                'needs_improvement': '🔴'
            }.get(reliability, '⚪')
            
            message = f"""
📊 **Résumé Performance Agent - {date}**

{reliability_emoji} **Statut Fiabilité**: {reliability.upper()}
🎯 **Score Moyen**: {avg_score}/100
📈 **Taux de Réussite**: {pass_rate}%
🧪 **Tests Exécutés**: {total_tests}

📋 **Détails**:
✅ Tests réussis: {metrics.get('total_tests_run', 0) * pass_rate // 100}
❌ Tests échoués: {metrics.get('total_tests_run', 0) - (metrics.get('total_tests_run', 0) * pass_rate // 100)}
⏳ En attente validation: {metrics.get('tests_pending_validation', 0)}

💬 **Notes**:
{metrics.get('notes', 'Aucune note')}

---
📈 **Tendance**: {self._get_trend_text(avg_score)}
"""
            
            formatted_message = format_for_monday(message, tag_user=tag_user)
            
            result = await self.monday_tool.create_update(
                item_id=item_id,
                update_body=formatted_message
            )
            
            if result.get("success"):
                logger.info(f"✅ Résumé performance posté (item {item_id})")
                return {
                    "success": True,
                    "update_id": result.get("update_id"),
                    "message": "Résumé performance posté"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error")
                }
        
        except Exception as e:
            logger.error(f"❌ Erreur post résumé performance: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def _get_score_emoji(score: int) -> str:
        """Retourne un emoji selon le score."""
        if score >= 90:
            return "🌟"
        elif score >= 80:
            return "✅"
        elif score >= 70:
            return "👍"
        elif score >= 50:
            return "⚠️"
        else:
            return "❌"
    
    @staticmethod
    def _get_trend_text(score: float) -> str:
        """Génère un texte de tendance selon le score."""
        if score >= 85:
            return "Excellente performance, maintenir le niveau 🚀"
        elif score >= 75:
            return "Bonne performance, légères améliorations possibles 📈"
        elif score >= 65:
            return "Performance acceptable, des améliorations sont nécessaires 📊"
        else:
            return "Performance à améliorer de manière prioritaire ⚠️"

