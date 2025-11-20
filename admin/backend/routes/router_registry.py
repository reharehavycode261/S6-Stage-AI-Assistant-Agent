from fastapi import FastAPI

from admin.backend.routes.dashboard_routes import router as dashboard_router
from admin.backend.routes.tasks_routes import router as tasks_router
from admin.backend.routes.tests_routes import router as tests_router
from admin.backend.routes.users_routes import router as users_router
from admin.backend.routes.languages_routes import router as languages_router
from admin.backend.routes.ai_models_routes import router as ai_models_router
from admin.backend.routes.integrations_routes import router as integrations_router
from admin.backend.routes.logs_routes import router as logs_router
from admin.backend.routes.config_routes import router as config_router
from admin.backend.routes.validations_routes import router as validations_router
from admin.backend.routes.workflows_routes import router as workflows_router
from admin.backend.routes.browser_qa_routes import router as browser_qa_router  
from admin.auth_routes import router as auth_router, audit_router  


class RouterRegistry:
    
    @staticmethod
    def register_all_routers(app: FastAPI, prefix: str = "/api") -> None:
        app.include_router(
            dashboard_router,
            prefix=prefix,
            tags=["Dashboard"]
        )

        app.include_router(
            tasks_router,
            prefix=prefix,
            tags=["Tasks"]
        )
        app.include_router(
            tests_router,
            prefix=prefix,
            tags=["Tests"]
        )

        app.include_router(
            users_router,
            prefix=prefix,
            tags=["Users"]
        )

        app.include_router(
            languages_router,
            prefix=prefix,
            tags=["Languages"]
        )

        app.include_router(
            ai_models_router,
            prefix=prefix,
            tags=["AI Models"]
        )

        app.include_router(
            integrations_router,
            prefix=prefix,
            tags=["Integrations"]
        )

        app.include_router(
            logs_router,
            prefix=prefix,
            tags=["Logs"]
        )

        app.include_router(
            config_router,
            prefix=prefix,
            tags=["Configuration"]
        )

        app.include_router(
            validations_router,
            prefix=prefix,
            tags=["Validations"]
        )

        app.include_router(
            workflows_router,
            prefix=prefix,
            tags=["Workflows"]
        )
        app.include_router(
            browser_qa_router,
            prefix=prefix,
            tags=["Browser QA"]
        )

        app.include_router(
            auth_router,
            tags=["Authentication"]
        )
        
        app.include_router(
            audit_router,
            tags=["Audit"]
        )
        
        print("✅ Tous les routers orientés objet ont été enregistrés")
        print(f"   → Dashboard: {prefix}/dashboard/metrics")
        print(f"   → Tasks: {prefix}/tasks")
        print(f"   → Tests: {prefix}/tests/dashboard")
        print(f"   → Users: {prefix}/users")
        print(f"   → Languages: {prefix}/languages/stats")
        print(f"   → AI Models: {prefix}/ai/usage")
        print(f"   → Integrations: {prefix}/integrations/...")
        print(f"   → Logs: {prefix}/logs")
        print(f"   → Config: {prefix}/config")
        print(f"   → Validations: {prefix}/validations/pending")
        print(f"   → Browser QA: {prefix}/browser-qa/results")
        print(f"   → Authentication: /api/auth/login")  # ✅ NOUVEAU
        print(f"   → Audit: /api/audit/logs")  # ✅ NOUVEAU

