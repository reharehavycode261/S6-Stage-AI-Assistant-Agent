import { useState, useEffect } from 'react';
import {
  AlertTriangle,
  AlertCircle,
  X,
  TrendingDown,
  Clock,
  Zap,
  Bell,
} from 'lucide-react';
import { Card } from '@/components/common/Card';

interface UserAlert {
  id: number;
  type: 'error_threshold' | 'inactive_user' | 'low_satisfaction' | 'high_task_failure';
  severity: 'high' | 'medium' | 'low';
  user_name: string;
  user_email: string;
  user_id: number;
  message: string;
  details: string;
  timestamp: string;
  acknowledged: boolean;
}

export function UserAlerts() {
  const [alerts, setAlerts] = useState<UserAlert[]>([]);
  const [filter, setFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');

  // Simuler le chargement d'alertes (à remplacer par un vrai appel API)
  useEffect(() => {
    // Mock data - remplacer par une vraie API
    const mockAlerts: UserAlert[] = [
      {
        id: 1,
        type: 'error_threshold',
        severity: 'high',
        user_name: 'Pierre Durand',
        user_email: 'pierre.durand@example.com',
        user_id: 5,
        message: 'Seuil d\'erreurs dépassé',
        details: '8 tâches échouées sur les 10 dernières (80% d\'échec)',
        timestamp: new Date(Date.now() - 1800000).toISOString(),
        acknowledged: false,
      },
      {
        id: 2,
        type: 'low_satisfaction',
        severity: 'medium',
        user_name: 'Marie Dubois',
        user_email: 'marie.dubois@example.com',
        user_id: 8,
        message: 'Satisfaction faible',
        details: 'Score de satisfaction : 2.0/5.0 - Commentaire négatif reçu',
        timestamp: new Date(Date.now() - 3600000).toISOString(),
        acknowledged: false,
      },
      {
        id: 3,
        type: 'inactive_user',
        severity: 'low',
        user_name: 'Luc Martin',
        user_email: 'luc.martin@example.com',
        user_id: 12,
        message: 'Utilisateur inactif',
        details: 'Aucune activité depuis 30 jours',
        timestamp: new Date(Date.now() - 7200000).toISOString(),
        acknowledged: false,
      },
      {
        id: 4,
        type: 'high_task_failure',
        severity: 'high',
        user_name: 'Sophie Laurent',
        user_email: 'sophie.laurent@example.com',
        user_id: 3,
        message: 'Taux d\'échec élevé',
        details: '5 tâches échouées consécutives - Possible problème technique',
        timestamp: new Date(Date.now() - 900000).toISOString(),
        acknowledged: false,
      },
    ];

    setAlerts(mockAlerts);
  }, []);

  const getSeverityConfig = (severity: UserAlert['severity']) => {
    const configs = {
      high: {
        bg: 'bg-red-50',
        border: 'border-red-200',
        text: 'text-red-800',
        badge: 'bg-red-600 text-white',
        icon: AlertCircle,
      },
      medium: {
        bg: 'bg-orange-50',
        border: 'border-orange-200',
        text: 'text-orange-800',
        badge: 'bg-orange-600 text-white',
        icon: AlertTriangle,
      },
      low: {
        bg: 'bg-yellow-50',
        border: 'border-yellow-200',
        text: 'text-yellow-800',
        badge: 'bg-yellow-600 text-white',
        icon: Clock,
      },
    };
    return configs[severity];
  };

  const getTypeIcon = (type: UserAlert['type']) => {
    const icons = {
      error_threshold: Zap,
      inactive_user: Clock,
      low_satisfaction: TrendingDown,
      high_task_failure: AlertCircle,
    };
    return icons[type];
  };

  const handleAcknowledge = (alertId: number) => {
    setAlerts(alerts.map(alert => 
      alert.id === alertId ? { ...alert, acknowledged: true } : alert
    ));
  };

  const handleDismiss = (alertId: number) => {
    setAlerts(alerts.filter(alert => alert.id !== alertId));
  };

  const filteredAlerts = alerts.filter(alert => {
    if (filter === 'all') return !alert.acknowledged;
    return alert.severity === filter && !alert.acknowledged;
  });

  const urgentAlerts = alerts.filter(a => a.severity === 'high' && !a.acknowledged).length;

  return (
    <Card>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 pb-4">
          <div className="flex items-center gap-3">
            <Bell className="h-6 w-6 text-orange-600" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Alertes et notifications</h3>
              <p className="text-sm text-gray-600">
                {urgentAlerts > 0 && (
                  <span className="text-red-600 font-semibold">
                    {urgentAlerts} alerte{urgentAlerts > 1 ? 's' : ''} urgente{urgentAlerts > 1 ? 's' : ''} •{' '}
                  </span>
                )}
                {filteredAlerts.length} notification{filteredAlerts.length > 1 ? 's' : ''} active{filteredAlerts.length > 1 ? 's' : ''}
              </p>
            </div>
          </div>

          {/* Filtres */}
          <div className="flex gap-2">
            <button
              onClick={() => setFilter('all')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Toutes
            </button>
            <button
              onClick={() => setFilter('high')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === 'high'
                  ? 'bg-red-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Urgentes
            </button>
            <button
              onClick={() => setFilter('medium')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === 'medium'
                  ? 'bg-orange-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Moyennes
            </button>
            <button
              onClick={() => setFilter('low')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === 'low'
                  ? 'bg-yellow-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Faibles
            </button>
          </div>
        </div>

        {/* Alertes */}
        <div className="space-y-3 max-h-[400px] overflow-y-auto">
          {filteredAlerts.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Bell className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p className="font-medium">Aucune alerte active</p>
              <p className="text-sm mt-1">Tout fonctionne correctement</p>
            </div>
          ) : (
            filteredAlerts.map((alert) => {
              const severityConfig = getSeverityConfig(alert.severity);
              const TypeIcon = getTypeIcon(alert.type);
              const SeverityIcon = severityConfig.icon;

              return (
                <div
                  key={alert.id}
                  className={`rounded-lg border-2 p-4 ${severityConfig.bg} ${severityConfig.border} transition-all hover:shadow-md`}
                >
                  <div className="flex items-start gap-3">
                    {/* Icône de type */}
                    <div className={`w-10 h-10 rounded-full ${severityConfig.badge} flex items-center justify-center flex-shrink-0`}>
                      <TypeIcon className="h-5 w-5" />
                    </div>

                    {/* Contenu */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <h4 className={`font-semibold ${severityConfig.text}`}>
                            {alert.message}
                          </h4>
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityConfig.badge}`}>
                            {alert.severity === 'high' && 'Urgent'}
                            {alert.severity === 'medium' && 'Moyen'}
                            {alert.severity === 'low' && 'Faible'}
                          </span>
                        </div>
                        <button
                          onClick={() => handleDismiss(alert.id)}
                          className="text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>

                      <p className="text-sm text-gray-700 mb-2">
                        <strong>{alert.user_name}</strong> ({alert.user_email})
                      </p>

                      <p className="text-sm text-gray-600 mb-3">{alert.details}</p>

                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-500">
                          {new Date(alert.timestamp).toLocaleString('fr-FR')}
                        </span>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleAcknowledge(alert.id)}
                            className="text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors"
                          >
                            Acquitter
                          </button>
                          <button
                            onClick={() => {/* TODO: Ouvrir le profil utilisateur */}}
                            className="text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors"
                          >
                            Voir le profil →
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Actions rapides */}
        {filteredAlerts.length > 0 && (
          <div className="border-t border-gray-200 pt-3 flex items-center justify-between">
            <button
              onClick={() => setAlerts(alerts.map(a => ({ ...a, acknowledged: true })))}
              className="text-sm text-gray-600 hover:text-gray-900 font-medium"
            >
              Tout acquitter
            </button>
            <button className="text-sm text-blue-600 hover:text-blue-800 font-medium">
              Configurer les alertes →
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}

