#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour le système de logging automatique des interactions agent.

Usage:
    python scripts/test_agent_logging.py
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le projet au PATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.evaluation.agent_output_logger import AgentOutputLogger


def test_manual_logging():
    """Test de logging manuel d'interactions."""
    
    print("=" * 80)
    print("🧪 TEST 1: Logging Manuel d'Interactions")
    print("=" * 80)
    
    logger = AgentOutputLogger()
    
    # Simuler quelques interactions
    test_interactions = [
        {
            "monday_update_id": "updateMday001",
            "monday_item_id": "12345678",
            "input_text": "Analyse le fichier main.py et explique sa structure",
            "agent_output": "Le fichier main.py contient l'API FastAPI principale avec 5 endpoints : /health, /process, /status, /evaluation/run, /evaluation/report. Il initialise l'agent VyData avec LangGraph.",
            "interaction_type": "analysis",
            "duration_seconds": 2.3,
            "success": True,
            "repository_url": "https://github.com/user/repo"
        },
        {
            "monday_update_id": "updateMday002",
            "monday_item_id": "12345679",
            "input_text": "Crée un formulaire de login avec validation",
            "agent_output": "PR #123 créée avec succès sur la branche feat/login-form. Fichiers: LoginForm.tsx, validation.ts, LoginForm.test.tsx",
            "interaction_type": "pr",
            "duration_seconds": 5.8,
            "success": True,
            "repository_url": "https://github.com/user/repo",
            "branch_name": "feat/login-form",
            "pr_number": "123",
            "pr_url": "https://github.com/user/repo/pull/123"
        },
        {
            "monday_update_id": "updateMday003",
            "monday_item_id": "12345680",
            "input_text": "Analyse les erreurs dans le système",
            "agent_output": "Error: Unable to analyze - repository not accessible",
            "interaction_type": "analysis",
            "duration_seconds": 1.2,
            "success": False,
            "error_message": "Repository not accessible",
            "repository_url": "https://github.com/user/private-repo"
        }
    ]
    
    # Logger chaque interaction
    for i, interaction in enumerate(test_interactions, 1):
        print(f"\n📝 Logging interaction {i}/{len(test_interactions)}...")
        
        interaction_id = logger.log_agent_interaction(**interaction)
        
        status = "✅" if interaction['success'] else "❌"
        print(f"{status} Interaction loggée: {interaction_id}")
        print(f"   Type: {interaction['interaction_type']}")
        print(f"   Input: {interaction['input_text'][:50]}...")
        print(f"   Success: {interaction['success']}")
    
    print(f"\n{'=' * 80}")
    print("✅ Test 1 complété!\n")


def test_retrieve_interactions():
    """Test de récupération des interactions."""
    
    print("=" * 80)
    print("🧪 TEST 2: Récupération des Interactions")
    print("=" * 80)
    
    logger = AgentOutputLogger()
    
    # Récupérer toutes les interactions
    print("\n📊 Toutes les interactions:")
    df_all = logger.get_interactions()
    print(f"   Total: {len(df_all)} interactions loggées")
    
    # Récupérer seulement les analyses réussies
    print("\n📊 Analyses réussies uniquement:")
    df_analysis = logger.get_interactions(
        interaction_type="analysis",
        success_only=True
    )
    print(f"   Total: {len(df_analysis)} analyses réussies")
    
    if not df_analysis.empty:
        print("\n   Dernières analyses:")
        for _, row in df_analysis.tail(3).iterrows():
            print(f"   • [{row['timestamp'][:16]}] {row['input_text'][:50]}...")
    
    # Récupérer les PRs
    print("\n📊 Pull Requests:")
    df_pr = logger.get_interactions(interaction_type="pr")
    print(f"   Total: {len(df_pr)} PRs")
    
    if not df_pr.empty:
        for _, row in df_pr.iterrows():
            status = "✅" if row['success'] else "❌"
            print(f"   {status} PR #{row['pr_number']} - {row['input_text'][:40]}...")
    
    print(f"\n{'=' * 80}")
    print("✅ Test 2 complété!\n")


def test_calculate_metrics():
    """Test de calcul des métriques."""
    
    print("=" * 80)
    print("🧪 TEST 3: Calcul des Métriques")
    print("=" * 80)
    
    logger = AgentOutputLogger()
    
    # Calculer métriques du jour
    print("\n📊 Calcul des métriques quotidiennes...")
    
    metrics = logger.calculate_performance_metrics(save_to_metrics=True)
    
    print(f"\n📈 MÉTRIQUES {metrics['metric_date']}:")
    print(f"   • Total interactions: {metrics['total_interactions']}")
    print(f"   • Analyses: {metrics['interactions_analysis']}")
    print(f"   • PRs: {metrics['interactions_pr']}")
    print(f"   • Succès: {metrics['success_count']}/{metrics['total_interactions']}")
    print(f"   • Taux de succès: {metrics['success_rate_percent']}%")
    print(f"   • Durée moyenne: {metrics['avg_duration_seconds']}s")
    print(f"   • Statut: {metrics['reliability_status'].upper()}")
    print(f"   • Notes: {metrics['notes']}")
    
    print(f"\n✅ Métriques sauvegardées dans performance_metrics.csv")
    
    print(f"\n{'=' * 80}")
    print("✅ Test 3 complété!\n")


def test_statistics_summary():
    """Test de génération des statistiques."""
    
    print("=" * 80)
    print("🧪 TEST 4: Statistiques Globales")
    print("=" * 80)
    
    logger = AgentOutputLogger()
    
    # Statistiques 7 derniers jours
    print("\n📊 Génération des statistiques (7 derniers jours)...")
    
    stats = logger.get_statistics_summary(days=7)
    
    if "message" in stats or "error" in stats:
        print(f"\n⚠️ {stats.get('message', stats.get('error'))}")
    else:
        print(f"\n📈 STATISTIQUES {stats['start_date']} → {stats['end_date']}:")
        print(f"   • Total interactions: {stats['total_interactions']}")
        print(f"   • Analyses: {stats['interactions_analysis']}")
        print(f"   • PRs: {stats['interactions_pr']}")
        print(f"   • Taux de succès: {stats['success_rate']}%")
        print(f"   • Durée moyenne: {stats['avg_duration_seconds']}s")
        print(f"   • Durée totale: {stats['total_duration_hours']}h")
    
    print(f"\n{'=' * 80}")
    print("✅ Test 4 complété!\n")


def test_export_excel():
    """Test d'export vers Excel."""
    
    print("=" * 80)
    print("🧪 TEST 5: Export vers Excel")
    print("=" * 80)
    
    logger = AgentOutputLogger()
    
    print("\n📤 Export des interactions vers Excel...")
    
    try:
        excel_file = logger.export_to_excel()
        print(f"✅ Fichier Excel créé: {excel_file}")
        print(f"   Vous pouvez l'ouvrir pour voir toutes les interactions formatées")
    except Exception as e:
        print(f"❌ Erreur export: {e}")
    
    print(f"\n{'=' * 80}")
    print("✅ Test 5 complété!\n")


def main():
    """Exécute tous les tests."""
    
    print("\n" + "=" * 80)
    print("🚀 TESTS DU SYSTÈME DE LOGGING AGENT")
    print("=" * 80 + "\n")
    
    try:
        # Test 1: Logging manuel
        test_manual_logging()
        
        # Test 2: Récupération
        test_retrieve_interactions()
        
        # Test 3: Calcul métriques
        test_calculate_metrics()
        
        # Test 4: Statistiques
        test_statistics_summary()
        
        # Test 5: Export Excel
        test_export_excel()
        
        # Résumé final
        print("=" * 80)
        print("🎉 TOUS LES TESTS COMPLÉTÉS AVEC SUCCÈS!")
        print("=" * 80)
        print("\n📋 Fichiers générés:")
        print("   • data/golden_datasets/agent_interactions_log.csv")
        print("   • data/golden_datasets/performance_metrics.csv")
        print("   • data/golden_datasets/agent_interactions_export.xlsx")
        print("\n💡 Vous pouvez maintenant:")
        print("   1. Ouvrir les CSV dans Excel pour voir les données")
        print("   2. Intégrer le wrapper dans votre agent")
        print("   3. Suivre les métriques quotidiennes")
        print("\n📖 Documentation: docs/AGENT_OUTPUT_LOGGING.md\n")
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

