import { useState, useEffect } from 'react';
import {
  Clock,
  CheckCircle,
  XCircle,
  UserPlus,
  UserMinus,
  UserCheck,
  Shield,
  ShieldOff,
  AlertTriangle,
  Edit,
  Star,
} from 'lucide-react';
import { Card } from '@/components/common/Card';

interface TimelineEvent {
  id: number;
  type: 'user_created' | 'user_updated' | 'user_suspended' | 'user_activated' | 'user_deleted' | 'task_completed' | 'task_failed' | 'satisfaction_updated';
  user_name: string;
  user_email: string;
  description: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export function UserTimeline() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [filter, setFilter] = useState<'all' | 'actions' | 'tasks'>('all');

  // Simuler le chargement d'événements (à remplacer par un vrai appel API)
  useEffect(() => {
    // Mock data - remplacer par une vraie API
    const mockEvents: TimelineEvent[] = [
      {
        id: 1,
        type: 'user_created',
        user_name: 'Marie Dupont',
        user_email: 'marie.dupont@example.com',
        description: 'Nouvel utilisateur créé',
        timestamp: new Date(Date.now() - 3600000).toISOString(),
      },
      {
        id: 2,
        type: 'task_completed',
        user_name: 'Jean Martin',
        user_email: 'jean.martin@example.com',
        description: 'Tâche complétée avec succès',
        timestamp: new Date(Date.now() - 7200000).toISOString(),
        metadata: { task_title: 'Création API REST' },
      },
      {
        id: 3,
        type: 'user_suspended',
        user_name: 'Pierre Durand',
        user_email: 'pierre.durand@example.com',
        description: 'Compte suspendu',
        timestamp: new Date(Date.now() - 10800000).toISOString(),
        metadata: { reason: 'Trop d\'échecs consécutifs' },
      },
      {
        id: 4,
        type: 'satisfaction_updated',
        user_name: 'Sophie Laurent',
        user_email: 'sophie.laurent@example.com',
        description: 'Score de satisfaction mis à jour',
        timestamp: new Date(Date.now() - 14400000).toISOString(),
        metadata: { score: 4.5, comment: 'Excellent outil' },
      },
      {
        id: 5,
        type: 'task_failed',
        user_name: 'Luc Bernard',
        user_email: 'luc.bernard@example.com',
        description: 'Tâche échouée',
        timestamp: new Date(Date.now() - 18000000).toISOString(),
        metadata: { task_title: 'Migration base de données', error: 'Timeout' },
      },
    ];

    setEvents(mockEvents);
  }, []);

  const getEventIcon = (type: TimelineEvent['type']) => {
    const icons = {
      user_created: UserPlus,
      user_updated: Edit,
      user_suspended: ShieldOff,
      user_activated: Shield,
      user_deleted: UserMinus,
      task_completed: CheckCircle,
      task_failed: XCircle,
      satisfaction_updated: Star,
    };
    return icons[type] || Clock;
  };

  const getEventColor = (type: TimelineEvent['type']) => {
    const colors = {
      user_created: 'bg-green-100 text-green-700 border-green-200',
      user_updated: 'bg-blue-100 text-blue-700 border-blue-200',
      user_suspended: 'bg-red-100 text-red-700 border-red-200',
      user_activated: 'bg-green-100 text-green-700 border-green-200',
      user_deleted: 'bg-gray-100 text-gray-700 border-gray-200',
      task_completed: 'bg-green-100 text-green-700 border-green-200',
      task_failed: 'bg-red-100 text-red-700 border-red-200',
      satisfaction_updated: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    };
    return colors[type] || 'bg-gray-100 text-gray-700 border-gray-200';
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffMins < 1) return 'À l\'instant';
    if (diffMins < 60) return `Il y a ${diffMins} min`;
    if (diffHours < 24) return `Il y a ${diffHours}h`;
    
    return date.toLocaleString('fr-FR', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const filteredEvents = events.filter((event) => {
    if (filter === 'all') return true;
    if (filter === 'actions') return ['user_created', 'user_updated', 'user_suspended', 'user_activated', 'user_deleted', 'satisfaction_updated'].includes(event.type);
    if (filter === 'tasks') return ['task_completed', 'task_failed'].includes(event.type);
    return true;
  });

  return (
    <Card>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 pb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Timeline des activités</h3>
            <p className="text-sm text-gray-600 mt-1">Historique en temps réel des actions utilisateurs</p>
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
              Tout
            </button>
            <button
              onClick={() => setFilter('actions')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === 'actions'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Actions
            </button>
            <button
              onClick={() => setFilter('tasks')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === 'tasks'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Tâches
            </button>
          </div>
        </div>

        {/* Timeline */}
        <div className="space-y-3 max-h-[500px] overflow-y-auto">
          {filteredEvents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Clock className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>Aucune activité récente</p>
            </div>
          ) : (
            filteredEvents.map((event, index) => {
              const Icon = getEventIcon(event.type);
              const colorClass = getEventColor(event.type);
              
              return (
                <div key={event.id} className="flex gap-3">
                  {/* Ligne verticale */}
                  <div className="flex flex-col items-center">
                    <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center ${colorClass}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    {index < filteredEvents.length - 1 && (
                      <div className="w-0.5 h-full bg-gray-200 my-1" />
                    )}
                  </div>

                  {/* Contenu */}
                  <div className="flex-1 pb-4">
                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h4 className="font-semibold text-gray-900">{event.description}</h4>
                          <p className="text-sm text-gray-600 mt-1">
                            {event.user_name} ({event.user_email})
                          </p>
                        </div>
                        <span className="text-xs text-gray-500 whitespace-nowrap">
                          {formatTimestamp(event.timestamp)}
                        </span>
                      </div>

                      {/* Métadonnées */}
                      {event.metadata && (
                        <div className="mt-2 pt-2 border-t border-gray-200">
                          {event.metadata.task_title && (
                            <div className="text-sm text-gray-700">
                              📋 Tâche : <strong>{event.metadata.task_title}</strong>
                            </div>
                          )}
                          {event.metadata.reason && (
                            <div className="text-sm text-gray-700">
                              💡 Raison : {event.metadata.reason}
                            </div>
                          )}
                          {event.metadata.score && (
                            <div className="text-sm text-gray-700">
                              ⭐ Score : {event.metadata.score}/5
                              {event.metadata.comment && ` - "${event.metadata.comment}"`}
                            </div>
                          )}
                          {event.metadata.error && (
                            <div className="text-sm text-red-600">
                              ⚠️ Erreur : {event.metadata.error}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 pt-3 text-center">
          <button className="text-sm text-blue-600 hover:text-blue-800 font-medium">
            Charger plus d'événements →
          </button>
        </div>
      </div>
    </Card>
  );
}

