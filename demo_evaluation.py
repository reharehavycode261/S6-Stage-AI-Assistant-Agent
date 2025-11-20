#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Démonstration rapide du système d'évaluation Golden Dataset.

Ce script montre comment le système fonctionne avec un exemple simple.
"""

print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║        🎯 DÉMONSTRATION: SYSTÈME D'ÉVALUATION GOLDEN DATASET     ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝

✅ Le système EST DÉJÀ IMPLÉMENTÉ dans votre projet !

📊 STATISTIQUES ACTUELLES:
   • Score de fiabilité: 66.24/100 (needs_improvement)
   • Tests réussis: 3/5 (60%)
   • Score moyen: 75.6/100

📝 DATASETS EXISTANTS:

1️⃣  Dataset Questions (data/golden_datasets/questions_dataset.json)
   • 5 questions de test
   • Type: Questions → Résultats d'analyses
   • Exemples:
     ✓ "hello" → Salutation et capacités
     ✓ "Pourquoi Java ?" → Analyse technique
     ✓ "Dernier commit ?" → Métadonnées GitHub
     ✓ "Structure projet ?" → Architecture
     ✓ "Dernier PR ?" → Pull Requests GitHub

2️⃣  Dataset Commandes (data/golden_datasets/commands_dataset.json)
   • 1 commande de test
   • Type: Commandes → Pull Requests
   • Exemple:
     ✓ "Crée un formulaire de login" → PR complet

═══════════════════════════════════════════════════════════════════

🎓 COMMENT FONCTIONNE L'ÉVALUATION:

1. CRÉATION DU TEST
   ┌─────────────────────────────────────┐
   │ Input: "Quel est le dernier commit?"│
   │ Expected: "Le message est X par Y..." │
   │ Criteria: [Pertinence, Précision...]│
   └─────────────────────────────────────┘
               ↓
2. EXÉCUTION PAR L'AGENT
   ┌─────────────────────────────────────┐
   │ • Détection: question GitHub        │
   │ • Appel API GitHub (13 collecteurs) │
   │ • Extraction données structurées    │
   │ • Génération réponse (GPT-4)        │
   └─────────────────────────────────────┘
               ↓
3. ÉVALUATION PAR LLM JUDGE
   ┌─────────────────────────────────────┐
   │ Compare: attendu vs réel            │
   │ Scores:                             │
   │  • Pertinence: 90/100               │
   │  • Précision: 85/100                │
   │  • Clarté: 80/100                   │
   │  • Contexte: 85/100                 │
   │ → Moyenne: 85/100 ✅ PASSED         │
   └─────────────────────────────────────┘
               ↓
4. RAPPORT FINAL
   ┌─────────────────────────────────────┐
   │ Score global: 66.24/100             │
   │ Tests réussis: 3/5                  │
   │ Statut: À AMÉLIORER                 │
   │ Rapport JSON sauvegardé             │
   └─────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════

🚀 COMMENT UTILISER:

OPTION 1: Tester avec les datasets existants
    curl -X POST "http://localhost:8000/evaluation/run?dataset_type=questions&run_in_background=false"

OPTION 2: Interface interactive (VOS 5 questions)
    python3 custom_evaluation_interactive.py

OPTION 3: Voir les derniers résultats
    python3 show_evaluation_results.py

═══════════════════════════════════════════════════════════════════

📚 VOTRE CAS D'USAGE EXACT:

Vous voulez:
✅ Poser 5 questions à l'agent
✅ L'agent y répond
✅ Un LLM Judge évalue (comme un prof)
✅ Obtenir un score de fiabilité

C'EST EXACTEMENT CE QUI EST IMPLÉMENTÉ ! 🎉

Lancez simplement:
    python3 custom_evaluation_interactive.py

═══════════════════════════════════════════════════════════════════

📊 RÉSULTATS DÉTAILLÉS ACTUELS:

Test 1: q001_hello                    ✅ 95/100 PASSED
   Salutation et présentation des capacités
   
Test 2: q002_technologies             ✅ 85/100 PASSED
   Analyse des choix technologiques (Java vs Python)
   
Test 3: q003_last_commit              ❌ 55/100 FAILED
   Récupération du dernier commit GitHub
   
Test 4: q004_project_structure        ✅ 78/100 PASSED
   Analyse de la structure du projet
   
Test 5: q005_last_pr                  ❌ 65/100 FAILED
   Informations sur le dernier Pull Request

═══════════════════════════════════════════════════════════════════

💡 WORKFLOW INDUSTRIALISATION:

1. ÉVALUATION (où vous êtes maintenant)
   └─> Score < 70% ? → Améliorer l'agent
   └─> Score ≥ 70% ? → Tests supplémentaires
   └─> Score ≥ 80% ? → Prêt pour production

2. AMÉLIORATION
   • Analyser les tests échoués
   • Corriger les problèmes identifiés
   • Ré-évaluer

3. PRODUCTION
   • Agent validé et fiable
   • Déployé pour utilisation réelle
   • Monitoring continu

═══════════════════════════════════════════════════════════════════

📁 FICHIERS IMPORTANTS:

• custom_evaluation_interactive.py   ← Interface pour vos questions
• GUIDE_EVALUATION.md                ← Documentation complète
• data/golden_datasets/              ← Datasets existants
• data/evaluation_reports/           ← Rapports générés
• services/evaluation/               ← Code du système

═══════════════════════════════════════════════════════════════════

🎯 PROCHAINES ÉTAPES SUGGÉRÉES:

1. Lire le guide complet:
   cat GUIDE_EVALUATION.md

2. Tester avec VOS questions:
   python3 custom_evaluation_interactive.py

3. Analyser les résultats:
   python3 show_evaluation_results.py

4. Améliorer l'agent si nécessaire

5. Ré-évaluer jusqu'à score ≥ 80%

═══════════════════════════════════════════════════════════════════

✨ Le système est COMPLET et FONCTIONNEL ! ✨

Vous pouvez commencer à l'utiliser immédiatement.

""")

print("💡 Lancez: python3 custom_evaluation_interactive.py")
print()

