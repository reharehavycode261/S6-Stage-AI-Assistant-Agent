/**
 * Utilitaires pour les couleurs et styles
 */
import { clsx, type ClassValue } from 'clsx';

/**
 * Combine des classes CSS (alternative à classnames)
 */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

/**
 * Retourne une couleur basée sur le statut
 */
export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'text-yellow-600 bg-yellow-50',
    running: 'text-blue-600 bg-blue-50',
    completed: 'text-green-600 bg-green-50',
    failed: 'text-red-600 bg-red-50',
    cancelled: 'text-gray-600 bg-gray-50',
    approved: 'text-green-600 bg-green-50',
    rejected: 'text-red-600 bg-red-50',
    abandoned: 'text-gray-600 bg-gray-50',
    expired: 'text-orange-600 bg-orange-50',
  };
  
  return colors[status] || 'text-gray-600 bg-gray-50';
}

/**
 * Retourne une couleur basée sur la priorité
 */
export function getPriorityColor(priority: string): string {
  const colors: Record<string, string> = {
    low: 'text-blue-600 bg-blue-50',
    medium: 'text-yellow-600 bg-yellow-50',
    high: 'text-orange-600 bg-orange-50',
    urgent: 'text-red-600 bg-red-50',
  };
  
  return colors[priority] || 'text-gray-600 bg-gray-50';
}

/**
 * Retourne une couleur basée sur le type de tâche
 */
export function getTaskTypeColor(type: string): string {
  const colors: Record<string, string> = {
    feature: 'text-blue-600 bg-blue-50',
    bugfix: 'text-red-600 bg-red-50',
    refactor: 'text-purple-600 bg-purple-50',
    documentation: 'text-green-600 bg-green-50',
    testing: 'text-yellow-600 bg-yellow-50',
    ui_change: 'text-pink-600 bg-pink-50',
    performance: 'text-orange-600 bg-orange-50',
    analysis: 'text-indigo-600 bg-indigo-50',
  };
  
  return colors[type] || 'text-gray-600 bg-gray-50';
}

/**
 * Retourne une couleur basée sur le niveau de log
 */
export function getLogLevelColor(level: string): string {
  const colors: Record<string, string> = {
    DEBUG: 'text-gray-600 bg-gray-50',
    INFO: 'text-blue-600 bg-blue-50',
    WARNING: 'text-yellow-600 bg-yellow-50',
    ERROR: 'text-red-600 bg-red-50',
    CRITICAL: 'text-red-700 bg-red-100 font-bold',
  };
  
  return colors[level] || 'text-gray-600 bg-gray-50';
}

/**
 * Retourne une couleur de progression basée sur le pourcentage
 */
export function getProgressColor(percentage: number): string {
  if (percentage < 25) return 'bg-red-500';
  if (percentage < 50) return 'bg-orange-500';
  if (percentage < 75) return 'bg-yellow-500';
  if (percentage < 100) return 'bg-blue-500';
  return 'bg-green-500';
}

/**
 * Retourne une couleur pour les graphiques basée sur l'index
 */
export function getChartColor(index: number): string {
  const colors = [
    '#3b82f6', // blue-500
    '#10b981', // green-500
    '#f59e0b', // yellow-500
    '#ef4444', // red-500
    '#8b5cf6', // purple-500
    '#ec4899', // pink-500
    '#06b6d4', // cyan-500
    '#f97316', // orange-500
  ];
  
  return colors[index % colors.length];
}

