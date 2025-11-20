# Chaînes LangChain - Intégration incrémentale

Ce dossier contient les chaînes LangChain pour structurer et valider les appels LLM dans le projet AI-Agent.

## Objectif
Adopter LangChain de manière **incrémentale et ciblée** pour:
- ✅ Génération structurée (Pydantic) des plans et analyses
- ✅ Validation automatique des sorties LLM
- ✅ Fallback multi-provider natif
- ✅ Tracing automatique vers LangSmith
- ✅ Éliminer le parsing fragile et les réparations JSON manuelles

## Étapes d'intégration

### ✅ Étape 1 - Plan d'implémentation structuré (COMPLÉTÉ)

**Fichiers créés:**
- `ai/chains/implementation_plan_chain.py` - Chaîne LCEL pour génération de plans
- `tests/test_implementation_plan_chain.py` - Tests unitaires

**Fichiers modifiés:**
- `nodes/implement_node.py` - Intégration avec fallback vers méthode legacy

**Bénéfices:**
- Plan d'implémentation validé par Pydantic (fini les JSON cassés)
- Métriques automatiques extraites (complexité, risques, fichiers à modifier)
- Fallback automatique Anthropic → OpenAI
- Compatibilité totale avec l'exécution existante

**Modèle de données:**
```python
class ImplementationPlan(BaseModel):
    task_summary: str
    architecture_approach: str
    steps: List[ImplementationStep]  # min 1 étape
    total_estimated_complexity: int
    overall_risk_assessment: str
    recommended_testing_strategy: str
    potential_blockers: List[str]
```

**Utilisation:**
```python
from ai.chains.implementation_plan_chain import generate_implementation_plan

# Génération avec fallback automatique
plan = await generate_implementation_plan(
    task_title="Créer API REST",
    task_description="Endpoints CRUD pour utilisateurs",
    task_type="feature",
    provider="anthropic",
    fallback_to_openai=True
)

# Extraction de métriques
from ai.chains.implementation_plan_chain import extract_plan_metrics
metrics = extract_plan_metrics(plan)
# {"total_steps": 5, "total_complexity": 25, "high_risk_steps_count": 1, ...}
```

**Stockage dans l'état:**
```python
state["results"]["implementation_plan_structured"]  # Dict Pydantic complet
state["results"]["implementation_plan_metrics"]     # Métriques extraites
```

### 🔄 Étape 2 - Analyse requirements structurée (À VENIR)

**Objectif:**
Remplacer l'analyse des requirements dans `analyze_node.py` par une chaîne LangChain avec validation Pydantic stricte.

**Bénéfices attendus:**
- Éliminer `_repair_json()` et autres fonctions de correction
- Catégorisation stricte des requirements (fonctionnel, technique, sécurité, etc.)
- Validation des dépendances et fichiers candidats
- Détection automatique de requirements ambigus ou incomplets

### 🔄 Étape 3 - Classification d'erreurs (À VENIR)

**Objectif:**
Créer une chaîne de classification des erreurs avant correction dans `debug_node.py`.

**Bénéfices attendus:**
- Regroupement intelligent des erreurs similaires
- Scoring de priorités (test failures > static issues)
- Réduction >20% des appels de correction redondants

### 🔄 Étape 4 - Fallback multi-provider centralisé (À VENIR)

**Objectif:**
Centraliser la gestion des providers LLM via une factory LangChain.

**Bénéfices attendus:**
- `with_fallback([provider1, provider2])` natif
- Ajouter un nouveau provider = 1 ligne de config
- Métriques unifiées de tous les appels LLM

### 🔄 Étape 5 - Mémoire et cache (OPTIONNEL)

**Objectif:**
Ajouter mémoire de session par nœud et cache de réponses.

**Bénéfices attendus:**
- Cache réduit appels identiques >30%
- Mémoire locale pour itérations complexes

## Architecture

```
ai/
├── __init__.py
└── chains/
    ├── __init__.py
    ├── README.md                        # Ce fichier
    ├── implementation_plan_chain.py     # ✅ Étape 1
    ├── analysis_chain.py                # 🔄 Étape 2 (à créer)
    ├── error_classification_chain.py    # 🔄 Étape 3 (à créer)
    └── llm_factory.py                   # 🔄 Étape 4 (à créer)
```

## Principe de fallback

Toutes les chaînes doivent inclure un fallback vers la méthode legacy:

```python
try:
    # Tentative avec LangChain
    result = await langchain_function()
except Exception as e:
    logger.warning(f"LangChain failed: {e}, using legacy method")
    result = legacy_function()
```

Cela garantit **zéro régression** pendant la migration.

## Dépendances

```txt
langchain==0.2.16
langchain-core==0.2.38
langchain-anthropic==0.1.23
langchain-openai==0.1.23
langgraph==0.2.14
```

## Configuration

Les chaînes utilisent automatiquement les clés API depuis `config/settings.py`:
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `LANGCHAIN_TRACING_V2=true` (optionnel, pour LangSmith)
- `LANGCHAIN_API_KEY` (optionnel, pour LangSmith)

## Tests

Chaque chaîne doit avoir son fichier de tests:
```bash
pytest tests/test_implementation_plan_chain.py -v
pytest tests/test_analysis_chain.py -v           # À créer
pytest tests/test_error_classification_chain.py -v # À créer
```

## Métriques de succès

| Étape | Critère de succès | État |
|-------|------------------|------|
| 1 | Plan retourne dict Pydantic valide + métriques | ✅ |
| 2 | Analyse requirements sans `_repair_json` | 🔄 |
| 3 | Regroupement réduit >20% appels redondants | 🔄 |
| 4 | Fallback Anthropic→OpenAI sans erreur métier | 🔄 |
| 5 | Cache réduit appels identiques >30% | 🔄 |

## Principe: Zones préservées

❌ **Ne PAS utiliser LangChain pour:**
- Exécution de commandes système
- Modifications de fichiers (utiliser `ClaudeCodeTool`)
- Opérations Git (utiliser `GitHubTool`)
- Tests et Celery/RabbitMQ

✅ **Utiliser LangChain pour:**
- Génération structurée (plans, analyses, classifications)
- Validation Pydantic
- Orchestration simple prompt → LLM → parser
- Fallback multi-provider
- Tracing LangSmith

## Notes de migration

**Problème d'architecture venv:**
Si vous rencontrez `ImportError: ... (have 'x86_64', need 'arm64')`, recréez le venv:
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Import paresseux:**
Les chaînes sont importées à la demande dans les nœuds pour éviter de charger LangChain au démarrage si non utilisé.

## Contact & Support

Pour questions sur l'intégration LangChain:
- Voir `docs/SETUP_GUIDE.md`
- Consulter les tests unitaires pour exemples d'usage

