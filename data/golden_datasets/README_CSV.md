# 📊 Guide d'utilisation des fichiers CSV pour Golden Datasets

## 📁 Fichiers créés

Trois fichiers CSV ont été créés dans ce dossier :

### 1. `golden_sets.csv` - Tests de référence (Golden Set)
**Colonnes :**
- `test_id` : Identifiant unique du test (ex: GS_A001, GS_P001)
- `test_type` : Type de test (`analysis` ou `pr`)
- `input_monday_update` : L'input qui déclenche l'agent (simulation d'un update Monday)
- `expected_output` : Le résultat attendu de l'agent
- `expected_output_type` : Type de sortie (`resultats_analyses` ou `pr`)
- `evaluation_criteria` : Critères d'évaluation séparés par `;`
- `priority` : Priorité du test (`high`, `medium`, `low`)
- `active` : Test actif ou non (`TRUE` ou `FALSE`)

**📝 Contenu actuel : 16 tests**
- 10 tests d'analyse (GS_A001 à GS_A010)
- 6 tests de PR (GS_P001 à GS_P006)

---

### 2. `evaluation_results.csv` - Résultats d'évaluation
**Colonnes :**
- `eval_id` : ID unique de l'évaluation (format: EVAL_YYYYMMDD_HHMMSS)
- `timestamp` : Date et heure de l'évaluation (ISO 8601)
- `test_id` : Référence au test du Golden Set
- `monday_update_id` : ID de l'update Monday qui a déclenché l'agent
- `agent_output` : La réponse générée par l'agent
- `llm_score` : Score attribué par le LLM judge (0-100)
- `llm_reasoning` : Justification du score LLM
- `human_validation_status` : Statut validation humaine (`validated`, `pending`, `rejected`, `to_review`)
- `human_score` : Score donné par l'humain (0-100, NULL si pas validé)
- `human_feedback` : Commentaire de l'humain
- `final_score` : Score final (moyenne pondérée LLM 60% + Human 40%)
- `status` : `PASS` (≥70) ou `FAIL` (<70)
- `duration_seconds` : Durée d'exécution de l'agent
- `error_message` : Message d'erreur (NULL si pas d'erreur)

**📝 Contenu actuel : 15 évaluations exemple**

---

### 3. `performance_metrics.csv` - Métriques de performance
**Colonnes :**
- `metric_date` : Date de la métrique (YYYY-MM-DD)
- `total_tests_run` : Nombre total de tests exécutés
- `tests_analysis` : Nombre de tests d'analyse
- `tests_pr` : Nombre de tests PR
- `pass_rate_percent` : Taux de réussite en %
- `avg_llm_score` : Score moyen du LLM judge
- `avg_human_score` : Score moyen des validations humaines
- `avg_final_score` : Score final moyen
- `avg_duration_s` : Durée moyenne d'exécution en secondes
- `tests_pending_validation` : Nombre de tests en attente de validation
- `reliability_status` : Statut (`excellent` ≥85, `good` ≥70, `needs_improvement` <70)
- `notes` : Notes et commentaires

**📝 Contenu actuel : 15 jours de métriques (23-06 octobre 2025)**

---

## 🚀 Utilisation dans Excel

### Option 1 : Import manuel (recommandé pour visualisation)

1. **Ouvrir Excel** et créer un nouveau classeur

2. **Importer chaque CSV dans une feuille séparée :**
   
   **Pour Excel (Windows/Mac) :**
   - Onglet "Données" → "Obtenir des données" → "À partir d'un fichier" → "CSV"
   - Sélectionner `golden_sets.csv`
   - Cliquer sur "Charger"
   - Renommer la feuille en `Golden_Sets`
   - Répéter pour `evaluation_results.csv` → feuille `Evaluation_Results`
   - Répéter pour `performance_metrics.csv` → feuille `Performance_Metrics`

3. **Sauvegarder le classeur** : `golden_datasets.xlsx`

### Option 2 : Conversion automatique avec Python

Si vous avez Python et pandas installés :

```bash
# Depuis la racine du projet
python scripts/csv_to_excel.py
```

Cela créera automatiquement `golden_datasets.xlsx` avec les 3 feuilles.

---

## 📊 Structure Excel finale

```
golden_datasets.xlsx
├── Feuille 1: Golden_Sets (16 tests de référence)
├── Feuille 2: Evaluation_Results (15 évaluations)
└── Feuille 3: Performance_Metrics (15 jours de métriques)
```

---

## ✏️ Modification des données

### Ajouter un nouveau test (Golden_Sets)

1. Ouvrir `golden_sets.csv` (ou la feuille Excel)
2. Ajouter une nouvelle ligne :
   ```csv
   GS_A011,analysis,Nouvelle question test,Réponse attendue,resultats_analyses,accuracy;completeness,high,TRUE
   ```
3. Sauvegarder

### Enregistrer une nouvelle évaluation (Evaluation_Results)

Le code Python se charge d'ajouter automatiquement les résultats via :
```python
from services.evaluation.excel_golden_dataset_service import ExcelGoldenDatasetService

service = ExcelGoldenDatasetService()
service.save_evaluation_result({
    "eval_id": "EVAL_20251107_100000",
    "timestamp": "2025-11-07T10:00:00",
    "test_id": "GS_A001",
    # ... autres champs
})
```

---

## 🎯 Critères d'évaluation disponibles

- `accuracy` : Exactitude de la réponse
- `completeness` : Complétude (tous les aspects traités)
- `clarity` : Clarté et structure
- `data_quality` : Qualité des données/code
- `code_quality` : Qualité du code (pour les PRs)
- `actionability` : Caractère actionnable

**Format dans le CSV :** Séparer par des points-virgules `;`
```
accuracy;completeness;clarity;data_quality;actionability
```

---

## 📈 Interprétation des scores

| Score | Statut | Signification |
|-------|--------|---------------|
| 90-100 | Excellent | Répond à tous les critères |
| 80-89 | Bon | Quelques problèmes mineurs |
| 70-79 | Adéquat | Manques notables |
| 50-69 | Pauvre | Erreurs ou données manquantes |
| 0-49 | Très pauvre | Ne répond pas correctement |

**Seuil de réussite par défaut : 70/100**

---

## 🔄 Workflow complet

```
1. Update Monday déclenche l'agent
        ↓
2. Agent génère une réponse (agent_output)
        ↓
3. LLM Judge évalue vs expected_output → llm_score
        ↓
4. Validation humaine (optionnelle) → human_score
        ↓
5. Calcul final_score (60% LLM + 40% Human)
        ↓
6. Enregistrement dans Evaluation_Results
        ↓
7. Mise à jour des Performance_Metrics quotidiennes
```

---

## 🛠️ Dépendances Python

Pour utiliser le script de conversion :

```bash
pip install pandas openpyxl
```

---

## 📞 Support

Pour toute question sur l'utilisation de ces fichiers CSV, consulter :
- `services/evaluation/excel_golden_dataset_service.py` : Service de gestion Excel
- `services/evaluation/llm_excel_evaluator.py` : Évaluateur LLM
- `services/evaluation/excel_evaluation_orchestrator.py` : Orchestrateur

---

## ✅ Checklist d'utilisation

- [ ] Fichiers CSV créés dans `data/golden_datasets/`
- [ ] Import dans Excel réussi (3 feuilles)
- [ ] Tests Golden Set ajoutés/modifiés selon vos besoins
- [ ] Script Python testé (optionnel)
- [ ] Workflow d'évaluation compris
- [ ] Prêt à lancer les évaluations !

**Bon courage avec l'évaluation de votre agent ! 🚀**











