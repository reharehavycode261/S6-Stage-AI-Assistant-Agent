from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import asyncpg
from config.settings import get_settings
from admin.backend.db_pool import DatabasePool
from admin.backend.cache_service import CacheService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
settings = get_settings()


class DashboardService:
    @staticmethod
    async def get_metrics() -> Dict[str, Any]:
        cache_key = CacheService.cache_key_dashboard_metrics()
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            return cached_data
        
        async with DatabasePool.get_connection() as db:
            try:
                tasks_active = await db.fetchval("""
                    SELECT COUNT(*) FROM tasks 
                    WHERE internal_status IN ('processing', 'testing', 'quality_check')
                """)
                
                tasks_this_month = await db.fetchval("""
                    SELECT COUNT(*) FROM tasks 
                    WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
                """)
                
                success_data = await db.fetchrow("""
                    SELECT 
                        COUNT(*) FILTER (WHERE status = 'completed') as completed,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed,
                        COUNT(*) as total
                    FROM task_runs 
                    WHERE DATE_TRUNC('month', started_at) = DATE_TRUNC('month', CURRENT_DATE)
                        AND status IN ('completed', 'failed')
                """)
                
                success_rate = 0
                if success_data and success_data['total'] > 0:
                    success_rate = (success_data['completed'] / success_data['total']) * 100
                
                # Temps moyen d'exécution CE MOIS (en secondes)
                avg_time = await db.fetchval("""
                    SELECT AVG(duration_seconds)
                    FROM task_runs
                    WHERE completed_at IS NOT NULL 
                        AND duration_seconds IS NOT NULL
                        AND DATE_TRUNC('month', started_at) = DATE_TRUNC('month', CURRENT_DATE)
                """) or 0
                
                # Coût IA CE MOIS (pas aujourd'hui!)
                ai_cost = await DashboardService._calculate_ai_cost_this_month(db)
                
                # Queue actuelle
                queue_size = await db.fetchval("""
                    SELECT COUNT(*) FROM workflow_queue 
                    WHERE status = 'pending'
                """) or 0
                
                metrics = {
                    "tasks_active": tasks_active or 0,
                    "tasks_this_month": tasks_this_month or 0,
                    "success_rate_this_month": round(success_rate, 1),
                    "avg_execution_time": round(avg_time, 2),
                    "ai_cost_this_month": round(ai_cost, 2),
                    "workers_active": 3,  # À récupérer depuis Celery
                    "queue_size": queue_size
                }
                
                # Mettre en cache pour 60 secondes
                await CacheService.set(cache_key, metrics, ttl=60)
                
                return metrics
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur DB: {str(e)}")
    
    @staticmethod
    async def _calculate_ai_cost_this_month(db: asyncpg.Connection) -> float:
        """Calculer le coût IA pour CE MOIS."""
        ai_cost = 0
        
        # Vérifier si table ai_cost_tracking existe
        cost_tracking_exists = await db.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'ai_cost_tracking'
            )
        """)
        
        if cost_tracking_exists:
            try:
                actual_cost = await db.fetchval("""
                    SELECT COALESCE(SUM(cost_usd), 0)
                    FROM ai_cost_tracking
                    WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
                """)
                if actual_cost and actual_cost > 0:
                    return float(actual_cost)
            except Exception:
                pass
        
        # Estimer depuis run_steps CE MOIS
        try:
            steps_count = await db.fetchval("""
                SELECT COUNT(*)
                FROM run_steps
                WHERE DATE_TRUNC('month', started_at) = DATE_TRUNC('month', CURRENT_DATE)
                AND completed_at IS NOT NULL
            """)
            if steps_count and steps_count > 0:
                ai_cost = steps_count * 0.05  # $0.05 par step
        except Exception:
            # Fallback sur task_runs CE MOIS
            runs_this_month = await db.fetchval("""
                SELECT COUNT(*)
                FROM task_runs
                WHERE DATE_TRUNC('month', started_at) = DATE_TRUNC('month', CURRENT_DATE)
                AND status = 'completed'
            """)
            if runs_this_month and runs_this_month > 0:
                ai_cost = runs_this_month * 0.20
        
        return ai_cost


@router.get("/metrics")
async def get_dashboard_metrics():
    """Récupérer les métriques du dashboard pour CE MOIS."""
    try:
        return await DashboardService.get_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur récupération métriques: {str(e)}")


@router.get("/tasks-trend")
async def get_tasks_trend(month: str = None, year: str = None):
    """
    Récupérer l'évolution des tâches sur les 7 derniers jours.
    Params optionnels: month (YYYY-MM), year (YYYY)
    """
    try:
        # Créer une clé de cache unique par filtre
        cache_key = f"dashboard:tasks_trend_{month}_{year}"
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            return cached_data
        
        async with DatabasePool.get_connection() as db:
            from datetime import datetime, timedelta
            
            # Si un mois est spécifié, utiliser ce mois
            if month:
                date_start = f"{month}-01"
                year_int = int(month.split('-')[0])
                month_int = int(month.split('-')[1])
                if month_int == 12:
                    next_month = f"{year_int + 1}-01-01"
                else:
                    next_month = f"{year_int}-{month_int + 1:02d}-01"
                
                where_clause = f"tr.started_at >= '{date_start}' AND tr.started_at < '{next_month}'"
            elif year:
                where_clause = f"EXTRACT(YEAR FROM tr.started_at) = {year}"
            else:
                where_clause = "tr.started_at >= CURRENT_DATE - INTERVAL '7 days'"

            query = f"""
                SELECT 
                    DATE_TRUNC('day', tr.started_at) as day,
                    COUNT(*) FILTER (WHERE tr.status = 'completed') as success,
                    COUNT(*) FILTER (WHERE tr.status = 'failed') as failed
                FROM task_runs tr
                WHERE {where_clause}
                    AND tr.status IN ('completed', 'failed')
                GROUP BY day
                ORDER BY day ASC
            """
            
            rows = await db.fetch(query)

            data_by_day = {}
            for row in rows:
                day_str = row['day'].strftime('%Y-%m-%d')
                data_by_day[day_str] = {
                    'success': row['success'],
                    'failed': row['failed']
                }

            from dateutil.relativedelta import relativedelta
            import calendar
            
            today = datetime.now().date()
            days_fr = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
            
            trend_data = []
            
            if month:
                year_int = int(month.split('-')[0])
                month_int = int(month.split('-')[1])

                days_in_month = calendar.monthrange(year_int, month_int)[1]

                for day_num in range(1, days_in_month + 1):
                    day = datetime(year_int, month_int, day_num).date()
                    day_str = day.strftime('%Y-%m-%d')
                    day_name = f"{day_num}/{month_int}"
                    
                    trend_data.append({
                        'date': day_name,
                        'success': data_by_day.get(day_str, {}).get('success', 0),
                        'failed': data_by_day.get(day_str, {}).get('failed', 0)
                    })
            elif year:
                months_fr = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 
                            'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
                
                for month_num in range(1, 13):
                    month_success = 0
                    month_failed = 0
                    
                    days_in_month = calendar.monthrange(int(year), month_num)[1]
                    for day_num in range(1, days_in_month + 1):
                        day = datetime(int(year), month_num, day_num).date()
                        day_str = day.strftime('%Y-%m-%d')
                        month_success += data_by_day.get(day_str, {}).get('success', 0)
                        month_failed += data_by_day.get(day_str, {}).get('failed', 0)
                    
                    trend_data.append({
                        'date': months_fr[month_num - 1],
                        'success': month_success,
                        'failed': month_failed
                    })
            else:
                for i in range(6, -1, -1):  # De -6 à 0
                    day = today - timedelta(days=i)
                    day_str = day.strftime('%Y-%m-%d')
                    day_name = days_fr[day.weekday()]
                    
                    trend_data.append({
                        'date': day_name,
                        'success': data_by_day.get(day_str, {}).get('success', 0),
                        'failed': data_by_day.get(day_str, {}).get('failed', 0)
                    })
            
            await CacheService.set(cache_key, trend_data, ttl=300)
            
            return trend_data
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur trend: {str(e)}")
