/**
 * Fonctions utilitaires de formatage
 */
import { formatDistanceToNow, format } from 'date-fns';
import { fr } from 'date-fns/locale';

/**
 * Formate une date en format relatif (il y a X minutes)
 */
export function formatRelativeTime(date: string | Date): string {
  return formatDistanceToNow(new Date(date), {
    addSuffix: true,
    locale: fr,
  });
}

/**
 * Formate une date en format complet
 */
export function formatFullDate(date: string | Date): string {
  return format(new Date(date), "PPpp", { locale: fr });
}

/**
 * Formate une durée en secondes en format lisible
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  
  if (minutes < 60) {
    return remainingSeconds > 0 
      ? `${minutes}m ${remainingSeconds}s`
      : `${minutes}m`;
  }
  
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  
  return remainingMinutes > 0
    ? `${hours}h ${remainingMinutes}m`
    : `${hours}h`;
}

/**
 * Formate un nombre en format monétaire
 */
export function formatCurrency(amount: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency,
  }).format(amount);
}

/**
 * Formate un nombre avec séparateurs
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('fr-FR').format(num);
}

/**
 * Formate un pourcentage
 */
export function formatPercentage(value: number, decimals: number = 1): string {
  return `${value.toFixed(decimals)}%`;
}

/**
 * Formate la taille d'un fichier
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

/**
 * Tronque un texte avec ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

/**
 * Formate un nom de branche Git
 */
export function formatBranchName(branch: string): string {
  // Enlever le préfixe origin/ si présent
  return branch.replace(/^origin\//, '');
}

/**
 * Extrait le nom du repository d'une URL GitHub
 */
export function extractRepoName(url: string): string {
  const match = url.match(/github\.com\/([^/]+\/[^/]+)/);
  return match ? match[1].replace(/\.git$/, '') : url;
}

/**
 * Formate un statut en français
 */
export function formatStatus(status: string): string {
  const statusMap: Record<string, string> = {
    pending: 'En attente',
    running: 'En cours',
    completed: 'Terminé',
    failed: 'Échoué',
    cancelled: 'Annulé',
    approved: 'Approuvé',
    rejected: 'Rejeté',
    abandoned: 'Abandonné',
    expired: 'Expiré',
  };
  
  return statusMap[status] || status;
}

/**
 * Formate un type de tâche en français
 */
export function formatTaskType(type: string): string {
  const typeMap: Record<string, string> = {
    feature: 'Fonctionnalité',
    bugfix: 'Correction de bug',
    refactor: 'Refactoring',
    documentation: 'Documentation',
    testing: 'Tests',
    ui_change: 'Interface',
    performance: 'Performance',
    analysis: 'Analyse',
  };
  
  return typeMap[type] || type;
}

/**
 * Formate une priorité en français
 */
export function formatPriority(priority: string): string {
  const priorityMap: Record<string, string> = {
    low: 'Basse',
    medium: 'Moyenne',
    high: 'Haute',
    urgent: 'Urgente',
  };
  
  return priorityMap[priority] || priority;
}

