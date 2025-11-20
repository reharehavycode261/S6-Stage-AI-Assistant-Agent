/**
 * Types TypeScript pour l'interface admin AI-Agent VyData
 * Basés sur les modèles backend (models/schemas.py)
 */

// ==================== ENUMS ====================

export enum TaskType {
  FEATURE = 'feature',
  BUGFIX = 'bugfix',
  REFACTOR = 'refactor',
  DOCUMENTATION = 'documentation',
  TESTING = 'testing',
  UI_CHANGE = 'ui_change',
  PERFORMANCE = 'performance',
  ANALYSIS = 'analysis',
}

export enum TaskPriority {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  URGENT = 'urgent',
}

export enum WorkflowStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum HumanValidationStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  ABANDONED = 'abandoned',
  EXPIRED = 'expired',
  CANCELLED = 'cancelled',
}

export enum UpdateType {
  NEW_REQUEST = 'new_request',
  MODIFICATION = 'modification',
  BUG_REPORT = 'bug_report',
  QUESTION = 'question',
  AFFIRMATION = 'affirmation',
  VALIDATION_RESPONSE = 'validation_response',
}

// ==================== TASKS ====================

export interface TaskRequest {
  task_id: string;
  title: string;
  description: string;
  task_type: TaskType;
  priority: TaskPriority;
  repository_url?: string;
  branch_name?: string;
  base_branch?: string;
  acceptance_criteria?: string;
  technical_context?: string;
  files_to_modify?: string[];
  estimated_complexity?: string;
  monday_item_id?: number;
  board_id?: number;
  task_db_id?: number;
  is_reactivation?: boolean;
  reactivation_context?: string;
  reactivation_count?: number;
  source_branch?: string;
  run_id?: number;
  queue_id?: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: WorkflowStatus;
  progress: number;
  current_step?: string;
  estimated_completion?: string;
  result_url?: string;
}

export interface TaskRun {
  tasks_runs_id: number;
  tasks_id: number;
  run_number: number;
  status: WorkflowStatus;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  repository_url?: string;
  branch_name?: string;
  pr_number?: number;
  pr_url?: string;
  merge_commit?: string;
}

export interface TaskDetail {
  tasks_id: number;
  monday_item_id: number;
  title: string;
  description: string;
  task_type: TaskType;
  priority: TaskPriority;
  status: WorkflowStatus;
  repository_url?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  runs: TaskRun[];
  validation?: HumanValidationRequest;
}

// ==================== WORKFLOW ====================

export interface WorkflowNode {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at?: string;
  completed_at?: string;
  duration?: number;
  error?: string;
}

export interface WorkflowState {
  workflow_id: string;
  status: WorkflowStatus;
  current_node?: string;
  completed_nodes: string[];
  task?: TaskRequest;
  results: Record<string, any>;
  error?: string;
  started_at?: string;
  completed_at?: string;
  langsmith_session?: string;
  db_task_id?: number;
  db_run_id?: number;
  db_step_id?: number;
}

export interface WorkflowProgress {
  task_id: string;
  workflow_id: string;
  current_node: string;
  progress_percentage: number;
  nodes: WorkflowNode[];
  estimated_time_remaining?: number;
}

// ==================== VALIDATION ====================

export interface HumanValidationRequest {
  validation_id: string;
  workflow_id: string;
  task_id: string;
  task_title: string;
  generated_code: string | Record<string, string>;
  code_summary: string;
  files_modified: string[];
  original_request: string;
  implementation_notes?: string;
  test_results?: string | Record<string, any>;
  pr_info?: PullRequestInfo | string;
  created_at: string;
  expires_at?: string;
  requested_by?: string;
}

export interface HumanValidationResponse {
  validation_id: string;
  status: HumanValidationStatus;
  comments?: string;
  suggested_changes?: string;
  approval_notes?: string;
  rejection_count?: number;
  modification_instructions?: string;
  should_retry_workflow?: boolean;
  validated_by?: string;
  validated_at: string;
  should_merge?: boolean;
  should_continue_workflow?: boolean;
}

// ==================== GIT & PULL REQUESTS ====================

export interface PullRequestInfo {
  number: number;
  title: string;
  url: string;
  branch: string;
  base_branch: string;
  status: string;
  created_at: string;
}

export interface GitOperationResult {
  success: boolean;
  message: string;
  branch?: string;
  commit_hash?: string;
  error?: string;
}

// ==================== TESTS ====================

export interface TestResult {
  success: boolean;
  test_type: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  coverage_percentage?: number;
  output: string;
  error?: string;
}

export interface LanguageTestStats {
  language: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  success_rate: number;
  avg_duration: number;
}

export interface TestDashboard {
  overall_success_rate: number;
  total_tests: number;
  by_language: LanguageTestStats[];
  recent_failures: TestFailure[];
  trends: TestTrend[];
}

export interface TestFailure {
  task_id: string;
  language: string;
  test_type: string;
  error_message: string;
  timestamp: string;
}

export interface TestTrend {
  date: string;
  success_rate: number;
  total_tests: number;
}

// ==================== MONITORING & METRICS ====================

export interface DashboardMetrics {
  tasks_active: number;
  tasks_today: number;
  success_rate_today: number;
  avg_execution_time: number;
  ai_cost_today: number;
  workers_active: number;
  queue_size: number;
}

export interface CeleryWorkerInfo {
  name: string;
  status: 'online' | 'offline';
  active_tasks: number;
  processed_tasks: number;
  cpu_usage?: number;
  memory_usage?: number;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  celery_workers: number;
  celery_healthy: boolean;
  rabbitmq_status: 'up' | 'down';
  postgres_status: 'up' | 'down';
  redis_status: 'up' | 'down';
  github_api_remaining: number;
  monday_api_remaining: number;
}

export interface AIModelUsage {
  model_name: string;
  provider: 'anthropic' | 'openai';
  total_tokens: number;
  total_requests: number;
  total_cost: number;
  avg_response_time: number;
  error_rate: number;
}

export interface CostSummary {
  period: 'today' | 'week' | 'month' | 'all';
  total_cost: number;
  by_model: AIModelUsage[];
  by_task_type: Record<string, number>;
  trend: CostTrend[];
}

export interface CostTrend {
  date: string;
  cost: number;
  requests: number;
}

// ==================== USERS ====================

export enum UserAccessStatus {
  AUTHORIZED = 'authorized',
  SUSPENDED = 'suspended',
  RESTRICTED = 'restricted',
  PENDING = 'pending',
}

export interface User {
  user_id: number;
  monday_user_id?: number;
  email: string;
  name?: string;
  slack_user_id?: string;
  is_active: boolean;
  created_at: string;
  total_tasks: number;
  total_validations: number;
  avg_response_time?: number;
  last_activity?: string;
  access_status?: UserAccessStatus;
  role?: string;
  team?: string;
  satisfaction_score?: number;
  satisfaction_comment?: string;
}

export interface UserStats {
  user_id: number;
  email: string;
  tasks_created: number;
  tasks_completed: number;
  tasks_failed: number;
  validations_approved: number;
  validations_rejected: number;
  avg_validation_time: number;
  preferred_languages: string[];
  last_activity_date?: string;
  satisfaction_score?: number;
  satisfaction_comment?: string;
  access_status: UserAccessStatus;
}

export interface UserHistoryItem {
  id: number;
  user_id: number;
  task_id: string;
  task_title: string;
  task_type: TaskType;
  status: WorkflowStatus;
  created_at: string;
  completed_at?: string;
  duration?: number;
  success: boolean;
}

export interface MondayUserInfo {
  id: number;
  name: string;
  email: string;
  role?: string;
  team?: string;
  status?: string;
  custom_fields?: Record<string, any>;
}

export interface UserManagementAction {
  action: 'update' | 'suspend' | 'activate' | 'delete' | 'restrict';
  user_id: number;
  data?: Partial<User>;
  reason?: string;
}

// ==================== INTEGRATIONS ====================

export interface MondayBoard {
  board_id: number;
  name: string;
  description?: string;
  workspace_id?: number;
  items_count: number;
  columns: MondayColumn[];
  is_active: boolean;
}

export interface MondayColumn {
  id: string;
  title: string;
  type: string;
}

export interface GitHubRepository {
  full_name: string;
  url: string;
  language?: string;
  stars: number;
  open_prs: number;
  last_commit?: string;
}

export interface SlackWorkspace {
  workspace_id: string;
  name: string;
  domain: string;
  members_count: number;
  bot_user_id: string;
}

export interface WebhookEvent {
  webhook_events_id: number;
  event_type: string;
  payload: Record<string, any>;
  received_at: string;
  processed: boolean;
  processed_at?: string;
  error_message?: string;
}

// ==================== LOGS ====================

export interface LogEntry {
  id: number;
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  service: string;
  message: string;
  task_id?: string;
  workflow_id?: string;
  context?: Record<string, any>;
}

export interface LogFilter {
  level?: string[];
  service?: string[];
  task_id?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}

// ==================== CONFIGURATION ====================

export interface SystemConfig {
  anthropic_api_key: string;
  openai_api_key?: string;
  github_token: string;
  monday_api_token: string;
  monday_board_id: string;
  slack_bot_token?: string;
  database_url: string;
  redis_url: string;
  rabbitmq_host: string;
  ai_model_temperature: number;
  ai_max_tokens: number;
  enable_smoke_tests: boolean;
  test_coverage_threshold: number;
  validation_timeout_command: number;
  validation_timeout_question: number;
}

// ==================== LANGUAGE DETECTION ====================

export interface LanguageDetectionResult {
  language: string;
  confidence: number;
  evidence: string[];
  fallback_used: boolean;
}

export interface LanguageStats {
  language: string;
  percentage: number;
  task_count: number;
  avg_confidence: number;
  failed_detections: number;
}

// ==================== QUEUE MANAGEMENT ====================

export interface QueueInfo {
  queue_id: string;
  monday_item_id: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  priority: number;
  created_at: string;
  started_at?: string;
  celery_task_id?: string;
}

export interface QueueStatus {
  monday_item_id: number;
  running_workflow?: QueueInfo;
  pending_workflows: QueueInfo[];
  total_queued: number;
}

// ==================== API RESPONSES ====================

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T = any> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

