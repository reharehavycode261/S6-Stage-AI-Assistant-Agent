import { Users, TrendingUp, TrendingDown, UserCheck, UserX, Star, AlertTriangle } from 'lucide-react';
import { Card } from '@/components/common/Card';
import { useUsersGlobalStats } from '@/hooks/useUserData';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';

interface GlobalUserStats {
  total_users: number;
  active_users: number;
  suspended_users: number;
  restricted_users: number;
  avg_satisfaction: number;
  avg_tasks_per_user: number;
  success_rate: number;
  total_tasks_completed: number;
  total_tasks_failed: number;
  trend_percentage: number; // Variation par rapport à la période précédente
}

export function UserStatsCard() {
  const { data: stats, isLoading } = useUsersGlobalStats();

  if (isLoading) {
    return (
      <Card title="Statistiques utilisateurs">
        <div className="flex items-center justify-center h-40">
          <LoadingSpinner size="md" />
        </div>
      </Card>
    );
  }

  const globalStats = stats as GlobalUserStats;

  if (!globalStats) {
    return (
      <Card title="Statistiques utilisateurs">
        <div className="text-center py-8 text-gray-500">
          <Users className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>Aucune donnée disponible</p>
        </div>
      </Card>
    );
  }

  const successRate = globalStats.total_tasks_completed > 0
    ? (globalStats.total_tasks_completed / (globalStats.total_tasks_completed + globalStats.total_tasks_failed)) * 100
    : 0;

  return (
    <Card>
      <div className="space-y-6">
        {/* En-tête */}
        <div className="flex items-center justify-between border-b border-gray-200 pb-4">
          <div>
            <h3 className="text-xl font-bold text-gray-900">Statistiques utilisateurs</h3>
            <p className="text-sm text-gray-600 mt-1">Vue d'ensemble de l'activité utilisateur</p>
          </div>
          <div className="w-12 h-12 bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl flex items-center justify-center">
            <Users className="h-6 w-6 text-blue-600" />
          </div>
        </div>

        {/* Grille principale */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {/* Total utilisateurs */}
          <div className="p-4 bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl border border-blue-200">
            <div className="flex items-center gap-2 mb-2">
              <Users className="h-5 w-5 text-blue-600" />
              <span className="text-sm font-medium text-blue-900">Total</span>
            </div>
            <div className="text-3xl font-bold text-blue-900">{globalStats.total_users}</div>
            <div className="flex items-center gap-1 mt-2">
              {globalStats.trend_percentage > 0 ? (
                <>
                  <TrendingUp className="h-3 w-3 text-green-600" />
                  <span className="text-xs text-green-600 font-medium">+{globalStats.trend_percentage.toFixed(1)}%</span>
                </>
              ) : (
                <>
                  <TrendingDown className="h-3 w-3 text-red-600" />
                  <span className="text-xs text-red-600 font-medium">{globalStats.trend_percentage.toFixed(1)}%</span>
                </>
              )}
            </div>
          </div>

          {/* Utilisateurs actifs */}
          <div className="p-4 bg-gradient-to-br from-green-50 to-green-100 rounded-xl border border-green-200">
            <div className="flex items-center gap-2 mb-2">
              <UserCheck className="h-5 w-5 text-green-600" />
              <span className="text-sm font-medium text-green-900">Actifs</span>
            </div>
            <div className="text-3xl font-bold text-green-900">{globalStats.active_users}</div>
            <div className="text-xs text-green-700 mt-2">
              {((globalStats.active_users / globalStats.total_users) * 100).toFixed(0)}% du total
            </div>
          </div>

          {/* Utilisateurs suspendus */}
          <div className="p-4 bg-gradient-to-br from-red-50 to-red-100 rounded-xl border border-red-200">
            <div className="flex items-center gap-2 mb-2">
              <UserX className="h-5 w-5 text-red-600" />
              <span className="text-sm font-medium text-red-900">Suspendus</span>
            </div>
            <div className="text-3xl font-bold text-red-900">{globalStats.suspended_users}</div>
            <div className="text-xs text-red-700 mt-2">
              {globalStats.total_users > 0 
                ? ((globalStats.suspended_users / globalStats.total_users) * 100).toFixed(0) 
                : 0}% du total
            </div>
          </div>

          {/* Utilisateurs restreints */}
          <div className="p-4 bg-gradient-to-br from-orange-50 to-orange-100 rounded-xl border border-orange-200">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-5 w-5 text-orange-600" />
              <span className="text-sm font-medium text-orange-900">Restreints</span>
            </div>
            <div className="text-3xl font-bold text-orange-900">{globalStats.restricted_users}</div>
            <div className="text-xs text-orange-700 mt-2">
              {globalStats.total_users > 0 
                ? ((globalStats.restricted_users / globalStats.total_users) * 100).toFixed(0) 
                : 0}% du total
            </div>
          </div>
        </div>

        {/* Métriques secondaires */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Satisfaction moyenne */}
          <div className="p-4 bg-gradient-to-r from-yellow-50 to-amber-50 rounded-xl border border-yellow-200">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Star className="h-5 w-5 text-yellow-500" />
                <span className="text-sm font-medium text-gray-700">Satisfaction moyenne</span>
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">
                {globalStats.avg_satisfaction.toFixed(1)}
              </span>
              <span className="text-lg text-gray-600">/5.0</span>
            </div>
            <div className="flex gap-1 mt-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <Star
                  key={star}
                  className={`h-4 w-4 ${
                    star <= Math.round(globalStats.avg_satisfaction)
                      ? 'text-yellow-400 fill-yellow-400'
                      : 'text-gray-300'
                  }`}
                />
              ))}
            </div>
          </div>

          {/* Tâches par utilisateur */}
          <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl border border-purple-200">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="h-5 w-5 text-purple-600" />
              <span className="text-sm font-medium text-gray-700">Tâches/utilisateur</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">
                {globalStats.avg_tasks_per_user.toFixed(1)}
              </span>
              <span className="text-sm text-gray-600">en moyenne</span>
            </div>
            <div className="text-xs text-gray-600 mt-2">
              Total : {globalStats.total_tasks_completed + globalStats.total_tasks_failed} tâches
            </div>
          </div>

          {/* Taux de succès */}
          <div className="p-4 bg-gradient-to-r from-cyan-50 to-blue-50 rounded-xl border border-cyan-200">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="h-5 w-5 text-cyan-600" />
              <span className="text-sm font-medium text-gray-700">Taux de succès</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">
                {successRate.toFixed(1)}%
              </span>
            </div>
            <div className="text-xs text-gray-600 mt-2">
              {globalStats.total_tasks_completed} ✓ / {globalStats.total_tasks_failed} ✗
            </div>
          </div>
        </div>

        {/* Barre de progression visuelle */}
        <div className="p-4 bg-gray-50 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Répartition des statuts</span>
            <span className="text-xs text-gray-500">{globalStats.total_users} utilisateurs</span>
          </div>
          <div className="h-3 bg-gray-200 rounded-full overflow-hidden flex">
            <div
              className="bg-green-500"
              style={{
                width: `${(globalStats.active_users / globalStats.total_users) * 100}%`,
              }}
              title={`${globalStats.active_users} actifs`}
            />
            <div
              className="bg-red-500"
              style={{
                width: `${(globalStats.suspended_users / globalStats.total_users) * 100}%`,
              }}
              title={`${globalStats.suspended_users} suspendus`}
            />
            <div
              className="bg-orange-500"
              style={{
                width: `${(globalStats.restricted_users / globalStats.total_users) * 100}%`,
              }}
              title={`${globalStats.restricted_users} restreints`}
            />
          </div>
          <div className="flex items-center justify-between mt-2 text-xs text-gray-600">
            <span>✓ Actifs ({globalStats.active_users})</span>
            <span>⊘ Suspendus ({globalStats.suspended_users})</span>
            <span>⚠ Restreints ({globalStats.restricted_users})</span>
          </div>
        </div>
      </div>
    </Card>
  );
}

