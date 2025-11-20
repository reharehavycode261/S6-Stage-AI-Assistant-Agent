import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout/Layout';

// Auth Components
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { RoleGuard } from './components/auth/RoleGuard';

// Pages
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { WorkflowPage } from './pages/WorkflowPage';
import { TasksPage } from './pages/TasksPage';
import { TaskDetailPage } from './pages/TaskDetailPage';
import { UsersPage } from './pages/UsersPage';
import { AIModelsPage } from './pages/AIModelsPage';
import { PerformancePage } from './pages/PerformancePage';
import { IntegrationsPage } from './pages/IntegrationsPage';
import { LogsPage } from './pages/LogsPage';
import { PlaygroundPage } from './pages/PlaygroundPage';
import { ConfigPage } from './pages/ConfigPage';
import { BrowserQAPage } from './pages/BrowserQAPage';
import { AuditLogsPage } from './pages/AuditLogsPage';

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000, // 30 seconds
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Route publique - Login */}
          <Route path="/login" element={<LoginPage />} />

          {/* Routes protégées */}
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Layout>
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/workflow" element={<WorkflowPage />} />
                    <Route path="/tasks" element={<TasksPage />} />
                    <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
                    <Route path="/users" element={<UsersPage />} />
                    <Route path="/ai-models" element={<AIModelsPage />} />
                    <Route path="/performance" element={<PerformancePage />} />
                    
                    {/* Routes sensibles - Admin & Developer uniquement */}
                    <Route
                      path="/config"
                      element={
                        <RoleGuard roles={['Admin', 'Developer']}>
                          <ConfigPage />
                        </RoleGuard>
                      }
                    />
                    <Route
                      path="/integrations"
                      element={
                        <RoleGuard roles={['Admin', 'Developer']}>
                          <IntegrationsPage />
                        </RoleGuard>
                      }
                    />
                    
                    {/* Routes accessibles à tous les rôles authentifiés */}
                    <Route path="/logs" element={<LogsPage />} />
                    <Route path="/playground" element={<PlaygroundPage />} />
                    <Route path="/browser-qa" element={<BrowserQAPage />} />
                    
                    {/* Audit Logs - Admin & Auditor uniquement */}
                    <Route
                      path="/audit"
                      element={
                        <RoleGuard roles={['Admin', 'Auditor']}>
                          <AuditLogsPage />
                        </RoleGuard>
                      }
                    />
                    
                    {/* Redirection par défaut */}
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Layout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;

