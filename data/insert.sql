INSERT INTO tasks (monday_item_id, monday_board_id, title, description, priority, repository_url, repository_name, monday_status, internal_status, created_by_user_id, assigned_to)
VALUES
(1001, 200, 'Implémenter API Auth', 'Développer un service d’authentification JWT', 'high', 'https://github.com/smartelia/auth-service', 'auth-service', 'In Progress', 'processing', 1, 'alice'),
(1002, 200, 'Créer UI Dashboard', 'Interface utilisateur pour le suivi des runs', 'medium', 'https://github.com/smartelia/dashboard-ui', 'dashboard-ui', 'Stuck', 'pending', 2, 'bob'),
(1003, 201, 'Pipeline CI/CD', 'Configurer GitHub Actions pour tests automatiques', 'high', 'https://github.com/smartelia/ci-pipeline', 'ci-pipeline', 'Done', 'completed', 1, 'charlie');


INSERT INTO task_runs (task_id, run_number, status, celery_task_id, current_node, progress_percentage, ai_provider, model_name, git_branch_name, pull_request_url)
VALUES
(1, 1, 'completed', 'celery-abc-123', 'finalize', 100, 'claude', 'claude-3-sonnet', 'feature/auth-api', 'https://github.com/smartelia/auth-service/pull/10'),
(1, 2, 'running', 'celery-def-456', 'testing', 70, 'openai', 'gpt-4', 'feature/auth-bugfix', NULL),
(2, 1, 'failed', 'celery-ghi-789', 'prepare_env', 20, 'claude', 'claude-3-haiku', 'feature/dashboard-ui', NULL);
