/**
 * Store Zustand pour l'authentification avec JWT et RBAC
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Types pour l'authentification
export type UserRole = 'Admin' | 'Developer' | 'Viewer' | 'Auditor';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  permissions: string[];
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthState {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // Actions
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
  hasRole: (roles: UserRole | UserRole[]) => boolean;
  logAuditEvent: (action: string, details: Record<string, any>) => Promise<void>;
}

// Permissions par rôle
const ROLE_PERMISSIONS: Record<UserRole, string[]> = {
  Admin: [
    'config:read',
    'config:write',
    'integrations:read',
    'integrations:write',
    'users:read',
    'users:write',
    'tasks:read',
    'tasks:write',
    'tasks:execute',
    'logs:read',
    'audit:read',
    'secrets:read',
    'secrets:write',
  ],
  Developer: [
    'config:read',
    'integrations:read',
    'tasks:read',
    'tasks:write',
    'tasks:execute',
    'logs:read',
    'audit:read',
  ],
  Viewer: [
    'tasks:read',
    'logs:read',
    'audit:read',
  ],
  Auditor: [
    'tasks:read',
    'logs:read',
    'audit:read',
    'audit:export',
  ],
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (credentials: LoginCredentials) => {
        set({ isLoading: true });
        try {
          // Appel API pour l'authentification
          const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/auth/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(credentials),
          });

          if (!response.ok) {
            throw new Error('Identifiants invalides');
          }

          const data = await response.json();
          
          // Décoder le JWT pour obtenir les infos utilisateur
          const payload = JSON.parse(atob(data.access_token.split('.')[1]));
          
          const user: AuthUser = {
            id: payload.sub,
            email: payload.email,
            name: payload.name,
            role: payload.role,
            permissions: ROLE_PERMISSIONS[payload.role as UserRole] || [],
          };

          // Enregistrer l'audit log
          await get().logAuditEvent('user_login', {
            user_id: user.id,
            email: user.email,
            role: user.role,
          });

          set({
            user,
            token: data.access_token,
            isAuthenticated: true,
            isLoading: false,
          });

          // Sauvegarder le token dans localStorage pour les interceptors Axios
          localStorage.setItem('auth_token', data.access_token);
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        const { user } = get();
        
        // Enregistrer l'audit log avant de logout
        if (user) {
          await get().logAuditEvent('user_logout', {
            user_id: user.id,
            email: user.email,
          });
        }

        set({
          user: null,
          token: null,
          isAuthenticated: false,
        });

        localStorage.removeItem('auth_token');
      },

      refreshToken: async () => {
        const { token } = get();
        if (!token) return;

        try {
          const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/auth/refresh`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });

          if (!response.ok) {
            throw new Error('Failed to refresh token');
          }

          const data = await response.json();
          set({ token: data.access_token });
          localStorage.setItem('auth_token', data.access_token);
        } catch (error) {
          // Token invalide, déconnecter l'utilisateur
          get().logout();
        }
      },

      hasPermission: (permission: string): boolean => {
        const { user } = get();
        if (!user) return false;
        return user.permissions.includes(permission);
      },

      hasRole: (roles: UserRole | UserRole[]): boolean => {
        const { user } = get();
        if (!user) return false;
        
        const roleArray = Array.isArray(roles) ? roles : [roles];
        return roleArray.includes(user.role);
      },

      // Helper pour enregistrer les événements d'audit
      logAuditEvent: async (action: string, details: Record<string, any>) => {
        const { token, user } = get();
        if (!token || !user) return;

        try {
          await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/audit/log`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({
              action,
              user_id: user.id,
              user_email: user.email,
              user_role: user.role,
              details,
              timestamp: new Date().toISOString(),
              ip_address: window.location.hostname,
              user_agent: navigator.userAgent,
            }),
          });
        } catch (error) {
          console.error('Failed to log audit event:', error);
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// Export helper pour utiliser les permissions dans les composants
export const usePermission = (permission: string) => {
  return useAuthStore((state) => state.hasPermission(permission));
};

export const useRole = (roles: UserRole | UserRole[]) => {
  return useAuthStore((state) => state.hasRole(roles));
};

