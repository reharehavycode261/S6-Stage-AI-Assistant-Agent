"""
Service d'authentification et d'autorisation
Gère JWT, hashing des mots de passe, et permissions RBAC
"""
import asyncpg
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

from models.auth_models import (
    User, UserInDB, UserCreate, UserUpdate,
    Token, TokenData, LoginRequest,
    UserRole, AuditLogCreate, AuditLog
)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service d'authentification"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
    
    # ==================== Hashing et vérification ====================
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifie si le mot de passe correspond au hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash un mot de passe"""
        return pwd_context.hash(password)
    
    # ==================== JWT ====================
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Crée un token JWT"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Optional[TokenData]:
        """Décode et valide un token JWT"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            name: str = payload.get("name")
            role: str = payload.get("role")
            exp: datetime = datetime.fromtimestamp(payload.get("exp"))
            
            if user_id is None or email is None:
                return None
            
            return TokenData(
                sub=user_id,
                email=email,
                name=name,
                role=role,
                exp=exp
            )
        except JWTError:
            return None
    
    # ==================== Utilisateurs ====================
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Récupère un utilisateur par son email"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT user_id, email, name, password_hash, role, is_active,
                       created_at, updated_at, last_login
                FROM users
                WHERE email = $1
                """,
                email
            )
            
            if row:
                return UserInDB(
                    user_id=row['user_id'],
                    email=row['email'],
                    name=row['name'],
                    password_hash=row['password_hash'],
                    role=UserRole(row['role']),
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    last_login=row['last_login']
                )
            return None
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Récupère un utilisateur par son ID"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT user_id, email, name, role, is_active,
                       created_at, updated_at, last_login
                FROM users
                WHERE user_id = $1
                """,
                user_id
            )
            
            if row:
                return User(
                    user_id=row['user_id'],
                    email=row['email'],
                    name=row['name'],
                    role=UserRole(row['role']),
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    last_login=row['last_login']
                )
            return None
    
    async def authenticate_user(self, email: str, password: str) -> Optional[UserInDB]:
        """Authentifie un utilisateur"""
        user = await self.get_user_by_email(email)
        
        if not user:
            return None
        if not user.is_active:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        
        return user
    
    async def update_last_login(self, user_id: int):
        """Met à jour la date de dernière connexion"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET last_login = CURRENT_TIMESTAMP
                WHERE user_id = $1
                """,
                user_id
            )
    
    async def create_user(self, user_create: UserCreate) -> User:
        """Crée un nouvel utilisateur"""
        password_hash = self.get_password_hash(user_create.password)
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, name, password_hash, role, is_active)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING user_id, email, name, role, is_active, created_at, updated_at, last_login
                """,
                user_create.email,
                user_create.name,
                password_hash,
                user_create.role.value,
                user_create.is_active
            )
            
            return User(
                user_id=row['user_id'],
                email=row['email'],
                name=row['name'],
                role=UserRole(row['role']),
                is_active=row['is_active'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                last_login=row['last_login']
            )
    
    async def update_user(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        """Met à jour un utilisateur"""
        updates = []
        values = []
        param_count = 1
        
        if user_update.email is not None:
            updates.append(f"email = ${param_count}")
            values.append(user_update.email)
            param_count += 1
        
        if user_update.name is not None:
            updates.append(f"name = ${param_count}")
            values.append(user_update.name)
            param_count += 1
        
        if user_update.role is not None:
            updates.append(f"role = ${param_count}")
            values.append(user_update.role.value)
            param_count += 1
        
        if user_update.is_active is not None:
            updates.append(f"is_active = ${param_count}")
            values.append(user_update.is_active)
            param_count += 1
        
        if user_update.password is not None:
            password_hash = self.get_password_hash(user_update.password)
            updates.append(f"password_hash = ${param_count}")
            values.append(password_hash)
            param_count += 1
        
        if not updates:
            return await self.get_user_by_id(user_id)
        
        values.append(user_id)
        query = f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE user_id = ${param_count}
            RETURNING user_id, email, name, role, is_active, created_at, updated_at, last_login
        """
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)
            
            if row:
                return User(
                    user_id=row['user_id'],
                    email=row['email'],
                    name=row['name'],
                    role=UserRole(row['role']),
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    last_login=row['last_login']
                )
            return None
    
    # ==================== Audit Logs ====================
    
    async def create_audit_log(self, audit_log: AuditLogCreate) -> AuditLog:
        """Crée un log d'audit"""
        import json
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO audit_logs (
                    action, user_id, user_email, user_role,
                    resource_type, resource_id, details,
                    ip_address, user_agent, status, severity
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11)
                RETURNING id, timestamp, action, user_id, user_email, user_role,
                          resource_type, resource_id, details, ip_address,
                          user_agent, status, severity
                """,
                audit_log.action,
                audit_log.user_id,
                audit_log.user_email,
                audit_log.user_role,
                audit_log.resource_type,
                audit_log.resource_id,
                json.dumps(audit_log.details),  
                audit_log.ip_address,
                audit_log.user_agent,
                audit_log.status,
                audit_log.severity
            )
            
            row_dict = dict(row)
            if isinstance(row_dict['details'], str):
                row_dict['details'] = json.loads(row_dict['details'])
            
            return AuditLog(**row_dict)
    
    async def get_audit_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ):
        """Récupère les logs d'audit avec filtres"""
        import json
        
        conditions = []
        params = []
        param_count = 1
        
        if start_date:
            conditions.append(f"timestamp >= ${param_count}")
            params.append(start_date)
            param_count += 1
        
        if end_date:
            conditions.append(f"timestamp <= ${param_count}")
            params.append(end_date)
            param_count += 1
        
        if user_id:
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)
            param_count += 1
        
        if action:
            conditions.append(f"action = ${param_count}")
            params.append(action)
            param_count += 1
        
        if severity:
            conditions.append(f"severity = ${param_count}")
            params.append(severity)
            param_count += 1
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        params.extend([limit, offset])
        
        query = f"""
            SELECT id, timestamp, action, user_id, user_email, user_role,
                   resource_type, resource_id, details, ip_address,
                   user_agent, status, severity
            FROM audit_logs
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ${param_count}
            OFFSET ${param_count + 1}
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            logs = []
            for row in rows:
                row_dict = dict(row)
                if isinstance(row_dict['details'], str):
                    row_dict['details'] = json.loads(row_dict['details'])
                logs.append(AuditLog(**row_dict))
            
            return logs
    
    async def get_audit_stats(self):
        """Récupère les statistiques d'audit"""
        async with self.db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM audit_logs")
            
            today = await conn.fetchval(
                """
                SELECT COUNT(*) FROM audit_logs
                WHERE timestamp >= CURRENT_DATE
                """
            )
            
            critical = await conn.fetchval(
                """
                SELECT COUNT(*) FROM audit_logs
                WHERE severity = 'critical'
                """
            )
            
            unique_users = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT user_id) FROM audit_logs
                WHERE user_id IS NOT NULL
                """
            )
            
            most_common = await conn.fetch(
                """
                SELECT action, COUNT(*) as count
                FROM audit_logs
                GROUP BY action
                ORDER BY count DESC
                LIMIT 10
                """
            )
            
            return {
                "total_events": total,
                "events_today": today,
                "critical_events": critical,
                "unique_users": unique_users,
                "most_common_actions": [
                    {"action": row['action'], "count": row['count']}
                    for row in most_common
                ],
                "events_by_hour": []  
            }

