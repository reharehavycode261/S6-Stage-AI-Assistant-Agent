import { useState, useEffect } from 'react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { LoadingSpinner } from '../common/LoadingSpinner';

interface BrowserQAResult {
  task_id: number;
  task_title: string;
  executed_at: string;
  success: boolean;
  tests_executed: number;
  tests_passed: number;
  tests_failed: number;
  screenshots?: string[];
  console_errors?: Array<{
    message: string;
    source: string;
    line: number;
  }>;
  network_requests?: Array<{
    url: string;
    method: string;
    status: number;
    duration_ms: number;
  }>;
  performance_metrics?: {
    load_time_ms?: number;
    dom_content_loaded_ms?: number;
    first_contentful_paint_ms?: number;
  };
  test_scenarios?: Array<{
    name: string;
    type: string;
    description: string;
    success: boolean;
  }>;
  error?: string;
}

interface BrowserQAResultsProps {
  taskId?: number;
  limit?: number;
  autoRefresh?: boolean;
}

export const BrowserQAResults = ({ 
  taskId, 
  limit = 10, 
  autoRefresh = false 
}: BrowserQAResultsProps) => {
  const [results, setResults] = useState<BrowserQAResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedResult, setSelectedResult] = useState<BrowserQAResult | null>(null);

  useEffect(() => {
    fetchResults();

    if (autoRefresh) {
      const interval = setInterval(fetchResults, 30000); 
      return () => clearInterval(interval);
    }
  }, [taskId, limit, autoRefresh]);

  const fetchResults = async () => {
    try {
      setLoading(true);
      const url = taskId 
        ? `/api/browser-qa/results/${taskId}`
        : `/api/browser-qa/recent?limit=${limit}`;
      
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch Browser QA results');
      
      const data = await response.json();
      setResults(Array.isArray(data) ? data : [data]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (loading && results.length === 0) {
    return (
      <Card className="p-8">
        <div className="flex justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 border-red-200 bg-red-50">
        <div className="flex items-center gap-3">
          <span className="text-2xl">❌</span>
          <div>
            <h3 className="font-semibold text-red-900">Erreur</h3>
            <p className="text-red-700">{error}</p>
          </div>
        </div>
      </Card>
    );
  }

  if (results.length === 0) {
    return (
      <Card className="p-8 text-center">
        <span className="text-4xl mb-4 block">🌐</span>
        <p className="text-gray-600">Aucun résultat Browser QA disponible</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Liste des résultats */}
      <div className="grid gap-4">
        {results.map((result) => (
          <div 
            key={`${result.task_id}-${result.executed_at}`}
            className={`cursor-pointer transition-all hover:shadow-lg ${
              selectedResult?.task_id === result.task_id ? 'ring-2 ring-blue-500' : ''
            }`}
            onClick={() => setSelectedResult(result)}
          >
            <Card className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  {result.task_title}
                </h3>
                <p className="text-sm text-gray-500">
                  {new Date(result.executed_at).toLocaleString('fr-FR')}
                </p>
              </div>
              <Badge 
                variant={result.success ? 'success' : 'error'}
                className="ml-4"
              >
                {result.success ? '✅ Réussi' : '❌ Échec'}
              </Badge>
            </div>

            <div className="grid grid-cols-4 gap-4 text-center">
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-2xl font-bold text-gray-900">
                  {result.tests_executed}
                </div>
                <div className="text-xs text-gray-600 mt-1">Tests exécutés</div>
              </div>

              <div className="bg-green-50 rounded-lg p-3">
                <div className="text-2xl font-bold text-green-600">
                  {result.tests_passed}
                </div>
                <div className="text-xs text-gray-600 mt-1">Réussis</div>
              </div>

              <div className="bg-red-50 rounded-lg p-3">
                <div className="text-2xl font-bold text-red-600">
                  {result.tests_failed}
                </div>
                <div className="text-xs text-gray-600 mt-1">Échoués</div>
              </div>

              <div className="bg-blue-50 rounded-lg p-3">
                <div className="text-2xl font-bold text-blue-600">
                  {result.screenshots?.length || 0}
                </div>
                <div className="text-xs text-gray-600 mt-1">Screenshots</div>
              </div>
            </div>

            {result.performance_metrics?.load_time_ms && (
              <div className="mt-4 flex items-center gap-2 text-sm text-gray-600">
                <span>⚡</span>
                <span>Temps de chargement: {result.performance_metrics.load_time_ms}ms</span>
              </div>
            )}

            {result.console_errors && result.console_errors.length > 0 && (
              <div className="mt-4 flex items-center gap-2 text-sm text-orange-600">
                <span>⚠️</span>
                <span>{result.console_errors.length} erreur(s) console</span>
              </div>
            )}
          </Card>
          </div>
        ))}
      </div>

      {/* Détails du résultat sélectionné */}
      {selectedResult && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-gray-900">
              Détails du test
            </h2>
            <button
              onClick={() => setSelectedResult(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          {/* Scénarios de test */}
          {selectedResult.test_scenarios && selectedResult.test_scenarios.length > 0 && (
            <div className="mb-6">
              <h3 className="font-semibold text-gray-900 mb-3">
                📋 Scénarios exécutés
              </h3>
              <div className="space-y-2">
                {selectedResult.test_scenarios.map((scenario, idx) => (
                  <div 
                    key={idx}
                    className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
                  >
                    <span className="text-lg">
                      {scenario.success ? '✅' : '❌'}
                    </span>
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">
                        {scenario.name}
                      </div>
                      <div className="text-sm text-gray-600 mt-1">
                        {scenario.description}
                      </div>
                      <Badge 
                        variant="info" 
                        className="mt-2 text-xs"
                      >
                        {scenario.type}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Erreurs console */}
          {selectedResult.console_errors && selectedResult.console_errors.length > 0 && (
            <div className="mb-6">
              <h3 className="font-semibold text-gray-900 mb-3">
                🐛 Erreurs console
              </h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {selectedResult.console_errors.map((error, idx) => (
                  <div 
                    key={idx}
                    className="p-3 bg-red-50 rounded-lg text-sm"
                  >
                    <div className="font-mono text-red-700 mb-1">
                      {error.message}
                    </div>
                    <div className="text-gray-600 text-xs">
                      {error.source}:{error.line}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Requêtes réseau */}
          {selectedResult.network_requests && selectedResult.network_requests.length > 0 && (
            <div className="mb-6">
              <h3 className="font-semibold text-gray-900 mb-3">
                🌐 Requêtes réseau
              </h3>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {selectedResult.network_requests.map((req, idx) => (
                  <div 
                    key={idx}
                    className="flex items-center justify-between p-2 bg-gray-50 rounded text-sm"
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <Badge 
                        variant={req.status >= 200 && req.status < 300 ? 'success' : 'error'}
                        className="text-xs shrink-0"
                      >
                        {req.status}
                      </Badge>
                      <span className="font-mono text-xs text-gray-600 shrink-0">
                        {req.method}
                      </span>
                      <span className="text-gray-900 truncate">
                        {req.url}
                      </span>
                    </div>
                    <span className="text-gray-500 text-xs ml-2 shrink-0">
                      {req.duration_ms}ms
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Métriques de performance */}
          {selectedResult.performance_metrics && (
            <div>
              <h3 className="font-semibold text-gray-900 mb-3">
                📊 Métriques de performance
              </h3>
              <div className="grid grid-cols-3 gap-4">
                {selectedResult.performance_metrics.load_time_ms && (
                  <div className="bg-blue-50 rounded-lg p-4">
                    <div className="text-sm text-gray-600 mb-1">
                      Load Time
                    </div>
                    <div className="text-2xl font-bold text-blue-600">
                      {selectedResult.performance_metrics.load_time_ms}ms
                    </div>
                  </div>
                )}
                {selectedResult.performance_metrics.dom_content_loaded_ms && (
                  <div className="bg-purple-50 rounded-lg p-4">
                    <div className="text-sm text-gray-600 mb-1">
                      DOM Content Loaded
                    </div>
                    <div className="text-2xl font-bold text-purple-600">
                      {selectedResult.performance_metrics.dom_content_loaded_ms}ms
                    </div>
                  </div>
                )}
                {selectedResult.performance_metrics.first_contentful_paint_ms && (
                  <div className="bg-green-50 rounded-lg p-4">
                    <div className="text-sm text-gray-600 mb-1">
                      First Contentful Paint
                    </div>
                    <div className="text-2xl font-bold text-green-600">
                      {selectedResult.performance_metrics.first_contentful_paint_ms}ms
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};

