import { Card } from '@/components/common/Card';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useDashboardMetrics, useSystemHealth, useLanguageStats, useTasksTrend } from '@/hooks/useApi';
import { useWebSocketStore } from '@/stores/useWebSocketStore';
import { formatCurrency, formatDuration } from '@/utils/format';
import {
  Activity,
  Clock,
  DollarSign,
  TrendingUp,
  CheckCircle,
  Calendar,
  RefreshCw,
} from 'lucide-react';
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useMemo, useState } from 'react';
 

type PeriodFilter = 'today' | 'week' | 'month' | '3months' | 'year' | 'all';
type StatusFilter = 'all' | 'completed' | 'failed' | 'active';
type LanguageFilter = 'all' | 'Python' | 'Java' | 'JavaScript' | 'TypeScript' | 'PHP' | 'Ruby' | 'Go' | 'Rust';

export function DashboardPage() {
  // Filtres globaux
  const [periodFilter, setPeriodFilter] = useState<PeriodFilter>('month');
  
  // Filtres pour le graphique des tâches (vides par défaut pour afficher les 7 derniers jours)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [tasksMonth, setTasksMonth] = useState<string>(''); // Vide = 7 derniers jours
  const [tasksYear, setTasksYear] = useState<string>('');
  
  // Filtres pour le graphique des langages (vides par défaut pour afficher le mois en cours)
  const [languageFilter, setLanguageFilter] = useState<LanguageFilter>('all');
  const [langMonth, setLangMonth] = useState<string>(''); // Vide = mois en cours
  const [langYear, setLangYear] = useState<string>('');

  const { data: metrics, isLoading: metricsLoading, refetch: refetchMetrics } = useDashboardMetrics();
  const { data: health, isLoading: healthLoading } = useSystemHealth();
  
  // Cast health to any to avoid type errors
  const healthData = health as any;
  const { data: languageStats, refetch: refetchLanguages } = useLanguageStats({ 
    month: langMonth || undefined, 
    year: langYear || undefined 
  });
  const { data: tasksTrendData, refetch: refetchTrend } = useTasksTrend({ 
    month: tasksMonth || undefined, 
    year: tasksYear || undefined 
  });
  const { activeWorkflows, liveMetrics } = useWebSocketStore();

  // Use live metrics if available, otherwise use fetched metrics
  const displayMetrics = liveMetrics || metrics;

  const isLoading = metricsLoading || healthLoading;

  // Fonction de rafraîchissement
  const handleRefresh = () => {
    refetchMetrics();
    refetchLanguages();
    refetchTrend();
  };

  // ✅ DONNÉES RÉELLES: Distribution des langages depuis l'API (avec filtres)
  const languageDistribution = useMemo(() => {
    if (!languageStats || !Array.isArray(languageStats) || languageStats.length === 0) {
      return [{ name: 'Aucune donnée', value: 100, color: '#94A3B8' }];
    }
    
    const colors: Record<string, string> = {
      'Python': '#3776AB',
      'Java': '#007396',
      'JavaScript': '#F7DF1E',
      'TypeScript': '#3178C6',
      'PHP': '#777BB4',
      'Ruby': '#CC342D',
      'Go': '#00ADD8',
      'Rust': '#CE412B',
      'Autre': '#94A3B8',
    };
    
    // Filtrer par langage si nécessaire
    let filteredStats = languageStats;
    if (languageFilter !== 'all') {
      filteredStats = languageStats.filter((lang: any) => lang.language === languageFilter);
    }
    
    if (filteredStats.length === 0) {
      return [{ name: 'Aucune donnée', value: 100, color: '#94A3B8' }];
    }
    
    return filteredStats.map((lang: any) => ({
      name: lang.language,
      value: lang.percentage,
      color: colors[lang.language] || '#94A3B8',
    }));
  }, [languageStats, languageFilter]);

  // Filtrage des données de tendance
  const filteredTrendData = useMemo(() => {
    if (!tasksTrendData || !Array.isArray(tasksTrendData)) return [];
    
    // Filtrer par statut
    if (statusFilter === 'all') return tasksTrendData;
    
    return tasksTrendData.map((day: any) => {
      if (statusFilter === 'completed') {
        return { ...day, failed: 0 };
      } else if (statusFilter === 'failed') {
        return { ...day, success: 0 };
      }
      return day;
    });
  }, [tasksTrendData, statusFilter]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Vue d'ensemble du système AI-Agent VyData</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Actualiser
          </button>
        </div>
      </div>

      {/* Filtre Période Global */}
      <Card>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Calendar className="h-5 w-5 text-gray-600" />
            <span className="font-medium text-gray-700">Période :</span>
          </div>
          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value as PeriodFilter)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
          >
            <option value="today">Aujourd'hui</option>
            <option value="week">Cette semaine</option>
            <option value="month">Ce mois</option>
            <option value="3months">3 derniers mois</option>
            <option value="year">Cette année</option>
            <option value="all">Toutes les données</option>
          </select>
          {periodFilter !== 'month' && (
            <button
              onClick={() => setPeriodFilter('month')}
              className="text-sm text-blue-600 hover:text-blue-800 underline"
            >
              Réinitialiser
            </button>
          )}
        </div>
      </Card>

          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Tâches actives</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {(displayMetrics as any)?.tasks_active || 0}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {(displayMetrics as any)?.tasks_this_month || 0} ce mois
                  </p>
                </div>
                <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center">
                  <Activity className="h-6 w-6 text-blue-600" />
                </div>
              </div>
            </Card>

            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Taux de succès</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {(displayMetrics as any)?.success_rate_this_month?.toFixed(1) || 0}%
                  </p>
                  <p className="text-xs text-green-600 mt-1 flex items-center">
                    <TrendingUp className="h-3 w-3 mr-1" />
                    +5% vs hier
                  </p>
                </div>
                <div className="w-12 h-12 bg-green-50 rounded-lg flex items-center justify-center">
                  <CheckCircle className="h-6 w-6 text-green-600" />
                </div>
              </div>
            </Card>

            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Temps moyen</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {formatDuration((displayMetrics as any)?.avg_execution_time || 0)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Par tâche</p>
                </div>
                <div className="w-12 h-12 bg-yellow-50 rounded-lg flex items-center justify-center">
                  <Clock className="h-6 w-6 text-yellow-600" />
                </div>
              </div>
            </Card>

            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Coût IA</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {formatCurrency((displayMetrics as any)?.ai_cost_this_month || 0)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Ce mois</p>
                </div>
                <div className="w-12 h-12 bg-purple-50 rounded-lg flex items-center justify-center">
                  <DollarSign className="h-6 w-6 text-purple-600" />
                </div>
              </div>
            </Card>
          </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tasks Trend */}
        <Card>
          <div className="space-y-4">
                {/* En-tête avec titre */}
                <div className="border-b border-pastel-rose-100 pb-3">
                  <h3 className="text-lg font-semibold bg-gradient-to-r from-pastel-rose-600 to-pastel-blue-500 bg-clip-text text-transparent">Évolution des tâches</h3>
                  <p className="text-sm text-gray-600">Filtres multicritères</p>
                </div>

                {/* Filtres multicritères */}
                <div className="space-y-3 bg-gradient-to-r from-pastel-rose-50 to-pastel-blue-50 p-3 rounded-xl border border-pastel-rose-100">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Mois (optionnel)</label>
                      <input
                        type="month"
                        value={tasksMonth}
                        onChange={(e) => setTasksMonth(e.target.value)}
                        placeholder="7 derniers jours"
                        className="w-full px-2 py-1.5 border-2 border-pastel-rose-200 rounded-lg text-sm focus:ring-2 focus:ring-pastel-rose-300 bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Année (optionnel)</label>
                      <select
                        value={tasksYear}
                        onChange={(e) => setTasksYear(e.target.value)}
                        className="w-full px-2 py-1.5 border-2 border-pastel-blue-200 rounded-lg text-sm focus:ring-2 focus:ring-pastel-blue-300 bg-white"
                      >
                        <option value="">Toutes</option>
                        {[2025, 2024, 2023, 2022].map(year => (
                          <option key={year} value={year}>{year}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Statut</label>
                      <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                        className="w-full px-2 py-1.5 border-2 border-pastel-lavender-200 rounded-lg text-sm focus:ring-2 focus:ring-pastel-lavender-300 bg-white"
                      >
                        <option value="all">Tous</option>
                        <option value="completed">✅ Complétées</option>
                        <option value="failed">❌ Échouées</option>
                        <option value="active">🔄 Actives</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => refetchTrend()}
                      className="flex-1 px-4 py-2 bg-gradient-to-r from-pastel-blue-400 to-pastel-lavender-400 text-white rounded-xl hover:from-pastel-blue-500 hover:to-pastel-lavender-500 transition-all text-sm font-medium shadow-md"
                    >
                      🔍 Rechercher
                    </button>
                    <button
                      onClick={() => {
                        setTasksMonth('');
                        setTasksYear('');
                        setStatusFilter('all');
                        setTimeout(() => refetchTrend(), 100);
                      }}
                      className="px-4 py-2 bg-gradient-to-r from-pastel-rose-100 to-pastel-rose-200 text-gray-700 rounded-xl hover:from-pastel-rose-200 hover:to-pastel-rose-300 transition-all text-sm font-medium"
                    >
                      ↺ Réinitialiser
                    </button>
                  </div>
                </div>

                {/* Indicateur de filtres actifs */}
                {(tasksMonth || tasksYear || statusFilter !== 'all') && (
                  <div className="text-xs text-pastel-blue-700 bg-gradient-to-r from-pastel-blue-50 to-pastel-lavender-50 px-3 py-2 rounded-xl border border-pastel-blue-200">
                    <strong>Filtres actifs:</strong> 
                    {tasksMonth && ` Mois: ${tasksMonth}`}
                    {tasksYear && ` • Année: ${tasksYear}`}
                    {statusFilter !== 'all' && ` • Statut: ${statusFilter}`}
                    {!tasksMonth && !tasksYear && statusFilter === 'all' && ' 7 derniers jours'}
                  </div>
                )}

                {/* Graphique */}
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={filteredTrendData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="success" fill="#10b981" name="Succès" />
                    <Bar dataKey="failed" fill="#ef4444" name="Échecs" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Language Distribution */}
            <Card>
              <div className="space-y-4">
                {/* En-tête avec titre */}
                <div className="border-b border-pastel-lavender-100 pb-3">
                  <h3 className="text-lg font-semibold bg-gradient-to-r from-pastel-lavender-600 to-pastel-mint-500 bg-clip-text text-transparent">Langages détectés</h3>
                  <p className="text-sm text-gray-600">Filtres multicritères</p>
                </div>

                {/* Filtres multicritères */}
                <div className="space-y-3 bg-gradient-to-r from-pastel-lavender-50 to-pastel-mint-50 p-3 rounded-xl border border-pastel-lavender-100">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Mois (optionnel)</label>
                      <input
                        type="month"
                        value={langMonth}
                        onChange={(e) => setLangMonth(e.target.value)}
                        placeholder="Mois en cours"
                        className="w-full px-2 py-1.5 border-2 border-pastel-lavender-200 rounded-lg text-sm focus:ring-2 focus:ring-pastel-lavender-300 bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Année (optionnel)</label>
                      <select
                        value={langYear}
                        onChange={(e) => setLangYear(e.target.value)}
                        className="w-full px-2 py-1.5 border-2 border-pastel-mint-200 rounded-lg text-sm focus:ring-2 focus:ring-pastel-mint-300 bg-white"
                      >
                        <option value="">Toutes</option>
                        {[2025, 2024, 2023, 2022].map(year => (
                          <option key={year} value={year}>{year}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Langage</label>
                      <select
                        value={languageFilter}
                        onChange={(e) => setLanguageFilter(e.target.value as LanguageFilter)}
                        className="w-full px-2 py-1.5 border-2 border-pastel-peach-200 rounded-lg text-sm focus:ring-2 focus:ring-pastel-peach-300 bg-white"
                      >
                        <option value="all">Tous</option>
                        <option value="Python">🐍 Python</option>
                        <option value="Java">☕ Java</option>
                        <option value="JavaScript">📜 JavaScript</option>
                        <option value="TypeScript">📘 TypeScript</option>
                        <option value="PHP">🐘 PHP</option>
                        <option value="Ruby">💎 Ruby</option>
                        <option value="Go">🔵 Go</option>
                        <option value="Rust">🦀 Rust</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => refetchLanguages()}
                      className="flex-1 px-4 py-2 bg-gradient-to-r from-pastel-lavender-400 to-pastel-mint-400 text-white rounded-xl hover:from-pastel-lavender-500 hover:to-pastel-mint-500 transition-all text-sm font-medium shadow-md"
                    >
                      🔍 Rechercher
                    </button>
                    <button
                      onClick={() => {
                        setLangMonth('');
                        setLangYear('');
                        setLanguageFilter('all');
                        setTimeout(() => refetchLanguages(), 100);
                      }}
                      className="px-4 py-2 bg-gradient-to-r from-pastel-lavender-100 to-pastel-lavender-200 text-gray-700 rounded-xl hover:from-pastel-lavender-200 hover:to-pastel-lavender-300 transition-all text-sm font-medium"
                    >
                      ↺ Réinitialiser
                    </button>
                  </div>
                </div>

                {/* Indicateur de filtres actifs */}
                {(langMonth || langYear || languageFilter !== 'all') && (
                  <div className="text-xs text-pastel-lavender-700 bg-gradient-to-r from-pastel-lavender-50 to-pastel-mint-50 px-3 py-2 rounded-xl border border-pastel-lavender-200">
                    <strong>Filtres actifs:</strong> 
                    {langMonth && ` Mois: ${langMonth}`}
                    {langYear && ` • Année: ${langYear}`}
                    {languageFilter !== 'all' && ` • Langage: ${languageFilter}`}
                    {!langMonth && !langYear && languageFilter === 'all' && ' Mois en cours'}
                  </div>
                )}

                {/* Graphique */}
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={languageDistribution}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {languageDistribution.map((entry: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          {/* System Health & Active Workflows */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* System Health */}
            <Card title="Santé du système">
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 bg-gradient-to-r from-pastel-mint-50 to-pastel-blue-50 rounded-xl border border-pastel-mint-100">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full shadow-sm ${healthData?.celery_healthy ? 'bg-pastel-mint-400' : 'bg-pastel-coral-400'}`} />
                    <span className="text-sm font-medium text-gray-700">Celery Workers</span>
                  </div>
                  <span className="text-sm text-gray-600 font-medium">
                    {healthData?.celery_workers || 0} actifs
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 bg-gradient-to-r from-pastel-blue-50 to-pastel-lavender-50 rounded-xl border border-pastel-blue-100">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full shadow-sm ${healthData?.rabbitmq_status === 'up' ? 'bg-pastel-mint-400' : 'bg-pastel-coral-400'}`} />
                    <span className="text-sm font-medium text-gray-700">RabbitMQ</span>
                  </div>
                  <span className="text-sm text-gray-600 font-medium">
                    {healthData?.rabbitmq_status === 'up' ? 'En ligne' : 'Hors ligne'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 bg-gradient-to-r from-pastel-lavender-50 to-pastel-rose-50 rounded-xl border border-pastel-lavender-100">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full shadow-sm ${healthData?.postgres_status === 'up' ? 'bg-pastel-mint-400' : 'bg-pastel-coral-400'}`} />
                    <span className="text-sm font-medium text-gray-700">PostgreSQL</span>
                  </div>
                  <span className="text-sm text-gray-600 font-medium">
                    {healthData?.postgres_status === 'up' ? 'En ligne' : 'Hors ligne'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 bg-gradient-to-r from-pastel-rose-50 to-pastel-peach-50 rounded-xl border border-pastel-rose-100">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full shadow-sm ${healthData?.redis_status === 'up' ? 'bg-pastel-mint-400' : 'bg-pastel-coral-400'}`} />
                    <span className="text-sm font-medium text-gray-700">Redis</span>
                  </div>
                  <span className="text-sm text-gray-600 font-medium">
                    {healthData?.redis_status === 'up' ? 'En ligne' : 'Hors ligne'}
                  </span>
                </div>
              </div>
            </Card>

            {/* Active Workflows */}
            <Card
              title="Workflows en cours"
              subtitle={`${activeWorkflows.size} actifs`}
            >
              <div className="space-y-3">
                {activeWorkflows.size === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Activity className="h-12 w-12 mx-auto mb-2 opacity-50 text-pastel-blue-300" />
                    <p className="font-medium">Aucun workflow en cours</p>
                  </div>
                ) : (
                  Array.from(activeWorkflows.values()).slice(0, 5).map((workflow) => (
                    <div
                      key={workflow.workflow_id}
                      className="p-3 bg-gradient-to-r from-pastel-blue-50 to-pastel-lavender-50 rounded-xl border border-pastel-blue-100"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium truncate flex-1 text-gray-700">
                          {workflow.task_id}
                        </span>
                        <span className="text-xs text-pastel-blue-600 font-semibold">
                          {workflow.progress_percentage}%
                        </span>
                      </div>
                      <div className="w-full bg-gradient-to-r from-pastel-rose-100 to-pastel-blue-100 rounded-full h-2">
                        <div
                          className="bg-gradient-to-r from-pastel-blue-400 to-pastel-lavender-400 h-2 rounded-full transition-all shadow-sm"
                          style={{ width: `${workflow.progress_percentage}%` }}
                        />
                      </div>
                      <div className="mt-2 text-xs text-gray-600 font-medium">
                        {workflow.current_node}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
    </div>
  );
}

