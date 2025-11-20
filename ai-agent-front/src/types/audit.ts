/**
 * Types pour le système d'audit logs
 */

export interface AuditLog {
  id: string;
  timestamp: string;
  action: string;
  user_id: string;
  user_email: string;
  user_role: string;
  resource_type?: string;
  resource_id?: string;
  details: Record<string, any>;
  ip_address: string;
  user_agent: string;
  status: 'success' | 'failed' | 'warning';
  severity: 'low' | 'medium' | 'high' | 'critical';
}

export interface AuditLogFilter {
  start_date?: string;
  end_date?: string;
  user_id?: string;
  action?: string;
  resource_type?: string;
  status?: string;
  severity?: string;
  search?: string;
}

export interface AuditStats {
  total_events: number;
  events_today: number;
  critical_events: number;
  unique_users: number;
  most_common_actions: Array<{ action: string; count: number }>;
  events_by_hour: Array<{ hour: string; count: number }>;
}

// Actions d'audit prédéfinies
export const AUDIT_ACTIONS = {
  // Authentification
  USER_LOGIN: 'user_login',
  USER_LOGOUT: 'user_logout',
  LOGIN_FAILED: 'login_failed',
  TOKEN_REFRESH: 'token_refresh',
  
  // Secrets
  SECRET_VIEWED: 'secret_viewed',
  SECRET_COPIED: 'secret_copied',
  SECRET_UPDATED: 'secret_updated',
  SECRET_DELETED: 'secret_deleted',
  
  // Configuration
  CONFIG_VIEWED: 'config_viewed',
  CONFIG_UPDATED: 'config_updated',
  CONFIG_EXPORTED: 'config_exported',
  
  // Intégrations
  INTEGRATION_VIEWED: 'integration_viewed',
  INTEGRATION_UPDATED: 'integration_updated',
  INTEGRATION_TESTED: 'integration_tested',
  
  // Tâches
  TASK_CREATED: 'task_created',
  TASK_UPDATED: 'task_updated',
  TASK_DELETED: 'task_deleted',
  TASK_CANCELLED: 'task_cancelled',
  TASK_RETRIED: 'task_retried',
  
  // Utilisateurs
  USER_CREATED: 'user_created',
  USER_UPDATED: 'user_updated',
  USER_DELETED: 'user_deleted',
  USER_ROLE_CHANGED: 'user_role_changed',
  
  // Système
  SYSTEM_SHUTDOWN: 'system_shutdown',
  SYSTEM_RESTART: 'system_restart',
  BACKUP_CREATED: 'backup_created',
  BACKUP_RESTORED: 'backup_restored',
} as const;

export type AuditActionType = typeof AUDIT_ACTIONS[keyof typeof AUDIT_ACTIONS];

