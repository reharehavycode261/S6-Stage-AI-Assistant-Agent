/**
 * Hook personnalisé pour l'authentification
 * Encapsule l'utilisation du store Zustand pour une meilleure ergonomie
 */
import { useAuthStore } from '@/stores/useAuthStore';
import { authService } from '@/services/auth';

export function useAuth() {
  const {
    user,
    token,
    isAuthenticated,
    isLoading,
    login,
    logout,
    refreshToken,
    hasPermission,
    hasRole,
    logAuditEvent
  } = useAuthStore();

  /**
   * Vérifier si l'utilisateur a l'un des rôles requis
   */
  const hasAnyRole = (roles: string[]): boolean => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  /**
   * Vérifier si l'utilisateur a toutes les permissions requises
   */
  const hasAllPermissions = (permissions: string[]): boolean => {
    return permissions.every(permission => hasPermission(permission));
  };

  /**
   * Vérifier si l'utilisateur a au moins une des permissions requises
   */
  const hasAnyPermission = (permissions: string[]): boolean => {
    return permissions.some(permission => hasPermission(permission));
  };

  /**
   * Vérifier si l'utilisateur est admin
   */
  const isAdmin = (): boolean => {
    return hasRole('Admin');
  };

  /**
   * Vérifier si l'utilisateur est développeur
   */
  const isDeveloper = (): boolean => {
    return hasRole('Developer');
  };

  /**
   * Vérifier si l'utilisateur est auditeur
   */
  const isAuditor = (): boolean => {
    return hasRole('Auditor');
  };

  /**
   * Vérifier si l'utilisateur est viewer
   */
  const isViewer = (): boolean => {
    return hasRole('Viewer');
  };

  /**
   * Obtenir les informations du token
   */
  const getTokenInfo = () => {
    if (!token) return null;
    
    try {
      const decoded = authService.decodeToken(token);
      return {
        userId: decoded.sub,
        email: decoded.email,
        name: decoded.name,
        role: decoded.role,
        expiresAt: new Date(decoded.exp * 1000),
        timeRemaining: authService.getTokenTimeRemaining(token)
      };
    } catch (error) {
      return null;
    }
  };

  /**
   * Vérifier si le token doit être rafraîchi
   */
  const shouldRefresh = (): boolean => {
    if (!token) return false;
    return authService.shouldRefreshToken(token);
  };

  return {
    // État
    user,
    token,
    isAuthenticated,
    isLoading,
    
    // Actions
    login,
    logout,
    refreshToken,
    logAuditEvent,
    
    // Permissions
    hasPermission,
    hasRole,
    hasAnyRole,
    hasAllPermissions,
    hasAnyPermission,
    
    // Helpers de rôles
    isAdmin,
    isDeveloper,
    isAuditor,
    isViewer,
    
    // Token
    getTokenInfo,
    shouldRefresh,
  };
}

// Export aussi un alias pour compatibilité
export { useAuth as useAuthentication };



