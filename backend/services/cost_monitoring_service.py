"""Service de monitoring des coûts IA avec tracking détaillé."""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import uuid
import time

from utils.logger import get_logger
from admin.backend.database import get_db_connection
from config.settings import get_settings

logger = get_logger(__name__)


class AIProvider(Enum):
    """Providers IA supportés."""
    CLAUDE = "claude"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class AIUsageRecord:
    """Enregistrement d'usage IA."""
    workflow_id: str
    task_id: str
    provider: AIProvider
    model: str
    operation: str  
    
    input_tokens: int
    output_tokens: int
    total_tokens: int    
    estimated_cost: float
    timestamp: datetime
    duration_seconds: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None


class CostMonitoringService:
    """Service de monitoring et agrégation des coûts IA."""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(self.__class__.__name__)
        
        self.usage_records = []
        
        self.db_pool = None
        
        self._daily_cache = {}
        self._session_cache = {}
        
        self.cost_thresholds = {
            "daily_warning": 50.0,   
            "daily_critical": 100.0, 
            "workflow_warning": 5.0,  
            "workflow_critical": 10.0 
        }
        
        self.pricing = {
            AIProvider.CLAUDE: {
                "claude-3-5-sonnet-20241022": {
                    "input": 0.003,   
                    "output": 0.015  
                },
                "claude-3-haiku": {
                    "input": 0.00025,  
                    "output": 0.00125 
                }
            },
            AIProvider.OPENAI: {
                "gpt-4": {
                    "input": 0.03,    
                    "output": 0.06   
                },
                "gpt-4-turbo": {
                    "input": 0.01,    
                    "output": 0.03    
                },
                "gpt-3.5-turbo": {
                    "input": 0.0015,  
                    "output": 0.002  
                }
            }
        }
    
    async def log_ai_usage(self, workflow_id: str, task_id: str, provider: str, 
                          model: str, operation: str, input_tokens: int, 
                          output_tokens: int, estimated_cost: float, success: bool = True) -> None:
        """Log l'utilisation de l'IA avec validation des paramètres."""
        
        if not workflow_id or workflow_id == "unknown":
            workflow_id = f"temp_workflow_{uuid.uuid4().hex[:8]}"
            self.logger.warning(f"⚠️ workflow_id manquant - généré temporaire: {workflow_id}")
        
        if not task_id or task_id == "unknown":
            task_id = f"temp_task_{int(time.time())}"
            self.logger.warning(f"⚠️ task_id manquant - généré temporaire: {task_id}")
        
        input_tokens = max(0, input_tokens or 0)
        output_tokens = max(0, output_tokens or 0)
        total_tokens = input_tokens + output_tokens
        
        estimated_cost = max(0.0, estimated_cost or 0.0)
        
        try:
            record = AIUsageRecord(
                workflow_id=workflow_id,
                task_id=task_id,
                provider=AIProvider(provider.lower()) if isinstance(provider, str) else provider,
                model=model or "unknown",
                operation=operation or "unknown",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                timestamp=datetime.now(timezone.utc),
                success=success
            )
            
            self.usage_records.append(record)
            
            self.logger.info(f"💰 Coût IA: {provider} - {input_tokens}+{output_tokens} tokens = ${estimated_cost:.4f}")
            
            await self._save_to_database(record)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors du logging de l'usage IA: {e}")
    
    async def get_workflow_costs(self, workflow_id: str) -> Dict[str, Any]:
        """Récupère les coûts d'un workflow spécifique."""
        
        if workflow_id in self._session_cache:
            records = self._session_cache[workflow_id]
        else:
            records = await self._get_workflow_records_from_db(workflow_id)
        
        if not records:
            return {
                "workflow_id": workflow_id,
                "total_cost": 0.0,
                "total_tokens": 0,
                "operations": [],
                "providers_used": []
            }
        
        total_cost = sum(r.estimated_cost for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        
        operations = []
        providers_used = set()
        
        for record in records:
            providers_used.add(record.provider.value)
            operations.append({
                "operation": record.operation,
                "provider": record.provider.value,
                "model": record.model,
                "tokens": record.total_tokens,
                "cost": record.estimated_cost,
                "timestamp": record.timestamp.isoformat(),
                "success": record.success
            })
        
        return {
            "workflow_id": workflow_id,
            "total_cost": round(total_cost, 6),
            "total_tokens": total_tokens,
            "operations": operations,
            "providers_used": list(providers_used),
            "operation_count": len(operations)
        }
    
    async def get_daily_stats(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Statistiques de coût pour une journée."""
        
        if date is None:
            date = datetime.now(timezone.utc)
        
        date_str = date.strftime("%Y-%m-%d")
        
        if date_str in self._daily_cache:
            return {"date": date_str, "cached_total": self._daily_cache[date_str]}
        
        try:
            conn = await get_db_connection()
            
            query = """
            SELECT 
                provider,
                model,
                operation,
                COUNT(*) as operation_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(estimated_cost) as total_cost,
                AVG(estimated_cost) as avg_cost_per_op
            FROM ai_usage_logs 
            WHERE DATE(timestamp) = $1
            GROUP BY provider, model, operation
            ORDER BY total_cost DESC
            """
            
            rows = await conn.fetch(query, date_str)
            
            if not rows:
                await conn.close()
                return {
                    "date": date_str,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "providers": {},
                    "operations": []
                }
            
            total_cost = 0.0
            total_tokens = 0
            providers = {}
            operations = []
            
            for row in rows:
                provider = row['provider']
                model = row['model']
                operation = row['operation']
                op_cost = float(row['total_cost'])
                op_tokens = int(row['total_tokens'])
                
                total_cost += op_cost
                total_tokens += op_tokens
                
                if provider not in providers:
                    providers[provider] = {"cost": 0.0, "tokens": 0, "models": set()}
                providers[provider]["cost"] += op_cost
                providers[provider]["tokens"] += op_tokens
                providers[provider]["models"].add(model)
                
                operations.append({
                    "provider": provider,
                    "model": model,
                    "operation": operation,
                    "count": int(row['operation_count']),
                    "input_tokens": int(row['total_input_tokens']),
                    "output_tokens": int(row['total_output_tokens']),
                    "total_tokens": op_tokens,
                    "total_cost": round(op_cost, 6),
                    "avg_cost": round(float(row['avg_cost_per_op']), 6)
                })
            
            for provider_data in providers.values():
                provider_data["models"] = list(provider_data["models"])
            
            self._daily_cache[date_str] = total_cost
            
            await conn.close()
            
            return {
                "date": date_str,
                "total_cost": round(total_cost, 6),
                "total_tokens": total_tokens,
                "providers": providers,
                "operations": operations
            }
                
        except Exception as e:
            self.logger.error(f"❌ Erreur récupération stats journalières: {e}")
            if 'conn' in locals():
                await conn.close()
            return {"date": date_str, "error": str(e)}
    
    async def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """Résumé mensuel des coûts."""
        
        try:
            conn = await get_db_connection()
            
            query = """
            SELECT 
                DATE(timestamp) as day,
                SUM(estimated_cost) as daily_cost,
                SUM(total_tokens) as daily_tokens,
                COUNT(DISTINCT workflow_id) as workflows_count
            FROM ai_usage_logs 
            WHERE EXTRACT(YEAR FROM timestamp) = $1 
              AND EXTRACT(MONTH FROM timestamp) = $2
            GROUP BY DATE(timestamp)
            ORDER BY day
            """
            
            rows = await conn.fetch(query, year, month)
            
            if not rows:
                await conn.close()
                return {
                    "year": year,
                    "month": month,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "daily_breakdown": []
                }
            
            total_cost = sum(float(row['daily_cost']) for row in rows)
            total_tokens = sum(int(row['daily_tokens']) for row in rows)
            total_workflows = sum(int(row['workflows_count']) for row in rows)
            
            daily_breakdown = []
            for row in rows:
                daily_breakdown.append({
                    "date": row['day'].strftime("%Y-%m-%d"),
                    "cost": round(float(row['daily_cost']), 6),
                    "tokens": int(row['daily_tokens']),
                    "workflows": int(row['workflows_count'])
                })
            
            await conn.close()
            
            return {
                "year": year,
                "month": month,
                "total_cost": round(total_cost, 6),
                "total_tokens": total_tokens,
                "total_workflows": total_workflows,
                "average_daily_cost": round(total_cost / len(rows), 6) if rows else 0,
                "days_with_usage": len(rows),
                "daily_breakdown": daily_breakdown
            }
                
        except Exception as e:
            self.logger.error(f"❌ Erreur résumé mensuel: {e}")
            if 'conn' in locals():
                await conn.close()
            return {"year": year, "month": month, "error": str(e)}
    
    def calculate_precise_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calcule le coût précis selon les tarifs actuels."""
        
        try:
            provider_enum = AIProvider(provider)
            pricing = self.pricing.get(provider_enum, {}).get(model)
            
            if not pricing:
                self.logger.warning(f"⚠️ Tarification non trouvée pour {provider}/{model}")
                return 0.0
            
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            
            return input_cost + output_cost
            
        except Exception as e:
            self.logger.error(f"❌ Erreur calcul coût: {e}")
            return 0.0
    
    async def _save_to_database(self, record: AIUsageRecord) -> None:
        """Sauvegarde un enregistrement en base."""
        
        try:
            conn = await get_db_connection()
            
            query = """
            INSERT INTO ai_usage_logs (
                workflow_id, task_id, provider, model, operation,
                input_tokens, output_tokens, total_tokens, estimated_cost,
                timestamp, duration_seconds, success, error_message
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """
            
            await conn.execute(query,
                record.workflow_id,
                record.task_id,
                record.provider.value,
                record.model,
                record.operation,
                record.input_tokens,
                record.output_tokens,
                record.total_tokens,
                record.estimated_cost,
                record.timestamp,
                record.duration_seconds,
                record.success,
                record.error_message
            )
            
            await conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Erreur sauvegarde coût en base: {e}")
            if 'conn' in locals():
                await conn.close()
    
    async def _get_workflow_records_from_db(self, workflow_id: str) -> List[AIUsageRecord]:
        """Récupère les enregistrements d'un workflow depuis la base."""
        
        try:
            conn = await get_db_connection()
            
            query = """
            SELECT * FROM ai_usage_logs 
            WHERE workflow_id = $1 
            ORDER BY timestamp
            """
            
            rows = await conn.fetch(query, workflow_id)
            
            records = []
            for row in rows:
                records.append(AIUsageRecord(
                    workflow_id=row['workflow_id'],
                    task_id=row['task_id'],
                    provider=AIProvider(row['provider']),
                    model=row['model'],
                    operation=row['operation'],
                    input_tokens=row['input_tokens'],
                    output_tokens=row['output_tokens'],
                    total_tokens=row['total_tokens'],
                    estimated_cost=row['estimated_cost'],
                    timestamp=row['timestamp'],
                    duration_seconds=row['duration_seconds'],
                    success=row['success'],
                    error_message=row['error_message']
                ))
            
            await conn.close()
            return records
                
        except Exception as e:
            self.logger.error(f"❌ Erreur récupération records workflow: {e}")
            if 'conn' in locals():
                await conn.close()
            return []

cost_monitor = CostMonitoringService() 