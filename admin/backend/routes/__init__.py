from .dashboard_routes import router as dashboard_router
from .tasks_routes import router as tasks_router
from .tests_routes import router as tests_router
from .users_routes import router as users_router
from .languages_routes import router as languages_router
from .ai_models_routes import router as ai_models_router
from .integrations_routes import router as integrations_router
from .logs_routes import router as logs_router
from .config_routes import router as config_router
from .validations_routes import router as validations_router
from .workflows_routes import router as workflows_router

__all__ = [
    "dashboard_router",
    "tasks_router",
    "tests_routes",
    "users_router",
    "languages_router",
    "ai_models_router",
    "integrations_router",
    "logs_router",
    "config_router",
    "validations_router",
    "workflows_router",
]
