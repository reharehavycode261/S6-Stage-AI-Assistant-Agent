import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useAppStore } from '@/stores/useAppStore';
import { cn } from '@/utils/colors';
import toast, { Toaster } from 'react-hot-toast';
import { useEffect } from 'react';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { sidebarOpen, notifications, removeNotification } = useAppStore();

  // Show toast notifications
  useEffect(() => {
    notifications.forEach((notification) => {
      const toastType = notification.type;
      const message = `${notification.title}: ${notification.message}`;

      switch (toastType) {
        case 'success':
          toast.success(message);
          break;
        case 'error':
          toast.error(message);
          break;
        case 'warning':
          toast(message, { icon: '⚠️' });
          break;
        case 'info':
          toast(message, { icon: 'ℹ️' });
          break;
      }

      // Remove notification after showing
      removeNotification(notification.id);
    });
  }, [notifications, removeNotification]);

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      
      <div
        className={cn(
          'transition-all duration-300',
          sidebarOpen ? 'ml-64' : 'ml-20'
        )}
      >
        <Header />
        
        <main className="p-6">
          {children}
        </main>
      </div>

      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#fff',
            color: '#363636',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
          },
          success: {
            iconTheme: {
              primary: '#10b981',
              secondary: '#fff',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
      />
    </div>
  );
}
