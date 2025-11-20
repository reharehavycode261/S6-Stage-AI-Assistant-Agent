import { ReactNode } from 'react';
import { useAuthStore } from '@/stores/useAuthStore';

interface PermissionGuardProps {
  children: ReactNode;
  permission: string;
  fallback?: ReactNode;
}

export function PermissionGuard({ children, permission, fallback = null }: PermissionGuardProps) {
  const hasPermission = useAuthStore((state) => state.hasPermission(permission));

  if (!hasPermission) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

