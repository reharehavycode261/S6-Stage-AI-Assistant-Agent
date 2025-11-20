import { useState } from 'react';
import { 
  Users, 
  Search, 
  Filter, 
  ChevronRight,
  CheckCircle,
  XCircle,
  Clock,
  Star,
  Shield,
  ShieldOff,
  AlertTriangle,
  TrendingUp,
  Calendar,
  Activity
} from 'lucide-react';
import { User, UserAccessStatus } from '@/types';
import { useUsers } from '@/hooks/useUserData';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { Badge } from '@/components/common/Badge';

interface UserHistorySidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectUser: (user: User) => void;
  selectedUserId?: number;
}

export function UserHistorySidebar({ 
  isOpen, 
  onClose, 
  onSelectUser,
  selectedUserId 
}: UserHistorySidebarProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<UserAccessStatus | 'all'>('all');
  const [sortBy, setSortBy] = useState<'name' | 'last_activity' | 'tasks_completed' | 'satisfaction_score'>('last_activity');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const { data: users, isLoading } = useUsers({
    access_status: statusFilter === 'all' ? undefined : statusFilter,
    search: searchTerm || undefined,
    sort_by: sortBy,
    order: sortOrder,
  });

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
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'À l\'instant';
    if (diffMins < 60) return `Il y a ${diffMins} min`;
    if (diffHours < 24) return `Il y a ${diffHours}h`;
    if (diffDays === 1) return 'Hier';
    if (diffDays < 7) return `Il y a ${diffDays} jours`;
    return lastActivity.toLocaleDateString('fr-FR');
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Sidebar */}
      <div className="fixed right-0 top-0 h-full w-[500px] bg-white shadow-2xl z-50 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Users className="h-6 w-6" />
              <h2 className="text-xl font-bold">Historique des utilisateurs</h2>
            </div>
            <button 
              onClick={onClose}
              className="text-white hover:bg-white/20 rounded-lg p-2 transition-colors"
            >
              ✕
            </button>
          </div>

          {/* Barre de recherche */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-white/70" />
            <input
              type="text"
              placeholder="Rechercher un utilisateur..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white/20 border border-white/30 rounded-lg text-white placeholder-white/70 focus:outline-none focus:ring-2 focus:ring-white/50"
            />
          </div>
        </div>

        {/* Filtres */}
        <div className="p-4 bg-gray-50 border-b border-gray-200">
          <div className="flex items-center gap-2 mb-3">
            <Filter className="h-4 w-4 text-gray-600" />
            <span className="text-sm font-medium text-gray-700">Filtres :</span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as UserAccessStatus | 'all')}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="all">Tous les statuts</option>
              <option value={UserAccessStatus.AUTHORIZED}>Autorisés</option>
              <option value={UserAccessStatus.SUSPENDED}>Suspendus</option>
              <option value={UserAccessStatus.RESTRICTED}>Restreints</option>
              <option value={UserAccessStatus.PENDING}>En attente</option>
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="last_activity">Dernière activité</option>
              <option value="name">Nom</option>
              <option value="tasks_completed">Tâches complétées</option>
              <option value="satisfaction_score">Satisfaction</option>
            </select>
          </div>

          <button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="mt-2 w-full px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
          >
            <TrendingUp className={`h-4 w-4 ${sortOrder === 'desc' ? 'rotate-180' : ''}`} />
            Ordre : {sortOrder === 'asc' ? 'Croissant' : 'Décroissant'}
          </button>
        </div>

        {/* Liste des utilisateurs */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <LoadingSpinner size="lg" />
            </div>
          ) : users && users.length > 0 ? (
            users.map((user) => (
              <div
                key={user.user_id}
                onClick={() => onSelectUser(user)}
                className={`p-4 rounded-xl border-2 cursor-pointer transition-all hover:shadow-md ${
                  selectedUserId === user.user_id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 bg-white hover:border-blue-300'
                }`}
              >
                {/* En-tête utilisateur */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 truncate">
                      {user.name || 'Utilisateur sans nom'}
                    </h3>
                    <p className="text-sm text-gray-600 truncate">{user.email}</p>
                    {user.role && (
                      <p className="text-xs text-gray-500 mt-1">Rôle : {user.role}</p>
                    )}
                  </div>
                  <ChevronRight className={`h-5 w-5 text-gray-400 flex-shrink-0 transition-transform ${
                    selectedUserId === user.user_id ? 'rotate-90' : ''
                  }`} />
                </div>

                {/* Statut */}
                <div className="mb-3">
                  {getStatusBadge(user.access_status)}
                </div>

                {/* Statistiques */}
                <div className="grid grid-cols-2 gap-2 mb-3">
                  <div className="flex items-center gap-2 text-sm">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <span className="text-gray-700">
                      <strong>{user.total_tasks || 0}</strong> tâches
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Star className="h-4 w-4 text-yellow-500" />
                    <span className="text-gray-700">
                      <strong>{user.satisfaction_score?.toFixed(1) || 'N/A'}</strong>/5
                    </span>
                  </div>
                </div>

                {/* Dernière activité */}
                <div className="flex items-center gap-2 text-xs text-gray-500 pt-2 border-t border-gray-200">
                  <Clock className="h-3 w-3" />
                  <span>{formatLastActivity(user.last_activity)}</span>
                </div>
              </div>
            ))
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <Users className="h-12 w-12 mb-3 opacity-50" />
              <p className="font-medium">Aucun utilisateur trouvé</p>
              <p className="text-sm text-gray-400 mt-1">Essayez de modifier vos filtres</p>
            </div>
          )}
        </div>

        {/* Footer avec statistiques */}
        <div className="p-4 bg-gray-50 border-t border-gray-200">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600">Total utilisateurs :</span>
            <span className="font-bold text-gray-900">{users?.length || 0}</span>
          </div>
        </div>
      </div>
    </>
  );
}

