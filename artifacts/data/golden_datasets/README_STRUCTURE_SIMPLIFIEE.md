# 📋 Golden Dataset - Structure Simplifiée

## 🎯 Vue d'ensemble

Le Golden Dataset a été **simplifié** pour ne contenir que **2 colonnes essentielles**. Cette simplification facilite la maintenance et la compréhension du système d'évaluation.

---

## 📊 Structure du fichier `golden_sets.csv`

### **Colonnes (seulement 2)**

| Colonne | Description | Exemple |
|---------|-------------|---------|
| `input_reference` | La question ou commande de test à envoyer au système | "Analyse le fichier main.py" |
| `output_reference` | La réponse parfaite attendue OU instruction d'évaluation pour le LLM-as-judge | "Le fichier main.py contient une API FastAPI avec..." |

---

## 🔄 Workflow d'évaluation

```
┌─────────────────────────────────────────────────────┐
│  1. Charger le Golden Dataset (input_reference)     │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  2. Envoyer input_reference au système              │
│     → Le système génère agent_output                │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  3. LLM-as-judge compare:                           │
│     • agent_output (réponse générée)                │
│     • output_reference (réponse attendue)           │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  4. LLM-as-judge génère:                            │
│     • Score /100                                    │
│     • Reasoning (justification)                     │
│     • Passed (true/false)                           │
└─────────────────────────────────────────────────────┘
```

---

## 📁 Fichiers du système

### 1. **`golden_sets.csv`** - Dataset de référence

**Format:**
```csv
input_reference,output_reference
"Analyse le fichier main.py","Le fichier main.py contient une API FastAPI avec 5 endpoints principaux..."
"hello","Bonjour ! 👋 Je suis VyData, votre assistant IA de développement..."
"Crée un formulaire de login","PR créée avec succès sur la branche feat/login-form..."
```

**Nombre de tests actuels:** 16

---

### 2. **`evaluation_results.csv`** - Résultats d'évaluation

**Format:**
```csv
timestamp,input_reference,output_reference,agent_output,llm_score,llm_reasoning,passed,duration_seconds
2025-11-10T14:30:00,Analyse main.py,"Fichier attendu...","Fichier généré...",85.0,"Excellente analyse...",true,2.5
```

**Colonnes:**
- `timestamp`: Date et heure de l'évaluation (ISO 8601)
- `input_reference`: Input du test
- `output_reference`: Output attendu
- `agent_output`: Réponse générée par l'agent
- `llm_score`: Score attribué par le LLM-as-judge (0-100)
- `llm_reasoning`: Justification du score
- `passed`: Test réussi (true/false, seuil par défaut: 70)
- `duration_seconds`: Durée d'exécution

---

## 🚀 Utilisation

### **Charger le Golden Dataset**

```python
from services.evaluation.golden_dataset_manager import GoldenDatasetManager

# Initialiser le gestionnaire
manager = GoldenDatasetManager()

# Charger tous les tests
df_tests = manager.load_golden_sets()

# Afficher
print(f"📊 {len(df_tests)} tests chargés")
print(df_tests.head())
```

### **Récupérer un test par index**

```python
# Récupérer le test à l'index 0
test = manager.get_test_by_index(0)

print(f"Input: {test['input_reference']}")
print(f"Output attendu: {test['output_reference']}")
```

### **Sauvegarder un résultat d'évaluation**

```python
from datetime import datetime

result = {
    "timestamp": datetime.now().isoformat(),
    "input_reference": "Analyse le fichier main.py",
    "output_reference": "Le fichier main.py contient...",
    "agent_output": "Réponse générée par l'agent...",
    "llm_score": 85.0,
    "llm_reasoning": "Excellente analyse, très complète...",
    "passed": True,
    "duration_seconds": 2.5
}

manager.save_evaluation_result(result)
```

### **Récupérer les statistiques**

```python
# Statistiques globales
stats = manager.get_statistics_summary()

print(f"Total évaluations: {stats['total_evaluations']}")
print(f"Taux de réussite: {stats['pass_rate']}%")
print(f"Score moyen: {stats['avg_score']}/100")
```

---

## ✅ Avantages de la structure simplifiée

1. **Simplicité** : Seulement 2 colonnes au lieu de 8
2. **Clarté** : Facile à comprendre et maintenir
3. **Flexibilité** : `output_reference` peut être une réponse attendue OU une instruction d'évaluation
4. **Efficacité** : Moins de métadonnées inutiles
5. **Focus** : Se concentre sur l'essentiel (input → output)

---

## 📝 Exemple complet de test

### Test dans `golden_sets.csv`:

```csv
input_reference,output_reference
"Analyse le fichier main.py","Le fichier main.py contient une API FastAPI avec 5 endpoints principaux: /health, /process, /status, /evaluation/run, /evaluation/report. Il utilise un agent VyData pour traiter les requêtes, intègre Monday.com et GitHub, et gère un workflow asynchrone avec LangGraph."
```

### Résultat dans `evaluation_results.csv`:

```csv
timestamp,input_reference,output_reference,agent_output,llm_score,llm_reasoning,passed,duration_seconds
2025-11-10T14:30:00,"Analyse le fichier main.py","Le fichier main.py contient...","L'agent a répondu: Le fichier main.py...",85.0,"L'analyse est très complète et précise. Tous les endpoints sont identifiés correctement.",true,2.5
```

---

## 🔧 Migration depuis l'ancien format

Un backup de l'ancien fichier a été créé automatiquement:
- **Backup**: `golden_sets_old_backup.csv` (8 colonnes)
- **Nouveau**: `golden_sets.csv` (2 colonnes)

Les anciennes colonnes supprimées:
- `test_id` (remplacé par l'index de ligne)
- `test_type` (non nécessaire)
- `expected_output_type` (non nécessaire)
- `evaluation_criteria` (géré par le LLM-as-judge)
- `priority` (non nécessaire)
- `active` (tous les tests sont actifs par défaut)

---

## 📞 Support

Pour toute question sur la nouvelle structure, référez-vous à:
- **Modèles**: `/models/evaluation_models.py`
- **Gestionnaire**: `/services/evaluation/golden_dataset_manager.py`
- **Documentation complète**: `/docs/GOLDEN_DATASET_EXPLICATION.md`

