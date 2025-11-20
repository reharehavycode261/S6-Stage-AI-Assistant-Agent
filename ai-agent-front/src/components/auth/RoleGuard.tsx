import { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore, UserRole } from '@/stores/useAuthStore';
import { AlertCircle } from 'lucide-react';

interface RoleGuardProps {
  children: ReactNode;
  roles: UserRole | UserRole[];
  fallback?: ReactNode;
}

export function RoleGuard({ children, roles, fallback }: RoleGuardProps) {
  const hasRole = useAuthStore((state) => state.hasRole(roles));

  if (!hasRole) {
    if (fallback) {
      return <>{fallback}</>;
    }

    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full mx-4 p-8 bg-white rounded-2xl shadow-xl border border-gray-100">
          <div className="flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4 mx-auto">
            <AlertCircle className="w-8 h-8 text-red-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-2">
            Accès refusé
          </h2>
          <p className="text-gray-600 text-center mb-6">
            Vous n'avez pas les permissions nécessaires pour accéder à cette page.
          </p>
          <div className="bg-gray-50 p-4 rounded-lg">
            <p className="text-sm text-gray-700">
              <span className="font-medium">Rôles requis:</span>{' '}
              {Array.isArray(roles) ? roles.join(', ') : roles}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

