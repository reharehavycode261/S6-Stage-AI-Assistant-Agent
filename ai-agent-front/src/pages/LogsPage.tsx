/**
 * LogsPage - Page de visualisation des logs avec filtres avancés
 * Fonctionnalités:
 * - Recherche full-text (regex, mots-clés)
 * - Export logs (CSV, JSON)
 * - Filtres avancés (service, niveau, temps, task_id)
 * - Lien direct vers TaskDetailPage
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Terminal, 
  Download, 
  Search, 
  Filter, 
  RefreshCw, 
  ExternalLink,
  Calendar,
  AlertCircle,
  Info,
  AlertTriangle,
  XCircle,
  Bug
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { getLogLevelColor } from '@/utils/colors';
import { formatFullDate } from '@/utils/format';

interface LogEntry {
  id: number;
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  service: string;
  message: string;
  task_id?: string;
  workflow_id?: string;
  context?: Record<string, any>;
}

type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
type ServiceType = 'celery' | 'api' | 'workflow' | 'database' | 'monitoring' | 'webhook';

export function LogsPage() {
  const navigate = useNavigate();
  
  // État des logs
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filteredLogs, setFilteredLogs] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // Filtres
  const [searchTerm, setSearchTerm] = useState('');
  const [useRegex, setUseRegex] = useState(false);
  const [selectedLevel, setSelectedLevel] = useState<LogLevel | ''>('');
  const [selectedService, setSelectedService] = useState<ServiceType | ''>('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [taskIdFilter, setTaskIdFilter] = useState('');
  const [workflowIdFilter, setWorkflowIdFilter] = useState('');
  
  // Statistiques
  const [stats, setStats] = useState({
    total: 0,
    errors: 0,
    warnings: 0,
    info: 0
  });

  // Charger les logs (simulé - à remplacer par vrai API)
  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    setIsLoading(true);
    try {
      // TODO: Remplacer par vrai appel API
      // const response = await apiClient.getLogs(filters);
      
      // Données mockées pour démonstration
      const mockLogs: LogEntry[] = [
        { 
          id: 1, 
          timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), 
          level: 'INFO', 
          service: 'celery', 
          message: 'Task "generate_tests" completed successfully in 45.2s',
          task_id: 'task-123',
          workflow_id: 'wf-456',
          context: { duration: 45.2, status: 'success' }
        },
        { 
          id: 2, 
          timestamp: new Date(Date.now() - 1000 * 60 * 10).toISOString(), 
          level: 'WARNING', 
          service: 'api', 
          message: 'High memory usage detected: 85% used (6.8GB/8GB)',
          context: { memory_used: 6.8, memory_total: 8, percentage: 85 }
        },
        { 
          id: 3, 
          timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(), 
          level: 'ERROR', 
          service: 'workflow', 
          message: 'Failed to clone repository: Authentication failed for https://github.com/user/repo.git',
          task_id: 'task-124',
          workflow_id: 'wf-457',
          context: { error: 'AuthenticationError', repo: 'user/repo' }
        },
        { 
          id: 4, 
          timestamp: new Date(Date.now() - 1000 * 60 * 20).toISOString(), 
          level: 'CRITICAL', 
          service: 'database', 
          message: 'Connection pool exhausted: Cannot acquire connection from pool',
          context: { pool_size: 20, active_connections: 20 }
        },
        { 
          id: 5, 
          timestamp: new Date(Date.now() - 1000 * 60 * 25).toISOString(), 
          level: 'DEBUG', 
          service: 'webhook', 
          message: 'Received webhook from Monday.com: item_updated event',
          context: { event_type: 'item_updated', board_id: '5084415062' }
        },
        { 
          id: 6, 
          timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(), 
          level: 'INFO', 
          service: 'monitoring', 
          message: 'Health check passed: All services operational',
          context: { celery: 'up', rabbitmq: 'up', postgres: 'up', redis: 'up' }
        },
      ];
      
      setLogs(mockLogs);
      setFilteredLogs(mockLogs);
      
      // Calculer les stats
      setStats({
        total: mockLogs.length,
        errors: mockLogs.filter(l => l.level === 'ERROR' || l.level === 'CRITICAL').length,
        warnings: mockLogs.filter(l => l.level === 'WARNING').length,
        info: mockLogs.filter(l => l.level === 'INFO').length,
      });
      
    } catch (error) {
      console.error('Failed to load logs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Appliquer les filtres
  useEffect(() => {
    let filtered = [...logs];

    // Filtre par recherche
    if (searchTerm) {
      if (useRegex) {
        try {
          const regex = new RegExp(searchTerm, 'i');
          filtered = filtered.filter(log => regex.test(log.message));
        } catch (e) {
          // Regex invalide, fallback sur recherche normale
          filtered = filtered.filter(log => 
            log.message.toLowerCase().includes(searchTerm.toLowerCase())
          );
        }
      } else {
        filtered = filtered.filter(log => 
          log.message.toLowerCase().includes(searchTerm.toLowerCase())
        );
      }
    }

    // Filtre par niveau
    if (selectedLevel) {
      filtered = filtered.filter(log => log.level === selectedLevel);
    }

    // Filtre par service
    if (selectedService) {
      filtered = filtered.filter(log => log.service === selectedService);
    }

    // Filtre par date
    if (startDate) {
      filtered = filtered.filter(log => new Date(log.timestamp) >= new Date(startDate));
    }
    if (endDate) {
      filtered = filtered.filter(log => new Date(log.timestamp) <= new Date(endDate));
    }

    // Filtre par task_id
    if (taskIdFilter) {
      filtered = filtered.filter(log => log.task_id?.includes(taskIdFilter));
    }

    // Filtre par workflow_id
    if (workflowIdFilter) {
      filtered = filtered.filter(log => log.workflow_id?.includes(workflowIdFilter));
    }

    setFilteredLogs(filtered);
  }, [logs, searchTerm, useRegex, selectedLevel, selectedService, startDate, endDate, taskIdFilter, workflowIdFilter]);

  // Export en CSV
  const exportToCSV = () => {
    const headers = ['Timestamp', 'Level', 'Service', 'Message', 'Task ID', 'Workflow ID'];
    const csvData = filteredLogs.map(log => [
      log.timestamp,
      log.level,
      log.service,
      `"${log.message.replace(/"/g, '""')}"`, // Échapper les guillemets
      log.task_id || '',
      log.workflow_id || ''
    ]);

    const csv = [
      headers.join(','),
      ...csvData.map(row => row.join(','))
    ].join('\n');

    downloadFile(csv, 'logs.csv', 'text/csv');
  };

  // Export en JSON
  const exportToJSON = () => {
    const json = JSON.stringify(filteredLogs, null, 2);
    downloadFile(json, 'logs.json', 'application/json');
  };

  // Helper pour télécharger un fichier
  const downloadFile = (content: string, filename: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  // Réinitialiser les filtres
  const resetFilters = () => {
    setSearchTerm('');
    setUseRegex(false);
    setSelectedLevel('');
    setSelectedService('');
    setStartDate('');
    setEndDate('');
    setTaskIdFilter('');
    setWorkflowIdFilter('');
  };

  // Icône selon le niveau
  const getLevelIcon = (level: LogLevel) => {
    switch (level) {
      case 'DEBUG': return <Bug className="w-4 h-4" />;
      case 'INFO': return <Info className="w-4 h-4" />;
      case 'WARNING': return <AlertTriangle className="w-4 h-4" />;
      case 'ERROR': return <XCircle className="w-4 h-4" />;
      case 'CRITICAL': return <AlertCircle className="w-4 h-4" />;
    }
  };

  // Couleur de bordure selon le niveau
  const getLevelBorderColor = (level: LogLevel) => {
    switch (level) {
      case 'DEBUG': return '#6b7280';
      case 'INFO': return '#10b981';
      case 'WARNING': return '#f59e0b';
      case 'ERROR': return '#ef4444';
      case 'CRITICAL': return '#dc2626';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gray-100 rounded-xl">
            <Terminal className="w-6 h-6 text-gray-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Logs & Debugging</h1>
            <p className="text-gray-600">Logs système en temps réel avec filtres avancés</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button onClick={loadLogs} variant="secondary" className="flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Actualiser
          </Button>
        </div>
      </div>

      {/* Statistiques */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total</p>
              <p className="text-2xl font-bold text-gray-900">{filteredLogs.length}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-lg">
              <Terminal className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Erreurs</p>
              <p className="text-2xl font-bold text-red-600">{stats.errors}</p>
            </div>
            <div className="p-3 bg-red-100 rounded-lg">
              <XCircle className="w-6 h-6 text-red-600" />
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Avertissements</p>
              <p className="text-2xl font-bold text-yellow-600">{stats.warnings}</p>
            </div>
            <div className="p-3 bg-yellow-100 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-yellow-600" />
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
      <div>
              <p className="text-sm text-gray-600">Info</p>
              <p className="text-2xl font-bold text-green-600">{stats.info}</p>
            </div>
            <div className="p-3 bg-green-100 rounded-lg">
              <Info className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </Card>
      </div>

      {/* Filtres avancés */}
      <Card>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-gray-600" />
              <h3 className="text-lg font-semibold text-gray-900">Filtres avancés</h3>
            </div>
            <Button onClick={resetFilters} variant="secondary" size="sm">
              Réinitialiser
            </Button>
          </div>

          {/* Recherche full-text */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Recherche full-text
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Rechercher dans les messages..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <label className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50">
                <input
                  type="checkbox"
                  checked={useRegex}
                  onChange={(e) => setUseRegex(e.target.checked)}
                  className="rounded text-blue-600"
                />
                <span className="text-sm text-gray-700">Regex</span>
              </label>
            </div>
          </div>

          {/* Grille de filtres */}
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {/* Niveau */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Niveau
              </label>
              <select
                value={selectedLevel}
                onChange={(e) => setSelectedLevel(e.target.value as LogLevel | '')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Tous</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
            </div>

            {/* Service */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Service
              </label>
              <select
                value={selectedService}
                onChange={(e) => setSelectedService(e.target.value as ServiceType | '')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Tous</option>
                <option value="celery">Celery</option>
                <option value="api">API</option>
                <option value="workflow">Workflow</option>
                <option value="database">Database</option>
                <option value="monitoring">Monitoring</option>
                <option value="webhook">Webhook</option>
              </select>
            </div>

            {/* Date début */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Date début
              </label>
              <input
                type="datetime-local"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Date fin */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Date fin
              </label>
              <input
                type="datetime-local"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Task ID */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Task ID
              </label>
              <input
                type="text"
                value={taskIdFilter}
                onChange={(e) => setTaskIdFilter(e.target.value)}
                placeholder="task-123"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Workflow ID */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Workflow ID
              </label>
              <input
                type="text"
                value={workflowIdFilter}
                onChange={(e) => setWorkflowIdFilter(e.target.value)}
                placeholder="wf-456"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Actions d'export */}
          <div className="flex items-center gap-2 pt-4 border-t border-gray-200">
            <Button onClick={exportToCSV} variant="secondary" className="flex items-center gap-2">
              <Download className="w-4 h-4" />
              Exporter CSV
            </Button>
            <Button onClick={exportToJSON} variant="secondary" className="flex items-center gap-2">
              <Download className="w-4 h-4" />
              Exporter JSON
            </Button>
            <span className="text-sm text-gray-600 ml-auto">
              {filteredLogs.length} log(s) affiché(s) sur {logs.length}
            </span>
          </div>
        </div>
      </Card>

      {/* Liste des logs */}
      <Card>
        <div className="p-6">
          <div className="space-y-2">
            {filteredLogs.length === 0 ? (
              <div className="text-center py-12">
                <Terminal className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">Aucun log ne correspond aux filtres</p>
              </div>
            ) : (
              filteredLogs.map((log) => (
                <div
                  key={log.id}
                  className="p-4 bg-gray-50 rounded-lg border-l-4 hover:bg-gray-100 transition-colors"
                  style={{ borderLeftColor: getLevelBorderColor(log.level) }}
                >
                  {/* Header du log */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className={`flex items-center gap-1 px-2 py-1 rounded ${getLogLevelColor(log.level)}`}>
                        {getLevelIcon(log.level)}
                        <span className="text-xs font-medium">{log.level}</span>
                      </div>
                      
                      <Badge variant="secondary" className="text-xs">
                        {log.service}
                      </Badge>
                      
                      {log.task_id && (
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-gray-500 font-mono">{log.task_id}</span>
                          <button
                            onClick={() => navigate(`/tasks/${log.task_id}`)}
                            className="p-1 hover:bg-gray-200 rounded transition-colors"
                            title="Voir le détail de la tâche"
                          >
                            <ExternalLink className="w-3 h-3 text-blue-600" />
                          </button>
                        </div>
                      )}
                      
                      {log.workflow_id && (
                        <span className="text-xs text-gray-500 font-mono">
                          {log.workflow_id}
                        </span>
                      )}
                    </div>
                    
                <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-gray-400" />
                      <span className="text-xs text-gray-500">
                        {formatFullDate(log.timestamp)}
                      </span>
                    </div>
                  </div>

                  {/* Message */}
                  <p className="text-sm text-gray-900 font-mono mb-2">
                    {log.message}
                  </p>

                  {/* Context (si présent) */}
                  {log.context && Object.keys(log.context).length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-gray-600 cursor-pointer hover:text-gray-900">
                        Voir le contexte
                      </summary>
                      <pre className="mt-2 p-2 bg-gray-900 text-green-400 rounded text-xs overflow-x-auto">
                        {JSON.stringify(log.context, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              ))
            )}
            </div>
        </div>
      </Card>
    </div>
  );
}
