import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Badge } from '@/components/common/Badge';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useTasks, useDashboardMetrics } from '@/hooks/useApi';
import { formatRelativeTime, formatPriority, formatDuration, formatCurrency } from '@/utils/format';
import { getPriorityColor } from '@/utils/colors';
import { 
  Search, 
  RefreshCw, 
  CheckCircle, 
  XCircle, 
  Clock, 
  DollarSign,
  Activity,
  TrendingUp,
  AlertCircle,
  GitBranch
} from 'lucide-react';
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

type PriorityFilter = 'all' | 'low' | 'medium' | 'high' | 'urgent';
type LanguageFilter = 'all' | 'Python' | 'Java' | 'JavaScript' | 'TypeScript' | 'PHP' | 'Ruby' | 'Go' | 'Rust';

export function TasksPage() {
  // Filtres de recherche
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all');
  const [languageFilter, setLanguageFilter] = useState<LanguageFilter>('all');
  
  // Filtres de période
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [selectedMonth, setSelectedMonth] = useState<string>(''); // Format: YYYY-MM
  
  const { data: tasksData, isLoading, refetch } = useTasks({
    status: statusFilter || undefined,
    priority: priorityFilter !== 'all' ? priorityFilter : undefined,
    per_page: 100, // Augmenter le nombre de tâches affichées
    page: 1,
  });

  const metricsQuery = useDashboardMetrics();
  const metrics = metricsQuery.data as any;

  const tasks = useMemo(() => (tasksData as any)?.items || [], [tasksData]);

  // Fonction de filtrage avancée
  const filteredTasks = useMemo(() => {
    return tasks.filter((task: any) => {
      // Filtre de recherche textuelle
      const matchesSearch = !searchQuery || 
        task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        task.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (task.repository_url && task.repository_url.toLowerCase().includes(searchQuery.toLowerCase()));

      // Filtre de priorité
      const matchesPriority = priorityFilter === 'all' || task.priority === priorityFilter;

      // Filtre de langage (basé sur repository_url)
      const matchesLanguage = languageFilter === 'all' || 
        (task.repository_url && task.repository_url.toLowerCase().includes(languageFilter.toLowerCase()));

      // Filtre par mois sélectionné
      let matchesMonth = true;
      if (selectedMonth) {
        const taskDate = new Date(task.created_at);
        const taskMonth = `${taskDate.getFullYear()}-${String(taskDate.getMonth() + 1).padStart(2, '0')}`;
        matchesMonth = taskMonth === selectedMonth;
      }

      // Filtre de date (plage personnalisée)
      const matchesDateFrom = !dateFrom || new Date(task.created_at) >= new Date(dateFrom);
      const matchesDateTo = !dateTo || new Date(task.created_at) <= new Date(dateTo);

      return matchesSearch && matchesPriority && matchesLanguage && matchesMonth && matchesDateFrom && matchesDateTo;
    });
  }, [tasks, searchQuery, priorityFilter, languageFilter, selectedMonth, dateFrom, dateTo]);

  // Statistiques calculées (utiliser internal_status de la DB)
  const stats = useMemo(() => {
    const completed = filteredTasks.filter((t: any) => t.internal_status === 'completed').length;
    const failed = filteredTasks.filter((t: any) => t.internal_status === 'failed').length;
    const processing = filteredTasks.filter((t: any) => ['processing', 'testing', 'debugging', 'quality_check'].includes(t.internal_status)).length;
    const pending = filteredTasks.filter((t: any) => t.internal_status === 'pending').length;
    
    const totalRuns = filteredTasks.reduce((sum: number, t: any) => sum + (t.runs?.length || 0), 0);
    const avgDuration = filteredTasks
      .filter((t: any) => t.runs && t.runs[0] && t.runs[0].duration_seconds)
      .reduce((sum: number, t: any) => sum + (t.runs[0].duration_seconds || 0), 0) / (filteredTasks.length || 1);

    return {
      total: filteredTasks.length,
      completed,
      failed,
      processing,
      pending,
      successRate: filteredTasks.length > 0 ? (completed / (completed + failed || 1)) * 100 : 0,
      avgDuration,
      totalRuns
    };
  }, [filteredTasks]);

  // Fonction de réinitialisation
  const handleReset = () => {
    setSearchQuery('');
    setStatusFilter('');
    setPriorityFilter('all');
    setLanguageFilter('all');
    setSelectedMonth('');
    setDateFrom('');
    setDateTo('');
    refetch();
  };

  // Données pour les graphiques (basées sur internal_status de la DB)
  const chartData = useMemo(() => {
    // Données par statut (internal_status de la base de données)
    const statusCount = filteredTasks.reduce((acc: Record<string, number>, task: any) => {
      const status = task.internal_status || 'pending';
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    // Grouper les statuts "en cours" (processing, testing, debugging, quality_check)
    const processingCount = (statusCount.processing || 0) + 
                           (statusCount.testing || 0) + 
                           (statusCount.debugging || 0) + 
                           (statusCount.quality_check || 0);

    const statusData = [
      { name: 'En attente', value: statusCount.pending || 0, color: '#FBBF24' },
      { name: 'En cours', value: processingCount, color: '#3B82F6' },
      { name: 'Terminées', value: statusCount.completed || 0, color: '#10B981' },
      { name: 'Échouées', value: statusCount.failed || 0, color: '#EF4444' }
    ].filter(item => item.value > 0);

    // Données par priorité (filtrer les undefined)
    const priorityCount = filteredTasks.reduce((acc: Record<string, number>, task: any) => {
      if (task.priority && task.priority !== 'undefined') {
        acc[task.priority] = (acc[task.priority] || 0) + 1;
      }
      return acc;
    }, {} as Record<string, number>);

    const priorityData = [
      { name: 'Basse', value: priorityCount.low || 0, color: '#10B981' },
      { name: 'Moyenne', value: priorityCount.medium || 0, color: '#FBBF24' },
      { name: 'Haute', value: priorityCount.high || 0, color: '#F97316' }
    ].filter(item => item.value > 0);

    return { statusData, priorityData };
  }, [filteredTasks]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Tâches</h1>
          <p className="text-gray-500 mt-1">
            Gestion et suivi des tâches d'automatisation
            <span className="ml-3 text-sm font-semibold text-blue-600">
              ({(tasksData as any)?.total || 0} dans la base • {tasks.length} chargées • {filteredTasks.length} affichées)
            </span>
          </p>
        </div>
        <Button
          variant="primary"
          size="md"
          onClick={() => refetch()}
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Actualiser
        </Button>
      </div>

      {/* Avertissement si pagination */}
      {(tasksData as any)?.total > tasks.length && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
          <div className="flex items-start">
            <AlertCircle className="h-5 w-5 text-yellow-400 mt-0.5 mr-3" />
            <div>
              <p className="text-sm font-medium text-yellow-800">
                Affichage partiel des tâches
              </p>
              <p className="text-sm text-yellow-700 mt-1">
                Seulement {tasks.length} tâches sur {(tasksData as any)?.total} sont chargées. 
                Utilisez les filtres pour affiner votre recherche ou augmentez le nombre de tâches par page.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Total des tâches */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total des tâches</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">{stats.total}</p>
              <p className="text-xs text-gray-500 mt-1">
                {stats.processing} en cours • {stats.pending} en attente
              </p>
            </div>
            <Activity className="h-10 w-10 text-blue-500" />
          </div>
        </Card>

        {/* Taux de succès */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Taux de succès</p>
              <p className="text-3xl font-bold text-green-600 mt-2">
                {stats.successRate.toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {stats.completed} réussies • {stats.failed} échouées
              </p>
            </div>
            <CheckCircle className="h-10 w-10 text-green-500" />
          </div>
        </Card>

        {/* Temps moyen */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Temps moyen</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {formatDuration(stats.avgDuration)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Par tâche
              </p>
            </div>
            <Clock className="h-10 w-10 text-yellow-500" />
          </div>
        </Card>

        {/* Coût IA */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Coût IA total</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {formatCurrency((metrics as any)?.ai_cost_this_month || 0)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Ce mois
              </p>
            </div>
            <DollarSign className="h-10 w-10 text-purple-500" />
          </div>
        </Card>
      </div>

      {/* Filtres multicritères */}
      <div>
        <Card>
          <div className="space-y-4">
            {/* En-tête des filtres */}
            <div className="border-b pb-3">
              <h3 className="text-lg font-semibold text-gray-900">Filtres de recherche</h3>
              <p className="text-sm text-gray-500">Affinez votre recherche avec plusieurs critères</p>
            </div>

          {/* Ligne 1: Recherche + Statut + Priorité */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Search */}
            <div className="relative">
              <label className="block text-xs font-medium text-gray-600 mb-1">Recherche</label>
              <Search className="absolute left-3 top-[34px] -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
                placeholder="Titre, description, repository..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10 w-full"
            />
          </div>

          {/* Status Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Statut</label>
          <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="input w-full"
          >
            <option value="">Tous les statuts</option>
            <option value="pending">En attente</option>
                <option value="processing">En traitement</option>
                <option value="testing">En test</option>
                <option value="debugging">En débogage</option>
                <option value="quality_check">Vérification qualité</option>
            <option value="completed">Terminé</option>
            <option value="failed">Échoué</option>
              </select>
            </div>

          {/* Priority Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Priorité</label>
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value as PriorityFilter)}
                className="input w-full"
              >
                <option value="all">Toutes</option>
                <option value="low">Basse</option>
                <option value="medium">Moyenne</option>
                <option value="high">Haute</option>
          </select>
            </div>
          </div>

          {/* Ligne 2: Langage + Mois + Période */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Language Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Langage</label>
              <select
                value={languageFilter}
                onChange={(e) => setLanguageFilter(e.target.value as LanguageFilter)}
                className="input w-full"
              >
                <option value="all">Tous</option>
                <option value="Python">Python</option>
                <option value="Java">Java</option>
                <option value="JavaScript">JavaScript</option>
                <option value="TypeScript">TypeScript</option>
                <option value="PHP">PHP</option>
                <option value="Ruby">Ruby</option>
                <option value="Go">Go</option>
                <option value="Rust">Rust</option>
              </select>
            </div>

            {/* Month Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Mois</label>
              <input
                type="month"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
                className="input w-full"
                placeholder="Sélectionner un mois"
              />
            </div>

            {/* Date From */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Date début</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="input w-full"
              />
            </div>

            {/* Date To */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Date fin</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="input w-full"
              />
            </div>
          </div>

          {/* Boutons d'action */}
          <div className="flex gap-2 pt-2">
            <Button
              variant="primary"
              size="md"
              onClick={() => refetch()}
              className="flex-1"
            >
              <Search className="h-4 w-4 mr-2" />
              Rechercher ({filteredTasks.length} résultats)
            </Button>
          <Button
            variant="secondary"
            size="md"
              onClick={handleReset}
          >
              <RefreshCw className="h-4 w-4 mr-2" />
              Réinitialiser
          </Button>
          </div>

          {/* Indicateur de filtres actifs */}
          {(searchQuery || statusFilter || priorityFilter !== 'all' || languageFilter !== 'all' || selectedMonth || dateFrom || dateTo) && (
            <div className="text-xs text-blue-600 bg-blue-50 px-3 py-2 rounded">
              <strong>Filtres actifs:</strong>
              {searchQuery && ` Recherche: "${searchQuery}"`}
              {statusFilter && ` • Statut: ${statusFilter}`}
              {priorityFilter !== 'all' && ` • Priorité: ${priorityFilter}`}
              {languageFilter !== 'all' && ` • Langage: ${languageFilter}`}
              {selectedMonth && ` • Mois: ${selectedMonth}`}
              {(dateFrom || dateTo) && ` • Période: ${dateFrom || '...'} → ${dateTo || '...'}`}
            </div>
          )}
          </div>
        </Card>
      </div>

      {/* Graphiques analytiques - Basés sur internal_status de la DB */}
      {filteredTasks.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Répartition par statut */}
          <Card>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-gray-900">Répartition par statut</h3>
                <span className="text-xs text-gray-500">{filteredTasks.length} tâches</span>
              </div>
              {chartData.statusData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={chartData.statusData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {chartData.statusData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[250px] text-gray-400 text-sm">
                  Aucune donnée
                </div>
              )}
            </div>
          </Card>

          {/* Répartition par priorité */}
          <Card>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-gray-900">Répartition par priorité</h3>
                <span className="text-xs text-gray-500">{chartData.priorityData.length} niveaux</span>
              </div>
              {chartData.priorityData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={chartData.priorityData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="value" name="Tâches" radius={[8, 8, 0, 0]}>
                      {chartData.priorityData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[250px] text-gray-400 text-sm">
                  Aucune donnée
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Tasks List */}
      {filteredTasks.length === 0 ? (
        <Card>
          <div className="text-center py-12 text-gray-500">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-gray-400" />
            <p className="text-lg font-medium">Aucune tâche trouvée</p>
            <p className="text-sm mt-2">Essayez de modifier vos filtres ou créez une nouvelle tâche</p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredTasks.map((task: any) => {
            const hasRuns = Array.isArray(task.runs) && task.runs.length > 0;
            const lastRun = hasRuns ? task.runs[0] : null;
            
            return (
              <Card key={task.tasks_id} className="hover:shadow-lg transition-all duration-200 hover:border-blue-300">
              <Link to={`/tasks/${task.tasks_id}`}>
                  <div className="space-y-4">
                    {/* Header: Titre + Statut */}
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 truncate">
                        {task.title}
                      </h3>
                      <StatusBadge status={task.internal_status} />
                          {hasRuns && lastRun?.pr_url && (
                            <a
                              href={lastRun.pr_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs px-2 py-1 bg-green-50 text-green-700 rounded-full hover:bg-green-100 transition-colors"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <GitBranch className="h-3 w-3 inline mr-1" />
                              PR Créée
                            </a>
                          )}
                        </div>
                        
                        <p className="text-sm text-gray-600 line-clamp-2">
                          {task.description}
                        </p>
                      </div>
                    </div>
                    
                    {/* Badges: Priorité + Repository */}
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge className={getPriorityColor(task.priority)}>
                        {formatPriority(task.priority)}
                      </Badge>

                      {task.repository_url && (
                        <span className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded-full font-mono flex items-center gap-1">
                          <GitBranch className="h-3 w-3" />
                          {task.repository_url.split('/').slice(-2).join('/')}
                        </span>
                      )}
                    </div>

                    {/* Statistiques détaillées */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 pt-3 border-t">
                      {/* Date de création */}
                      <div className="text-center">
                        <p className="text-xs text-gray-500 mb-1">Créée</p>
                        <p className="text-sm font-semibold text-gray-900">
                        {formatRelativeTime(task.created_at)}
                        </p>
                      </div>

                      {/* Nombre d'exécutions */}
                      <div className="text-center">
                        <p className="text-xs text-gray-500 mb-1">Exécutions</p>
                        <p className="text-sm font-semibold text-gray-900">
                          {task.runs?.length || 0}
                        </p>
                      </div>

                      {/* Durée d'exécution */}
                      {hasRuns && lastRun?.duration_seconds ? (
                        <div className="text-center">
                          <p className="text-xs text-gray-500 mb-1">Durée</p>
                          <p className="text-sm font-semibold text-gray-900">
                            <Clock className="h-3 w-3 inline mr-1" />
                            {formatDuration(lastRun.duration_seconds)}
                          </p>
                        </div>
                      ) : (
                        <div className="text-center">
                          <p className="text-xs text-gray-500 mb-1">Durée</p>
                          <p className="text-sm text-gray-400">—</p>
                        </div>
                      )}

                      {/* Coût estimé (basé sur durée) */}
                      {hasRuns && lastRun?.duration_seconds ? (
                        <div className="text-center">
                          <p className="text-xs text-gray-500 mb-1">Coût IA</p>
                          <p className="text-sm font-semibold text-purple-600">
                            <DollarSign className="h-3 w-3 inline mr-1" />
                            {formatCurrency((lastRun.duration_seconds / 60) * 0.05)}
                          </p>
                        </div>
                      ) : (
                        <div className="text-center">
                          <p className="text-xs text-gray-500 mb-1">Coût IA</p>
                          <p className="text-sm text-gray-400">—</p>
                        </div>
                      )}

                      {/* Taux de succès */}
                      <div className="text-center">
                        <p className="text-xs text-gray-500 mb-1">Succès</p>
                        {hasRuns && Array.isArray(task.runs) && task.runs.length > 0 ? (
                          <p className="text-sm font-semibold text-green-600">
                            {((task.runs.filter((r: any) => r.status === 'completed').length / task.runs.length) * 100).toFixed(0)}%
                          </p>
                        ) : (
                          <p className="text-sm text-gray-400">—</p>
                        )}
                      </div>
                    </div>

                    {/* Informations supplémentaires pour échecs */}
                    {hasRuns && lastRun?.status === 'failed' && lastRun.error_message && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                        <div className="flex items-start gap-2">
                          <XCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                          <div className="flex-1">
                            <p className="text-xs font-medium text-red-800 mb-1">Dernière erreur</p>
                            <p className="text-xs text-red-700 line-clamp-2">{lastRun.error_message}</p>
                          </div>
                    </div>
                  </div>
                    )}

                    {/* Badge de tâche récente */}
                    {new Date().getTime() - new Date(task.created_at).getTime() < 24 * 60 * 60 * 1000 && (
                      <div className="absolute top-4 right-4">
                        <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-medium rounded-full flex items-center gap-1">
                          <TrendingUp className="h-3 w-3" />
                          Nouveau
                        </span>
                  </div>
                    )}
                </div>
              </Link>
            </Card>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {tasksData && (tasksData as any).pages > 1 && (
        <Card>
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Page {(tasksData as any).page} sur {(tasksData as any).pages} ({(tasksData as any).total} tâches)
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={(tasksData as any).page === 1}>
                Précédent
              </Button>
              <Button variant="secondary" size="sm" disabled={(tasksData as any).page === (tasksData as any).pages}>
                Suivant
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

