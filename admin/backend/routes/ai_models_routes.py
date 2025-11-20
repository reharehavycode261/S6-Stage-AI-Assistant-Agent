
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
import asyncpg
from config.settings import get_settings
from admin.backend.db_pool import DatabasePool
from admin.backend.cache_service import CacheService

router = APIRouter(prefix="/ai", tags=["AI Models"])
settings = get_settings()


class AIModelService:
    @staticmethod
    async def get_usage(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Usage des modèles IA CE MOIS - AVEC CACHE."""
        # Vérifier le cache
        cache_key = CacheService.cache_key_ai_usage()
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            return cached_data
        
        # Si pas en cache, récupérer depuis la DB
        async with DatabasePool.get_connection() as db:
            try:
                # Essayer depuis run_steps
                try:
                    rows = await db.fetch("""
                        SELECT 
                            'claude-3-sonnet' as model_name,
                            'anthropic' as provider,
                            COUNT(*) as total_requests,
                            AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_response_time,
                            COUNT(*) FILTER (WHERE status = 'failed') as errors
                        FROM run_steps
                        WHERE DATE_TRUNC('month', started_at) = DATE_TRUNC('month', CURRENT_DATE)
                        AND completed_at IS NOT NULL
                        GROUP BY model_name, provider
                        HAVING COUNT(*) > 0
                    """)
                except Exception:
                    rows = await db.fetch("""
                        SELECT 
                            'claude-3-sonnet' as model_name,
                            'anthropic' as provider,
                            COUNT(*) as total_requests,
                            AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_response_time,
                            COUNT(*) FILTER (WHERE status = 'failed') as errors
                        FROM task_runs
                        WHERE DATE_TRUNC('month', started_at) = DATE_TRUNC('month', CURRENT_DATE)
                        AND completed_at IS NOT NULL
                        GROUP BY model_name, provider
                    """)
                
                if not rows or len(rows) == 0:
                    return []
                
                result = []
                for row in rows:
                    total = row['total_requests'] or 1
                    errors = row['errors'] or 0
                    
                    result.append({
                        "model_name": row['model_name'],
                        "provider": row['provider'],
                        "total_tokens": 0,
                        "total_requests": total,
                        "total_cost": 0,
                        "avg_response_time": round(row['avg_response_time'] or 0, 2),
                        "error_rate": round((errors / total * 100), 2)
                    })
                
                # Mettre en cache pour 2 minutes
                await CacheService.set(cache_key, result, ttl=CacheService.TTL_SHORT * 4)
                
                return result
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur DB: {str(e)}")


@router.get("/usage")
async def get_ai_model_usage(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Usage des modèles IA CE MOIS."""
    try:
        return await AIModelService.get_usage(start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur usage IA: {str(e)}")
