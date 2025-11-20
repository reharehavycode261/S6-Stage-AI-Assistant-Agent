#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'initialisation du vector store avec pgvector.

Ce script:
1. Applique la migration SQL pour créer l'extension pgvector
2. Crée les tables message_embeddings et project_context_embeddings
3. Crée les index HNSW pour la recherche rapide
4. Vérifie que tout est opérationnel
"""

import asyncio
import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def check_postgresql_connection():
    """Vérifie la connexion à PostgreSQL."""
    try:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password
        )
        await conn.close()
        logger.info("✅ Connexion PostgreSQL réussie")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
        return False


async def apply_migration():
    """Applique la migration SQL pour pgvector."""
    migration_file = Path(__file__).parent.parent / "migrations" / "add_pgvector_extension.sql"
    
    if not migration_file.exists():
        logger.error(f"❌ Fichier de migration non trouvé: {migration_file}")
        return False
    
    try:
        # Lire le fichier SQL
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Se connecter et exécuter
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password
        )
        
        logger.info("🔧 Application de la migration pgvector...")
        
        # Exécuter le script SQL complet
        await conn.execute(migration_sql)
        
        await conn.close()
        
        logger.info("✅ Migration pgvector appliquée avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur application migration: {e}")
        return False


async def verify_tables():
    """Vérifie que les tables ont été créées correctement."""
    try:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password
        )
        
        # Vérifier l'extension pgvector
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        
        if not result:
            logger.error("❌ Extension pgvector non installée")
            await conn.close()
            return False
        
        logger.info("✅ Extension pgvector installée")
        
        # Vérifier les tables
        tables_to_check = ['message_embeddings', 'project_context_embeddings']
        
        for table in tables_to_check:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                table
            )
            
            if not exists:
                logger.error(f"❌ Table '{table}' non trouvée")
                await conn.close()
                return False
            
            logger.info(f"✅ Table '{table}' créée")
        
        # Vérifier les index HNSW
        indexes = await conn.fetch(
            """
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE tablename IN ('message_embeddings', 'project_context_embeddings')
                AND indexname LIKE '%embedding%'
            """
        )
        
        logger.info(f"✅ Index créés: {len(indexes)}")
        for idx in indexes:
            logger.info(f"   • {idx['indexname']} sur {idx['tablename']}")
        
        # Compter les enregistrements
        message_count = await conn.fetchval("SELECT COUNT(*) FROM message_embeddings")
        context_count = await conn.fetchval("SELECT COUNT(*) FROM project_context_embeddings")
        
        logger.info(f"📊 Statistiques:")
        logger.info(f"   • Messages: {message_count}")
        logger.info(f"   • Contextes: {context_count}")
        
        await conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur vérification tables: {e}")
        return False


async def test_embedding_storage():
    """Teste le stockage d'un embedding de test."""
    try:
        from services.vector_store_service import vector_store_service
        
        await vector_store_service.initialize()
        
        # Créer un embedding de test
        test_embedding = [0.1] * 1536  # Vecteur de test
        
        record_id = await vector_store_service.store_message_embedding(
            message_text="Test message pour vérifier le vector store",
            embedding=test_embedding,
            message_language="fr",
            message_type="user_message",
            metadata={"test": True}
        )
        
        logger.info(f"✅ Test de stockage réussi (ID: {record_id})")
        
        await vector_store_service.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test de stockage: {e}")
        return False


async def main():
    """Fonction principale d'initialisation."""
    logger.info("="*80)
    logger.info("🚀 INITIALISATION DU VECTOR STORE (pgvector + RAG)")
    logger.info("="*80)
    
    # Étape 1: Vérifier la connexion
    logger.info("\n📋 Étape 1/5: Vérification de la connexion PostgreSQL")
    if not await check_postgresql_connection():
        logger.error("❌ Échec: Impossible de se connecter à PostgreSQL")
        return 1
    
    # Étape 2: Appliquer la migration
    logger.info("\n📋 Étape 2/5: Application de la migration pgvector")
    if not await apply_migration():
        logger.error("❌ Échec: Erreur lors de l'application de la migration")
        return 1
    
    # Étape 3: Vérifier les tables
    logger.info("\n📋 Étape 3/5: Vérification des tables et index")
    if not await verify_tables():
        logger.error("❌ Échec: Erreur lors de la vérification des tables")
        return 1
    
    # Étape 4: Tester le stockage
    logger.info("\n📋 Étape 4/5: Test du stockage d'embeddings")
    if not await test_embedding_storage():
        logger.error("❌ Échec: Erreur lors du test de stockage")
        return 1
    
    # Étape 5: Résumé
    logger.info("\n📋 Étape 5/5: Résumé de l'initialisation")
    logger.info("="*80)
    logger.info("✅ INITIALISATION TERMINÉE AVEC SUCCÈS")
    logger.info("="*80)
    logger.info("")
    logger.info("📝 Prochaines étapes:")
    logger.info("   1. Redémarrer le service AI-Agent")
    logger.info("   2. Les messages @vydata seront automatiquement stockés")
    logger.info("   3. La recherche sémantique multilingue est active")
    logger.info("")
    logger.info("💡 Pour vérifier les statistiques:")
    logger.info("   python scripts/vector_store_stats.py")
    logger.info("")
    logger.info("="*80)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Initialisation interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Erreur fatale: {e}", exc_info=True)
        sys.exit(1)

