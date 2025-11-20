from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncpg
from config.settings import get_settings

router = APIRouter(prefix="/logs", tags=["Logs"])
settings = get_settings()


class LogService:  
    @staticmethod
    async def get_db_connection():
        try:
            conn = await asyncpg.connect(settings.database_url)
            return conn
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur connexion DB: {str(e)}")
    
    @staticmethod
    async def get_logs(
        level: Optional[List[str]] = None,
        service: Optional[List[str]] = None,
        task_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 50
    ) -> Dict[str, Any]:
        db = await LogService.get_db_connection()
        try:
            offset = (page - 1) * per_page
            
            rows = await db.fetch("""
                SELECT 
                    tr.tasks_runs_id as id,
                    tr.started_at as timestamp,
                    CASE 
                        WHEN tr.status = 'failed' THEN 'ERROR'
                        WHEN tr.status = 'completed' THEN 'INFO'
                        ELSE 'WARNING'
                    END as level,
                    'workflow' as service,
                    COALESCE(tr.error_message, 'Workflow exécuté') as message,
                    tr.task_id::text as task_id
                FROM task_runs tr
                WHERE tr.started_at IS NOT NULL
                ORDER BY tr.started_at DESC
                LIMIT $1 OFFSET $2
            """, per_page, offset)
            
            total = await db.fetchval("SELECT COUNT(*) FROM task_runs WHERE started_at IS NOT NULL")
            
            items = []
            for row in rows:
                items.append({
                    "id": row['id'],
                    "timestamp": row['timestamp'].isoformat() if row['timestamp'] else datetime.now().isoformat(),
                    "level": row['level'],
                    "service": row['service'],
                    "message": row['message'] or "Aucun message",
                    "task_id": row['task_id'],
                    "context": {}
                })
            
            return {
                "items": items,
                "total": total or 0,
                "page": page,
                "per_page": per_page,
                "pages": ((total or 0) + per_page - 1) // per_page
            }
            
        finally:
            await db.close()


@router.get("")
async def get_logs(
    level: Optional[List[str]] = Query(None),
    service: Optional[List[str]] = Query(None),
    task_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200)
):
    try:
        return await LogService.get_logs(level, service, task_id, page, per_page)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur logs: {str(e)}")

