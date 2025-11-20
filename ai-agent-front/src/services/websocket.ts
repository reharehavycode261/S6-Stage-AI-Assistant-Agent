/**
 * Service WebSocket pour les mises à jour en temps réel
 */
import { io, Socket } from 'socket.io-client';
import type { WorkflowProgress, LogEntry, DashboardMetrics } from '@/types';

type EventCallback<T = any> = (data: T) => void;

class WebSocketService {
  private socket: Socket | null = null;
  private listeners: Map<string, Set<EventCallback>> = new Map();
  private maxReconnectAttempts = 5;

  constructor() {
    this.connect();
  }

  private connect() {
    const wsUrl = import.meta.env.VITE_WS_URL || 'http://localhost:8000';

    this.socket = io(wsUrl, {
      transports: ['websocket'],
      autoConnect: true,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: this.maxReconnectAttempts,
    });

    this.socket.on('connect', () => {
      console.log('✅ WebSocket connecté');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('❌ WebSocket déconnecté:', reason);
    });

    this.socket.on('reconnect_attempt', (attemptNumber) => {
      console.log(`🔄 Tentative de reconnexion ${attemptNumber}/${this.maxReconnectAttempts}`);
    });

    this.socket.on('reconnect_failed', () => {
      console.error('❌ Échec de la reconnexion WebSocket');
    });

    // Enregistrer les handlers pour les événements serveur
    this.setupEventHandlers();
  }

  private setupEventHandlers() {
    if (!this.socket) return;

    // Workflow progress updates
    this.socket.on('workflow:progress', (data: WorkflowProgress) => {
      this.emit('workflow:progress', data);
    });

    // Workflow completed
    this.socket.on('workflow:completed', (data: any) => {
      this.emit('workflow:completed', data);
    });

    // Workflow failed
    this.socket.on('workflow:failed', (data: any) => {
      this.emit('workflow:failed', data);
    });

    // New log entry
    this.socket.on('log:new', (data: LogEntry) => {
      this.emit('log:new', data);
    });

    // Dashboard metrics update
    this.socket.on('metrics:update', (data: DashboardMetrics) => {
      this.emit('metrics:update', data);
    });

    // Task status change
    this.socket.on('task:status', (data: any) => {
      this.emit('task:status', data);
    });

    // Validation pending
    this.socket.on('validation:pending', (data: any) => {
      this.emit('validation:pending', data);
    });

    // Validation completed
    this.socket.on('validation:completed', (data: any) => {
      this.emit('validation:completed', data);
    });
  }

  /**
   * S'abonner à un événement
   */
  on<T = any>(event: string, callback: EventCallback<T>) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);

    // Retourner une fonction pour se désabonner
    return () => this.off(event, callback);
  }

  /**
   * Se désabonner d'un événement
   */
  off(event: string, callback: EventCallback) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
      if (callbacks.size === 0) {
        this.listeners.delete(event);
      }
    }
  }

  /**
   * Émettre un événement côté client (pour les listeners locaux)
   */
  private emit<T = any>(event: string, data: T) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach((callback) => callback(data));
    }
  }

  /**
   * Envoyer un événement au serveur
   */
  send(event: string, data: any) {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    } else {
      console.warn('WebSocket non connecté, impossible d\'envoyer:', event);
    }
  }

  /**
   * S'abonner aux updates d'une tâche spécifique
   */
  subscribeToTask(taskId: string) {
    this.send('subscribe:task', { task_id: taskId });
  }

  /**
   * Se désabonner des updates d'une tâche
   */
  unsubscribeFromTask(taskId: string) {
    this.send('unsubscribe:task', { task_id: taskId });
  }

  /**
   * S'abonner aux logs en temps réel
   */
  subscribeToLogs(filter?: { level?: string; service?: string }) {
    this.send('subscribe:logs', filter || {});
  }

  /**
   * Se désabonner des logs
   */
  unsubscribeFromLogs() {
    this.send('unsubscribe:logs', {});
  }

  /**
   * Vérifier si le WebSocket est connecté
   */
  isConnected(): boolean {
    return this.socket?.connected || false;
  }

  /**
   * Fermer la connexion WebSocket
   */
  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.listeners.clear();
  }
}

// Singleton instance
export const wsService = new WebSocketService();

// Export par défaut
export default wsService;

