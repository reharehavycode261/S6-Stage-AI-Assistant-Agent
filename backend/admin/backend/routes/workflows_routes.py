from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import asyncpg
from config.settings import get_settings

router = APIRouter(prefix="/workflows", tags=["Workflows"])
settings = get_settings()


class WorkflowService:
    WORKFLOW_NODES = [
        'prepare',
        'analyze', 
        'implement',
        'test',
        'QA',
        'finalize',
        'validation',
        'merge',
        'update'
    ]
    
    @staticmethod
    async def get_db_connection():
        try:
            conn = await asyncpg.connect(settings.database_url)
            return conn
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur connexion DB: {str(e)}")
    
    @staticmethod
    async def get_active_workflows() -> List[Dict[str, Any]]:
        db = await WorkflowService.get_db_connection()
        try:
            rows = await db.fetch("""
                SELECT 
                    tr.tasks_runs_id,
                    tr.task_id,
                    t.monday_item_id,
                    t.title,
                    tr.run_number,
                    tr.status,
                    tr.current_node,
                    tr.progress_percentage,
                    tr.started_at,
                    tr.completed_at,
                    EXTRACT(EPOCH FROM (COALESCE(tr.completed_at, NOW()) - tr.started_at)) as duration_seconds
                FROM task_runs tr
                LEFT JOIN tasks t ON t.tasks_id = tr.task_id
                WHERE tr.status IN ('running', 'started')
                ORDER BY tr.started_at DESC
                LIMIT 20
            """)
            
            result = []
            for row in rows:
                steps = await db.fetch("""
                    SELECT 
                        node_name,
                        status,
                        step_order,
                        started_at,
                        completed_at,
                        duration_seconds,
                        error_details
                    FROM run_steps
                    WHERE task_run_id = $1
                    ORDER BY step_order ASC
                """, row['tasks_runs_id'])
                
                result.append({
                    "workflow_id": f"wf_{row['tasks_runs_id']}",
                    "task_id": str(row['monday_item_id']) if row['monday_item_id'] else str(row['task_id']),
                    "title": row['title'],
                    "run_number": row['run_number'],
                    "status": row['status'],
                    "current_node": row['current_node'],
                    "progress_percentage": row['progress_percentage'] or 0,
                    "started_at": row['started_at'].isoformat() if row['started_at'] else None,
                    "completed_at": row['completed_at'].isoformat() if row['completed_at'] else None,
                    "duration_seconds": round(row['duration_seconds']) if row['duration_seconds'] else 0,
                    "nodes": [dict(step) for step in steps]
                })
            
            return result
            
        finally:
            await db.close()
    
    @staticmethod
    async def get_workflow_by_id(workflow_id: str) -> Dict[str, Any]:
        try:
            tasks_runs_id = int(workflow_id.replace('wf_', ''))
        except ValueError:
            raise HTTPException(status_code=400, detail="Format workflow_id invalide")
        
        db = await WorkflowService.get_db_connection()
        try:
            run = await db.fetchrow("""
                SELECT 
                    tr.tasks_runs_id,
                    tr.task_id,
                    t.monday_item_id,
                    t.title,
                    t.description,
                    tr.run_number,
                    tr.status,
                    tr.current_node,
                    tr.progress_percentage,
                    tr.ai_provider,
                    tr.model_name,
                    tr.result,
                    tr.error_message,
                    tr.started_at,
                    tr.completed_at,
                    EXTRACT(EPOCH FROM (COALESCE(tr.completed_at, NOW()) - tr.started_at)) as duration_seconds
                FROM task_runs tr
                LEFT JOIN tasks t ON t.tasks_id = tr.task_id
                WHERE tr.tasks_runs_id = $1
            """, tasks_runs_id)
            
            if not run:
                raise HTTPException(status_code=404, detail="Workflow non trouvé")
            steps = await db.fetch("""
                SELECT 
                    run_steps_id,
                    node_name,
                    step_order,
                    status,
                    retry_count,
                    input_data,
                    output_data,
                    output_log,
                    error_details,
                    started_at,
                    completed_at,
                    duration_seconds
                FROM run_steps
                WHERE task_run_id = $1
                ORDER BY step_order ASC
            """, tasks_runs_id)
            

            nodes_data = []
            for node_name in WorkflowService.WORKFLOW_NODES:
                step = next((s for s in steps if s['node_name'] == node_name), None)
                
                if step:
                    nodes_data.append({
                        "id": node_name,
                        "name": node_name,
                        "status": step['status'],
                        "duration": step['duration_seconds'],
                        "started_at": step['started_at'].isoformat() if step['started_at'] else None,
                        "completed_at": step['completed_at'].isoformat() if step['completed_at'] else None,
                        "retry_count": step['retry_count'],
                        "error_details": step['error_details'],
                        "output_log": step['output_log']
                    })
                else:

                    nodes_data.append({
                        "id": node_name,
                        "name": node_name,
                        "status": "pending",
                        "duration": None
                    })
            
            return {
                "workflow_id": workflow_id,
                "task_id": str(run['monday_item_id']) if run['monday_item_id'] else str(run['task_id']),
                "title": run['title'],
                "description": run['description'],
                "run_number": run['run_number'],
                "status": run['status'],
                "current_node": run['current_node'],
                "progress_percentage": run['progress_percentage'] or 0,
                "ai_provider": run['ai_provider'],
                "model_name": run['model_name'],
                "error_message": run['error_message'],
                "started_at": run['started_at'].isoformat() if run['started_at'] else None,
                "completed_at": run['completed_at'].isoformat() if run['completed_at'] else None,
                "duration_seconds": round(run['duration_seconds']) if run['duration_seconds'] else 0,
                "nodes": nodes_data
            }
            
        finally:
            await db.close()
    
    @staticmethod
    async def get_recent_workflows(limit: int = 10) -> List[Dict[str, Any]]:
        db = await WorkflowService.get_db_connection()
        try:
            rows = await db.fetch("""
                SELECT 
                    tr.tasks_runs_id,
                    tr.task_id,
                    t.monday_item_id,
                    t.title,
                    tr.run_number,
                    tr.status,
                    tr.current_node,
                    tr.progress_percentage,
                    tr.started_at,
                    tr.completed_at,
                    EXTRACT(EPOCH FROM (tr.completed_at - tr.started_at)) as duration_seconds
                FROM task_runs tr
                LEFT JOIN tasks t ON t.tasks_id = tr.task_id
                WHERE tr.status IN ('completed', 'failed')
                AND tr.completed_at IS NOT NULL
                ORDER BY tr.completed_at DESC
                LIMIT $1
            """, limit)
            
            result = []
            for row in rows:
                result.append({
                    "workflow_id": f"wf_{row['tasks_runs_id']}",
                    "task_id": str(row['monday_item_id']) if row['monday_item_id'] else str(row['task_id']),
                    "title": row['title'],
                    "run_number": row['run_number'],
                    "status": row['status'],
                    "current_node": row['current_node'],
                    "progress_percentage": 100 if row['status'] == 'completed' else row['progress_percentage'] or 0,
                    "started_at": row['started_at'].isoformat() if row['started_at'] else None,
                    "completed_at": row['completed_at'].isoformat() if row['completed_at'] else None,
                    "duration_seconds": round(row['duration_seconds']) if row['duration_seconds'] else 0
                })
            
            return result
            
        finally:
            await db.close()


@router.get("/active")
async def get_active_workflows():
    try:
        return await WorkflowService.get_active_workflows()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur workflows actifs: {str(e)}")


@router.get("/recent")
async def get_recent_workflows(limit: int = 10):
    try:
        return await WorkflowService.get_recent_workflows(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur workflows récents: {str(e)}")


@router.get("/{workflow_id}")
async def get_workflow_by_id(workflow_id: str):
    try:
        return await WorkflowService.get_workflow_by_id(workflow_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur workflow: {str(e)}")

