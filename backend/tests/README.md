# Tests du Projet AI-Agent

## 📁 Structure des tests

### `workflow/` - Tests fonctionnels
- `test_workflow.py` - **Test principal du workflow LangGraph**
  - Teste la structure du graphe
  - Teste l'exécution du workflow avec des données simulées
  - Valide la navigation entre les nœuds
- `test_rabbitmq_integration.py` - Test d'intégration RabbitMQ

### `scripts/` - Scripts de correction (archives)
- Scripts temporaires utilisés pour corriger les erreurs LangGraph
- **Peuvent être supprimés** une fois le projet stabilisé
- Conservés pour référence historique

## 🚀 Comment exécuter les tests

```bash
# Test du workflow LangGraph
python tests/workflow/test_workflow.py

# Test d'intégration RabbitMQ
python tests/workflow/test_rabbitmq_integration.py
```

## 📊 Résultats des tests

### ✅ Workflow LangGraph
- Structure du graphe : ✅ 8 nœuds, 8 connexions
- Exécution : ✅ Workflow démarre et s'exécute
- Navigation : ✅ Nœuds s'exécutent dans l'ordre
- Gestion d'erreurs : ✅ Erreurs capturées et loggées

### ⚠️ Problèmes connus
- Erreur Git (attendu - repository de test)
- Erreur `'error_logs'` (mineur - à corriger)
