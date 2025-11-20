/**
 * Hooks API Optimisés avec TanStack Query
 * Gestion intelligente du cache et des invalidations
 */
import { useQuery, useMutation, useQueryClient, UseQueryOptions } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import type {
  TaskDetail,
} from '@/types';

// ==================== DASHBOARD ====================

export function useDashboardMetrics() {
  return useQuery({
    queryKey: ['dashboard', 'metrics'],
    queryFn: () => apiClient.getDashboardMetrics(),
    staleTime: 60 * 1000, // 60 secondes (correspond au TTL backend)
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useCostsSummary(period: 'today' | 'week' | 'month' | 'all' = 'today') {
  return useQuery({
    queryKey: ['costs', period],
    queryFn: () => apiClient.getCostsSummary(period),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

// ==================== TASKS ====================

export function useTasks(params?: {
  status?: string;
  task_type?: string;
  priority?: string;
  page?: number;
  per_page?: number;
}) {
  return useQuery({
    queryKey: ['tasks', params],
    queryFn: () => apiClient.getTasks(params),
    staleTime: 30 * 1000, // 30 secondes (correspond au TTL backend)
    placeholderData: (previousData) => previousData, // Garder les données précédentes pendant le chargement
  });
}

export function useTaskById(
  taskId: string,
  options?: Partial<UseQueryOptions<TaskDetail>>
) {
  return useQuery({
    queryKey: ['tasks', taskId],
    queryFn: () => apiClient.getTaskById(taskId),
    enabled: options?.enabled ?? !!taskId,
    staleTime: 15 * 1000, // 15 secondes
    refetchInterval: (query) => {
      // Refetch automatique toutes les 30s si la tâche est active
      const activeStatuses = ['processing', 'testing', 'quality_check'];
      const data = query?.state?.data as any;
      return data?.internal_status && activeStatuses.includes(data.internal_status)
        ? 30 * 1000
        : false;
    },
    ...options,
  });
}

export function useRetryTask() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (taskId: string) => apiClient.retryTask(taskId),
    onSuccess: (_, taskId) => {
      // Invalider le cache de la tâche spécifique
      queryClient.invalidateQueries({ queryKey: ['tasks', taskId] });
      // Invalider la liste des tâches
      queryClient.invalidateQueries({ queryKey: ['tasks'], exact: false });
      // Invalider les métriques du dashboard
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'metrics'] });
    },
  });
}

export function useCancelTask() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (taskId: string) => apiClient.cancelTask(taskId),
    onSuccess: (_, taskId) => {
      queryClient.invalidateQueries({ queryKey: ['tasks', taskId] });
      queryClient.invalidateQueries({ queryKey: ['tasks'], exact: false });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'metrics'] });
    },
  });
}

// ==================== WORKFLOWS ====================

export function useWorkflowProgress(workflowId: string) {
  return useQuery({
    queryKey: ['workflows', workflowId, 'progress'],
    queryFn: () => apiClient.getWorkflowProgress(workflowId),
    enabled: !!workflowId,
    staleTime: 10 * 1000, // 10 secondes
    refetchInterval: 15 * 1000, // Refresh toutes les 15s pour suivre la progression
  });
}

export function useWorkflowHistory(params?: {
  start_date?: string;
  end_date?: string;
  status?: string;
  page?: number;
}) {
  return useQuery({
    queryKey: ['workflows', 'history', params],
    queryFn: () => apiClient.getWorkflowHistory(params),
    staleTime: 60 * 1000, // 1 minute
    placeholderData: (previousData) => previousData,
  });
}

export function useActiveWorkflows() {
  return useQuery({
    queryKey: ['workflows', 'active'],
    queryFn: () => apiClient.getActiveWorkflows(),
    staleTime: 30 * 1000, // 30 secondes
    refetchInterval: 30 * 1000, // Refresh toutes les 30s
  });
}

// ==================== VALIDATIONS ====================

export function usePendingValidations() {
  return useQuery({
    queryKey: ['validations', 'pending'],
    queryFn: () => apiClient.getPendingValidations(),
    staleTime: 30 * 1000, // 30 secondes
    refetchInterval: 60 * 1000, // Refresh toutes les minutes
  });
}

export function useValidationById(validationId: string) {
  return useQuery({
    queryKey: ['validations', validationId],
    queryFn: () => apiClient.getValidationById(validationId),
    enabled: !!validationId,
    staleTime: 15 * 1000,
  });
}

export function useSubmitValidation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ validationId, response }: { validationId: string; response: any }) =>
      apiClient.submitValidation(validationId, response),
    onSuccess: (_, { validationId }) => {
      queryClient.invalidateQueries({ queryKey: ['validations', validationId] });
      queryClient.invalidateQueries({ queryKey: ['validations', 'pending'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'metrics'] });
    },
  });
}

// ==================== TESTS ====================

export function useTestDashboard() {
  return useQuery({
    queryKey: ['tests', 'dashboard'],
    queryFn: () => apiClient.getTestDashboard(),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

export function useTestsByLanguage(language: string) {
  return useQuery({
    queryKey: ['tests', 'language', language],
    queryFn: () => apiClient.getTestsByLanguage(language),
    enabled: !!language,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// ==================== USERS ====================

export function useUsers(params?: {
  search?: string;
  is_active?: boolean;
  page?: number;
}) {
  return useQuery({
    queryKey: ['users', params],
    queryFn: () => apiClient.getUsers(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    placeholderData: (previousData) => previousData,
  });
}

export function useUserStats(userId: number) {
  return useQuery({
    queryKey: ['users', userId, 'stats'],
    queryFn: () => apiClient.getUserStats(userId),
    enabled: !!userId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useUpdateUserSlackId() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ userId, slackUserId }: { userId: number; slackUserId: string }) =>
      apiClient.updateUserSlackId(userId, slackUserId),
    onSuccess: (_, { userId }) => {
      queryClient.invalidateQueries({ queryKey: ['users', userId] });
      queryClient.invalidateQueries({ queryKey: ['users'], exact: false });
    },
  });
}

// ==================== AI MODELS ====================

export function useAIModelUsage(params?: {
  start_date?: string;
  end_date?: string;
}) {
  return useQuery({
    queryKey: ['ai', 'usage', params],
    queryFn: () => apiClient.getAIModelUsage(params),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

// ==================== LANGUAGES ====================

export function useLanguageStats() {
  return useQuery({
    queryKey: ['languages', 'stats'],
    queryFn: () => apiClient.getLanguageStats(),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// ==================== INTEGRATIONS ====================

export function useMondayBoards() {
  return useQuery({
    queryKey: ['integrations', 'monday', 'boards'],
    queryFn: () => apiClient.getMondayBoards(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useTestMondayIntegration() {
  return useMutation({
    mutationFn: () => apiClient.testMondayIntegration(),
  });
}

export function useGitHubRepos() {
  return useQuery({
    queryKey: ['integrations', 'github', 'repos'],
    queryFn: () => apiClient.getGitHubRepos(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useTestGitHubIntegration() {
  return useMutation({
    mutationFn: () => apiClient.testGitHubIntegration(),
  });
}

export function useSlackWorkspace() {
  return useQuery({
    queryKey: ['integrations', 'slack', 'workspace'],
    queryFn: () => apiClient.getSlackWorkspace(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useTestSlackIntegration() {
  return useMutation({
    mutationFn: () => apiClient.testSlackIntegration(),
  });
}

// ==================== LOGS ====================

export function useLogs(filter: any, page: number = 1) {
  return useQuery({
    queryKey: ['logs', filter, page],
    queryFn: () => apiClient.getLogs(filter, page),
    staleTime: 30 * 1000, // 30 secondes
    placeholderData: (previousData) => previousData,
  });
}

// ==================== CONFIG ====================

export function useSystemConfig() {
  return useQuery({
    queryKey: ['config', 'system'],
    queryFn: () => apiClient.getSystemConfig(),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useUpdateSystemConfig() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (config: any) => apiClient.updateSystemConfig(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config', 'system'] });
    },
  });
}

// ==================== EVALUATION ====================

export function useRunEvaluation() {
  return useMutation({
    mutationFn: (datasetType?: 'questions' | 'commands') =>
      apiClient.runEvaluation(datasetType),
  });
}

export function useEvaluationReports() {
  return useQuery({
    queryKey: ['evaluation', 'reports'],
    queryFn: () => apiClient.getEvaluationReports(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useEvaluationReport(reportId: string) {
  return useQuery({
    queryKey: ['evaluation', 'reports', reportId],
    queryFn: () => apiClient.getEvaluationReport(reportId),
    enabled: !!reportId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

