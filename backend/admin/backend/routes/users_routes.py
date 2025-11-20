from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
import asyncpg
from config.settings import get_settings
from admin.backend.db_pool import DatabasePool
from admin.backend.cache_service import CacheService

router = APIRouter(prefix="/users", tags=["Users"])
settings = get_settings()


class UserService:
    
    @staticmethod
    async def get_users(
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "last_activity",
        order: str = "desc"
    ) -> Dict[str, Any]:
        cache_key = f"users:{page}:{search}:{sort_by}:{order}"
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            return cached_data

        async with DatabasePool.get_connection() as db:
            try:
                # Récupérer les utilisateurs depuis la table monday_users avec leurs stats
                users_query = """
                    SELECT 
                        mu.monday_user_id,
                        mu.monday_item_id,
                        mu.name,
                        mu.email,
                        mu.role,
                        mu.team,
                        mu.access_status,
                        mu.satisfaction_score,
                        mu.satisfaction_comment,
                        mu.last_activity,
                        mu.is_active,
                        mu.created_at,
                        -- Stats des tâches
                        COUNT(t.tasks_id) as total_tasks,
                        COUNT(t.tasks_id) FILTER (WHERE t.internal_status = 'completed') as completed_tasks,
                        COUNT(t.tasks_id) FILTER (WHERE t.internal_status = 'failed') as failed_tasks
                    FROM monday_users mu
                    LEFT JOIN tasks t ON t.monday_item_id = mu.monday_item_id
                    GROUP BY mu.monday_user_id, mu.monday_item_id, mu.name, mu.email, 
                             mu.role, mu.team, mu.access_status, mu.satisfaction_score,
                             mu.satisfaction_comment, mu.last_activity, mu.is_active, mu.created_at
                """
                
                users = await db.fetch(users_query)
                
                items = []
                for user_row in users:
                    items.append({
                        "user_id": user_row['monday_user_id'],
                        "monday_user_id": user_row['monday_user_id'],
                        "monday_item_id": user_row['monday_item_id'],
                        "email": user_row['email'],
                        "name": user_row['name'],
                        "role": user_row['role'],
                        "team": user_row['team'],
                        "is_active": user_row['is_active'],
                        "created_at": user_row['created_at'].isoformat() if user_row['created_at'] else None,
                        "total_tasks": user_row['total_tasks'] or 0,
                        "total_validations": 0,  # TODO: Calculer depuis human_validations
                        "avg_response_time": None,
                        "last_activity": user_row['last_activity'].isoformat() if user_row['last_activity'] else None,
                        "access_status": user_row['access_status'] or "authorized",
                        "satisfaction_score": float(user_row['satisfaction_score']) if user_row['satisfaction_score'] else None,
                        "satisfaction_comment": user_row['satisfaction_comment'],
                    })
                
                # Tri
                if sort_by == "name":
                    items.sort(key=lambda x: x["name"], reverse=(order == "desc"))
                elif sort_by == "last_activity":
                    items.sort(key=lambda x: x["last_activity"] or "", reverse=(order == "desc"))
                elif sort_by == "tasks_completed":
                    items.sort(key=lambda x: x["total_tasks"], reverse=(order == "desc"))
                elif sort_by == "satisfaction_score":
                    items.sort(key=lambda x: x["satisfaction_score"] or 0, reverse=(order == "desc"))
                
                # Recherche
                if search:
                    search_lower = search.lower()
                items = [
                        item for item in items 
                        if search_lower in item["email"].lower() 
                        or search_lower in item["name"].lower()
                        or (item.get("role") and search_lower in item["role"].lower())
                    ]
                
                # Pagination
                total = len(items)
                start = (page - 1) * per_page
                end = start + per_page
                paginated_items = items[start:end]
                
                result = paginated_items  # Retourner directement la liste pour compatibilité
                
                await CacheService.set(cache_key, result, ttl=60)  # Cache 1 minute
                
                return result
                
            except Exception as e:
                import traceback
                print(f"❌ ERREUR get_users: {str(e)}\n{traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=f"Erreur DB: {str(e)}")


@router.get("/stats/global")
async def get_global_stats():
    """Récupère les statistiques globales des utilisateurs."""
    try:
        async with DatabasePool.get_connection() as db:
            # Stats globales depuis monday_users
            total_users = await db.fetchval("SELECT COUNT(*) FROM monday_users") or 0
            active_users = await db.fetchval("""
                SELECT COUNT(*) 
                FROM monday_users 
                WHERE last_activity >= DATE_TRUNC('month', CURRENT_DATE)
            """) or 0
            
            # Compter par statut
            suspended_users = await db.fetchval("""
                SELECT COUNT(*) FROM monday_users WHERE access_status = 'suspended'
            """) or 0
            
            restricted_users = await db.fetchval("""
                SELECT COUNT(*) FROM monday_users WHERE access_status = 'restricted'
            """) or 0
            
            # Stats des tâches
            total_tasks = await db.fetchval("SELECT COUNT(*) FROM tasks") or 0
            completed_tasks = await db.fetchval("SELECT COUNT(*) FROM tasks WHERE internal_status = 'completed'") or 0
            failed_tasks = await db.fetchval("SELECT COUNT(*) FROM tasks WHERE internal_status = 'failed'") or 0
            
            # Calculer le taux de succès
            success_rate = 0
            if total_tasks > 0:
                success_rate = (completed_tasks / total_tasks) * 100
            
            # Calculer la moyenne de tâches par utilisateur
            avg_tasks_per_user = 0
            if total_users > 0:
                avg_tasks_per_user = total_tasks / total_users
            
            # Satisfaction moyenne
            avg_satisfaction = await db.fetchval("""
                SELECT AVG(satisfaction_score) 
                FROM monday_users 
                WHERE satisfaction_score IS NOT NULL
            """) or 0
            
            # Calculer la tendance (mois actuel vs mois précédent)
            users_last_month = await db.fetchval("""
                SELECT COUNT(*) 
                FROM monday_users 
                WHERE last_activity >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
                AND last_activity < DATE_TRUNC('month', CURRENT_DATE)
            """) or 1  # Éviter division par zéro
            
            trend_percentage = ((active_users - users_last_month) / users_last_month * 100) if users_last_month > 0 else 0
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "suspended_users": suspended_users,
                "restricted_users": restricted_users,
                "avg_satisfaction": round(float(avg_satisfaction), 1),
                "avg_tasks_per_user": round(avg_tasks_per_user, 1),
                "success_rate": round(success_rate, 1),
                "total_tasks_completed": completed_tasks,
                "total_tasks_failed": failed_tasks,
                "trend_percentage": round(trend_percentage, 1)
            }
    except Exception as e:
        import traceback
        error_detail = f"Erreur récupération stats globales: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ ERREUR /api/users/stats/global: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("")
async def get_users(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: Optional[str] = Query("last_activity"),
    order: Optional[str] = Query("desc"),
    access_status: Optional[str] = None
):
    """Liste des utilisateurs avec pagination et filtres."""
    try:
        users = await UserService.get_users(search, page, per_page, sort_by, order)
        
        # Filtrer par access_status si spécifié
        if access_status and access_status != "all":
            users = [u for u in users if u.get("access_status") == access_status]
        
        return users
    except Exception as e:
        import traceback
        error_detail = f"Erreur récupération utilisateurs: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ ERREUR /api/users: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)
