/**
 * Store pour gérer les connexions WebSocket
 */
import { create } from 'zustand';
import { wsService } from '@/services/websocket';
import type { WorkflowProgress, LogEntry, DashboardMetrics } from '@/types';

interface WebSocketState {
  isConnected: boolean;
  
  // Real-time data
  recentLogs: LogEntry[];
  liveMetrics: DashboardMetrics | null;
  activeWorkflows: Map<string, WorkflowProgress>;
  
  // Actions
  setConnected: (connected: boolean) => void;
  addLog: (log: LogEntry) => void;
  updateMetrics: (metrics: DashboardMetrics) => void;
  updateWorkflowProgress: (progress: WorkflowProgress) => void;
  clearLogs: () => void;
  
  // WebSocket subscriptions
  subscribeToTask: (taskId: string) => void;
  unsubscribeFromTask: (taskId: string) => void;
  subscribeToLogs: () => void;
  unsubscribeFromLogs: () => void;
}

const MAX_LOGS = 100; // Keep only last 100 logs in memory

export const useWebSocketStore = create<WebSocketState>((set, get) => {
  // Setup WebSocket event listeners
  wsService.on('workflow:progress', (progress: WorkflowProgress) => {
    get().updateWorkflowProgress(progress);
  });

  wsService.on('log:new', (log: LogEntry) => {
    get().addLog(log);
  });

  wsService.on('metrics:update', (metrics: DashboardMetrics) => {
    get().updateMetrics(metrics);
  });

  // Monitor connection status
  setInterval(() => {
    set({ isConnected: wsService.isConnected() });
  }, 1000);

  return {
    // Initial state
    isConnected: false,
    recentLogs: [],
    liveMetrics: null,
    activeWorkflows: new Map(),

    // Actions
    setConnected: (connected) => set({ isConnected: connected }),

    addLog: (log) =>
      set((state) => {
        const newLogs = [...state.recentLogs, log];
        // Keep only last MAX_LOGS entries
        if (newLogs.length > MAX_LOGS) {
          newLogs.shift();
        }
        return { recentLogs: newLogs };
      }),

    updateMetrics: (metrics) => set({ liveMetrics: metrics }),

    updateWorkflowProgress: (progress) =>
      set((state) => {
        const newWorkflows = new Map(state.activeWorkflows);
        newWorkflows.set(progress.workflow_id, progress);
        return { activeWorkflows: newWorkflows };
      }),

    clearLogs: () => set({ recentLogs: [] }),

    // WebSocket subscriptions
    subscribeToTask: (taskId) => wsService.subscribeToTask(taskId),
    unsubscribeFromTask: (taskId) => wsService.unsubscribeFromTask(taskId),
    subscribeToLogs: () => wsService.subscribeToLogs(),
    unsubscribeFromLogs: () => wsService.unsubscribeFromLogs(),
  };
});

