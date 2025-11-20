#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour afficher les statistiques du vector store.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vector_store_service import vector_store_service
from services.embedding_service import embedding_service
from utils.logger import get_logger

logger = get_logger(__name__)


async def main():
    """Affiche les statistiques du vector store."""
    try:
        await vector_store_service.initialize()
        
        print("="*80)
        print("📊 STATISTIQUES DU VECTOR STORE")
        print("="*80)
        
        # Statistiques du vector store
        stats = await vector_store_service.get_statistics()
        
        print("\n🗃️  BASE DE DONNÉES:")
        print(f"   • Total messages stockés: {stats.get('total_messages', 0)}")
        print(f"   • Total contextes projet: {stats.get('total_contexts', 0)}")
        print(f"   • Messages dernières 24h: {stats.get('messages_last_24h', 0)}")
        print(f"   • Langues détectées: {stats.get('languages_count', 0)}")
        print(f"   • Items Monday uniques: {stats.get('unique_items', 0)}")
        
        # Statistiques du cache d'embeddings
        cache_stats = embedding_service.get_cache_stats()
        
        print("\n💾 CACHE D'EMBEDDINGS:")
        print(f"   • Entrées totales: {cache_stats.get('total_entries', 0)}")
        print(f"   • Entrées valides: {cache_stats.get('valid_entries', 0)}")
        print(f"   • Entrées expirées: {cache_stats.get('expired_entries', 0)}")
        print(f"   • TTL: {cache_stats.get('ttl_hours', 0)} heures")
        print(f"   • Modèle: {cache_stats.get('model', 'N/A')}")
        print(f"   • Dimensions: {cache_stats.get('dimensions', 0)}")
        
        print("\n" + "="*80)
        
        await vector_store_service.close()
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

