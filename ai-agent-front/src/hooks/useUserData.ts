import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { User, UserManagementAction, UserAccessStatus } from '@/types';

/**
 * Hook pour gérer les données utilisateurs
 */

// Récupérer tous les utilisateurs
export function useUsers(filters?: {
  access_status?: UserAccessStatus;
  search?: string;
  sort_by?: 'name' | 'last_activity' | 'tasks_completed' | 'satisfaction_score';
  order?: 'asc' | 'desc';
}) {
  return useQuery({
    queryKey: ['users', filters],
    queryFn: async () => {
      const response = await apiClient.getUsers({
        access_status: filters?.access_status,
        search: filters?.search,
        sort_by: filters?.sort_by,
        order: filters?.order,
      });
      return response;
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

// Récupérer un utilisateur spécifique
export function useUser(userId?: number) {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: async () => {
      if (!userId) return null;
      return await apiClient.getUserById(userId);
    },
    enabled: !!userId,
  });
}

// Récupérer les statistiques d'un utilisateur
export function useUserStats(userId?: number) {
  return useQuery({
    queryKey: ['user-stats', userId],
    queryFn: async () => {
      if (!userId) return null;
      return await apiClient.getUserStats(userId);
    },
    enabled: !!userId,
  });
}

// Récupérer l'historique d'un utilisateur
export function useUserHistory(userId?: number, limit: number = 50) {
  return useQuery({
    queryKey: ['user-history', userId, limit],
    queryFn: async () => {
      if (!userId) return [];
      return await apiClient.getUserHistory(userId, limit);
    },
    enabled: !!userId,
  });
}

// Mettre à jour un utilisateur
export function useUpdateUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ userId, data }: { userId: number; data: Partial<User> }) => {
      return await apiClient.updateUser(userId, data);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['user', variables.userId] });
      queryClient.invalidateQueries({ queryKey: ['users'] });
      queryClient.invalidateQueries({ queryKey: ['user-stats', variables.userId] });
    },
  });
}

// Suspendre un utilisateur
export function useSuspendUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ userId, reason }: { userId: number; reason?: string }) => {
      return await apiClient.suspendUser(userId, reason);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['user', variables.userId] });
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

// Activer un utilisateur
export function useActivateUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (userId: number) => {
      return await apiClient.activateUser(userId);
    },
    onSuccess: (_, userId) => {
      queryClient.invalidateQueries({ queryKey: ['user', userId] });
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

// Restreindre l'accès d'un utilisateur
export function useRestrictUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ userId, reason }: { userId: number; reason?: string }) => {
      return await apiClient.restrictUser(userId, reason);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['user', variables.userId] });
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

// Supprimer un utilisateur
export function useDeleteUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ userId, reason }: { userId: number; reason?: string }) => {
      return await apiClient.deleteUser(userId, reason);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

// Mettre à jour le score de satisfaction
export function useUpdateSatisfaction() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ 
      userId, 
      score, 
      comment 
    }: { 
      userId: number; 
      score: number; 
      comment?: string 
    }) => {
      return await apiClient.updateUserSatisfaction(userId, score, comment);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['user', variables.userId] });
      queryClient.invalidateQueries({ queryKey: ['user-stats', variables.userId] });
    },
  });
}

// Récupérer les statistiques globales des utilisateurs
export function useUsersGlobalStats() {
  return useQuery({
    queryKey: ['users-global-stats'],
    queryFn: async () => {
      return await apiClient.getUsersGlobalStats();
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Exécuter une action de gestion sur un utilisateur
export function useUserManagementAction() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (action: UserManagementAction) => {
      return await apiClient.performUserManagementAction(action);
    },
    onSuccess: (_, action) => {
      queryClient.invalidateQueries({ queryKey: ['user', action.user_id] });
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

