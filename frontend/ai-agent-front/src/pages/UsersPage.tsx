import { useState } from 'react';
import {
  Users,
  Search,
  Filter,
  Plus,
  Download,
  Bell,
  TrendingUp,
  AlertTriangle,
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { UserHistorySidebar } from '@/components/users/UserHistorySidebar';
import { UserManagementModal } from '@/components/users/UserManagementModal';
import { UserStatsCard } from '@/components/users/UserStatsCard';
import { UserTable } from '@/components/users/UserTable';
import { UserTimeline } from '@/components/users/UserTimeline';
import { UserAlerts } from '@/components/users/UserAlerts';
import { User, UserAccessStatus } from '@/types';
import { useUsers } from '@/hooks/useUserData';

export function UsersPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<UserAccessStatus | 'all'>('all');
  const [sortBy, setSortBy] = useState<'name' | 'last_activity' | 'tasks_completed' | 'satisfaction_score'>('last_activity');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [showAlerts, setShowAlerts] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);
  
  // Sidebar et modal
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Récupérer les utilisateurs avec filtres
  const { data: users, isLoading, refetch } = useUsers({
    access_status: statusFilter === 'all' ? undefined : statusFilter,
    search: searchTerm || undefined,
    sort_by: sortBy,
    order: sortOrder,
  });

  const handleSelectUser = (user: User) => {
    setSelectedUser(user);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedUser(null);
  };

  const handleExportUsers = () => {
    // TODO: Implémenter l'export CSV/Excel
    console.log('Export des utilisateurs...');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Gestion des utilisateurs</h1>
          <p className="text-gray-500 mt-1">
            Administration complète des utilisateurs de l'AI-Agent VyData
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowAlerts(!showAlerts)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              showAlerts
                ? 'bg-orange-600 text-white hover:bg-orange-700'
                : 'bg-orange-100 text-orange-700 hover:bg-orange-200'
            }`}
          >
            <Bell className="h-4 w-4" />
            Alertes
          </button>
          <button
            onClick={() => setShowTimeline(!showTimeline)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              showTimeline
                ? 'bg-purple-600 text-white hover:bg-purple-700'
                : 'bg-purple-100 text-purple-700 hover:bg-purple-200'
            }`}
          >
            <TrendingUp className="h-4 w-4" />
            Timeline
          </button>
          <button
            onClick={handleExportUsers}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <Download className="h-4 w-4" />
            Exporter
          </button>
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Users className="h-4 w-4" />
            Historique
          </button>
        </div>
      </div>

      {/* Alertes utilisateurs */}
      {showAlerts && <UserAlerts />}

      {/* Timeline globale */}
      {showTimeline && <UserTimeline />}

      {/* Statistiques globales */}
      <UserStatsCard />

      {/* Filtres et recherche */}
      <Card>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Filter className="h-5 w-5 text-gray-600" />
              <span className="font-semibold text-gray-900">Filtres et recherche avancée</span>
            </div>
            <button
              onClick={() => {
                setSearchTerm('');
                setStatusFilter('all');
                setSortBy('last_activity');
                setSortOrder('desc');
                refetch();
              }}
              className="text-sm text-blue-600 hover:text-blue-800 underline"
            >
              Réinitialiser les filtres
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Recherche */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Recherche
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Nom, email, rôle..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Filtre de statut */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Statut
              </label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as any)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="all">Tous les statuts</option>
                <option value={UserAccessStatus.AUTHORIZED}>Autorisés</option>
                <option value={UserAccessStatus.SUSPENDED}>Suspendus</option>
                <option value={UserAccessStatus.RESTRICTED}>Restreints</option>
                <option value={UserAccessStatus.PENDING}>En attente</option>
              </select>
            </div>

            {/* Tri */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Trier par
              </label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="last_activity">Dernière activité</option>
                <option value="name">Nom</option>
                <option value="tasks_completed">Tâches complétées</option>
                <option value="satisfaction_score">Satisfaction</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Ordre :</label>
            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium"
            >
              {sortOrder === 'asc' ? '↑ Croissant' : '↓ Décroissant'}
            </button>
            {searchTerm && (
              <span className="text-sm text-gray-600">
                Recherche active : "<strong>{searchTerm}</strong>"
              </span>
            )}
          </div>
        </div>
      </Card>

      {/* Tableau des utilisateurs */}
      {isLoading ? (
        <Card>
          <div className="flex items-center justify-center h-64">
            <LoadingSpinner size="lg" />
          </div>
        </Card>
      ) : (
        <UserTable users={users || []} onSelectUser={handleSelectUser} />
      )}

      {/* Sidebar de l'historique */}
      <UserHistorySidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onSelectUser={handleSelectUser}
        selectedUserId={selectedUser?.user_id}
      />

      {/* Modal de gestion */}
      <UserManagementModal
        userId={selectedUser?.user_id || null}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  );
}
