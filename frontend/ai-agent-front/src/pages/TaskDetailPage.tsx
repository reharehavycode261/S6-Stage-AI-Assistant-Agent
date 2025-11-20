import { useParams, Link } from 'react-router-dom';
import { Card } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Badge } from '@/components/common/Badge';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useTask, useRetryTask, useCancelTask } from '@/hooks/useApi';
import { formatFullDate, formatDuration, formatTaskType, formatPriority } from '@/utils/format';
import { getTaskTypeColor, getPriorityColor } from '@/utils/colors';
import { ArrowLeft, RefreshCw, X, ExternalLink, GitBranch } from 'lucide-react';

export function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const { data: taskData, isLoading } = useTask(taskId!);
  const retryTask = useRetryTask();
  const cancelTask = useCancelTask();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!taskData) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Tâche non trouvée</p>
        <Link to="/tasks">
          <Button variant="secondary" className="mt-4">
            Retour aux tâches
          </Button>
        </Link>
      </div>
    );
  }

  const task = taskData as any; // Type assertion pour éviter erreurs TypeScript
  const latestRun = task.runs?.[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/tasks">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Retour
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{task.title}</h1>
            <p className="text-gray-500 mt-1">Tâche #{task.tasks_id}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => retryTask.mutate(String(task.tasks_id))}
            isLoading={retryTask.isPending}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Relancer
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => cancelTask.mutate(String(task.tasks_id))}
            isLoading={cancelTask.isPending}
          >
            <X className="h-4 w-4 mr-2" />
            Annuler
          </Button>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-center">
            <p className="text-sm text-gray-600 mb-2">Statut</p>
            <StatusBadge status={task.status} showDot={true} />
          </div>
        </Card>

        <Card>
          <div className="text-center">
            <p className="text-sm text-gray-600 mb-2">Type</p>
            <Badge className={getTaskTypeColor(task.task_type)}>
              {formatTaskType(task.task_type)}
            </Badge>
          </div>
        </Card>

        <Card>
          <div className="text-center">
            <p className="text-sm text-gray-600 mb-2">Priorité</p>
            <Badge className={getPriorityColor(task.priority)}>
              {formatPriority(task.priority)}
            </Badge>
          </div>
        </Card>

        <Card>
          <div className="text-center">
            <p className="text-sm text-gray-600 mb-2">Exécutions</p>
            <p className="text-2xl font-bold text-gray-900">{task.runs?.length || 0}</p>
          </div>
        </Card>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description */}
          <Card title="Description">
            <p className="text-gray-700 whitespace-pre-wrap">{task.description}</p>
          </Card>

          {/* Latest Run */}
          {latestRun && (
            <Card
              title="Dernière exécution"
              subtitle={`Run #${latestRun.run_number}`}
            >
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-gray-600">Statut</label>
                    <div className="mt-1">
                      <StatusBadge status={latestRun.status} />
                    </div>
                  </div>

                  <div>
                    <label className="text-sm text-gray-600">Durée</label>
                    <p className="text-sm font-medium mt-1">
                      {latestRun.started_at && latestRun.completed_at
                        ? formatDuration(
                            (new Date(latestRun.completed_at).getTime() -
                              new Date(latestRun.started_at).getTime()) /
                              1000
                          )
                        : 'N/A'}
                    </p>
                  </div>

                  {latestRun.branch_name && (
                    <div>
                      <label className="text-sm text-gray-600">Branche</label>
                      <p className="text-sm font-mono font-medium mt-1 flex items-center gap-1">
                        <GitBranch className="h-3 w-3" />
                        {latestRun.branch_name}
                      </p>
                    </div>
                  )}

                  {latestRun.pr_number && (
                    <div>
                      <label className="text-sm text-gray-600">Pull Request</label>
                      <a
                        href={latestRun.pr_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-primary-600 hover:text-primary-700 mt-1 flex items-center gap-1"
                      >
                        #{latestRun.pr_number}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  )}
                </div>

                {latestRun.error_message && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-800 font-mono">
                      {latestRun.error_message}
                    </p>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* All Runs */}
          {task.runs && task.runs.length > 1 && (
            <Card title="Historique des exécutions">
              <div className="space-y-2">
                {task.runs.map((run: any) => (
                  <div
                    key={run.tasks_runs_id}
                    className="p-3 bg-gray-50 rounded-lg flex items-center justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium">Run #{run.run_number}</span>
                        <StatusBadge status={run.status} />
                      </div>
                      {run.started_at && (
                        <p className="text-xs text-gray-600">
                          {formatFullDate(run.started_at)}
                        </p>
                      )}
                    </div>

                    {run.pr_url && (
                      <a
                        href={run.pr_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-primary-600 hover:text-primary-700"
                      >
                        Voir PR →
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Right Column - Metadata */}
        <div className="space-y-6">
          <Card title="Informations">
            <div className="space-y-3">
              <div>
                <label className="text-sm text-gray-600">ID Monday.com</label>
                <p className="text-sm font-mono font-medium">{task.monday_item_id}</p>
              </div>

              {task.repository_url && (
                <div>
                  <label className="text-sm text-gray-600">Repository</label>
                  <a
                    href={task.repository_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-mono font-medium text-primary-600 hover:text-primary-700 flex items-center gap-1 mt-1"
                  >
                    {task.repository_url.split('/').slice(-2).join('/')}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}

              <div>
                <label className="text-sm text-gray-600">Créée le</label>
                <p className="text-sm font-medium">{formatFullDate(task.created_at)}</p>
              </div>

              <div>
                <label className="text-sm text-gray-600">Mise à jour le</label>
                <p className="text-sm font-medium">{formatFullDate(task.updated_at)}</p>
              </div>

              {task.completed_at && (
                <div>
                  <label className="text-sm text-gray-600">Terminée le</label>
                  <p className="text-sm font-medium">{formatFullDate(task.completed_at)}</p>
                </div>
              )}
            </div>
          </Card>

          {/* Validation */}
          {task.validation && (
            <Card title="Validation">
              <div className="space-y-3">
                <div>
                  <label className="text-sm text-gray-600">Statut</label>
                  <div className="mt-1">
                    <StatusBadge status={task.validation.status} />
                  </div>
                </div>

                {task.validation.validated_by && (
                  <div>
                    <label className="text-sm text-gray-600">Validé par</label>
                    <p className="text-sm font-medium">{task.validation.validated_by}</p>
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}








