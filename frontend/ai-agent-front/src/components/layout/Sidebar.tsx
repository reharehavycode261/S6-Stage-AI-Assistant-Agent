import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  GitBranch,
  ListTodo,
  Brain,
  Zap,
  Blocks,
  Terminal,
  PlayCircle,
  Settings,
  Chrome,
  Shield,
  Users,
} from 'lucide-react';
import { cn } from '@/utils/colors';
import { useAppStore } from '@/stores/useAppStore';
import { useAuthStore } from '@/stores/useAuthStore';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard, requiresPermission: null },
  { name: 'Tâches', href: '/tasks', icon: ListTodo, requiresPermission: null },
  { name: 'Utilisateurs', href: '/users', icon: Users, requiresPermission: null },
  { name: 'Workflow', href: '/workflow', icon: GitBranch, requiresPermission: null },
  { name: 'Browser QA', href: '/browser-qa', icon: Chrome, requiresPermission: null },
  { name: 'Modèles IA', href: '/ai-models', icon: Brain, requiresPermission: null },
  { name: 'Performance', href: '/performance', icon: Zap, requiresPermission: null },
  { name: 'Intégrations', href: '/integrations', icon: Blocks, requiresPermission: 'integrations:read' },
  { name: 'Logs', href: '/logs', icon: Terminal, requiresPermission: null },
  { name: 'Playground', href: '/playground', icon: PlayCircle, requiresPermission: null },
  { name: 'Audit Logs', href: '/audit', icon: Shield, requiresPermission: 'audit:read' },
  { name: 'Configuration', href: '/config', icon: Settings, requiresPermission: 'config:read' },
];

export function Sidebar() {
  const sidebarOpen = useAppStore((state) => state.sidebarOpen);
  const { hasPermission } = useAuthStore();
 
  // Filtrer la navigation selon les permissions
  const visibleNavigation = navigation.filter((item) => {
    if (!item.requiresPermission) return true;
    return hasPermission(item.requiresPermission);
  });
 
  return (
    <aside
      className={cn(
        'fixed left-0 top-0 h-screen bg-white border-r border-gray-200 transition-all duration-300 z-40',
        sidebarOpen ? 'w-64' : 'w-20'
      )}
    >
      {/* Logo */}
      <div className="h-16 flex items-center justify-center border-b border-gray-200 px-4">
        {sidebarOpen ? (
          <div className="text-center">
            <h1 className="text-xl font-bold text-primary-600 font-brand">AI-Agent</h1>
            <p className="text-xs text-gray-500">VyData Admin</p>
          </div>
        ) : (
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center text-white font-bold">
            AI
          </div>
        )}
      </div>
 
      {/* Navigation */}
      <nav className="flex-1 p-5 space-y-3 overflow-y-auto scrollbar-thin">
        {visibleNavigation.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-4 py-3 rounded-xl text-[15px] font-medium transition-colors',
                  isActive
                    ? 'bg-blue-50 text-blue-700 border border-blue-200'
                    : 'text-gray-700 hover:bg-gray-100',
                  !sidebarOpen && 'justify-center px-0 py-2'
                )
              }
            >
              <span
                className={cn(
                  'flex items-center justify-center',
                  !sidebarOpen && 'h-9 w-9 rounded-lg'
                )}
              >
                <Icon className={sidebarOpen ? 'h-5 w-5' : 'h-5 w-5'} />
              </span>
              {sidebarOpen && <span>{item.name}</span>}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
