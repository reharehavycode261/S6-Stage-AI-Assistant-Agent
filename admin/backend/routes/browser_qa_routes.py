from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

from admin.backend.db_pool import DatabasePool
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/browser-qa", tags=["browser-qa"])


class BrowserQAResult(BaseModel):
    """Modèle pour un résultat de test Browser QA."""
    task_id: int
    task_title: str
    executed_at: datetime
    success: bool
    tests_executed: int
    tests_passed: int
    tests_failed: int
    screenshots: List[str]
    console_errors: List[Dict[str, Any]]
    network_requests: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]
    test_scenarios: List[Dict[str, Any]]
    error: Optional[str]


@router.get("/results", response_model=List[BrowserQAResult])
async def get_browser_qa_results(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    task_id: Optional[int] = None,
    success_only: Optional[bool] = None
):

    try:
        check_column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'task_runs' 
            AND column_name = 'browser_qa_results'
        """
        
        column_exists = await DatabasePool.fetchval(check_column_query)
        
        if not column_exists:
            logger.warning("⚠️ Colonne browser_qa_results n'existe pas encore - retour liste vide")
            return []
        
        query = """
            SELECT 
                t.tasks_id as task_id,
                t.title as task_title,
                tr.started_at as executed_at,
                tr.browser_qa_results
            FROM tasks t
            INNER JOIN task_runs tr ON t.tasks_id = tr.task_id
            WHERE tr.browser_qa_results IS NOT NULL
        """
        
        params = []
        param_count = 1
        
        if task_id is not None:
            query += f" AND t.tasks_id = ${param_count}"
            params.append(task_id)
            param_count += 1
        
        if success_only is not None:
            query += f" AND (tr.browser_qa_results->>'success')::boolean = ${param_count}"
            params.append(success_only)
            param_count += 1
        
        query += f" ORDER BY tr.started_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
        params.extend([limit, offset])
        
        rows = await DatabasePool.fetch(query, *params)
        
        results = []
        for row in rows:
            qa_data = row["browser_qa_results"]
            
            results.append(BrowserQAResult(
                task_id=row["task_id"],
                task_title=row["task_title"],
                executed_at=row["executed_at"],
                success=qa_data.get("success", False),
                tests_executed=qa_data.get("tests_executed", 0),
                tests_passed=qa_data.get("tests_passed", 0),
                tests_failed=qa_data.get("tests_failed", 0),
                screenshots=qa_data.get("screenshots", []),
                console_errors=qa_data.get("console_errors", []),
                network_requests=qa_data.get("network_requests", []),
                performance_metrics=qa_data.get("performance_metrics", {}),
                test_scenarios=qa_data.get("test_scenarios", []),
                error=qa_data.get("error")
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération résultats Browser QA: {e}", exc_info=True)
        return []


@router.get("/results/{task_id}", response_model=BrowserQAResult)
async def get_browser_qa_result_by_task(task_id: int):
    try:
        check_column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'task_runs' 
            AND column_name = 'browser_qa_results'
        """
        
        column_exists = await DatabasePool.fetchval(check_column_query)
        
        if not column_exists:
            raise HTTPException(status_code=404, detail=f"Colonne browser_qa_results n'existe pas encore")
        
        query = """
            SELECT 
                t.tasks_id as task_id,
                t.title as task_title,
                tr.started_at as executed_at,
                tr.browser_qa_results
            FROM tasks t
            INNER JOIN task_runs tr ON t.tasks_id = tr.task_id
            WHERE t.tasks_id = $1 AND tr.browser_qa_results IS NOT NULL
            ORDER BY tr.started_at DESC
            LIMIT 1
        """
        
        row = await DatabasePool.fetchrow(query, task_id)
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Aucun résultat Browser QA pour task_id={task_id}")
        
        qa_data = row["browser_qa_results"]
        
        return BrowserQAResult(
            task_id=row["task_id"],
            task_title=row["task_title"],
            executed_at=row["executed_at"],
            success=qa_data.get("success", False),
            tests_executed=qa_data.get("tests_executed", 0),
            tests_passed=qa_data.get("tests_passed", 0),
            tests_failed=qa_data.get("tests_failed", 0),
            screenshots=qa_data.get("screenshots", []),
            console_errors=qa_data.get("console_errors", []),
            network_requests=qa_data.get("network_requests", []),
            performance_metrics=qa_data.get("performance_metrics", {}),
            test_scenarios=qa_data.get("test_scenarios", []),
            error=qa_data.get("error")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur récupération résultat Browser QA task_id={task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_browser_qa_stats():
    """
    Récupère les statistiques globales des tests Browser QA.
    
    Returns:
        Statistiques Browser QA
    """
    try:
        check_column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'task_runs' 
            AND column_name = 'browser_qa_results'
        """
        
        column_exists = await DatabasePool.fetchval(check_column_query)
        
        if not column_exists:
            logger.warning("⚠️ Colonne browser_qa_results n'existe pas encore - retour stats vides")
            return {
                "total_runs": 0,
                "total_success": 0,
                "total_failed": 0,
                "success_rate": 0.0,
                "avg_tests_per_run": 0.0,
                "total_tests_executed": 0,
                "total_tests_passed": 0,
                "total_tests_failed": 0,
                "pass_rate": 0.0
            }
        
        query = """
            SELECT 
                COUNT(*) as total_tests,
                COUNT(*) FILTER (WHERE (browser_qa_results->>'success')::boolean = true) as total_success,
                COUNT(*) FILTER (WHERE (browser_qa_results->>'success')::boolean = false) as total_failed,
                AVG((browser_qa_results->>'tests_executed')::int) as avg_tests_per_run,
                SUM((browser_qa_results->>'tests_executed')::int) as total_tests_executed,
                SUM((browser_qa_results->>'tests_passed')::int) as total_tests_passed,
                SUM((browser_qa_results->>'tests_failed')::int) as total_tests_failed
            FROM task_runs
            WHERE browser_qa_results IS NOT NULL
        """
        
        row = await DatabasePool.fetchrow(query)
        
        if not row or row["total_tests"] == 0:
            return {
                "total_runs": 0,
                "total_success": 0,
                "total_failed": 0,
                "success_rate": 0.0,
                "avg_tests_per_run": 0.0,
                "total_tests_executed": 0,
                "total_tests_passed": 0,
                "total_tests_failed": 0,
                "pass_rate": 0.0
            }
        
        return {
            "total_runs": row["total_tests"] or 0,
            "total_success": row["total_success"] or 0,
            "total_failed": row["total_failed"] or 0,
            "success_rate": round((row["total_success"] or 0) / max(row["total_tests"] or 1, 1) * 100, 2),
            "avg_tests_per_run": round(row["avg_tests_per_run"] or 0, 2),
            "total_tests_executed": row["total_tests_executed"] or 0,
            "total_tests_passed": row["total_tests_passed"] or 0,
            "total_tests_failed": row["total_tests_failed"] or 0,
            "pass_rate": round((row["total_tests_passed"] or 0) / max(row["total_tests_executed"] or 1, 1) * 100, 2)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération stats Browser QA: {e}", exc_info=True)
        return {
            "total_runs": 0,
            "total_success": 0,
            "total_failed": 0,
            "success_rate": 0.0,
            "avg_tests_per_run": 0.0,
            "total_tests_executed": 0,
            "total_tests_passed": 0,
            "total_tests_failed": 0,
            "pass_rate": 0.0
        }


@router.get("/recent")
async def get_recent_browser_qa_results(limit: int = Query(default=10, ge=1, le=50)):
    """
    Récupère les résultats Browser QA les plus récents (vue simplifiée).
    
    Args:
        limit: Nombre de résultats
        
    Returns:
        Liste simplifiée des résultats récents
    """
    try:
        check_column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'task_runs' 
            AND column_name = 'browser_qa_results'
        """
        
        column_exists = await DatabasePool.fetchval(check_column_query)

        if not column_exists:
            logger.warning("⚠️ Colonne browser_qa_results n'existe pas encore - retour liste vide")
            return []

        query = """
            SELECT 
                t.tasks_id as task_id,
                t.title as task_title,
                tr.started_at as executed_at,
                (tr.browser_qa_results->>'success')::boolean as success,
                (tr.browser_qa_results->>'tests_executed')::int as tests_executed,
                (tr.browser_qa_results->>'tests_passed')::int as tests_passed,
                (tr.browser_qa_results->>'tests_failed')::int as tests_failed
            FROM tasks t
            INNER JOIN task_runs tr ON t.tasks_id = tr.task_id
            WHERE tr.browser_qa_results IS NOT NULL
            ORDER BY tr.started_at DESC
            LIMIT $1
        """
        
        rows = await DatabasePool.fetch(query, limit)
        
        return [
            {
                "task_id": row["task_id"],
                "task_title": row["task_title"],
                "executed_at": row["executed_at"].isoformat(),
                "success": row["success"],
                "tests_executed": row["tests_executed"],
                "tests_passed": row["tests_passed"],
                "tests_failed": row["tests_failed"]
            }
            for row in rows
        ]
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération résultats récents Browser QA: {e}", exc_info=True)
        return []

