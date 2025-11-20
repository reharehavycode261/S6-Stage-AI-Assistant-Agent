#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Indexation du Golden Dataset avec le système RAG Multilingue.

Ce script indexe tous les golden examples dans le vector store avec:
- Embeddings vectoriels
- Détection automatique de langue
- Support multilingue complet
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.golden_dataset_rag_extension import golden_dataset_rag_extension
from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from utils.logger import get_logger

logger = get_logger(__name__)


async def main():
    """Fonction principale d'indexation."""
    print("\n" + "="*80)
    print("📚 INDEXATION DU GOLDEN DATASET AVEC RAG MULTILINGUE")
    print("="*80)
    print()
    
    try:
        # 1. Charger le golden dataset
        print("📂 Étape 1: Chargement du Golden Dataset...")
        print("-" * 80)
        
        manager = GoldenDatasetManager()
        df = manager.load_golden_sets()
        
        print(f"✅ {len(df)} golden examples chargés")
        print(f"   Colonnes: {list(df.columns)}")
        
        # Afficher aperçu
        print(f"\n📋 Aperçu des données:")
        print(df.head(3).to_string())
        
        # 2. Indexation avec RAG
        print("\n\n🤖 Étape 2: Indexation avec Embeddings...")
        print("-" * 80)
        print("⏳ Cette opération peut prendre quelques minutes...")
        print("   • Génération d'embeddings via OpenAI")
        print("   • Détection automatique de langue")
        print("   • Stockage dans PostgreSQL (pgvector)")
        print()
        
        stats = await golden_dataset_rag_extension.index_golden_dataset(
            dataset_df=df,
            force_reindex=False  # Demander confirmation si déjà indexé
        )
        
        # 3. Afficher les statistiques
        print("\n\n📊 Étape 3: Statistiques d'Indexation")
        print("-" * 80)
        print(f"✅ Total de lignes traitées: {stats['total_rows']}")
        print(f"✅ Examples indexés avec succès: {stats['indexed_count']}")
        print(f"❌ Erreurs: {stats['errors_count']}")
        
        print(f"\n🌍 Langues détectées:")
        for lang, count in stats['languages_detected'].items():
            print(f"   • {lang}: {count} examples")
        
        if stats['errors']:
            print(f"\n⚠️  Erreurs rencontrées:")
            for error in stats['errors'][:5]:
                print(f"   • {error}")
        
        # 4. Test de recherche sémantique
        print("\n\n🔍 Étape 4: Test de Recherche Sémantique")
        print("-" * 80)
        
        test_queries = [
            "Comment fonctionne le système de validation ?",
            "How to fix a 404 error?",
            "¿Cómo crear un formulario de login?",
            "Wie funktioniert das Caching?"
        ]
        
        for query in test_queries:
            print(f"\n📝 Requête: '{query}'")
            print("   Recherche des examples similaires...")
            
            similar = await golden_dataset_rag_extension.find_similar_golden_examples(
                query=query,
                top_k=2,
                match_threshold=0.5
            )
            
            if similar:
                print(f"   ✅ {len(similar)} examples trouvés:")
                for i, ex in enumerate(similar, 1):
                    print(f"      {i}. Similarité: {ex['similarity_score']:.2f} | Langue: {ex['language']}")
                    print(f"         Input: {ex['input_reference'][:80]}...")
            else:
                print("   ❌ Aucun example similaire trouvé")
        
        # 5. Statistiques finales
        print("\n\n📈 Étape 5: Statistiques Finales du Vector Store")
        print("-" * 80)
        
        final_stats = await golden_dataset_rag_extension.get_golden_dataset_statistics()
        
        print("📊 Vector Store:")
        print(f"   • Total contextes indexés: {final_stats['vector_store']['total_indexed_contexts']}")
        print(f"   • Langues supportées: {final_stats['vector_store']['languages_count']}")
        
        print("\n📊 Évaluation Classique:")
        classic = final_stats['classic_evaluation']
        if classic.get('total_evaluations', 0) > 0:
            print(f"   • Total évaluations: {classic['total_evaluations']}")
            print(f"   • Taux de réussite: {classic['pass_rate']}%")
            print(f"   • Score moyen: {classic['avg_score']}/100")
        else:
            print("   • Aucune évaluation disponible")
        
        # 6. Résumé final
        print("\n\n" + "="*80)
        print("🎉 INDEXATION TERMINÉE AVEC SUCCÈS !")
        print("="*80)
        print()
        print("✅ Capacités activées:")
        print("   • Recherche sémantique multilingue dans golden examples")
        print("   • Détection automatique de langue")
        print("   • Évaluation enrichie avec contexte similaire")
        print("   • Support de toutes les langues (via embeddings)")
        print()
        print("📝 Prochaines étapes:")
        print("   1. Utiliser golden_dataset_rag_extension.find_similar_golden_examples()")
        print("   2. Enrichir l'évaluation avec evaluate_with_similarity_context()")
        print("   3. Comparer les méthodes avec compare_evaluation_methods()")
        print()
        print("🚀 Le système est prêt pour l'évaluation multilingue !")
        print()
        
        return 0
        
    except FileNotFoundError as e:
        print(f"\n❌ Erreur: Fichier Golden Dataset introuvable")
        print(f"   {e}")
        print(f"\n💡 Solution: Vérifiez que le fichier existe:")
        print(f"   data/golden_datasets/golden_sets.csv")
        return 1
        
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

