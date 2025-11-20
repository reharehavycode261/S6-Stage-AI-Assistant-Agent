#!/usr/bin/env python3
"""Test d'intégration rapide du système Golden Dataset + RAG Multilingue."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from services.evaluation.golden_dataset_rag_extension import golden_dataset_rag_extension
from services.evaluation.llm_judge_rag_enriched import LLMJudgeRAGEnriched


async def test_integration():
    """Test d'intégration complet."""
    print("\n" + "="*80)
    print("🧪 TEST D'INTÉGRATION: Golden Dataset + RAG Multilingue")
    print("="*80)
    
    try:
        # 1. Charger le golden dataset
        print("\n1️⃣  Chargement du Golden Dataset...")
        manager = GoldenDatasetManager()
        df = manager.load_golden_sets()
        print(f"   ✅ {len(df)} tests chargés")
        
        # 2. Initialiser le vector store
        print("\n2️⃣  Initialisation du Vector Store...")
        await golden_dataset_rag_extension.initialize()
        print(f"   ✅ Vector store initialisé")
        
        # 3. Vérifier si déjà indexé
        print("\n3️⃣  Vérification de l'indexation...")
        stats = await golden_dataset_rag_extension.get_golden_dataset_statistics()
        indexed_count = stats['vector_store']['total_indexed_contexts']
        
        if indexed_count > 0:
            print(f"   ✅ {indexed_count} examples déjà indexés")
        else:
            print(f"   ⚠️  Aucun example indexé")
            print(f"   💡 Exécutez: python scripts/index_golden_dataset_with_rag.py")
            return False
        
        # 4. Test de recherche sémantique
        print("\n4️⃣  Test de recherche sémantique...")
        test_query = "Comment fonctionne le système?"
        similar = await golden_dataset_rag_extension.find_similar_golden_examples(
            query=test_query,
            top_k=2
        )
        print(f"   Query: '{test_query}'")
        print(f"   ✅ {len(similar)} examples similaires trouvés")
        
        if similar:
            for i, ex in enumerate(similar[:2], 1):
                print(f"      {i}. Similarité: {ex['similarity_score']:.2f} | Langue: {ex['language']}")
        
        # 5. Test du LLM Judge enrichi RAG
        print("\n5️⃣  Test du LLM Judge enrichi RAG...")
        judge = LLMJudgeRAGEnriched(use_rag=True, rag_top_k=2)
        
        test = manager.get_test_by_index(0)
        result = await judge.evaluate_response_with_rag(
            reference_input=test['input_reference'],
            reference_output=test['output_reference'],
            agent_response=test['output_reference'],  # Simulation
            use_rag=True
        )
        
        print(f"   ✅ Évaluation terminée")
        print(f"      • Score: {result['score']}/100")
        print(f"      • RAG activé: {result['rag_enabled']}")
        print(f"      • Examples trouvés: {result['rag_similar_count']}")
        print(f"      • Langue: {result['rag_language_detected']}")
        
        # 6. Résumé
        print("\n" + "="*80)
        print("✅ TOUS LES TESTS D'INTÉGRATION RÉUSSIS !")
        print("="*80)
        print("\n📋 Système opérationnel:")
        print("   ✅ Golden Dataset Manager")
        print("   ✅ Extension RAG Multilingue")
        print("   ✅ Vector Store (pgvector)")
        print("   ✅ Recherche Sémantique")
        print("   ✅ LLM Judge enrichi RAG")
        print("\n🚀 Le système est prêt pour l'évaluation multilingue enrichie !")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)

