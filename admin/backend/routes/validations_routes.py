from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import asyncpg
from config.settings import get_settings

router = APIRouter(prefix="/validations", tags=["Validations"])
settings = get_settings()


class ValidationService:
    
    @staticmethod
    async def get_db_connection():
        try:
            conn = await asyncpg.connect(settings.database_url)
            return conn
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur connexion DB: {str(e)}")
    
    @staticmethod
    async def get_pending_validations() -> List[Dict[str, Any]]:
        """Validations en attente."""
        db = await ValidationService.get_db_connection()
        try:
            rows = await db.fetch("""
                SELECT 
                    validation_id,
                    task_id,
                    task_title,
                    generated_code,
                    code_summary,
                    files_modified,
                    original_request,
                    implementation_notes,
                    test_results,
                    pr_info,
                    created_at,
                    expires_at,
                    requested_by,
                    workflow_id
                FROM human_validations
                WHERE status = 'pending'
                AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY created_at DESC
            """)
            
            return [dict(row) for row in rows]
            
        finally:
            await db.close()


@router.get("/pending")
async def get_pending_validations():
    """Validations en attente."""
    try:
        return await ValidationService.get_pending_validations()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur validations: {str(e)}")

