from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import asyncpg
from config.settings import get_settings

router = APIRouter(prefix="/tests", tags=["Tests"])
settings = get_settings()


class TestService:
    
    @staticmethod
    async def get_db_connection():
        try:
            conn = await asyncpg.connect(settings.database_url)
            return conn
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur connexion DB: {str(e)}")
    
    @staticmethod
    async def get_dashboard() -> Dict[str, Any]:
        db = await TestService.get_db_connection()
        try:
            try:
                stats = await db.fetchrow("""
                    SELECT 
                        COUNT(*) as total_tests,
                        COUNT(*) FILTER (WHERE status = 'completed') as passed_tests,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed_tests,
                        AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration
                    FROM run_steps
                    WHERE completed_at IS NOT NULL
                    AND DATE_TRUNC('month', started_at) = DATE_TRUNC('month', CURRENT_DATE)
                """)
                
                total = stats['total_tests'] or 0
                passed = stats['passed_tests'] or 0
                failed = stats['failed_tests'] or 0
            except Exception:
                stats = await db.fetchrow("""
                    SELECT 
                        COUNT(*) as total_tests,
                        COUNT(*) FILTER (WHERE status = 'completed') as passed_tests,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed_tests
                    FROM task_runs
                    WHERE completed_at IS NOT NULL
                    AND DATE_TRUNC('month', started_at) = DATE_TRUNC('month', CURRENT_DATE)
                """)
                
                total = stats['total_tests'] or 0
                passed = stats['passed_tests'] or 0
                failed = stats['failed_tests'] or 0
            
            success_rate = (passed / total * 100) if total > 0 else 0
            by_language = []
            try:
                language_stats = await db.fetch("""
                    SELECT 
                        CASE 
                            WHEN repository_url LIKE '%DAO%' OR repository_url LIKE '%java%' THEN 'Java'
                            WHEN repository_url LIKE '%python%' THEN 'Python'
                            WHEN repository_url LIKE '%javascript%' OR repository_url LIKE '%-js-%' THEN 'JavaScript'
                            WHEN repository_url LIKE '%typescript%' OR repository_url LIKE '%-ts-%' THEN 'TypeScript'
                            ELSE 'Other'
                        END as language,
                        COUNT(DISTINCT tr.tasks_runs_id) as total_tests,
                        COUNT(DISTINCT CASE WHEN tr.status = 'completed' THEN tr.tasks_runs_id END) as passed_tests,
                        COUNT(DISTINCT CASE WHEN tr.status = 'failed' THEN tr.tasks_runs_id END) as failed_tests,
                        AVG(EXTRACT(EPOCH FROM (tr.completed_at - tr.started_at))) as avg_duration
                    FROM task_runs tr
                    LEFT JOIN tasks t ON t.tasks_id = tr.task_id
                    WHERE tr.completed_at IS NOT NULL
                    AND DATE_TRUNC('month', tr.started_at) = DATE_TRUNC('month', CURRENT_DATE)
                    AND t.repository_url IS NOT NULL
                    GROUP BY language
                    ORDER BY total_tests DESC
                """)
                
                for row in language_stats:
                    if row['total_tests'] > 0:
                        success = (row['passed_tests'] / row['total_tests'] * 100) if row['total_tests'] > 0 else 0
                        by_language.append({
                            "language": row['language'],
                            "total_tests": row['total_tests'],
                            "passed_tests": row['passed_tests'],
                            "failed_tests": row['failed_tests'],
                            "success_rate": round(success, 1),
                            "avg_duration": round(row['avg_duration']) if row['avg_duration'] else 0
                        })
            except Exception:
                pass

            recent_failures = []
            try:
                failures = await db.fetch("""
                    SELECT 
                        t.monday_item_id,
                        t.repository_url,
                        tr.error_message,
                        tr.completed_at,
                        CASE 
                            WHEN t.repository_url LIKE '%DAO%' OR t.repository_url LIKE '%java%' THEN 'Java'
                            WHEN t.repository_url LIKE '%python%' THEN 'Python'
                            WHEN t.repository_url LIKE '%javascript%' THEN 'JavaScript'
                            ELSE 'Other'
                        END as language
                    FROM task_runs tr
                    LEFT JOIN tasks t ON t.tasks_id = tr.task_id
                    WHERE tr.status = 'failed'
                    AND DATE_TRUNC('month', tr.started_at) = DATE_TRUNC('month', CURRENT_DATE)
                    ORDER BY tr.completed_at DESC
                    LIMIT 10
                """)
                
                for row in failures:
                    recent_failures.append({
                        "task_id": f"task-{row['monday_item_id']}" if row['monday_item_id'] else "N/A",
                        "language": row['language'],
                        "test_type": "workflow_execution",
                        "error_message": (row['error_message'] or "Unknown error")[:200],
                        "timestamp": row['completed_at'].isoformat() if row['completed_at'] else None
                    })
            except Exception:
                pass
            
            return {
                "overall_success_rate": round(success_rate, 1),
                "total_tests": total,
                "passed_tests": passed,
                "failed_tests": failed,
                "by_language": by_language,
                "recent_failures": recent_failures
            }
            
        finally:
            await db.close()


@router.get("/dashboard")
async def get_test_dashboard():
    """Dashboard des tests CE MOIS."""
    try:
        return await TestService.get_dashboard()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur dashboard tests: {str(e)}")

