/**
 * Store pour la gestion des tâches
 */
import { create } from 'zustand';
import type { TaskDetail, TaskStatusResponse, WorkflowProgress } from '@/types';

interface TaskState {
  // Tasks data
  tasks: Map<string, TaskDetail>;
  taskStatuses: Map<string, TaskStatusResponse>;
  workflowProgress: Map<string, WorkflowProgress>;
  
  // Filters
  statusFilter: string | null;
  typeFilter: string | null;
  priorityFilter: string | null;
  searchQuery: string;
  
  // Selected task
  selectedTaskId: string | null;
  
  // Actions
  setTasks: (tasks: TaskDetail[]) => void;
  addTask: (task: TaskDetail) => void;
  updateTask: (taskId: string, task: Partial<TaskDetail>) => void;
  setTaskStatus: (taskId: string, status: TaskStatusResponse) => void;
  setWorkflowProgress: (workflowId: string, progress: WorkflowProgress) => void;
  selectTask: (taskId: string | null) => void;
  
  // Filters
  setStatusFilter: (status: string | null) => void;
  setTypeFilter: (type: string | null) => void;
  setPriorityFilter: (priority: string | null) => void;
  setSearchQuery: (query: string) => void;
  clearFilters: () => void;
  
  // Helpers
  getTask: (taskId: string) => TaskDetail | undefined;
  getFilteredTasks: () => TaskDetail[];
}

export const useTaskStore = create<TaskState>((set, get) => ({
  // Initial state
  tasks: new Map(),
  taskStatuses: new Map(),
  workflowProgress: new Map(),
  statusFilter: null,
  typeFilter: null,
  priorityFilter: null,
  searchQuery: '',
  selectedTaskId: null,

  // Actions
  setTasks: (tasks) =>
    set({
      tasks: new Map(tasks.map((task) => [String(task.tasks_id), task])),
    }),

  addTask: (task) =>
    set((state) => {
      const newTasks = new Map(state.tasks);
      newTasks.set(String(task.tasks_id), task);
      return { tasks: newTasks };
    }),

  updateTask: (taskId, taskUpdate) =>
    set((state) => {
      const newTasks = new Map(state.tasks);
      const existing = newTasks.get(taskId);
      if (existing) {
        newTasks.set(taskId, { ...existing, ...taskUpdate });
      }
      return { tasks: newTasks };
    }),

  setTaskStatus: (taskId, status) =>
    set((state) => {
      const newStatuses = new Map(state.taskStatuses);
      newStatuses.set(taskId, status);
      return { taskStatuses: newStatuses };
    }),

  setWorkflowProgress: (workflowId, progress) =>
    set((state) => {
      const newProgress = new Map(state.workflowProgress);
      newProgress.set(workflowId, progress);
      return { workflowProgress: newProgress };
    }),

  selectTask: (taskId) => set({ selectedTaskId: taskId }),

  // Filters
  setStatusFilter: (status) => set({ statusFilter: status }),
  setTypeFilter: (type) => set({ typeFilter: type }),
  setPriorityFilter: (priority) => set({ priorityFilter: priority }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  clearFilters: () =>
    set({
      statusFilter: null,
      typeFilter: null,
      priorityFilter: null,
      searchQuery: '',
    }),

  // Helpers
  getTask: (taskId) => get().tasks.get(taskId),

  getFilteredTasks: () => {
    const { tasks, statusFilter, typeFilter, priorityFilter, searchQuery } = get();
    let filtered = Array.from(tasks.values());

    if (statusFilter) {
      filtered = filtered.filter((task) => task.status === statusFilter);
    }

    if (typeFilter) {
      filtered = filtered.filter((task) => task.task_type === typeFilter);
    }

    if (priorityFilter) {
      filtered = filtered.filter((task) => task.priority === priorityFilter);
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (task) =>
          task.title.toLowerCase().includes(query) ||
          task.description.toLowerCase().includes(query)
      );
    }

    return filtered;
  },
}));

