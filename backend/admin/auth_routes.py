from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import timedelta

from models.auth_models import (
    LoginRequest, LoginResponse, Token,
    User, UserCreate, UserUpdate,
    AuditLogCreate, AuditLog, AuditLogFilter,
    UserRole
)
from services.auth_service import AuthService, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
audit_router = APIRouter(prefix="/api/audit", tags=["Audit"])

security = HTTPBearer()

def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> User:
    token = credentials.credentials
    
    token_data = auth_service.decode_token(token)
    
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await auth_service.get_user_by_id(int(token_data.sub))
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utilisateur désactivé",
        )
    
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user


async def require_admin_or_auditor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in [UserRole.ADMIN, UserRole.AUDITOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs et auditeurs",
        )
    return current_user


# ==================== Routes d'authentification ====================

@router.post("/login", response_model=LoginResponse)
async def login(
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        body = await http_request.json()
        print(f"🔍 DEBUG - Body reçu: {body}")

        login_request = LoginRequest(**body)
        print(f"✅ DEBUG - LoginRequest validé: {login_request}")
        
    except Exception as e:
        print(f"❌ DEBUG - Erreur de parsing: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur de parsing: {str(e)}"
        )
    
    user = await auth_service.authenticate_user(
        login_request.email,
        login_request.password
    )
    
    if not user:
        await auth_service.create_audit_log(AuditLogCreate(
            action="login_failed",
            user_id=0,
            user_email=login_request.email,
            user_role="unknown",
            details={"reason": "invalid_credentials"},
            ip_address=http_request.client.host,
            user_agent=http_request.headers.get("user-agent", "unknown"),
            status="failed",
            severity="medium"
        ))
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await auth_service.update_last_login(user.user_id)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={
            "sub": str(user.user_id),
            "email": user.email,
            "name": user.name,
            "role": user.role.value
        },
        expires_delta=access_token_expires
    )

    await auth_service.create_audit_log(AuditLogCreate(
        action="user_login",
        user_id=user.user_id,
        user_email=user.email,
        user_role=user.role.value,
        details={"login_time": str(user.last_login)},
        ip_address=http_request.client.host,
        user_agent=http_request.headers.get("user-agent", "unknown"),
        status="success",
        severity="low"
    ))

    user_dict = {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login
    }
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=User(**user_dict)
    )


@router.post("/logout")
async def logout(
    http_request: Request,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):

    await auth_service.create_audit_log(AuditLogCreate(
        action="user_logout",
        user_id=current_user.user_id,
        user_email=current_user.email,
        user_role=current_user.role.value,
        details={},
        ip_address=http_request.client.host,
        user_agent=http_request.headers.get("user-agent", "unknown"),
        status="success",
        severity="low"
    ))
    
    return {"message": "Déconnexion réussie"}


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Récupère les informations de l'utilisateur connecté"""
    return current_user


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={
            "sub": str(current_user.user_id),
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role.value
        },
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


# ==================== Routes de gestion des utilisateurs (Admin uniquement) ====================

@router.post("/users", response_model=User)
async def create_user(
    user_create: UserCreate,
    http_request: Request,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service)
):

    existing_user = await auth_service.get_user_by_email(user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un utilisateur avec cet email existe déjà"
        )

    new_user = await auth_service.create_user(user_create)

    await auth_service.create_audit_log(AuditLogCreate(
        action="user_created",
        user_id=current_user.user_id,
        user_email=current_user.email,
        user_role=current_user.role.value,
        resource_type="user",
        resource_id=str(new_user.user_id),
        details={
            "created_user_email": new_user.email,
            "created_user_role": new_user.role.value
        },
        ip_address=http_request.client.host,
        user_agent=http_request.headers.get("user-agent", "unknown"),
        status="success",
        severity="medium"
    ))
    
    return new_user


@router.get("/users", response_model=list[User])
async def list_users(
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service)
):

    return []


@router.put("/users/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    http_request: Request,
    current_user: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service)
):
    
    updated_user = await auth_service.update_user(user_id, user_update)
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    await auth_service.create_audit_log(AuditLogCreate(
        action="user_updated",
        user_id=current_user.user_id,
        user_email=current_user.email,
        user_role=current_user.role.value,
        resource_type="user",
        resource_id=str(user_id),
        details={"updated_fields": user_update.dict(exclude_unset=True)},
        ip_address=http_request.client.host,
        user_agent=http_request.headers.get("user-agent", "unknown"),
        status="success",
        severity="medium"
    ))
    
    return updated_user


# ==================== Routes d'audit ====================

@audit_router.get("/logs")
async def get_audit_logs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    current_user: User = Depends(require_admin_or_auditor),
    auth_service: AuthService = Depends(get_auth_service)
):
    
    offset = (page - 1) * per_page
    
    logs = await auth_service.get_audit_logs(
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        action=action,
        severity=severity,
        limit=per_page,
        offset=offset
    )
    
    return {"logs": logs, "page": page, "per_page": per_page}


@audit_router.get("/stats")
async def get_audit_stats(
    current_user: User = Depends(require_admin_or_auditor),
    auth_service: AuthService = Depends(get_auth_service)
):
    return await auth_service.get_audit_stats()


@audit_router.post("/log")
async def create_audit_log(
    audit_log: AuditLogCreate,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    log = await auth_service.create_audit_log(audit_log)
    return {"success": True, "log_id": log.id}


@audit_router.get("/export")
async def export_audit_logs(
    current_user: User = Depends(require_admin_or_auditor),
    auth_service: AuthService = Depends(get_auth_service)
):
    return {"message": "Export à implémenter"}

