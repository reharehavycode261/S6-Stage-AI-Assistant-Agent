#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test du système de scoring (LLM as Judge).
Teste avec les données réelles loggées.
"""

import sys
import asyncio
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.vydata_evaluator import VyDataEvaluator
from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from services.evaluation.agent_output_logger import AgentOutputLogger
import pandas as pd
from utils.logger import get_logger

logger = get_logger(__name__)


async def test_scoring_with_real_data():
    """Teste le scoring avec les données réelles de l'agent."""
    
    print("\n" + "="*80)
    print("🧪 TEST DU SYSTÈME DE SCORING (LLM AS JUDGE)")
    print("="*80)
    
    # 1. Charger les données réelles loggées
    print("\n📊 Étape 1: Chargement des interactions réelles...")
    output_logger = AgentOutputLogger()
    
    try:
        df = pd.read_csv('data/golden_datasets/agent_interactions_log.csv')
        # Prendre seulement les interactions de type "analysis" (pas les tests)
        real_interactions = df[
            (df['interaction_type'] == 'analysis') & 
            (df['monday_item_id'].astype(str).str.len() > 8)  # IDs réels Monday
        ]
        
        if len(real_interactions) == 0:
            print("⚠️ Aucune interaction réelle trouvée")
            return
        
        print(f"✅ {len(real_interactions)} interactions réelles trouvées")
        
    except Exception as e:
        print(f"❌ Erreur chargement interactions: {e}")
        return
    
    # 2. Charger le golden dataset
    print("\n📚 Étape 2: Chargement du golden dataset...")
    dataset_manager = GoldenDatasetManager()
    
    try:
        golden_df = pd.read_csv('data/golden_datasets/golden_sets.csv')
        print(f"✅ {len(golden_df)} tests dans le golden dataset")
    except Exception as e:
        print(f"❌ Erreur chargement golden dataset: {e}")
        return
    
    # 3. Initialiser l'évaluateur (avec fallback OpenAI si Anthropic échoue)
    print("\n🤖 Étape 3: Initialisation de l'évaluateur LLM...")
    
    evaluator = None
    try:
        # Essayer d'abord avec Anthropic
        evaluator = VyDataEvaluator(
            model_name="claude-3-5-sonnet-20241022",
            provider="anthropic"
        )
        print("✅ Évaluateur initialisé avec Anthropic")
    except Exception as e:
        print(f"⚠️ Anthropic échoué: {e}")
        print("🔄 Tentative avec OpenAI...")
        try:
            evaluator = VyDataEvaluator(
                model_name="gpt-4",
                provider="openai"
            )
            print("✅ Évaluateur initialisé avec OpenAI (fallback)")
        except Exception as e2:
            print(f"❌ OpenAI échoué aussi: {e2}")
            return
    
    # 4. Tester avec la dernière interaction réelle
    print("\n🎯 Étape 4: Test de scoring sur la dernière interaction...")
    
    last_interaction = real_interactions.iloc[-1]
    
    print(f"\n📝 INTERACTION À ÉVALUER:")
    print(f"   • ID: {last_interaction['interaction_id']}")
    print(f"   • Date: {last_interaction['timestamp']}")
    print(f"   • Input: {last_interaction['input_text'][:100]}...")
    print(f"   • Output: {str(last_interaction['agent_output'])[:150]}...")
    print(f"   • Durée: {last_interaction['duration_seconds']}s")
    
    # Chercher un golden set similaire (pour avoir un expected_output)
    # Pour ce test, on va utiliser un golden set générique d'analyse
    test_golden = golden_df[golden_df['test_type'] == 'analysis'].iloc[0]
    
    print(f"\n📚 GOLDEN SET DE RÉFÉRENCE (pour comparaison):")
    print(f"   • Test ID: {test_golden['test_id']}")
    print(f"   • Expected Output: {test_golden['expected_output'][:150]}...")
    
    # 5. Évaluer
    print(f"\n🔍 Étape 5: Évaluation avec LLM as Judge...")
    print(f"⏳ Patience, le LLM analyse la réponse...")
    
    try:
        evaluation_result = evaluator.evaluate_response(
            test_id=str(last_interaction['interaction_id']),
            reference_input=str(last_interaction['input_text']),
            reference_output=test_golden['expected_output'],  # Golden set de référence
            agent_response=str(last_interaction['agent_output']),
            monday_update_id=str(last_interaction['monday_update_id'])
        )
        
        print("\n" + "="*80)
        print("✅ RÉSULTAT DE L'ÉVALUATION")
        print("="*80)
        
        print(f"\n📊 SCORE GLOBAL: {evaluation_result['llm_score']}/100")
        
        if evaluation_result.get('criteria_scores'):
            print(f"\n📈 SCORES PAR CRITÈRE:")
            for criterion, score in evaluation_result['criteria_scores'].items():
                print(f"   • {criterion.capitalize()}: {score}/100")
        
        print(f"\n💭 RAISONNEMENT:")
        print(f"{evaluation_result['llm_reasoning']}")
        
        print(f"\n⏱️  DURÉE: {evaluation_result['duration_seconds']:.1f}s")
        
        # Déterminer le statut
        score = evaluation_result['llm_score']
        if score >= 90:
            status = "🟢 EXCELLENT"
        elif score >= 80:
            status = "🟡 BON"
        elif score >= 70:
            status = "🟠 ACCEPTABLE"
        else:
            status = "🔴 INSUFFISANT"
        
        print(f"\n🎯 STATUT: {status}")
        
        # 6. Sauvegarder le résultat
        print("\n💾 Étape 6: Sauvegarde du résultat...")
        
        try:
            dataset_manager.save_evaluation_result(
                test_id=str(last_interaction['interaction_id']),
                llm_score=evaluation_result['score'],
                llm_reasoning=evaluation_result['reasoning'],
                criteria_scores=evaluation_result.get('criteria_scores', {}),
                evaluation_duration=evaluation_result['duration_seconds']
            )
            print("✅ Résultat sauvegardé dans evaluation_results.csv")
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde: {e}")
        
        print("\n" + "="*80)
        print("✅ TEST TERMINÉ AVEC SUCCÈS")
        print("="*80)
        
        return evaluation_result
        
    except Exception as e:
        print(f"\n❌ ERREUR LORS DE L'ÉVALUATION: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_scoring_with_golden_set():
    """Teste le scoring avec un test du golden dataset."""
    
    print("\n" + "="*80)
    print("🧪 TEST AVEC UN CAS DU GOLDEN DATASET")
    print("="*80)
    
    # Charger le golden dataset
    try:
        golden_df = pd.read_csv('data/golden_datasets/golden_sets.csv')
        
        # Prendre le premier test d'analyse
        test = golden_df[golden_df['test_type'] == 'analysis'].iloc[0]
        
        print(f"\n📚 Test sélectionné:")
        print(f"   • ID: {test['test_id']}")
        print(f"   • Input: {test['input_monday_update']}")
        print(f"   • Expected: {test['expected_output'][:100]}...")
        
        # Simuler une réponse de l'agent (ici on utilise l'expected output avec une petite variation)
        agent_response = test['expected_output'] + " De plus, l'architecture suit les principes SOLID."
        
        print(f"\n🤖 Réponse de l'agent (simulée):")
        print(f"   {agent_response[:150]}...")
        
        # Initialiser l'évaluateur
        print("\n🔍 Évaluation...")
        
        try:
            evaluator = VyDataEvaluator(provider="openai", model_name="gpt-4")
        except:
            try:
                evaluator = VyDataEvaluator(provider="anthropic")
            except Exception as e:
                print(f"❌ Impossible d'initialiser l'évaluateur: {e}")
                return
        
        result = evaluator.evaluate_response(
            test_id=test['test_id'],
            reference_input=test['input_monday_update'],
            reference_output=test['expected_output'],
            agent_response=agent_response
        )
        
        print(f"\n✅ Score: {result['llm_score']}/100")
        print(f"\n💭 Raisonnement:")
        print(f"{result['llm_reasoning']}")
        
        if result.get('criteria_scores'):
            print(f"\n📊 Scores par critère:")
            for criterion, score in result['criteria_scores'].items():
                print(f"   • {criterion}: {score}/100")
        
        return result
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Point d'entrée principal."""
    
    print("\n🚀 DÉMARRAGE DES TESTS DE SCORING")
    
    # Test 1: Avec données réelles
    print("\n" + "="*80)
    print("TEST 1: SCORING SUR DONNÉES RÉELLES")
    print("="*80)
    
    result1 = await test_scoring_with_real_data()
    
    # Test 2: Avec golden dataset
    print("\n\n" + "="*80)
    print("TEST 2: SCORING SUR GOLDEN DATASET")
    print("="*80)
    
    result2 = await test_scoring_with_golden_set()
    
    print("\n\n" + "="*80)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*80)
    
    if result1:
        print(f"\n✅ Test 1 (Données réelles): Score = {result1['llm_score']}/100")
    else:
        print(f"\n❌ Test 1 (Données réelles): ÉCHEC")
    
    if result2:
        print(f"✅ Test 2 (Golden dataset): Score = {result2['llm_score']}/100")
    else:
        print(f"❌ Test 2 (Golden dataset): ÉCHEC")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())

