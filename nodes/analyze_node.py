"""Nœud d'analyse des requirements - analyse les spécifications et génère un plan."""

import os
from typing import Dict, Any, Tuple
from models.state import GraphState
from tools.ai_engine_hub import ai_hub, AIRequest, TaskType
from utils.logger import get_logger
from utils.persistence_decorator import with_persistence
from utils.helpers import get_working_directory

logger = get_logger(__name__)

USE_LANGCHAIN_ANALYSIS = True


def validate_description_quality(description: str, title: str = "") -> Tuple[bool, str, str]:
    """
    Valide si la description est suffisamment détaillée pour l'implémentation.
    
    Args:
        description: Description de la tâche
        title: Titre de la tâche (optionnel, pour enrichissement)
        
    Returns:
        Tuple (is_valid, message, enriched_description)
    """
    if not description:
        return False, "Description manquante", title or "Aucune description fournie"
    
    description_clean = description.strip()
    
    if len(description_clean) < 20:
        logger.warning(f"⚠️ Description trop courte ({len(description_clean)} caractères)")
        if title:
            enriched = f"""Basé sur le titre: {title}

Analysez le titre pour comprendre ce qui doit être implémenté.
Si le titre mentionne une méthode/fonction, implémentez-la.
Si le titre mentionne un fichier, créez/modifiez-le.

Description originale: {description_clean}"""
            return False, f"Description courte, utilisation du titre", enriched
        return False, "Description trop courte (< 20 caractères)", description_clean
    
    vague_keywords = ["statut", "status", "todo", "à faire", "fix", "bug", "test"]
    if description_clean.lower() in vague_keywords:
        logger.warning(f"⚠️ Description trop vague: '{description_clean}'")
        if title:
            enriched = f"""⚠️ Description originale trop vague: "{description_clean}"

🎯 BASEZ-VOUS SUR LE TITRE: {title}

Analysez le titre pour extraire:
- QUELLE fonctionnalité implémenter
- DANS QUEL fichier/classe
- COMMENT l'implémenter (regardez le contexte du code existant)

Exemple: Si le titre dit "Ajouter méthode count()", alors:
1. Identifiez la classe cible (ex: GenericDAO)
2. Créez une méthode public long count()
3. Implémentez SELECT COUNT(*) FROM table
"""
            return False, f"Description vague ('{description_clean}'), utilisation du titre", enriched
        return False, f"Description trop vague: '{description_clean}'", description_clean
    
    has_technical_terms = any(word in description_clean.lower() for word in [
        "méthode", "method", "function", "fonction", "classe", "class", 
        "api", "endpoint", "ajouter", "créer", "create", "modifier", 
        "modify", "implémenter", "implement", "développer", "fichier",
        "file", "select", "insert", "update", "delete", "sql"
    ])
    
    if not has_technical_terms and len(description_clean) < 50:
        logger.warning("⚠️ Description manque de détails techniques")
        if title:
            enriched = f"""Description courte et peu technique: {description_clean}

📋 Titre: {title}

Utilisez le titre pour comprendre l'objectif et implémentez en fonction du contexte du code existant.
"""
            return False, "Description peu technique, enrichie avec titre", enriched
    
    return True, "Description valide", description_clean


@with_persistence("analyze_requirements")
async def analyze_requirements(state: GraphState) -> GraphState:
    """
    Nœud d'analyse des requirements : analyse la tâche et détermine la stratégie d'implémentation.
    
    Ce nœud :
    1. Parse la description de la tâche
    2. Identifie les composants techniques nécessaires
    3. Détermine la complexité et les risques
    4. Prépare le contexte pour l'implémentation
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec l'analyse des requirements
    """
    logger.info(f"🔍 Analyse des requirements pour: {state['task'].title}")
    
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    state["results"]["current_status"] = "analyzing"
    state["results"]["ai_messages"].append("Début de l'analyse des requirements...")
    
    state["current_node"] = "analyze_requirements"
    
    try:
        task = state["task"]
        
        is_valid, validation_msg, enriched_description = validate_description_quality(
            task.description, 
            task.title
        )
        
        if not is_valid:
            logger.warning(f"⚠️ Validation description: {validation_msg}")
            logger.info(f"📝 Description enrichie avec le titre de la tâche")
            task.description = enriched_description
            state["results"]["ai_messages"].append(
                f"⚠️ Description originale vague, enrichissement avec le titre: {task.title}"
            )
        else:
            logger.info(f"✅ Description valide: {validation_msg}")
        
        analysis_context = {
            "task_title": task.title,
            "description": task.description,
            "task_type": task.task_type,
            "priority": task.priority,
            "acceptance_criteria": task.acceptance_criteria,
            "technical_context": task.technical_context,
            "files_to_modify": task.files_to_modify,
            "estimated_complexity": task.estimated_complexity,
            "repository_url": task.repository_url
        }
        
        if USE_LANGCHAIN_ANALYSIS:
            try:
                logger.info("🔗 Utilisation de la chaîne LangChain requirements_analysis...")
                
                from ai.chains.requirements_analysis_chain import (
                    generate_requirements_analysis,
                    extract_analysis_metrics
                )
                
                run_step_id = state.get("db_step_id")
                working_dir = get_working_directory(state)  
                
                logger.info(f"📁 working_directory extrait du state: {working_dir}")
                if not working_dir:
                    logger.warning(f"⚠️ working_directory est None ! Clés disponibles: {list(state.keys())}")
                
                project_scan_result = None
                if working_dir and os.path.exists(working_dir):
                    try:
                        from ai.chains.requirements_analysis_chain import _scan_project_files
                        project_scan_result = _scan_project_files(working_dir)
                        if project_scan_result:
                            logger.info(f"✅ Scan projet: {project_scan_result['total_files']} fichiers, technologies: {project_scan_result['technologies']}")
                            state["results"]["project_scan"] = project_scan_result
                    except Exception as scan_error:
                        logger.warning(f"⚠️ Erreur scan projet: {scan_error}")
                
                structured_analysis = await generate_requirements_analysis(
                    task_title=task.title,
                    task_description=task.description,
                    task_type=task.task_type,
                    priority=task.priority,
                    acceptance_criteria=task.acceptance_criteria,
                    technical_context=task.technical_context,
                    files_to_modify=task.files_to_modify,
                    repository_url=task.repository_url,
                    working_dir=working_dir,  
                    additional_context={
                        "workflow_id": state.get("workflow_id", "unknown"),
                        "task_id": task.task_id  
                    },
                    provider="anthropic",
                    fallback_to_openai=True,
                    validate_files=True if working_dir else False,  
                    run_step_id=run_step_id
                )
                
                metrics = extract_analysis_metrics(structured_analysis)
                
                logger.info(
                    f"✅ Analyse structurée générée: "
                    f"{metrics['total_files']} fichiers, "
                    f"{metrics['total_risks']} risques, "
                    f"{metrics['total_ambiguities']} ambiguïtés, "
                    f"quality_score={metrics['quality_score']:.2f}"
                )
                
                analysis_result = _convert_langchain_analysis_to_legacy_format(
                    structured_analysis
                )
                
                state["results"]["structured_requirements_analysis"] = structured_analysis.model_dump()
                state["results"]["analysis_metrics"] = metrics
                
            except Exception as e:
                logger.warning(f"⚠️ Échec chaîne LangChain, fallback vers méthode legacy: {e}")
                analysis_result = await _legacy_analyze_requirements(state, analysis_context)
        else:
            analysis_result = await _legacy_analyze_requirements(state, analysis_context)
        
        if not state["results"]:
            state["results"] = {}
            
        state["results"]["requirements_analysis"] = analysis_result
        
        if analysis_result.get("refined_files_to_modify"):
            task.files_to_modify = analysis_result["refined_files_to_modify"]
        
        if analysis_result.get("refined_complexity"):
            task.estimated_complexity = analysis_result["refined_complexity"]
        
        implementation_plan = analysis_result.get("implementation_plan", {})
        estimated_effort = analysis_result.get("estimated_effort", "Unknown")
        risk_level = analysis_result.get("risk_level", "Medium")
        
        logger.info("✅ Analyse requirements terminée",
                   estimated_effort=estimated_effort,
                   risk_level=risk_level,
                   files_count=len(analysis_result.get("refined_files_to_modify", [])),
                   steps_count=len(implementation_plan.get("steps", [])))
        
        state["results"]["analysis_summary"] = {
            "complexity_score": analysis_result.get("complexity_score", 5),
            "estimated_duration_minutes": analysis_result.get("estimated_duration_minutes", 30),
            "requires_external_deps": analysis_result.get("requires_external_deps", False),
            "breaking_changes_risk": analysis_result.get("breaking_changes_risk", False),
            "test_strategy": analysis_result.get("test_strategy", "unit"),
            "implementation_approach": analysis_result.get("implementation_approach", "standard")
        }
        
        return state
        
    except Exception as e:
        error_msg = f"Exception lors de l'analyse des requirements: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["error"] = error_msg
        return state


def _create_analysis_prompt(context: Dict[str, Any]) -> str:
    """Crée un prompt détaillé pour l'analyse des requirements."""
    
    prompt = f"""
# 🔍 ANALYSE DÉTAILLÉE DES REQUIREMENTS - AI-Agent

Tu es un expert en analyse de requirements pour le développement logiciel automatisé.
Analyse en profondeur cette tâche et génère un plan d'implémentation structuré.

## 📋 INFORMATIONS DE LA TÂCHE

**Titre**: {context['task_title']}
**Type**: {context['task_type']}
**Priorité**: {context['priority']}

**Description**: 
{context['description']}

**Critères d'acceptation**:
{context.get('acceptance_criteria', 'Non spécifiés')}

**Contexte technique**:
{context.get('technical_context', 'Non spécifié')}

**Fichiers suggérés à modifier**:
{context.get('files_to_modify', 'Non spécifiés')}

**Complexité estimée initiale**: {context.get('estimated_complexity', 'Non évaluée')}

**Repository**: {context['repository_url']}

## 🎯 TÂCHES D'ANALYSE REQUISES

Fournis une analyse structurée au format JSON avec les clés suivantes :

```json
{{
    "summary": "Résumé en 2-3 phrases de ce qui doit être fait",
    "complexity_analysis": {{
        "complexity_score": "Nombre de 1 à 10",
        "complexity_factors": ["Liste des facteurs de complexité"],
        "technical_challenges": ["Défis techniques identifiés"]
    }},
    "implementation_plan": {{
        "approach": "Approche d'implémentation recommandée",
        "steps": [
            {{
                "step": 1,
                "description": "Description de l'étape",
                "estimated_time_minutes": 15,
                "dependencies": ["Dépendances de cette étape"],
                "deliverables": ["Livrables de cette étape"]
            }}
        ]
    }},
    "files_analysis": {{
        "refined_files_to_modify": ["Liste affinée des fichiers à modifier"],
        "new_files_to_create": ["Nouveaux fichiers à créer"],
        "files_to_test": ["Fichiers nécessitant des tests spécifiques"]
    }},
    "requirements_breakdown": {{
        "functional_requirements": ["Requirements fonctionnels"],
        "non_functional_requirements": ["Requirements non-fonctionnels"],
        "acceptance_criteria_refined": ["Critères d'acceptation détaillés"]
    }},
    "risk_assessment": {{
        "risk_level": "Low/Medium/High",
        "potential_risks": ["Risques identifiés"],
        "mitigation_strategies": ["Stratégies d'atténuation"]
    }},
    "testing_strategy": {{
        "test_types_needed": ["unit", "integration", "e2e"],
        "test_scenarios": ["Scénarios de test clés"],
        "edge_cases": ["Cas limites à tester"]
    }},
    "external_dependencies": {{
        "requires_external_deps": false,
        "new_packages_needed": ["Nouveaux packages requis"],
        "api_integrations": ["Intégrations API nécessaires"]
    }},
    "estimated_effort": {{
        "estimated_duration_minutes": 45,
        "confidence_level": "High/Medium/Low",
        "effort_breakdown": {{
            "analysis": 10,
            "implementation": 25,
            "testing": 10,
            "debugging": 5,
            "documentation": 5
        }}
    }},
    "success_criteria": {{
        "definition_of_done": ["Critères de fin de tâche"],
        "quality_gates": ["Seuils de qualité à respecter"],
        "acceptance_tests": ["Tests d'acceptation à valider"]
    }}
}}
```

## 🚨 INSTRUCTIONS CRITIQUES - FORMAT DE RÉPONSE

**OBLIGATOIRE**: Tu DOIS répondre avec UNIQUEMENT le JSON structuré ci-dessus.

**FORMAT EXACT REQUIS**:
```json
{{
    "summary": "...",
    "complexity_analysis": {{ ... }},
    "implementation_plan": {{ ... }}
}}
```

**INTERDIT**:
- ❌ PAS de texte avant ou après le JSON
- ❌ PAS d'explications narratives
- ❌ PAS de markdown sauf le bloc ```json
- ❌ PAS de commentaires dans le JSON

**OBLIGATOIRE**:
- ✅ Commence directement par ```json
- ✅ Termine directement après ```
- ✅ JSON valide et complet
- ✅ Toutes les clés requises présentes

Si tu ne peux pas analyser correctement, retourne quand même le JSON avec des valeurs par défaut.

RAPPEL: Cette réponse sera parsée automatiquement - SEUL LE JSON SERA LU.
"""
    
    return prompt


def _parse_analysis_response(response_content: str) -> Dict[str, Any]:
    """Parse et valide la réponse d'analyse IA avec gestion intelligente code/JSON."""
    
    import json
    import re
    
    try:
        logger.info(f"🔍 Parsing réponse IA: {response_content[:200]}...")
        
        if _is_code_response(response_content):
            logger.info("🔍 Détection: Réponse contient du code - Extraction intelligente")
            return _extract_analysis_from_code_response(response_content)
        
        json_str = None
        
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',  # ```json { ... } ```
            r'```javascript\s*(\{.*?\})\s*```',  # ```javascript { ... } ```
            r'```js\s*(\{.*?\})\s*```',  # ```js { ... } ```
            r'```\s*(\{.*?\})\s*```',  # ``` { ... } ```
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, response_content, re.DOTALL)
            if match:
                json_str = match.group(1)
                logger.info(f"✅ JSON trouvé avec pattern: {pattern[:20]}...")
                break
        
        if not json_str:
            json_pattern = r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}'
            json_match = re.search(json_pattern, response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                logger.info("✅ JSON trouvé par regex directe (pattern amélioré)")
            else:
                first_brace = response_content.find('{')
                last_brace = response_content.rfind('}')
                
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = response_content[first_brace:last_brace + 1]
                    logger.info("✅ JSON extrait entre première et dernière accolades")
                else:
                    logger.warning("⚠️ Aucun JSON détecté - Génération analyse par défaut depuis le texte")
                    logger.info(f"📝 Texte de réponse pour analyse: {response_content[:200]}...")
                    return _generate_analysis_from_text(response_content)
        
        json_str = json_str.strip()
        logger.info(f"🧹 Nettoyage JSON: {json_str[:100]}...")
        
        json_str = re.sub(r'//.*?\n', '\n', json_str)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        json_str = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', json_str)  # Clés
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)   # Valeurs
        
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        json_str = re.sub(r'\n\s*', ' ', json_str)
        
        json_str = re.sub(r'(\w+)(\s*:)', r'"\1"\2', json_str)
        
        logger.info(f"✅ JSON nettoyé: {json_str[:100]}...")
        
        try:
            analysis_result = json.loads(json_str)
            logger.info("✅ JSON parsé avec succès")
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Erreur JSON parsing: {e}")
            logger.info("🔧 Tentative réparation du JSON...")
            try:
                json_str = _repair_json(json_str)
                analysis_result = json.loads(json_str)
                logger.info("✅ JSON réparé et parsé avec succès")
            except Exception as repair_error:
                logger.error(f"❌ Impossible de réparer le JSON: {repair_error}")
                logger.error(f"JSON problématique: {json_str[:500]}...")
                return _get_default_analysis_with_error(f"JSON invalide: {str(e)}")
        
        default_analysis = {
            "summary": "Analyse en cours...",
            "complexity_score": 5,
            "estimated_duration_minutes": 30,
            "risk_level": "Medium",
            "refined_files_to_modify": [],
            "implementation_plan": {"steps": []},
            "requires_external_deps": False,
            "breaking_changes_risk": False,
            "test_strategy": "unit",
            "implementation_approach": "standard"
        }
        
        for key, default_value in default_analysis.items():
            if key not in analysis_result:
                analysis_result[key] = default_value
        
        if "complexity_analysis" in analysis_result:
            analysis_result["complexity_score"] = analysis_result["complexity_analysis"].get("complexity_score", 5)
        
        if "estimated_effort" in analysis_result:
            analysis_result["estimated_duration_minutes"] = analysis_result["estimated_effort"].get("estimated_duration_minutes", 30)
        
        if "risk_assessment" in analysis_result:
            analysis_result["risk_level"] = analysis_result["risk_assessment"].get("risk_level", "Medium")
        
        if "files_analysis" in analysis_result:
            analysis_result["refined_files_to_modify"] = analysis_result["files_analysis"].get("refined_files_to_modify", [])
        
        if "external_dependencies" in analysis_result:
            analysis_result["requires_external_deps"] = analysis_result["external_dependencies"].get("requires_external_deps", False)
        
        return analysis_result
        
    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON analyse: {e}")
        if 'json_str' in locals():
            logger.error(f"JSON problématique (premiers 500 chars): {json_str[:500]}")
            logger.error(f"Erreur à la position {e.pos}: caractère '{json_str[e.pos:e.pos+10] if e.pos < len(json_str) else 'fin'}'")
            
            try:
                repaired_json = _advanced_json_repair(json_str)
                logger.info("Tentative de réparation JSON avancée...")
                analysis_result = json.loads(repaired_json)
                logger.info("✅ Réparation JSON réussie!")
                
                default_analysis = {
                    "summary": "Analyse en cours...",
                    "complexity_score": 5,
                    "estimated_duration_minutes": 30,
                    "risk_level": "Medium",
                    "refined_files_to_modify": [],
                    "implementation_plan": {"steps": []},
                    "requires_external_deps": False,
                    "breaking_changes_risk": False,
                    "test_strategy": "unit",
                    "implementation_approach": "standard"
                }
                
                for key, default_value in default_analysis.items():
                    if key not in analysis_result:
                        analysis_result[key] = default_value
                        
                return analysis_result
                
            except Exception as repair_error:
                logger.error(f"Échec réparation JSON avancée: {repair_error}")
        else:
            logger.error("Variable json_str non disponible pour debug")
            
        return _get_default_analysis_with_error(f"Erreur parsing JSON: {str(e)}", response_content)
        
    except Exception as e:
        logger.error(f"Erreur inattendue parsing analyse: {e}")
        return _get_default_analysis_with_error(f"Erreur inattendue: {str(e)}", response_content, "High")


def _repair_json(json_str: str) -> str:
    """Tentative de réparation automatique d'un JSON malformé."""
    import re
    
    json_str = re.sub(r'//.*?\n', '', json_str)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    json_str = re.sub(r'(?<!")(\w+)(?!"):', r'"\1":', json_str)
    
    json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
    
    json_str = re.sub(r':\s*true\b', ': true', json_str)
    json_str = re.sub(r':\s*false\b', ': false', json_str)
    json_str = re.sub(r':\s*null\b', ': null', json_str)
    
    return json_str


def _advanced_json_repair(json_str: str) -> str:
    """Réparation JSON avancée avec détection d'erreurs spécifiques."""
    import re
    logger.info("🔧 Début réparation JSON avancée...")
    
    json_str = re.sub(r'^```json\s*', '', json_str)
    json_str = re.sub(r'\s*```$', '', json_str)
         
    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
    
    json_str = re.sub(r'(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)
    
    json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
    
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    
    json_str = re.sub(r':\s*True\b', ': true', json_str)
    json_str = re.sub(r':\s*False\b', ': false', json_str)
    json_str = re.sub(r':\s*None\b', ': null', json_str)
    
    json_str = re.sub(r'//.*?\n', '\n', json_str)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    json_str = re.sub(r'#.*?\n', '\n', json_str)
    
    json_str = re.sub(r'\s+', ' ', json_str)
    json_str = json_str.strip()
    
    logger.info(f"🔧 JSON après réparation (premiers 200 chars): {json_str[:200]}")
    
    return json_str


def _is_code_response(response: str) -> bool:
    """Détecte si la réponse contient principalement du code plutôt que du JSON."""
    code_indicators = [
        'def ', 'function ', 'class ', 'import ', 'from ',
        'const ', 'let ', 'var ', 'if __name__',
        '```python', '```javascript', '```js', '```typescript'
    ]
    
    json_indicators = [
        '"summary":', '"complexity_score":', '"implementation_plan":',
        '"estimated_duration":', '"risk_level":'
    ]
    
    code_score = sum(1 for indicator in code_indicators if indicator in response)
    json_score = sum(1 for indicator in json_indicators if indicator in response)
    
    return code_score > json_score


def _extract_analysis_from_code_response(response: str) -> Dict[str, Any]:
    """Extrait une analyse intelligente d'une réponse contenant du code."""
    import re
    
    logger.info("🧠 Analyse intelligente de la réponse code")
    
    complexity_score = _estimate_complexity_from_code(response)
    
    files_mentioned = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*\.(py|js|ts|jsx|tsx|html|css))', response)
    refined_files = list(set([f[0] for f in files_mentioned]))
    
    has_imports = bool(re.search(r'(import|require|from)\s+[\'"][^\'"]+[\'"]', response))
    
    lines_count = len([line for line in response.split('\n') if line.strip() and not line.strip().startswith('#')])
    estimated_duration = max(30, min(180, lines_count * 2))
    
    return {
        "summary": f"Analyse basée sur le code généré ({lines_count} lignes de code détectées)",
        "complexity_score": complexity_score,
        "estimated_duration_minutes": estimated_duration,
        "risk_level": "Low" if complexity_score <= 3 else "Medium" if complexity_score <= 7 else "High",
        "refined_files_to_modify": refined_files,
        "implementation_plan": {
            "steps": [
                "Créer les fichiers de base identifiés",
                "Implémenter la logique principale",
                "Ajouter la gestion d'erreurs",
                "Écrire les tests correspondants"
            ]
        },
        "requires_external_deps": has_imports,
        "breaking_changes_risk": False,
        "test_strategy": "unit",
        "implementation_approach": "code-first",
        "code_analysis": {
            "lines_detected": lines_count,
            "files_mentioned": refined_files,
            "has_external_deps": has_imports,
            "generated_from_code": True
        }
    }


def _estimate_complexity_from_code(code: str) -> int:
    """Estime la complexité basée sur le code généré."""
    complexity_indicators = {
        'class ': 2, 'def ': 1, 'if ': 1, 'for ': 1, 'while ': 1,
        'try:': 2, 'except': 2, 'async ': 2, 'await ': 1,
        'import ': 0.5, 'from ': 0.5
    }
    
    score = 0
    for indicator, weight in complexity_indicators.items():
        count = code.count(indicator)
        score += count * weight
    
    return min(10, max(1, int(score / 3)))  


def _generate_analysis_from_text(response: str) -> Dict[str, Any]:
    """Génère une analyse basée sur le texte de réponse avec extraction intelligente."""
    import re
    
    logger.info("🤖 Génération d'analyse intelligente depuis le texte narratif")
    
    word_count = len(response.split())
    
    steps = _extract_steps_from_text(response)
    logger.info(f"📋 {len(steps)} étapes extraites du texte")
    
    files_pattern = r'([a-zA-Z_][a-zA-Z0-9_/]*\.(py|js|ts|jsx|tsx|html|css|json|md|txt))'
    files_found = list(set(re.findall(files_pattern, response)))
    refined_files = [f[0] for f in files_found]
    logger.info(f"📂 {len(refined_files)} fichiers détectés: {refined_files[:3]}")
    
    complexity_keywords = ['complex', 'difficult', 'challenge', 'multiple', 'integration', 'advanced', 
                          'complexe', 'difficile', 'défi', 'plusieurs', 'intégration', 'avancé', 
                          'sophisticated', 'intricate', 'compliqué']
    simple_keywords = ['simple', 'basic', 'easy', 'straightforward', 'quick', 'facile', 'basique', 'rapide',
                      'simple', 'direct', 'léger', 'minimal']
    
    complexity_mentions = sum(1 for keyword in complexity_keywords if keyword.lower() in response.lower())
    simple_mentions = sum(1 for keyword in simple_keywords if keyword.lower() in response.lower())
    
    if simple_mentions > complexity_mentions * 2:
        complexity_score = 2
        estimated_duration = 20
        risk_level = "Low"
    elif simple_mentions > complexity_mentions:
        complexity_score = 3
        estimated_duration = 30
        risk_level = "Low"
    elif complexity_mentions > simple_mentions * 2:
        complexity_score = 8
        estimated_duration = 120
        risk_level = "High"
    elif complexity_mentions > simple_mentions:
        complexity_score = 7
        estimated_duration = 90
        risk_level = "Medium"
    else:
        complexity_score = 5
        estimated_duration = 60
        risk_level = "Medium"
    
    if len(refined_files) > 0:
        estimated_duration += len(refined_files) * 10  
    
    summary = _extract_summary_from_text(response)
    
    return {
        "summary": summary,
        "complexity_score": complexity_score,
        "estimated_duration_minutes": estimated_duration,
        "risk_level": risk_level,
        "refined_files_to_modify": refined_files,
        "implementation_plan": {
            "steps": steps,
            "approach": "text-derived"
        },
        "requires_external_deps": 'install' in response.lower() or 'dependency' in response.lower() or 'dépendance' in response.lower(),
        "breaking_changes_risk": 'breaking' in response.lower() or 'incompatible' in response.lower(),
        "test_strategy": "unit",
        "implementation_approach": "text-analysis",
        "text_analysis": {
            "word_count": word_count,
            "complexity_indicators": complexity_mentions,
            "simplicity_indicators": simple_mentions,
            "files_detected": len(refined_files),
            "steps_extracted": len(steps),
            "generated_from_text": True
        }
    }


def _extract_steps_from_text(text: str) -> list:
    """Extrait les étapes depuis un texte non structuré."""
    import re
    
    steps = []
    
    numbered_patterns = [
        r'(?:^|\n)\s*(\d+)[\.\)]\s+([^\n]+)',  
        r'(?:^|\n)\s*Étape\s+(\d+)\s*:\s*([^\n]+)',  
        r'(?:^|\n)\s*Step\s+(\d+)\s*:\s*([^\n]+)',  
    ]
    
    for pattern in numbered_patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
        if matches:
            steps = [match[1].strip() if isinstance(match, tuple) else match.strip() for match in matches]
            break
    
    if not steps:
        bullet_patterns = [
            r'(?:^|\n)\s*[-•*]\s+([^\n]+)',  
        ]
        
        for pattern in bullet_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            if matches and len(matches) >= 2:  
                steps = [match.strip() for match in matches[:10]]  
                break
    
    if not steps:
        steps = [
            "Analyser les exigences de la tâche",
            "Concevoir l'architecture et le plan",
            "Implémenter les changements nécessaires",
            "Tester et valider l'implémentation",
            "Finaliser et documenter"
        ]
    
    return steps


def _extract_summary_from_text(text: str) -> str:
    """Extrait un résumé intelligent depuis le texte."""
    sentences = text.split('.')
    meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
    
    if meaningful_sentences:
        summary = '. '.join(meaningful_sentences[:2]) + '.'
        if len(summary) > 200:
            summary = summary[:197] + '...'
        return summary
    else:
        return f"Analyse basée sur le texte ({len(text.split())} mots)"


def _get_default_analysis_with_error(error_msg: str, raw_response: str = "", risk_level: str = "Medium") -> Dict[str, Any]:
    """Retourne une analyse par défaut en cas d'erreur de parsing."""
    return {
        "error": error_msg,
        "raw_response": raw_response[:500] if raw_response else "",     
        "summary": "Analyse non disponible en raison d'une erreur de parsing",
        "complexity_score": 5,
        "estimated_duration_minutes": 30,
        "risk_level": risk_level,
        "refined_files_to_modify": [],
        "implementation_plan": {"steps": []},
        "requires_external_deps": False,
        "breaking_changes_risk": False,
        "test_strategy": "unit",
        "implementation_approach": "standard"
    }


def _convert_langchain_analysis_to_legacy_format(structured_analysis) -> Dict[str, Any]:
    """
    Convertit l'analyse LangChain structurée vers le format legacy.
    
    Args:
        structured_analysis: Instance de RequirementsAnalysis (Pydantic)
        
    Returns:
        Dictionnaire au format legacy compatible avec l'ancien code
    """
    refined_files = [f.path for f in structured_analysis.candidate_files]
    
    implementation_steps = []
    if structured_analysis.candidate_files:
        for i, file in enumerate(structured_analysis.candidate_files, 1):
            implementation_steps.append(
                f"{i}. {file.action.capitalize()} {file.path}: {file.reason}"
            )
    
    complexity_mapping = {
        "trivial": 2,
        "simple": 3,
        "moderate": 5,
        "complex": 7,
        "very_complex": 9
    }
    
    risk_mapping = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "critical": "Critical"
    }
    
    overall_risk = "Low"
    if structured_analysis.risks:
        risk_levels = [r.level.value for r in structured_analysis.risks]
        if "critical" in risk_levels:
            overall_risk = "Critical"
        elif "high" in risk_levels:
            overall_risk = "High"
        elif "medium" in risk_levels:
            overall_risk = "Medium"
    
    return {
        "summary": structured_analysis.task_summary,
        "complexity_score": structured_analysis.complexity_score,
        "complexity_level": structured_analysis.complexity.value,
        "estimated_duration_minutes": structured_analysis.estimated_duration_minutes,
        "risk_level": overall_risk,
        "refined_files_to_modify": refined_files,
        "refined_complexity": complexity_mapping.get(
            structured_analysis.complexity.value, 
            structured_analysis.complexity_score
        ),
        "implementation_plan": {
            "steps": implementation_steps,
            "approach": structured_analysis.implementation_approach
        },
        "requires_external_deps": structured_analysis.requires_external_deps,
        "breaking_changes_risk": structured_analysis.breaking_changes_risk,
        "test_strategy": structured_analysis.test_strategy,
        "implementation_approach": structured_analysis.implementation_approach,
        "estimated_effort": f"{structured_analysis.estimated_duration_minutes} minutes",
        "dependencies": [d.model_dump() for d in structured_analysis.dependencies],
        "risks": [r.model_dump() for r in structured_analysis.risks],
        "ambiguities": [a.model_dump() for a in structured_analysis.ambiguities],
        "missing_info": structured_analysis.missing_info,
        "quality_score": structured_analysis.quality_score
    }


async def _legacy_analyze_requirements(state: GraphState, analysis_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Méthode legacy d'analyse des requirements (fallback).
    Encapsule l'ancien code pour permettre un fallback gracieux.
    
    Args:
        state: État du graphe
        analysis_context: Contexte de l'analyse
        
    Returns:
        Résultat de l'analyse au format legacy
    """
    logger.info("📜 Utilisation de la méthode legacy d'analyse...")
    
    analysis_prompt = _create_analysis_prompt(analysis_context)
    
    analysis_context["workflow_id"] = state.get("workflow_id", "unknown")
    analysis_context["task_id"] = state["task"].task_id
    
    ai_request = AIRequest(
        prompt=analysis_prompt,
        task_type=TaskType.ANALYSIS,
        context=analysis_context
    )
    
    response = await ai_hub.analyze_requirements(ai_request)
    
    if not response.success:
        error_msg = f"Erreur lors de l'analyse des requirements: {response.error}"
        logger.error(error_msg)
        return _get_default_analysis_with_error(error_msg)
    
    analysis_result = _parse_analysis_response(response.content)
    
    return analysis_result 