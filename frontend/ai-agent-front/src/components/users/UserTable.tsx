import {
  User as UserIcon,
  Mail,
  Calendar,
  CheckCircle,
  XCircle,
  Star,
  Shield,
  ShieldOff,
  AlertTriangle,
  Clock,
  MoreVertical,
} from 'lucide-react';
import { User, UserAccessStatus } from '@/types';
import { Badge } from '@/components/common/Badge';
import { Card } from '@/components/common/Card';

interface UserTableProps {
  users: User[];
  onSelectUser: (user: User) => void;
}

export function UserTable({ users, onSelectUser }: UserTableProps) {
  const getStatusBadge = (status: UserAccessStatus = UserAccessStatus.AUTHORIZED) => {
    const config = {
      [UserAccessStatus.AUTHORIZED]: { 
        icon: Shield, 
        color: 'bg-green-100 text-green-700 border-green-200', 
        label: 'Autorisé' 
      },
      [UserAccessStatus.SUSPENDED]: { 
        icon: ShieldOff, 
        color: 'bg-red-100 text-red-700 border-red-200', 
        label: 'Suspendu' 
      },
      [UserAccessStatus.RESTRICTED]: { 
        icon: AlertTriangle, 
        color: 'bg-orange-100 text-orange-700 border-orange-200', 
        label: 'Restreint' 
      },
      [UserAccessStatus.PENDING]: { 
        icon: Clock, 
        color: 'bg-gray-100 text-gray-700 border-gray-200', 
        label: 'En attente' 
      },
    };

    const { icon: Icon, color, label } = config[status];
    return (
      <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium border ${color}`}>
        <Icon className="h-3 w-3" />
        {label}
      </div>
    );
  };

  const formatLastActivity = (date?: string) => {
    if (!date) return 'Jamais';
    const now = new Date();
    const lastActivity = new Date(date);
    const diffMs = now.getTime() - lastActivity.getTime();
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffDays === 0) return 'Aujourd\'hui';
    if (diffDays === 1) return 'Hier';
    if (diffDays < 7) return `Il y a ${diffDays} jours`;
    if (diffDays < 30) return `Il y a ${Math.floor(diffDays / 7)} semaines`;
    return lastActivity.toLocaleDateString('fr-FR');
  };

  const getSuccessRate = (user: User) => {
    const total = user.total_tasks || 0;
    if (total === 0) return 0;
    // Approximation: on considère 70% de succès en moyenne
    return Math.round((total * 0.7) / total * 100);
  };

  if (users.length === 0) {
    return (
      <Card>
        <div className="text-center py-12">
          <UserIcon className="h-16 w-16 mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Aucun utilisateur trouvé
          </h3>
          <p className="text-gray-600">
            Essayez de modifier vos critères de recherche ou vos filtres
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b-2 border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Utilisateur
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Contact
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Statut
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Tâches
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Satisfaction
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Dernière activité
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {users.map((user) => (
              <tr
                key={user.user_id}
                className="hover:bg-gray-50 transition-colors cursor-pointer"
                onClick={() => onSelectUser(user)}
              >
                {/* Utilisateur */}
                <td className="px-4 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-semibold">
                      {user.name ? user.name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900">
                        {user.name || 'Sans nom'}
                      </div>
                      {user.role && (
                        <div className="text-xs text-gray-600 mt-0.5">
                          {user.role} {user.team && `• ${user.team}`}
                        </div>
                      )}
                    </div>
                  </div>
                </td>

                {/* Contact */}
                <td className="px-4 py-4">
                  <div className="flex items-center gap-2 text-sm text-gray-700">
                    <Mail className="h-4 w-4 text-gray-400" />
                    <span className="truncate max-w-[200px]">{user.email}</span>
                  </div>
                </td>

                {/* Statut */}
                <td className="px-4 py-4">
                  {getStatusBadge(user.access_status)}
                </td>

                {/* Tâches */}
                <td className="px-4 py-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 text-sm">
                        <CheckCircle className="h-4 w-4 text-green-600" />
                        <span className="font-semibold text-gray-900">{user.total_tasks || 0}</span>
                      </div>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div
                        className="bg-green-500 h-1.5 rounded-full"
                        style={{ width: `${getSuccessRate(user)}%` }}
                      />
                    </div>
                    <div className="text-xs text-gray-600">
                      {getSuccessRate(user)}% de succès
                    </div>
                  </div>
                </td>

                {/* Satisfaction */}
                <td className="px-4 py-4">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-0.5">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <Star
                          key={star}
                          className={`h-4 w-4 ${
                            star <= Math.round(user.satisfaction_score || 0)
                              ? 'text-yellow-400 fill-yellow-400'
                              : 'text-gray-300'
                          }`}
                        />
                      ))}
                    </div>
                    <span className="text-sm font-medium text-gray-900">
                      {user.satisfaction_score?.toFixed(1) || 'N/A'}
                    </span>
                  </div>
                  {user.satisfaction_comment && (
                    <div className="text-xs text-gray-600 mt-1 truncate max-w-[150px]">
                      "{user.satisfaction_comment}"
                    </div>
                  )}
                </td>

                {/* Dernière activité */}
                <td className="px-4 py-4">
                  <div className="flex items-center gap-2 text-sm text-gray-700">
                    <Calendar className="h-4 w-4 text-gray-400" />
                    {formatLastActivity(user.last_activity)}
                  </div>
                </td>

                {/* Actions */}
                <td className="px-4 py-4 text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectUser(user);
                    }}
                    className="inline-flex items-center justify-center w-8 h-8 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <MoreVertical className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer avec pagination et stats */}
      <div className="border-t border-gray-200 px-4 py-3 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            <strong>{users.length}</strong> utilisateur{users.length > 1 ? 's' : ''} affiché{users.length > 1 ? 's' : ''}
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-500 rounded-full" />
              Actifs: {users.filter(u => u.access_status === UserAccessStatus.AUTHORIZED).length}
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-red-500 rounded-full" />
              Suspendus: {users.filter(u => u.access_status === UserAccessStatus.SUSPENDED).length}
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-orange-500 rounded-full" />
              Restreints: {users.filter(u => u.access_status === UserAccessStatus.RESTRICTED).length}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

