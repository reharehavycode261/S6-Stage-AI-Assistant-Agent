"""
Modèles d'authentification et d'autorisation pour l'interface admin
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """Rôles des utilisateurs"""
    ADMIN = "Admin"
    DEVELOPER = "Developer"
    VIEWER = "Viewer"
    AUDITOR = "Auditor"


class UserBase(BaseModel):
    """Schéma de base pour un utilisateur"""
    email: EmailStr
    name: str
    role: UserRole = UserRole.VIEWER
    is_active: bool = True


class UserCreate(UserBase):
    """Schéma pour créer un utilisateur"""
    password: str = Field(..., min_length=8, description="Mot de passe (min 8 caractères)")


class UserUpdate(BaseModel):
    """Schéma pour mettre à jour un utilisateur"""
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class User(UserBase):
    """Schéma complet d'un utilisateur"""
    user_id: int
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserInDB(User):
    """Schéma utilisateur en base de données (avec hash du mot de passe)"""
    password_hash: str


class Token(BaseModel):
    """Schéma pour le token JWT"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  


class TokenData(BaseModel):
    """Données contenues dans le token JWT"""
    sub: str  
    email: str
    name: str
    role: str
    exp: datetime


class LoginRequest(BaseModel):
    """Schéma pour la requête de login"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Schéma pour la réponse de login"""
    access_token: str
    token_type: str = "bearer"
    user: User


class PasswordChange(BaseModel):
    """Schéma pour changer le mot de passe"""
    current_password: str
    new_password: str = Field(..., min_length=8)


class AuditLogCreate(BaseModel):
    """Schéma pour créer un log d'audit"""
    action: str
    user_id: int
    user_email: str
    user_role: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: dict = {}
    ip_address: str
    user_agent: str
    status: str = "success"  
    severity: str = "low"  


class AuditLog(AuditLogCreate):
    """Schéma complet d'un log d'audit"""
    id: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogFilter(BaseModel):
    """Filtres pour les logs d'audit"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    user_id: Optional[int] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    search: Optional[str] = None
    page: int = 1
    per_page: int = 50


class AuditStats(BaseModel):
    """Statistiques des logs d'audit"""
    total_events: int
    events_today: int
    critical_events: int
    unique_users: int
    most_common_actions: List[dict]
    events_by_hour: List[dict]

