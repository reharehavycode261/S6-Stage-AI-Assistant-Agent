"""Applique la migration manuellement étape par étape."""
import asyncpg
import asyncio


async def apply_migration():
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='admin',
        password='password',
        database='ai_agent_admin'
    )
    
    print('🔄 Application de la migration enhanced_validation_rejection_system...\n')
    
    # 1) Ajouter colonnes à human_validations
    print('📋 Ajout des colonnes à human_validations...')
    try:
        await conn.execute("""
            ALTER TABLE human_validations 
            ADD COLUMN IF NOT EXISTS rejection_count INTEGER NOT NULL DEFAULT 0
        """)
        print('  ✅ rejection_count ajoutée')
    except Exception as e:
        print(f'  ⚠️ rejection_count: {e}')
    
    try:
        await conn.execute("""
            ALTER TABLE human_validations 
            ADD COLUMN IF NOT EXISTS modification_instructions TEXT
        """)
        print('  ✅ modification_instructions ajoutée')
    except Exception as e:
        print(f'  ⚠️ modification_instructions: {e}')
    
    try:
        await conn.execute("""
            ALTER TABLE human_validations 
            ADD COLUMN IF NOT EXISTS is_retry BOOLEAN NOT NULL DEFAULT FALSE
        """)
        print('  ✅ is_retry ajoutée')
    except Exception as e:
        print(f'  ⚠️ is_retry: {e}')
    
    try:
        await conn.execute("""
            ALTER TABLE human_validations 
            ADD COLUMN IF NOT EXISTS parent_validation_id VARCHAR(100)
        """)
        print('  ✅ parent_validation_id ajoutée')
    except Exception as e:
        print(f'  ⚠️ parent_validation_id: {e}')
    
    # 2) Ajouter colonnes à human_validation_responses
    print('\n📋 Ajout des colonnes à human_validation_responses...')
    try:
        await conn.execute("""
            ALTER TABLE human_validation_responses 
            ADD COLUMN IF NOT EXISTS rejection_count INTEGER NOT NULL DEFAULT 0
        """)
        print('  ✅ rejection_count ajoutée')
    except Exception as e:
        print(f'  ⚠️ rejection_count: {e}')
    
    try:
        await conn.execute("""
            ALTER TABLE human_validation_responses 
            ADD COLUMN IF NOT EXISTS modification_instructions TEXT
        """)
        print('  ✅ modification_instructions ajoutée')
    except Exception as e:
        print(f'  ⚠️ modification_instructions: {e}')
    
    try:
        await conn.execute("""
            ALTER TABLE human_validation_responses 
            ADD COLUMN IF NOT EXISTS should_retry_workflow BOOLEAN NOT NULL DEFAULT FALSE
        """)
        print('  ✅ should_retry_workflow ajoutée')
    except Exception as e:
        print(f'  ⚠️ should_retry_workflow: {e}')
    
    # 3) Créer le trigger de limite de rejets
    print('\n📋 Création du trigger check_rejection_limit...')
    try:
        await conn.execute("""
            CREATE OR REPLACE FUNCTION check_rejection_limit() RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.response_status = 'rejected' AND NEW.rejection_count >= 3 THEN
                    NEW.response_status := 'abandoned';
                    NEW.should_retry_workflow := FALSE;
                    NEW.comments := COALESCE(NEW.comments, '') || 
                        E'\\n\\n[SYSTÈME] Limite de 3 rejets atteinte. Passage en abandon automatique.';
                END IF;
                
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        print('  ✅ Fonction check_rejection_limit créée')
    except Exception as e:
        print(f'  ⚠️ Fonction: {e}')
    
    try:
        await conn.execute("""
            DROP TRIGGER IF EXISTS check_rejection_limit_trigger ON human_validation_responses;
        """)
        await conn.execute("""
            CREATE TRIGGER check_rejection_limit_trigger
            BEFORE INSERT OR UPDATE ON human_validation_responses
            FOR EACH ROW EXECUTE FUNCTION check_rejection_limit();
        """)
        print('  ✅ Trigger check_rejection_limit_trigger créé')
    except Exception as e:
        print(f'  ⚠️ Trigger: {e}')
    
    # 4) Créer les index
    print('\n📋 Création des index...')
    indexes = [
        ("idx_human_validations_rejection_count", "human_validations(rejection_count)"),
        ("idx_human_validations_parent_validation", "human_validations(parent_validation_id)", "WHERE parent_validation_id IS NOT NULL"),
        ("idx_human_validations_is_retry", "human_validations(is_retry)", "WHERE is_retry = TRUE"),
    ]
    
    for idx_name, idx_columns, *where_clause in indexes:
        where = where_clause[0] if where_clause else ""
        try:
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_columns} {where}
            """)
            print(f'  ✅ {idx_name}')
        except Exception as e:
            print(f'  ⚠️ {idx_name}: {e}')
    
    print('\n✅ Migration appliquée avec succès!')
    await conn.close()


if __name__ == "__main__":
    asyncio.run(apply_migration())

