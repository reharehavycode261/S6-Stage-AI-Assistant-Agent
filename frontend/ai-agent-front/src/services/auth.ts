/**
 * Service d'authentification
 * Gère les tokens JWT, le stockage local et les appels API d'authentification
 */
import { jwtDecode } from 'jwt-decode';

export interface TokenPayload {
  sub: string;  // user_id
  email: string;
  name: string;
  role: string;
  exp: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: {
    user_id: number;
    email: string;
    name: string;
    role: string;
    is_active: boolean;
  };
}

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

class AuthService {
  /**
   * Stocker le token dans le localStorage
   */
  setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
  }

  /**
   * Récupérer le token depuis le localStorage
   */
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  /**
   * Supprimer le token du localStorage
   */
  removeToken(): void {
    localStorage.removeItem(TOKEN_KEY);
  }

  /**
   * Stocker les données utilisateur dans le localStorage
   */
  setUser(user: any): void {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  /**
   * Récupérer les données utilisateur depuis le localStorage
   */
  getUser(): any | null {
    const user = localStorage.getItem(USER_KEY);
    return user ? JSON.parse(user) : null;
  }

  /**
   * Supprimer les données utilisateur du localStorage
   */
  removeUser(): void {
    localStorage.removeItem(USER_KEY);
  }

  /**
   * Vérifier si l'utilisateur est authentifié
   */
  isAuthenticated(): boolean {
    const token = this.getToken();
    if (!token) return false;

    try {
      const decoded = this.decodeToken(token);
      return !this.isTokenExpired(decoded);
    } catch {
      return false;
    }
  }

  /**
   * Décoder le token JWT
   */
  decodeToken(token: string): TokenPayload {
    return jwtDecode<TokenPayload>(token);
  }

  /**
   * Vérifier si le token est expiré
   */
  isTokenExpired(decoded: TokenPayload): boolean {
    const currentTime = Date.now() / 1000;
    return decoded.exp < currentTime;
  }

  /**
   * Obtenir le temps restant avant expiration (en secondes)
   */
  getTokenTimeRemaining(token: string): number {
    try {
      const decoded = this.decodeToken(token);
      const currentTime = Date.now() / 1000;
      return Math.max(0, decoded.exp - currentTime);
    } catch {
      return 0;
    }
  }

  /**
   * Vérifier si le token doit être rafraîchi
   * (rafraîchir si moins de 5 minutes restantes)
   */
  shouldRefreshToken(token: string): boolean {
    const timeRemaining = this.getTokenTimeRemaining(token);
    return timeRemaining > 0 && timeRemaining < 300; // 5 minutes
  }

  /**
   * Se déconnecter (nettoyer le localStorage)
   */
  logout(): void {
    this.removeToken();
    this.removeUser();
  }

  /**
   * Sauvegarder la réponse d'authentification
   */
  saveAuthResponse(response: AuthResponse): void {
    this.setToken(response.access_token);
    this.setUser(response.user);
  }

  /**
   * Obtenir le header d'autorisation pour les requêtes API
   */
  getAuthHeader(): Record<string, string> {
    const token = this.getToken();
    if (!token) return {};

    return {
      Authorization: `Bearer ${token}`
    };
  }

  /**
   * Vérifier si l'utilisateur a un rôle spécifique
   */
  hasRole(requiredRole: string): boolean {
    const user = this.getUser();
    if (!user) return false;

    return user.role === requiredRole;
  }

  /**
   * Vérifier si l'utilisateur a l'un des rôles requis
   */
  hasAnyRole(requiredRoles: string[]): boolean {
    const user = this.getUser();
    if (!user) return false;

    return requiredRoles.includes(user.role);
  }
}

// Export d'une instance unique (singleton)
export const authService = new AuthService();



