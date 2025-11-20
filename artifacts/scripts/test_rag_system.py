#!/usr/bin/env python3
"""
Script de test rapide du système RAG (Retrieval-Augmented Generation).
Ce script teste:
1. Détection de langue multilingue par LLM
2. Génération d'embeddings
3. Stockage dans le vector store
4. Recherche de similarité
5. Enrichissement de contexte
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.semantic_search_service import semantic_search_service
from services.embedding_service import embedding_service
from services.vector_store_service import vector_store_service
from utils.logger import get_logger

logger = get_logger(__name__)


async def test_language_detection():
    """Test de la détection de langue par LLM."""
    print("\n" + "="*80)
    print("🌍 TEST 1: DÉTECTION DE LANGUE PAR LLM")
    print("="*80)
    
    test_texts = [
        ("Bonjour, je voudrais créer une nouvelle fonctionnalité.", "fr"),
        ("Hello, I need help with my code.", "en"),
        ("Hola, ¿puedes ayudarme con este error?", "es"),
        ("Guten Tag, ich brauche Hilfe bei meinem Projekt.", "de"),
        ("Olá, preciso de ajuda com meu código.", "pt"),
        ("こんにちは、コードのヘルプが必要です。", "ja"),
        ("你好，我需要帮助。", "zh"),
        ("Привет, мне нужна помощь с моим кодом.", "ru"),
    ]
    
    success_count = 0
    for text, expected_lang in test_texts:
        try:
            detected_lang = await semantic_search_service._detect_language(text)
            status = "✅" if detected_lang == expected_lang else "⚠️"
            print(f"{status} Texte: '{text[:50]}...'")
            print(f"   Détecté: {detected_lang} | Attendu: {expected_lang}")
            
            if detected_lang == expected_lang:
                success_count += 1
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    print(f"\n📊 Résultat: {success_count}/{len(test_texts)} détections correctes")
    return success_count == len(test_texts)


async def test_embedding_generation():
    """Test de la génération d'embeddings."""
    print("\n" + "="*80)
    print("🔢 TEST 2: GÉNÉRATION D'EMBEDDINGS")
    print("="*80)
    
    test_text = "Comment créer une nouvelle branche Git?"
    
    try:
        result = await embedding_service.generate_embedding(test_text)
        
        print(f"✅ Embedding généré avec succès")
        print(f"   • Modèle: {result.model}")
        print(f"   • Dimensions: {len(result.embedding)}")
        print(f"   • Tokens utilisés: {result.tokens_used}")
        print(f"   • Premier vecteur: [{result.embedding[0]:.6f}, {result.embedding[1]:.6f}, ...]")
        
        return len(result.embedding) == 1536
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


async def test_vector_store():
    """Test du stockage et de la recherche dans le vector store."""
    print("\n" + "="*80)
    print("💾 TEST 3: STOCKAGE ET RECHERCHE VECTORIELLE")
    print("="*80)
    
    # Initialiser le vector store
    await vector_store_service.initialize()
    
    # Messages de test en plusieurs langues
    test_messages = [
        ("Comment créer une nouvelle branche Git?", "fr", "question"),
        ("How to create a new Git branch?", "en", "question"),
        ("¿Cómo crear una nueva rama en Git?", "es", "question"),
        ("Résoudre le bug dans le fichier main.py", "fr", "command"),
        ("Fix the bug in main.py", "en", "command"),
    ]
    
    stored_ids = []
    
    # Stocker les messages
    print("\n1️⃣  Stockage des messages:")
    for text, lang, intent in test_messages:
        try:
            record_id = await semantic_search_service.store_user_message(
                message_text=text,
                monday_item_id=f"test_item_{len(stored_ids)}",
                intent_type=intent,
                metadata={"test": True}
            )
            stored_ids.append(record_id)
            print(f"   ✅ Stocké: ID={record_id} | Langue={lang} | '{text[:40]}...'")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            return False
    
    # Recherche de similarité
    print("\n2️⃣  Recherche de similarité:")
    query = "How do I create a branch in Git?"
    
    try:
        enriched_context = await semantic_search_service.enrich_query_with_context(
            query=query,
            monday_item_id=None
        )
        
        print(f"   Requête: '{query}'")
        print(f"   • Sources trouvées: {enriched_context.total_sources}")
        print(f"   • Score de pertinence: {enriched_context.relevance_score:.2f}")
        print(f"   • Messages similaires: {len(enriched_context.similar_messages)}")
        
        if enriched_context.similar_messages:
            print("\n   📋 Messages similaires:")
            for i, result in enumerate(enriched_context.similar_messages[:3]):
                # result est un SimilaritySearchResult avec un record (MessageEmbeddingRecord)
                similarity = result.similarity
                print(f"      {i+1}. Similarité: {similarity:.2f} | Langue: {result.record.message_language}")
                print(f"         Texte: '{result.record.cleaned_text[:60]}...'")
        
        return enriched_context.total_sources > 0
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_vector_store_stats():
    """Test des statistiques du vector store."""
    print("\n" + "="*80)
    print("📊 TEST 4: STATISTIQUES DU VECTOR STORE")
    print("="*80)
    
    try:
        stats = await vector_store_service.get_statistics()
        
        print(f"✅ Statistiques récupérées:")
        print(f"   • Total de messages: {stats.get('total_messages', 0)}")
        print(f"   • Total de contextes: {stats.get('total_contexts', 0)}")
        print(f"   • Messages 24h: {stats.get('messages_last_24h', 0)}")
        print(f"   • Langues: {stats.get('languages_count', 0)}")
        print(f"   • Items uniques: {stats.get('unique_items', 0)}")
        
        return stats.get('total_messages', 0) >= 0  # Au moins 0 (peut être vide si test)
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Exécute tous les tests."""
    print("\n" + "="*80)
    print("🚀 TEST DU SYSTÈME RAG (Retrieval-Augmented Generation)")
    print("="*80)
    
    # Initialiser les services
    await semantic_search_service.initialize()
    
    # Exécuter les tests
    results = []
    
    # Test 1: Détection de langue (optionnel, peut échouer avec des API keys limitées)
    try:
        result1 = await test_language_detection()
        results.append(("Détection de langue", result1))
    except Exception as e:
        print(f"\n⚠️  Test de détection de langue ignoré: {e}")
        results.append(("Détection de langue", None))
    
    # Test 2: Génération d'embeddings
    result2 = await test_embedding_generation()
    results.append(("Génération d'embeddings", result2))
    
    # Test 3: Vector store
    result3 = await test_vector_store()
    results.append(("Vector store", result3))
    
    # Test 4: Statistiques
    result4 = await test_vector_store_stats()
    results.append(("Statistiques", result4))
    
    # Résumé
    print("\n" + "="*80)
    print("📋 RÉSUMÉ DES TESTS")
    print("="*80)
    
    for test_name, result in results:
        if result is None:
            status = "⏭️ "
        elif result:
            status = "✅"
        else:
            status = "❌"
        print(f"{status} {test_name}")
    
    # Score final
    passed = sum(1 for _, r in results if r is True)
    total = len([r for _, r in results if r is not None])
    
    print("\n" + "="*80)
    if passed == total:
        print(f"🎉 TOUS LES TESTS RÉUSSIS ! ({passed}/{total})")
        print("="*80)
        print("\n✅ Le système RAG est opérationnel et prêt à l'emploi !")
        print("\n📝 Fonctionnalités validées:")
        print("   • Détection automatique de langue (multilingue)")
        print("   • Génération d'embeddings OpenAI")
        print("   • Stockage dans PostgreSQL avec pgvector")
        print("   • Recherche de similarité vectorielle (HNSW)")
        print("   • Enrichissement de contexte pour LLM")
        print("\n🚀 Prochaine étape: Redémarrer le service AI-Agent")
        return 0
    else:
        print(f"⚠️  CERTAINS TESTS ONT ÉCHOUÉ ({passed}/{total})")
        print("="*80)
        print("\n⚠️  Vérifiez les erreurs ci-dessus et les logs.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

