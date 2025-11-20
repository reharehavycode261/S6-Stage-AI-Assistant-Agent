/**
 * Store principal de l'application
 */
import { create } from 'zustand';
import type { SystemHealth, DashboardMetrics } from '@/types';

interface AppState {
  // System health
  systemHealth: SystemHealth | null;
  isSystemHealthy: boolean;
  
  // Dashboard metrics
  metrics: DashboardMetrics | null;
  
  // UI state
  sidebarOpen: boolean;
  darkMode: boolean;
  
  // Notifications
  notifications: Notification[];
  
  // Actions
  setSystemHealth: (health: SystemHealth) => void;
  setMetrics: (metrics: DashboardMetrics) => void;
  toggleSidebar: () => void;
  toggleDarkMode: () => void;
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
}

interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: Date;
}

export const useAppStore = create<AppState>((set, get) => ({
  // Initial state
  systemHealth: null,
  isSystemHealthy: true,
  metrics: null,
  sidebarOpen: true,
  darkMode: false,
  notifications: [],

  // Actions
  setSystemHealth: (health) =>
    set({
      systemHealth: health,
      isSystemHealthy: health.status === 'healthy',
    }),

  setMetrics: (metrics) => set({ metrics }),

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),

  addNotification: (notification) => {
    const id = `notif-${Date.now()}-${Math.random()}`;
    set((state) => ({
      notifications: [
        ...state.notifications,
        { ...notification, id, timestamp: new Date() },
      ],
    }));
    
    // Auto-remove après 5 secondes
    setTimeout(() => {
      get().removeNotification(id);
    }, 5000);
  },

  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),

  clearNotifications: () => set({ notifications: [] }),
}));

