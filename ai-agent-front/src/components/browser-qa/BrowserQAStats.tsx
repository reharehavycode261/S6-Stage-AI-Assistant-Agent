import { useState, useEffect } from 'react';
import { Card } from '../common/Card';
import { LoadingSpinner } from '../common/LoadingSpinner';

interface BrowserQAStatsData {
  total_runs: number;
  total_success: number;
  total_failed: number;
  success_rate: number;
  avg_tests_per_run: number;
  total_tests_executed: number;
  total_tests_passed: number;
  total_tests_failed: number;
  pass_rate: number;
}

export const BrowserQAStats = () => {
  const [stats, setStats] = useState<BrowserQAStatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/browser-qa/stats');
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-8">
        <div className="flex justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </Card>
    );
  }

  if (error || !stats) {
    return (
      <Card className="p-6 border-red-200 bg-red-50">
        <div className="flex items-center gap-3">
          <span className="text-2xl">❌</span>
          <div>
            <h3 className="font-semibold text-red-900">Erreur</h3>
            <p className="text-red-700">{error || 'No stats available'}</p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* Total Runs */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-600">
            Tests Browser Exécutés
          </h3>
          <span className="text-2xl">🚀</span>
        </div>
        <div className="text-3xl font-bold text-gray-900">
          {stats.total_runs}
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-sm text-green-600">
            {stats.total_success} réussis
          </span>
          <span className="text-sm text-red-600">
            {stats.total_failed} échoués
          </span>
        </div>
      </Card>

      {/* Success Rate */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-600">
            Taux de Réussite
          </h3>
          <span className="text-2xl">📈</span>
        </div>
        <div className="text-3xl font-bold text-gray-900">
          {stats.success_rate.toFixed(1)}%
        </div>
        <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div 
            className="h-full bg-green-500 transition-all duration-500"
            style={{ width: `${stats.success_rate}%` }}
          />
        </div>
      </Card>

      {/* Tests Executed */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-600">
            Total Tests
          </h3>
          <span className="text-2xl">🧪</span>
        </div>
        <div className="text-3xl font-bold text-gray-900">
          {stats.total_tests_executed}
        </div>
        <div className="mt-2 text-sm text-gray-600">
          {stats.avg_tests_per_run.toFixed(1)} tests/run en moyenne
        </div>
      </Card>

      {/* Pass Rate */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-600">
            Taux de Passage
          </h3>
          <span className="text-2xl">✅</span>
        </div>
        <div className="text-3xl font-bold text-gray-900">
          {stats.pass_rate.toFixed(1)}%
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-sm text-green-600">
            {stats.total_tests_passed} passés
          </span>
          <span className="text-sm text-red-600">
            {stats.total_tests_failed} échoués
          </span>
        </div>
      </Card>
    </div>
  );
};

