from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any, List
import asyncpg
import json
from config.settings import get_settings
from admin.backend.db_pool import DatabasePool
from admin.backend.cache_service import CacheService

router = APIRouter(prefix="/tasks", tags=["Tasks"])
settings = get_settings()


class TaskService:
    
    @staticmethod
    async def get_tasks(
        status: Optional[str] = None,
        priority: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        cache_key = CacheService.cache_key_tasks(status, page)
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            return cached_data

        async with DatabasePool.get_connection() as db:
            try:
                where_clauses = []
                params = []
                param_count = 0
                
                if status:
                    param_count += 1
                    where_clauses.append(f"internal_status = ${param_count}")
                    params.append(status)
                
                if priority:
                    param_count += 1
                    where_clauses.append(f"priority = ${param_count}")
                    params.append(priority)
                
                where_sql = ""
                if where_clauses:
                    where_sql = "WHERE " + " AND ".join(where_clauses)
                
                total = await db.fetchval(f"SELECT COUNT(*) FROM tasks {where_sql}", *params)

                offset = (page - 1) * per_page
                param_count += 1
                limit_param = f"${param_count}"
                param_count += 1
                offset_param = f"${param_count}"
                
                query = f"""
                    SELECT 
                        t.*,
                        (
                            SELECT jsonb_agg(
                                jsonb_build_object(
                                    'tasks_runs_id', tr.tasks_runs_id,
                                    'run_number', tr.run_number,
                                    'status', tr.status,
                                    'started_at', tr.started_at,
                                    'completed_at', tr.completed_at
                                ) ORDER BY tr.started_at DESC
                            )
                            FROM task_runs tr
                            WHERE tr.task_id = t.tasks_id
                        ) as runs
                    FROM tasks t
                    {where_sql}
                    ORDER BY t.created_at DESC
                    LIMIT {limit_param} OFFSET {offset_param}
                """
                
                params.extend([per_page, offset])
                rows = await db.fetch(query, *params)
                
                items = []
                for row in rows:
                    task = dict(row)
                    if task.get('runs') and isinstance(task['runs'], str):
                        task['runs'] = json.loads(task['runs'])
                    task['runs'] = task['runs'] or []
                    items.append(task)
                
                result = {
                    "items": items,
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "pages": (total + per_page - 1) // per_page
                }

                await CacheService.set(cache_key, result, ttl=CacheService.TTL_SHORT)
                
                return result
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur DB: {str(e)}")
    
    @staticmethod
    async def get_task_by_id(task_id: int) -> Dict[str, Any]:

        cache_key = CacheService.cache_key_task_detail(task_id)
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            return cached_data

        async with DatabasePool.get_connection() as db:
            try:
                task = await db.fetchrow("""
                    SELECT 
                        t.*,
                        (
                            SELECT jsonb_agg(
                                jsonb_build_object(
                                    'tasks_runs_id', tr.tasks_runs_id,
                                    'run_number', tr.run_number,
                                    'status', tr.status,
                                    'started_at', tr.started_at,
                                    'completed_at', tr.completed_at,
                                    'error_message', tr.error_message
                                ) ORDER BY tr.started_at DESC
                            )
                            FROM task_runs tr
                            WHERE tr.task_id = t.tasks_id
                        ) as runs,
                        (
                            SELECT jsonb_build_object(
                                'validation_id', hv.validation_id,
                                'status', hv.status,
                                'validated_by', hv.requested_by,
                                'created_at', hv.created_at
                            )
                            FROM human_validations hv
                            WHERE hv.task_id = t.tasks_id
                            ORDER BY hv.created_at DESC
                            LIMIT 1
                        ) as validation
                    FROM tasks t
                    WHERE t.tasks_id = $1
                """, task_id)
                
                if not task:
                    raise HTTPException(status_code=404, detail="Tâche non trouvée")
                
                result = dict(task)
                if result.get('runs') and isinstance(result['runs'], str):
                    result['runs'] = json.loads(result['runs'])
                result['runs'] = result['runs'] or []
                await CacheService.set(cache_key, result, ttl=CacheService.TTL_SHORT)
                
                return result
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur DB: {str(e)}")


@router.get("")
async def get_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    try:
        return await TaskService.get_tasks(status, priority, page, per_page)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur récupération tâches: {str(e)}")


@router.get("/{task_id}")
async def get_task_by_id(task_id: int):
    try:
        return await TaskService.get_task_by_id(task_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur récupération tâche: {str(e)}")


@router.post("/{task_id}/retry")
async def retry_task(task_id: int):
    try:
        await CacheService.invalidate_task_caches(task_id)
        
        # TODO: Implémenter la logique de retry
        return {"message": "Tâche relancée avec succès", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du retry: {str(e)}")


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: int):
    """Annuler une tâche en cours."""
    try:
        await CacheService.invalidate_task_caches(task_id)
        
        # TODO: Implémenter la logique d'annulation
        return {"message": "Tâche annulée avec succès", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'annulation: {str(e)}")
