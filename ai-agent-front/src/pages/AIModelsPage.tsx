import { Card } from '@/components/common/Card';
import { useAIModelUsage } from '@/hooks/useApi';
import { formatCurrency, formatNumber } from '@/utils/format';
import { Brain, DollarSign } from 'lucide-react';

export function AIModelsPage() {
  const { data: modelUsage, isLoading } = useAIModelUsage();

  // ✅ DONNÉES RÉELLES depuis l'API
  const models = Array.isArray(modelUsage) ? modelUsage : [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  const totalCost = models.reduce((sum: number, m: any) => sum + (m.total_cost || 0), 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Modèles IA</h1>
        <p className="text-gray-500 mt-1">Monitoring des modèles et coûts</p>
      </div>

      {/* Total Cost Card - DONNÉES RÉELLES */}
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">Coût total ce mois</p>
            <p className="text-4xl font-bold text-gray-900 mt-1">
              {formatCurrency(totalCost)}
            </p>
            {totalCost === 0 && (
              <p className="text-xs text-gray-500 mt-1">Coût estimé basé sur les exécutions</p>
            )}
          </div>
          <div className="w-16 h-16 bg-purple-50 rounded-lg flex items-center justify-center">
            <DollarSign className="h-8 w-8 text-purple-600" />
          </div>
        </div>
      </Card>

      {/* Models List - DONNÉES RÉELLES */}
      <div className="space-y-4">
        {models.length > 0 ? (
          models.map((model: any) => (
            <Card key={model.model_name} title={model.model_name}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-sm text-gray-600">Provider</p>
                  <p className="text-lg font-semibold text-gray-900 capitalize">{model.provider}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Requêtes</p>
                  <p className="text-lg font-semibold text-gray-900">{formatNumber(model.total_requests)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Tokens</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {model.total_tokens > 0 ? formatNumber(model.total_tokens) : 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Coût</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {model.total_cost > 0 ? formatCurrency(model.total_cost) : 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Temps moyen</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {model.avg_response_time ? `${model.avg_response_time.toFixed(1)}s` : 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Taux d'erreur</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {model.error_rate !== undefined ? `${model.error_rate.toFixed(1)}%` : 'N/A'}
                  </p>
                </div>
              </div>
            </Card>
          ))
        ) : (
          <Card>
            <div className="text-center py-12 text-gray-500">
              <Brain className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">Aucun modèle IA utilisé</p>
              <p className="text-sm mt-2">Les statistiques apparaîtront ici quand des modèles seront utilisés</p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

