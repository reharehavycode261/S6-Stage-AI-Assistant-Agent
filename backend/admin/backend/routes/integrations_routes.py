from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from datetime import datetime
import asyncpg
from config.settings import get_settings

router = APIRouter(prefix="/integrations", tags=["Integrations"])
settings = get_settings()


class IntegrationService:
    @staticmethod
    async def get_db_connection():
        try:
            conn = await asyncpg.connect(settings.database_url)
            return conn
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur connexion DB: {str(e)}")
    
    @staticmethod
    async def get_monday_boards() -> List[Dict[str, Any]]:
        db = await IntegrationService.get_db_connection()
        try:
            rows = await db.fetch("""
                SELECT 
                    monday_board_id,
                    COUNT(*) as items_count,
                    MAX(created_at) as last_activity
                FROM tasks
                WHERE monday_board_id IS NOT NULL
                AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
                GROUP BY monday_board_id
            """)
            
            if not rows or len(rows) == 0:
                return [{
                    "board_id": int(settings.monday_board_id) if settings.monday_board_id else 0,
                    "name": "AI Agent Tasks",
                    "description": "Board principal",
                    "workspace_id": 1,
                    "items_count": 0,
                    "is_active": True
                }]
            
            result = []
            for row in rows:
                result.append({
                    "board_id": int(row['monday_board_id']),
                    "name": f"Board {row['monday_board_id']}",
                    "description": "Board Monday.com",
                    "workspace_id": 1,
                    "items_count": row['items_count'],
                    "is_active": True,
                    "last_activity": row['last_activity'].isoformat() if row['last_activity'] else None
                })
            
            return result
            
        finally:
            await db.close()
    
    @staticmethod
    async def get_github_repos() -> List[Dict[str, Any]]:
        db = await IntegrationService.get_db_connection()
        try:
            rows = await db.fetch("""
                SELECT 
                    repository_url as url,
                    repository_name as name,
                    COUNT(*) as task_count,
                    MAX(updated_at) as last_activity
                FROM tasks
                WHERE repository_url IS NOT NULL
                AND DATE_TRUNC('month', updated_at) = DATE_TRUNC('month', CURRENT_DATE)
                GROUP BY repository_url, repository_name
                ORDER BY task_count DESC
            """)
            
            if not rows or len(rows) == 0:
                return []
            
            result = []
            for row in rows:
                name = row['name'] or (row['url'].split('/')[-1] if row['url'] else "Unknown")
                
                result.append({
                    "full_name": name,
                    "url": row['url'],
                    "language": "Unknown",
                    "task_count": row['task_count'],
                    "last_activity": row['last_activity'].isoformat() if row['last_activity'] else None
                })
            
            return result
            
        finally:
            await db.close()
    
    @staticmethod
    def get_slack_workspace() -> Dict[str, Any]:
        return {
            "workspace_id": settings.slack_workspace_id or "T12345",
            "name": "VyCode Team",
            "domain": "vycode",
            "members_count": 15,
            "bot_user_id": "U12345"
        }


@router.get("/monday/boards")
async def get_monday_boards():
    try:
        return await IntegrationService.get_monday_boards()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Monday boards: {str(e)}")


@router.get("/github/repos")
async def get_github_repos():
    try:
        return await IntegrationService.get_github_repos()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur GitHub repos: {str(e)}")


@router.get("/slack/workspace")
async def get_slack_workspace():
    try:
        return IntegrationService.get_slack_workspace()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Slack workspace: {str(e)}")

