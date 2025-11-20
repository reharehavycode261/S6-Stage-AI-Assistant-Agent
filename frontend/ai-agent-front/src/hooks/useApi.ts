/**
 * Hook personnalisé pour les appels API avec React Query
 */
import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAppStore } from '@/stores/useAppStore';

/**
 * Hook pour récupérer le health check
 */
export function useSystemHealth(options?: UseQueryOptions) {
  const setSystemHealth = useAppStore((state) => state.setSystemHealth);
  
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: async () => {
      const data = await apiClient.healthCheck();
      setSystemHealth(data);
      return data;
    },
    refetchInterval: 10000, // Refresh every 10 seconds
    ...options,
  });
}

/**
 * Hook pour récupérer les métriques du dashboard
 */
export function useDashboardMetrics(options?: UseQueryOptions) {
  const setMetrics = useAppStore((state) => state.setMetrics);
  
  return useQuery({
    queryKey: ['dashboard', 'metrics'],
    queryFn: async () => {
      const data = await apiClient.getDashboardMetrics();
      setMetrics(data);
      return data;
    },
    refetchInterval: 5000, // Refresh every 5 seconds
    ...options,
  });
}

/**
 * Hook pour récupérer l'évolution des tâches (7 derniers jours)
 */
export function useTasksTrend(params?: { month?: string; year?: string }, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['dashboard', 'tasks-trend', params],
    queryFn: () => apiClient.getTasksTrend(params?.month, params?.year),
    refetchInterval: 60000, // Refresh every minute
    ...options,
  });
}

/**
 * Hook pour récupérer les coûts
 */
export function useCostsSummary(period: 'today' | 'week' | 'month' | 'all' = 'today', options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['costs', period],
    queryFn: () => apiClient.getCostsSummary(period),
    ...options,
  });
}

/**
 * Hook pour récupérer les tâches
 */
export function useTasks(params?: any, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['tasks', params],
    queryFn: () => apiClient.getTasks(params),
    ...options,
  });
}

/**
 * Hook pour récupérer une tâche spécifique
 */
export function useTask(taskId: string, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: () => apiClient.getTaskById(taskId),
    enabled: !!taskId,
    ...options,
  });
}

/**
 * Hook pour récupérer le statut d'une tâche
 */
export function useTaskStatus(taskId: string, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['task', taskId, 'status'],
    queryFn: () => apiClient.getTaskStatus(taskId),
    enabled: !!taskId,
    refetchInterval: 2000, // Refresh every 2 seconds
    ...options,
  });
}

/**
 * Hook pour retry une tâche
 */
export function useRetryTask(options?: UseMutationOptions<any, Error, string>) {
  return useMutation({
    mutationFn: (taskId: string) => apiClient.retryTask(taskId),
    ...options,
  });
}

/**
 * Hook pour cancel une tâche
 */
export function useCancelTask(options?: UseMutationOptions<any, Error, string>) {
  return useMutation({
    mutationFn: (taskId: string) => apiClient.cancelTask(taskId),
    ...options,
  });
}

/**
 * Hook pour récupérer les validations en attente
 */
export function usePendingValidations(options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['validations', 'pending'],
    queryFn: () => apiClient.getPendingValidations(),
    refetchInterval: 5000,
    ...options,
  });
}

/**
 * Hook pour soumettre une validation
 */
export function useSubmitValidation(options?: UseMutationOptions<any, Error, { validationId: string; response: any }>) {
  return useMutation({
    mutationFn: ({ validationId, response }: { validationId: string; response: any }) =>
      apiClient.submitValidation(validationId, response),
    ...options,
  });
}

/**
 * Hook pour récupérer le test dashboard
 */
export function useTestDashboard(options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['tests', 'dashboard'],
    queryFn: () => apiClient.getTestDashboard(),
    ...options,
  });
}

/**
 * Hook pour récupérer les utilisateurs
 */
export function useUsers(params?: any, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['users', params],
    queryFn: () => apiClient.getUsers(params),
    ...options,
  });
}

/**
 * Hook pour récupérer l'usage des modèles IA
 */
export function useAIModelUsage(params?: any, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['ai', 'usage', params],
    queryFn: () => apiClient.getAIModelUsage(params),
    ...options,
  });
}

/**
 * Hook pour récupérer les stats de langages
 */
export function useLanguageStats(params?: { month?: string; year?: string }, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['languages', 'stats', params],
    queryFn: () => apiClient.getLanguageStats(params?.month, params?.year),
    ...options,
  });
}

/**
 * Hook pour récupérer les logs
 */
export function useLogs(filter: any, page: number = 1, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['logs', filter, page],
    queryFn: () => apiClient.getLogs(filter, page),
    ...options,
  });
}

/**
 * Hook pour récupérer la configuration système
 */
export function useSystemConfig(options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['config', 'system'],
    queryFn: () => apiClient.getSystemConfig(),
    ...options,
  });
}

/**
 * Hook pour mettre à jour la configuration
 */
export function useUpdateSystemConfig(options?: UseMutationOptions) {
  return useMutation({
    mutationFn: (config: any) => apiClient.updateSystemConfig(config),
    ...options,
  });
}

/**
 * Hook pour récupérer les boards Monday
 */
export function useMondayBoards(options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['integrations', 'monday', 'boards'],
    queryFn: () => apiClient.getMondayBoards(),
    ...options,
  });
}

/**
 * Hook pour récupérer les repos GitHub
 */
export function useGitHubRepos(options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['integrations', 'github', 'repos'],
    queryFn: () => apiClient.getGitHubRepos(),
    ...options,
  });
}

/**
 * Hook pour récupérer le workspace Slack
 */
export function useSlackWorkspace(options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['integrations', 'slack', 'workspace'],
    queryFn: () => apiClient.getSlackWorkspace(),
    ...options,
  });
}

/**
 * Hook pour récupérer les workflows actifs
 */
export function useActiveWorkflows(options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['workflows', 'active'],
    queryFn: () => apiClient.getActiveWorkflows(),
    refetchInterval: 3000, // Refresh every 3 seconds
    ...options,
  });
}

/**
 * Hook pour récupérer les workflows récents
 */
export function useRecentWorkflows(limit: number = 10, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['workflows', 'recent', limit],
    queryFn: () => apiClient.getRecentWorkflows(limit),
    ...options,
  });
}

/**
 * Hook pour récupérer un workflow spécifique
 */
export function useWorkflow(workflowId: string, options?: UseQueryOptions) {
  return useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => apiClient.getWorkflowById(workflowId),
    enabled: !!workflowId,
    refetchInterval: 2000, // Refresh every 2 seconds for active workflows
    ...options,
  });
}

