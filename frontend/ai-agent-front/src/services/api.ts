/**
 * Service API pour communiquer avec le backend FastAPI
 */
import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  ApiResponse,
  PaginatedResponse,
  TaskDetail,
  TaskStatusResponse,
  DashboardMetrics,
  SystemHealth,
  CostSummary,
  TestDashboard,
  UserStats,
  MondayBoard,
  GitHubRepository,
  SlackWorkspace,
  WebhookEvent,
  LogEntry,
  LogFilter,
  HumanValidationRequest,
  HumanValidationResponse,
  WorkflowProgress,
  AIModelUsage,
  LanguageStats,
  QueueStatus,
} from '@/types';

class ApiClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor() {
    this.baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        // Ajouter un token d'authentification si nécessaire
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Rediriger vers la page de connexion
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // ==================== HEALTH & STATUS ====================

  async healthCheck(): Promise<SystemHealth> {
    const { data } = await this.client.get('/health');
    return data;
  }

  async getCeleryStatus(): Promise<{
    workers_count: number;
    workers: string[];
    active_tasks: number;
    reserved_tasks: number;
    queues: string[];
  }> {
    const { data } = await this.client.get('/celery/status');
    return data;
  }

  // ==================== DASHBOARD ====================

  async getDashboardMetrics(): Promise<DashboardMetrics> {
    const { data } = await this.client.get('/api/dashboard/metrics');
    return data;
  }

  async getTasksTrend(month?: string, year?: string): Promise<Array<{date: string; success: number; failed: number}>> {
    const params = new URLSearchParams();
    if (month) params.append('month', month);
    if (year) params.append('year', year);
    const queryString = params.toString();
    const { data } = await this.client.get(`/api/dashboard/tasks-trend${queryString ? '?' + queryString : ''}`);
    return data;
  }

  async getCostsSummary(period: 'today' | 'week' | 'month' | 'all' = 'today'): Promise<CostSummary> {
    const { data } = await this.client.get(`/costs/${period}`);
    return data;
  }

  // ==================== TASKS ====================

  async getTasks(params?: {
    status?: string;
    task_type?: string;
    priority?: string;
    page?: number;
    per_page?: number;
  }): Promise<PaginatedResponse<TaskDetail>> {
    const { data } = await this.client.get('/api/tasks', { params });
    return data;
  }

  async getTaskById(taskId: string): Promise<TaskDetail> {
    const { data } = await this.client.get(`/api/tasks/${taskId}`);
    return data;
  }

  async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    const { data } = await this.client.get(`/tasks/${taskId}/status`);
    return data;
  }

  async retryTask(taskId: string): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/tasks/${taskId}/retry`);
    return data;
  }

  async cancelTask(taskId: string): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/tasks/${taskId}/cancel`);
    return data;
  }

  // ==================== WORKFLOW ====================

  async getWorkflowProgress(workflowId: string): Promise<WorkflowProgress> {
    const { data } = await this.client.get(`/api/workflows/${workflowId}/progress`);
    return data;
  }

  async getWorkflowHistory(params?: {
    start_date?: string;
    end_date?: string;
    status?: string;
    page?: number;
  }): Promise<PaginatedResponse<WorkflowProgress>> {
    const { data } = await this.client.get('/api/workflows/history', { params });
    return data;
  }

  async getQueueStatus(mondayItemId: number): Promise<QueueStatus> {
    const { data } = await this.client.get(`/api/queue/${mondayItemId}/status`);
    return data;
  }

  // ==================== VALIDATION ====================

  async getPendingValidations(): Promise<HumanValidationRequest[]> {
    const { data } = await this.client.get('/api/validations/pending');
    return data;
  }

  async getValidationById(validationId: string): Promise<HumanValidationRequest> {
    const { data } = await this.client.get(`/api/validations/${validationId}`);
    return data;
  }

  async submitValidation(
    validationId: string,
    response: Partial<HumanValidationResponse>
  ): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/validations/${validationId}/respond`, response);
    return data;
  }

  // ==================== TESTS ====================

  async getTestDashboard(): Promise<TestDashboard> {
    const { data } = await this.client.get('/api/tests/dashboard');
    return data;
  }

  async getTestsByLanguage(language: string): Promise<any> {
    const { data } = await this.client.get(`/api/tests/language/${language}`);
    return data;
  }

  async retryFailedTest(taskId: string, testType: string): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/tests/${taskId}/${testType}/retry`);
    return data;
  }

  // ==================== USERS ====================

  async getUsers(params?: {
    search?: string;
    is_active?: boolean;
    access_status?: string;
    sort_by?: string;
    order?: string;
    page?: number;
  }): Promise<any> {
    const { data } = await this.client.get('/api/users', { params });
    return data;
  }

  async getUserById(userId: number): Promise<any> {
    const { data } = await this.client.get(`/api/users/${userId}`);
    return data;
  }

  async getUserStats(userId: number): Promise<UserStats> {
    const { data } = await this.client.get(`/api/users/${userId}/stats`);
    return data;
  }

  async getUserHistory(userId: number, limit: number = 50): Promise<any[]> {
    const { data } = await this.client.get(`/api/users/${userId}/history?limit=${limit}`);
    return data;
  }

  async updateUser(userId: number, userData: any): Promise<ApiResponse> {
    const { data } = await this.client.put(`/api/users/${userId}`, userData);
    return data;
  }

  async suspendUser(userId: number, reason?: string): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/users/${userId}/suspend`, { reason });
    return data;
  }

  async activateUser(userId: number): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/users/${userId}/activate`);
    return data;
  }

  async restrictUser(userId: number, reason?: string): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/users/${userId}/restrict`, { reason });
    return data;
  }

  async deleteUser(userId: number, reason?: string): Promise<ApiResponse> {
    const { data } = await this.client.delete(`/api/users/${userId}`, { data: { reason } });
    return data;
  }

  async updateUserSatisfaction(userId: number, score: number, comment?: string): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/users/${userId}/satisfaction`, { score, comment });
    return data;
  }

  async getUsersGlobalStats(): Promise<any> {
    const { data } = await this.client.get('/api/users/stats/global');
    return data;
  }

  async performUserManagementAction(action: any): Promise<ApiResponse> {
    const { data } = await this.client.post('/api/users/management-action', action);
    return data;
  }

  async syncUserWithMonday(userId: number): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/users/${userId}/sync-monday`);
    return data;
  }

  async updateUserSlackId(userId: number, slackUserId: string): Promise<ApiResponse> {
    const { data } = await this.client.put(`/api/users/${userId}/slack`, { slack_user_id: slackUserId });
    return data;
  }

  // ==================== AI MODELS ====================

  async getAIModelUsage(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<AIModelUsage[]> {
    const { data } = await this.client.get('/api/ai/usage', { params });
    return data;
  }

  async getLanguageStats(month?: string, year?: string): Promise<LanguageStats[]> {
    const params = new URLSearchParams();
    if (month) params.append('month', month);
    if (year) params.append('year', year);
    const queryString = params.toString();
    const { data } = await this.client.get(`/api/languages/stats${queryString ? '?' + queryString : ''}`);
    return data;
  }

  // ==================== INTEGRATIONS ====================

  // Monday.com
  async getMondayBoards(): Promise<MondayBoard[]> {
    const { data } = await this.client.get('/api/integrations/monday/boards');
    return data;
  }

  async getMondayUserInfo(userId: number): Promise<any> {
    const { data } = await this.client.get(`/api/integrations/monday/users/${userId}`);
    return data;
  }

  async getAllMondayUsers(): Promise<any[]> {
    const { data } = await this.client.get('/api/integrations/monday/users');
    return data;
  }

  async updateMondayUser(userId: number, userData: any): Promise<ApiResponse> {
    const { data } = await this.client.put(`/api/integrations/monday/users/${userId}`, userData);
    return data;
  }

  async getMondayBoardColumns(boardId: number): Promise<any[]> {
    const { data } = await this.client.get(`/api/integrations/monday/boards/${boardId}/columns`);
    return data;
  }

  async updateMondayItemColumn(boardId: number, itemId: number, columnId: string, value: any): Promise<ApiResponse> {
    const { data } = await this.client.put(
      `/api/integrations/monday/boards/${boardId}/items/${itemId}/columns/${columnId}`,
      { value }
    );
    return data;
  }

  async archiveMondayItem(itemId: number): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/integrations/monday/items/${itemId}/archive`);
    return data;
  }

  async addMondayLog(itemId: number, message: string): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/integrations/monday/items/${itemId}/updates`, { message });
    return data;
  }

  async testMondayIntegration(): Promise<ApiResponse> {
    const { data } = await this.client.post('/api/integrations/monday/test');
    return data;
  }

  // GitHub
  async getGitHubRepos(): Promise<GitHubRepository[]> {
    const { data } = await this.client.get('/api/integrations/github/repos');
    return data;
  }

  async testGitHubIntegration(): Promise<ApiResponse> {
    const { data } = await this.client.post('/api/integrations/github/test');
    return data;
  }

  // Slack
  async getSlackWorkspace(): Promise<SlackWorkspace> {
    const { data } = await this.client.get('/api/integrations/slack/workspace');
    return data;
  }

  async testSlackIntegration(): Promise<ApiResponse> {
    const { data } = await this.client.post('/api/integrations/slack/test');
    return data;
  }

  async sendTestSlackMessage(userId: string, message: string): Promise<ApiResponse> {
    const { data } = await this.client.post('/api/integrations/slack/test-message', {
      user_id: userId,
      message,
    });
    return data;
  }

  // Webhooks
  async getWebhookEvents(params?: {
    event_type?: string;
    processed?: boolean;
    start_date?: string;
    end_date?: string;
    page?: number;
  }): Promise<PaginatedResponse<WebhookEvent>> {
    const { data } = await this.client.get('/api/webhooks/events', { params });
    return data;
  }

  // ==================== LOGS ====================

  async getLogs(filter: LogFilter, page: number = 1): Promise<PaginatedResponse<LogEntry>> {
    const { data } = await this.client.get('/api/logs', {
      params: { ...filter, page },
    });
    return data;
  }

  async downloadLogs(filter: LogFilter): Promise<Blob> {
    const { data } = await this.client.get('/api/logs/download', {
      params: filter,
      responseType: 'blob',
    });
    return data;
  }

  // ==================== CONFIGURATION ====================

  async getSystemConfig(): Promise<Record<string, any>> {
    const { data } = await this.client.get('/api/config');
    return data;
  }

  async updateSystemConfig(config: Partial<Record<string, any>>): Promise<ApiResponse> {
    const { data } = await this.client.put('/api/config', config);
    return data;
  }

  // ==================== ADMIN ====================

  async triggerCleanup(): Promise<ApiResponse> {
    const { data } = await this.client.post('/admin/cleanup');
    return data;
  }

  async restartWorker(workerName: string): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/admin/workers/${workerName}/restart`);
    return data;
  }

  async purgeQueue(queueName: string): Promise<ApiResponse> {
    const { data } = await this.client.post(`/api/admin/queues/${queueName}/purge`);
    return data;
  }

  // ==================== AUDIT ====================

  async getAuditLogs(filter: any): Promise<any> {
    const { data } = await this.client.get('/api/audit/logs', { params: filter });
    return data;
  }

  async getAuditStats(): Promise<any> {
    const { data } = await this.client.get('/api/audit/stats');
    return data;
  }

  async exportAuditLogs(filter: any): Promise<Blob> {
    const { data } = await this.client.get('/api/audit/export', {
      params: filter,
      responseType: 'blob',
    });
    return data;
  }

  async logAuditEvent(event: any): Promise<ApiResponse> {
    const { data } = await this.client.post('/api/audit/log', event);
    return data;
  }

  // ==================== EVALUATION ====================

  async runEvaluation(datasetType?: 'questions' | 'commands'): Promise<ApiResponse> {
    const { data } = await this.client.post('/evaluation/run', null, {
      params: { dataset_type: datasetType, run_in_background: true },
    });
    return data;
  }

  async getEvaluationReports(): Promise<any[]> {
    const { data } = await this.client.get('/evaluation/reports');
    return data.reports || [];
  }

  async getEvaluationReport(reportId: string): Promise<any> {
    const { data } = await this.client.get(`/evaluation/reports/${reportId}`);
    return data;
  }

  // ==================== WORKFLOWS ====================

  async getActiveWorkflows(): Promise<any[]> {
    const { data } = await this.client.get('/api/workflows/active');
    return data;
  }

  async getRecentWorkflows(limit: number = 10): Promise<any[]> {
    const { data } = await this.client.get(`/api/workflows/recent?limit=${limit}`);
    return data;
  }

  async getWorkflowById(workflowId: string): Promise<any> {
    const { data } = await this.client.get(`/api/workflows/${workflowId}`);
    return data;
  }
}

// Singleton instance
export const apiClient = new ApiClient();

// Export par défaut
export default apiClient;

