"""Nœud de debug avec OpenAI LLM suite à demande humaine."""

import openai
from typing import Dict, Any, List
from models.state import GraphState
from utils.logger import get_logger
from config.settings import get_settings
from config.langsmith_config import langsmith_config

logger = get_logger(__name__)
settings = get_settings()


async def openai_debug_after_human_request(state: GraphState) -> GraphState:
    """
    Nœud de debug avec OpenAI LLM après demande humaine.
    
    Ce nœud :
    1. Analyse la demande de debug humaine
    2. Utilise OpenAI pour analyser les problèmes
    3. Génère des suggestions de correction
    4. Met à jour le code si possible
    5. Re-lance les tests
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec les corrections OpenAI
    """
    task = state["task"]
    logger.info(f"🔧 Debug OpenAI pour: {task.title}")
    
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)
    
    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []
    
    state["results"]["ai_messages"].append("🔧 Analyse debug avec OpenAI LLM...")
    
    try:
        if "human_debug_attempts" not in state["results"]:
            state["results"]["human_debug_attempts"] = 0
        
        state["results"]["human_debug_attempts"] += 1
        max_human_debug = 2  
        
        logger.info(f"🔧 Debug OpenAI après validation humaine: tentative {state['results']['human_debug_attempts']}/{max_human_debug}")
        
        if state["results"]["human_debug_attempts"] > max_human_debug:
            logger.warning(f"⚠️ Limite de debug après validation humaine atteinte ({max_human_debug}) - arrêt forcé")
            state["results"]["ai_messages"].append("⚠️ Limite de debug atteinte - workflow arrêté")
            state["results"]["debug_limit_reached"] = True
            state["results"]["should_continue"] = False
            return state
        
        debug_request = state["results"].get("debug_request", "Problème à corriger")
        
        modification_instructions = state["results"].get("modification_instructions")
        if modification_instructions:
            logger.info(f"📝 Instructions de modification reçues: {modification_instructions[:200]}...")
            debug_request = modification_instructions
        
        validation_response = state["results"].get("validation_response")
        if validation_response:
            human_comments = getattr(validation_response, 'comments', '') or ''
        else:
            human_comments = ""
        
        logger.info(f"📝 Demande debug humaine: {debug_request}")
        
        debug_context = _prepare_debug_context(state, debug_request, human_comments)
        
        openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        
        debug_prompt = _create_debug_prompt(debug_context)
        
        logger.info("🤖 Appel OpenAI pour analyse debug...")
        state["results"]["ai_messages"].append("🤖 Consultation OpenAI LLM...")
        
        response = await openai_client.chat.completions.create(
            model="gpt-4",  
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert développeur qui aide à débugger du code. Analyse les problèmes et propose des solutions concrètes."
                },
                {
                    "role": "user", 
                    "content": debug_prompt
                }
            ],
            temperature=0.1,  
            max_tokens=2000
        )
        
        debug_analysis = response.choices[0].message.content
        
        logger.info(f"✅ Analyse OpenAI reçue: {len(debug_analysis)} caractères")
        state["results"]["ai_messages"].append("✅ Analyse OpenAI terminée")
        
        debug_suggestions = _parse_openai_debug_response(debug_analysis)
        
        state["results"]["openai_debug"] = {
            "analysis": debug_analysis,
            "suggestions": debug_suggestions,
            "human_request": debug_request,
            "model_used": "gpt-4",
            "timestamp": state.get("current_time")
        }
        
        if langsmith_config.client:
            try:
                langsmith_config.client.create_run(
                    name="openai_debug_analysis",
                    run_type="llm",
                    inputs={
                        "debug_request": debug_request,
                        "human_comments": human_comments,
                        "context": debug_context
                    },
                    outputs={
                        "analysis": debug_analysis,
                        "suggestions_count": len(debug_suggestions),
                        "model": "gpt-4"
                    },
                    session_name=state.get("langsmith_session"),
                    extra={
                        "workflow_id": state.get("workflow_id"),
                        "openai_debug": True,
                        "triggered_by": "human_validation"
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        if debug_suggestions:
            logger.info(f"🔧 Application de {len(debug_suggestions)} suggestions debug")
            state["results"]["ai_messages"].append(f"🔧 Application de {len(debug_suggestions)} suggestions...")
            
            if modification_instructions:
                logger.info("🔄 Déclenchement de ré-implémentation avec instructions de modification")
                state["results"]["reimplement_with_modifications"] = True
                state["results"]["modification_reason"] = "openai_debug_with_human_instructions"
                state["results"]["trigger_reimplementation"] = True
                state["results"]["ai_messages"].append("🔄 Ré-implémentation déclenchée avec instructions humaines")
            
            state["results"]["debug_applied"] = True
            state["results"]["debug_suggestions_applied"] = debug_suggestions
        
        state["results"]["openai_debug_completed"] = True
        state["results"]["should_retest"] = True  
        
        logger.info(f"🔧 Debug OpenAI terminé avec {len(debug_suggestions)} suggestions")
        state["results"]["ai_messages"].append("✅ Debug OpenAI terminé - Prêt pour re-test")
        
    except Exception as e:
        error_msg = f"Erreur debug OpenAI: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        if "error_logs" not in state["results"]:
            state["results"]["error_logs"] = []
        if "ai_messages" not in state["results"]:
            state["results"]["ai_messages"] = []
            
        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ {error_msg}")
        state["results"]["openai_debug_failed"] = True
    
    return state


def _prepare_debug_context(state: GraphState, debug_request: str, human_comments: str) -> Dict[str, Any]:
    """Prépare le contexte pour l'analyse debug OpenAI."""
    
    task = state["task"]
    results = state.get("results", {})
    
    context = {
        "task_info": {
            "title": task.title,
            "description": task.description,
            "type": task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type)
        },
        "human_feedback": {
            "debug_request": debug_request,
            "comments": human_comments
        },
        "test_results": results.get("test_results", {}),
        "error_logs": results.get("error_logs", []),
        "implementation_info": results.get("implementation_results", {}),
        "pr_info": results.get("pr_info", {}),
        "completed_nodes": state.get("completed_nodes", [])
    }
    
    return context


def _create_debug_prompt(context: Dict[str, Any]) -> str:
    """Crée le prompt pour l'analyse debug OpenAI."""
    
    task_info = context["task_info"]
    human_feedback = context["human_feedback"]
    test_results = context["test_results"]
    error_logs = context["error_logs"]
    
    prompt = f"""
DEMANDE DE DEBUG SUITE À FEEDBACK HUMAIN

=== CONTEXTE DE LA TÂCHE ===
Titre: {task_info["title"]}
Description: {task_info["description"]}
Type: {task_info["type"]}

=== FEEDBACK HUMAIN ===
Demande de debug: {human_feedback["debug_request"]}
Commentaires: {human_feedback["comments"]}

=== RÉSULTATS DES TESTS ===
{_format_test_results(test_results)}

=== ERREURS RENCONTRÉES ===
{_format_error_logs(error_logs)}

=== DEMANDE ===
Analyse les problèmes identifiés par l'humain et propose des solutions concrètes.

Réponds avec:
1. ANALYSE: Identification des problèmes principaux
2. CAUSES: Causes probables des problèmes  
3. SOLUTIONS: Solutions spécifiques et actionables
4. PRIORITÉ: Ordre de résolution recommandé

Sois précis et actionnable dans tes recommandations.
"""
    
    return prompt.strip()


def _format_test_results(test_results: Any) -> str:
    """
    Formate les résultats de tests pour le prompt.
    
    ✅ CORRECTION ERREUR 3: Gère test_results comme liste ou dict
    """
    if not test_results:
        return "Aucun résultat de test disponible"
    
    if isinstance(test_results, list):
        test_results_dict = {
            "tests": test_results,
            "count": len(test_results),
            "success": all(
                t.get("success", False) if isinstance(t, dict) else False 
                for t in test_results
            )
        }
    elif isinstance(test_results, dict):
        test_results_dict = test_results
    else:
        return f"⚠️ Résultats de tests dans un format inattendu: {type(test_results)}"
    
    if test_results_dict.get("success"):
        return "✅ Tests réussis"
    else:
        failed_tests = test_results_dict.get("failed_tests", [])
        if failed_tests:
            return f"❌ {len(failed_tests)} test(s) échoué(s):\n" + "\n".join([f"- {test}" for test in failed_tests[:5]])
        else:
            if "tests" in test_results_dict:
                failed_count = sum(
                    1 for t in test_results_dict["tests"] 
                    if isinstance(t, dict) and not t.get("success", False)
                )
                if failed_count > 0:
                    return f"❌ {failed_count} test(s) échoué(s)"
            return "❌ Tests échoués (détails non disponibles)"


def _format_error_logs(error_logs: List[str]) -> str:
    """Formate les logs d'erreur pour le prompt."""
    if not error_logs:
        return "Aucune erreur logguée"
    
    recent_errors = error_logs[-5:]
    return "\n".join([f"- {error}" for error in recent_errors])


def _parse_openai_debug_response(response: str) -> List[Dict[str, str]]:
    """Parse la réponse OpenAI et extrait les suggestions actionables."""
    
    suggestions = []
    
    import re
    
    solution_patterns = [
        r'(?:SOLUTIONS?|RECOMMANDATIONS?)[:\s]*(.*?)(?=\n\n|\n[A-Z]{2,}|$)',
        r'(?:\d+\.\s*)(.*?)(?=\n\d+\.|$)',
    ]
    
    for pattern in solution_patterns:
        matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
        for match in matches:
            if match.strip() and len(match.strip()) > 10:
                suggestions.append({
                    "type": "suggestion",
                    "description": match.strip(),
                    "priority": "medium"
                })
    
    if not suggestions:
        suggestions.append({
            "type": "general",
            "description": "Analyser la réponse OpenAI complète pour identifier les actions",
            "priority": "high",
            "full_response": response
        })
    
    return suggestions[:10]  