import { useState } from 'react';
import { Bell, Menu, Settings, User, Search, LogOut, Shield } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/common/Button';
import { useAppStore } from '@/stores/useAppStore';
import { useWebSocketStore } from '@/stores/useWebSocketStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { cn } from '@/utils/colors';

export function Header() {
  const navigate = useNavigate();
  const { toggleSidebar, notifications, systemHealth } = useAppStore();
  const { isConnected } = useWebSocketStore();
  const { user, logout } = useAuthStore();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const pendingNotifications = notifications.filter((n) => n.type === 'warning' || n.type === 'error');

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'Admin': return 'bg-purple-600';
      case 'Developer': return 'bg-blue-600';
      case 'Viewer': return 'bg-green-600';
      case 'Auditor': return 'bg-orange-600';
      default: return 'bg-gray-600';
    }
  };

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 sticky top-0 z-30">
      {/* Left section */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleSidebar}
          className="p-2"
        >
          <Menu className="h-5 w-5" />
        </Button>

        {/* Search bar */}
        <div className="relative w-96 hidden md:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Rechercher des tâches, utilisateurs..."
            className="input pl-10 w-full"
          />
        </div>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-3">
        {/* WebSocket Status */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50">
          <div
            className={cn(
              'w-2 h-2 rounded-full',
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            )}
          />
          <span className="text-xs text-gray-600">
            {isConnected ? 'Connecté' : 'Déconnecté'}
          </span>
        </div>

        {/* System Health */}
        {systemHealth && (
          <div
            className={cn(
              'px-3 py-1.5 rounded-lg text-xs font-medium',
              systemHealth.status === 'healthy'
                ? 'bg-green-50 text-green-700'
                : systemHealth.status === 'degraded'
                ? 'bg-yellow-50 text-yellow-700'
                : 'bg-red-50 text-red-700'
            )}
          >
            {systemHealth.status === 'healthy' ? '✓ Système sain' : '⚠ Problème détecté'}
          </div>
        )}

        {/* Notifications */}
        <button className="relative p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <Bell className="h-5 w-5 text-gray-600" />
          {pendingNotifications.length > 0 && (
            <span className="absolute top-1 right-1 w-4 h-4 bg-red-500 text-white text-xs flex items-center justify-center rounded-full">
              {pendingNotifications.length}
            </span>
          )}
        </button>

        {/* Settings */}
        <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <Settings className="h-5 w-5 text-gray-600" />
        </button>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <div className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center',
              getRoleColor(user?.role || '')
            )}>
              <User className="h-4 w-4 text-white" />
            </div>
            <div className="hidden lg:block text-left">
              <div className="text-sm font-medium text-gray-700">{user?.name || 'User'}</div>
              <div className="text-xs text-gray-500">{user?.role}</div>
            </div>
          </button>

          {/* Dropdown menu */}
          {showUserMenu && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowUserMenu(false)}
              />
              <div className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-lg border border-gray-200 py-2 z-50">
                {/* User info */}
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-900">{user?.name}</p>
                  <p className="text-xs text-gray-500 truncate">{user?.email}</p>
                  <div className="mt-2">
                    <span className={cn(
                      'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium text-white',
                      getRoleColor(user?.role || '')
                    )}>
                      <Shield className="w-3 h-3" />
                      {user?.role}
                    </span>
                  </div>
                </div>

                {/* Menu items */}
                <div className="py-2">
                  <button
                    onClick={() => {
                      navigate('/audit');
                      setShowUserMenu(false);
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                  >
                    <Shield className="w-4 h-4" />
                    Audit Logs
                  </button>
                  <button
                    onClick={() => {
                      navigate('/config');
                      setShowUserMenu(false);
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                  >
                    <Settings className="w-4 h-4" />
                    Configuration
                  </button>
                </div>

                {/* Logout */}
                <div className="border-t border-gray-100 pt-2">
                  <button
                    onClick={handleLogout}
                    className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                  >
                    <LogOut className="w-4 h-4" />
                    Se déconnecter
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
