import { Card } from '@/components/common/Card';
import { formatCurrency, formatDuration } from '@/utils/format';
import { Activity, CheckCircle, Clock } from 'lucide-react';
import { ReactNode } from 'react';

interface Props {
  metrics: any;
  children?: ReactNode;
}

export function AgentPerformanceOverview({ metrics, children }: Props) {
  const tasksThisMonth = Number((metrics as any)?.tasks_this_month ?? 0);
  const avgExecution = Number((metrics as any)?.avg_execution_time ?? 0);
  const successRate = Number((metrics as any)?.success_rate_this_month ?? 0);
  const aiCost = Number((metrics as any)?.ai_cost_this_month ?? 0);
  const successPercent = Math.max(0, Math.min(100, successRate));
  const gaugeData = [
    { name: 'done', value: successPercent },
    { name: 'remain', value: Math.max(0, 100 - successPercent) },
  ];
  const estimatedCompleted = Math.max(0, Math.round((tasksThisMonth * successPercent) / 100));
  const activeNow = Number((metrics as any)?.tasks_active ?? 0);
  const estimatedFailed = Math.max(0, tasksThisMonth - estimatedCompleted - activeNow);

  return (
    <Card className="p-0">
      <div className="relative rounded-xl">
        {/* Container général sans fond bleu */}
        <div className="p-4 md:p-6">
          {/* Layout: colonne bleue (réduite) + zone libre */}
          <div className="grid md:grid-cols-[300px_1fr] gap-6">
            {/* Colonne bleue réduite */}
            <div className="rounded-2xl bg-gradient-to-br from-blue-600 to-blue-700 text-white p-6 md:p-8 shadow-md">
              <div className="">
                <h2 className="text-2xl md:text-3xl font-extrabold font-brand">Agent Performance</h2>
                <p className="opacity-90 mt-1 text-sm">Vue d'ensemble des performances de l'agent</p>
              </div>

              {/* Valeur principale */}
              <div className="mt-8">
                <div className="text-6xl font-extrabold nums-tabular leading-none">
                  {tasksThisMonth.toLocaleString('fr-FR')}
                </div>
                <div className="opacity-90 mt-2">Tâches ce mois</div>
              </div>

              {/* Ligne de stats avec bullets (style AgentOps) */}
              <div className="mt-6 flex items-center gap-10 text-white/95">
                <div className="flex items-center gap-3">
                  <span className="inline-block w-2 h-2 rounded-full bg-white" />
                  <div>
                    <div className="text-sm opacity-90">Succès</div>
                    <div className="text-2xl font-semibold nums-tabular">{estimatedCompleted.toLocaleString('fr-FR')}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="inline-block w-2 h-2 rounded-full bg-white" />
                  <div>
                    <div className="text-sm opacity-90">Actives</div>
                    <div className="text-2xl font-semibold nums-tabular">{activeNow.toLocaleString('fr-FR')}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="inline-block w-2 h-2 rounded-full bg-white" />
                  <div>
                    <div className="text-sm opacity-90">Échecs</div>
                    <div className="text-2xl font-semibold nums-tabular">{estimatedFailed.toLocaleString('fr-FR')}</div>
                  </div>
                </div>
              </div>

              {/* Petit chart attractif (demi-donut) */}
              <div className="mt-8">
                <div className="relative bg-white/10 rounded-xl p-4 overflow-hidden">
                  <div className="absolute left-0 right-0 top-8 md:top-10 z-10 text-center pointer-events-none">
                    <div className="text-2xl font-extrabold nums-tabular">{successPercent.toFixed(0)}%</div>
                    <div className="text-xs opacity-90">Taux de succès</div>
                  </div>
                  <div className="relative z-0 h-40">
                    <svg viewBox="0 0 400 200" className="w-full h-full">
                      <defs>
                        <linearGradient id="arcGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                          <stop offset="0%" stopColor="#22c55e" />
                          <stop offset="100%" stopColor="#16a34a" />
                        </linearGradient>
                      </defs>
                      {/* Arc de fond */}
                      <path
                        d="M20 180 A180 180 0 0 1 380 180"
                        fill="none"
                        stroke="rgba(255,255,255,0.35)"
                        strokeWidth="24"
                        strokeLinecap="round"
                      />
                      {/* Arc de progression */}
                      {(() => {
                        const startX = 20;
                        const startY = 180;
                        const radius = 180;
                        const sweep = Math.max(1, Math.min(180, (180 * successPercent) / 100));
                        // Path pour l'arc de progression
                        const endAngle = 180 - sweep;
                        const toX = 200 + radius * Math.cos((endAngle * Math.PI) / 180);
                        const toY = 200 - radius * Math.sin((endAngle * Math.PI) / 180);
                        const largeArcFlag = sweep > 180 ? 1 : 0;
                        const d = `M ${startX} ${startY} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${toX} ${toY}`;
                        return (
                          <path
                            d={d}
                            fill="none"
                            stroke="url(#arcGradient)"
                            strokeWidth="24"
                            strokeLinecap="round"
                          />
                        );
                      })()}
                    </svg>
                  </div>
                </div>
              </div>
            </div>

            {/* Contenu d'overview à droite (vos widgets) */}
            <div className="mt-6 md:mt-0">
              {children}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}


