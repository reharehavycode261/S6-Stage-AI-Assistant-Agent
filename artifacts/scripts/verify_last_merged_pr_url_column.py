"""Script de vérification et application de la migration last_merged_pr_url."""

import asyncio
import asyncpg
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)


async def verify_and_apply_migration():
    """Vérifie si la colonne last_merged_pr_url existe et l'ajoute si nécessaire."""
    
    settings = get_settings()
    
    try:
        # Se connecter à la base de données
        logger.info("📊 Connexion à la base de données PostgreSQL...")
        conn = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password
        )
        
        logger.info("✅ Connexion réussie")
        
        # Vérifier si la colonne existe
        logger.info("🔍 Vérification de l'existence de la colonne last_merged_pr_url...")
        result = await conn.fetchrow("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'task_runs'
            AND column_name = 'last_merged_pr_url'
        """)
        
        if result:
            logger.info(f"✅ Colonne last_merged_pr_url existe déjà:")
            logger.info(f"   Type: {result['data_type']}")
            logger.info(f"   Taille: {result['character_maximum_length']}")
            
            # Vérifier l'index
            index_result = await conn.fetchrow("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'task_runs'
                AND indexname = 'idx_task_runs_last_merged_pr_url'
            """)
            
            if index_result:
                logger.info(f"✅ Index idx_task_runs_last_merged_pr_url existe")
            else:
                logger.warning(f"⚠️ Index idx_task_runs_last_merged_pr_url manquant")
                
                # Créer l'index
                logger.info("📝 Création de l'index...")
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_task_runs_last_merged_pr_url 
                    ON task_runs(last_merged_pr_url) 
                    WHERE last_merged_pr_url IS NOT NULL
                """)
                logger.info("✅ Index créé avec succès")
            
        else:
            logger.warning("⚠️ Colonne last_merged_pr_url n'existe pas")
            logger.info("📝 Application de la migration...")
            
            # Appliquer la migration
            await conn.execute("""
                ALTER TABLE task_runs 
                ADD COLUMN IF NOT EXISTS last_merged_pr_url VARCHAR(500)
            """)
            logger.info("✅ Colonne last_merged_pr_url ajoutée")
            
            # Ajouter le commentaire
            await conn.execute("""
                COMMENT ON COLUMN task_runs.last_merged_pr_url IS 
                'URL de la dernière Pull Request fusionnée récupérée depuis GitHub lors de la mise à jour Monday.com'
            """)
            logger.info("✅ Commentaire ajouté")
            
            # Créer l'index
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_runs_last_merged_pr_url 
                ON task_runs(last_merged_pr_url) 
                WHERE last_merged_pr_url IS NOT NULL
            """)
            logger.info("✅ Index créé")
        
        # Statistiques sur les colonnes de task_runs
        logger.info("\n📊 Statistiques de la table task_runs:")
        columns = await conn.fetch("""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'task_runs'
            ORDER BY ordinal_position
        """)
        
        logger.info(f"   Total colonnes: {len(columns)}")
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            max_length = f"({col['character_maximum_length']})" if col['character_maximum_length'] else ""
            logger.info(f"   - {col['column_name']:30s} {col['data_type']}{max_length:10s} {nullable}")
        
        # Compter les URLs sauvegardées
        logger.info("\n📈 Statistiques d'utilisation:")
        count = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_runs,
                COUNT(last_merged_pr_url) as with_url,
                COUNT(*) - COUNT(last_merged_pr_url) as without_url
            FROM task_runs
        """)
        
        if count:
            logger.info(f"   Total runs: {count['total_runs']}")
            logger.info(f"   Avec last_merged_pr_url: {count['with_url']}")
            logger.info(f"   Sans last_merged_pr_url: {count['without_url']}")
            
            if count['with_url'] > 0:
                # Afficher quelques exemples
                examples = await conn.fetch("""
                    SELECT tasks_runs_id, last_merged_pr_url, started_at
                    FROM task_runs
                    WHERE last_merged_pr_url IS NOT NULL
                    ORDER BY started_at DESC
                    LIMIT 3
                """)
                
                logger.info("\n📝 Exemples récents:")
                for ex in examples:
                    logger.info(f"   Run #{ex['tasks_runs_id']}: {ex['last_merged_pr_url']}")
        
        # Fermer la connexion
        await conn.close()
        logger.info("\n✅ Vérification terminée avec succès")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("VÉRIFICATION MIGRATION: last_merged_pr_url")
    print("=" * 70)
    print()
    
    result = asyncio.run(verify_and_apply_migration())
    
    print()
    print("=" * 70)
    if result:
        print("✅ SUCCÈS: Migration vérifiée et appliquée si nécessaire")
    else:
        print("❌ ÉCHEC: Erreur lors de la vérification")
    print("=" * 70)

