from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from config.settings import get_settings

router = APIRouter(prefix="/config", tags=["Configuration"])
settings = get_settings()


class ConfigService:

    @staticmethod
    def get_system_config() -> Dict[str, Any]:
        """Configuration système (masquée pour sécurité)."""
        return {
            "monday_board_id": settings.monday_board_id,
            "monday_api_url": settings.monday_api_url,
            "github_token": "ghp_****" if settings.github_token else None,
            "anthropic_api_key": "sk-****" if settings.anthropic_api_key else None,
            "slack_enabled": settings.slack_enabled,
            "database_url": "postgresql://admin:****@localhost:5432/ai_agent_admin",
            "redis_url": settings.redis_url,
            "celery_broker_url": "amqp://****",
            "ai_model_temperature": settings.ai_model_temperature,
            "ai_max_tokens": settings.ai_max_tokens,
            "enable_smoke_tests": settings.enable_smoke_tests,
            "test_coverage_threshold": settings.test_coverage_threshold
        }


@router.get("")
async def get_system_config():
    """Configuration système."""
    try:
        return ConfigService.get_system_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur configuration: {str(e)}")

