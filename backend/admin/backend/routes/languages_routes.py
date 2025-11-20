from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import asyncpg
from config.settings import get_settings
from admin.backend.db_pool import DatabasePool
from admin.backend.cache_service import CacheService

router = APIRouter(prefix="/languages", tags=["Languages"])
settings = get_settings()


class LanguageDetectionService:  
    @staticmethod
    async def get_languages_stats(month: str = None, year: str = None) -> List[Dict[str, Any]]:
        cache_key = f"language:stats_{month}_{year}"
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            return cached_data
        async with DatabasePool.get_connection() as db:
            try:
                if month:
                    date_start = f"{month}-01"
                    year_int = int(month.split('-')[0])
                    month_int = int(month.split('-')[1])
                    if month_int == 12:
                        next_month = f"{year_int + 1}-01-01"
                    else:
                        next_month = f"{year_int}-{month_int + 1:02d}-01"
                    
                    date_filter = f"tr.started_at >= '{date_start}' AND tr.started_at < '{next_month}'"
                elif year:
                    date_filter = f"EXTRACT(YEAR FROM tr.started_at) = {year}"
                else:
       
                    date_filter = "DATE_TRUNC('month', tr.started_at) = DATE_TRUNC('month', CURRENT_DATE)"
                
                query = f"""
                SELECT 
                    CASE 
                        -- Détection basée sur le repository_url (projet traité par l'IA)
                        -- On analyse l'URL complète pour extraire le nom du repo
                        
                        -- TypeScript/Angular (priorité haute - avant JavaScript)
                        WHEN LOWER(t.repository_url) LIKE '%typescript%'
                             OR LOWER(t.repository_url) LIKE '%-ts-%'
                             OR LOWER(t.repository_url) LIKE '%angular%'
                             OR LOWER(t.repository_url) LIKE '%-angular-%'
                             OR LOWER(t.repository_url) LIKE '%/angular%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%typescript%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%-ts-%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%angular%' THEN 'TypeScript'
                        
                        -- Python
                        WHEN LOWER(t.repository_url) LIKE '%python%' 
                             OR LOWER(t.repository_url) LIKE '%-py-%'
                             OR LOWER(t.repository_url) LIKE '%/py-%'
                             OR LOWER(t.repository_url) LIKE '%-django-%'
                             OR LOWER(t.repository_url) LIKE '%-flask-%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%python%' THEN 'Python'
                        
                        -- Java (détection de patterns Java: DAO, Spring, Hibernate, etc.)
                        WHEN LOWER(t.repository_url) LIKE '%java%'
                             OR LOWER(t.repository_url) LIKE '%dao%' 
                             OR LOWER(t.repository_url) LIKE '%spring%'
                             OR LOWER(t.repository_url) LIKE '%hibernate%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%java%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%dao%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%spring%' THEN 'Java'
                        
                        -- JavaScript/Node
                        WHEN LOWER(t.repository_url) LIKE '%javascript%'
                             OR LOWER(t.repository_url) LIKE '%-js-%'
                             OR LOWER(t.repository_url) LIKE '%node%'
                             OR LOWER(t.repository_url) LIKE '%react%'
                             OR LOWER(t.repository_url) LIKE '%vue%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%javascript%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%-js-%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%node%' THEN 'JavaScript'
                        
                        -- Go
                        WHEN LOWER(t.repository_url) LIKE '%/go/%'
                             OR LOWER(t.repository_url) LIKE '%golang%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%golang%' THEN 'Go'
                        
                        -- Rust
                        WHEN LOWER(t.repository_url) LIKE '%rust%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%rust%' THEN 'Rust'
                        
                        -- PHP
                        WHEN LOWER(t.repository_url) LIKE '%php%'
                             OR LOWER(t.repository_url) LIKE '%laravel%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%php%' THEN 'PHP'
                        
                        -- Ruby
                        WHEN LOWER(t.repository_url) LIKE '%ruby%'
                             OR LOWER(t.repository_url) LIKE '%rails%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%ruby%' THEN 'Ruby'
                        
                        -- C#
                        WHEN LOWER(t.repository_url) LIKE '%csharp%'
                             OR LOWER(t.repository_url) LIKE '%.net%'
                             OR LOWER(COALESCE(t.repository_name, '')) LIKE '%csharp%' THEN 'C#'
                        
                        ELSE 'Non détecté'
                    END as language,
                    COUNT(DISTINCT tr.tasks_runs_id) as task_count
                FROM task_runs tr
                INNER JOIN tasks t ON t.tasks_id = tr.task_id
                WHERE tr.status = 'completed'
                    AND {date_filter}
                    AND t.repository_url IS NOT NULL
                GROUP BY language
                ORDER BY task_count DESC
                """
                
                rows = await db.fetch(query)
                
                if not rows or len(rows) == 0:
                    return []
                
                total_tasks = sum(row['task_count'] for row in rows)
                
                result = []
                for row in rows:
                    percentage = (row['task_count'] / total_tasks * 100) if total_tasks > 0 else 0
                    result.append({
                        "language": row['language'],
                        "percentage": round(percentage, 1),
                        "task_count": row['task_count'],
                        "avg_confidence": 100,  
                        "failed_detections": 0
                    })
                
                await CacheService.set(cache_key, result, ttl=CacheService.TTL_LONG)
                
                return result
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur DB: {str(e)}")
    
    @staticmethod
    async def get_language_details(language: str) -> Dict[str, Any]:
        """Obtenir les détails pour un langage spécifique - OPTIMISÉ."""
        async with DatabasePool.get_connection() as db:
            try:
                tasks = await db.fetch("""
                    SELECT 
                        tasks_id,
                        title,
                        completed_at,
                        EXTRACT(EPOCH FROM (completed_at - started_at)) as duration
                    FROM tasks
                    WHERE internal_status = 'completed'
                    AND DATE_TRUNC('month', completed_at) = DATE_TRUNC('month', CURRENT_DATE)
                    ORDER BY completed_at DESC
                    LIMIT 10
                """)
                
                return {
                    "language": language,
                    "recent_tasks": [dict(task) for task in tasks],
                    "total_tasks_this_month": len(tasks)
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur DB: {str(e)}")


@router.get("/stats")
async def get_language_stats(month: str = None, year: str = None):
    """
    Statistiques des langages TRAITÉS par l'IA.
    Params optionnels: month (YYYY-MM), year (YYYY)
    """
    try:
        return await LanguageDetectionService.get_languages_stats(month, year)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur stats langages: {str(e)}")


@router.get("/{language}/details")
async def get_language_details(language: str):
    """Détails pour un langage spécifique."""
    try:
        return await LanguageDetectionService.get_language_details(language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur détails langage: {str(e)}")

