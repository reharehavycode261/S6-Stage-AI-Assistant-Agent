import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { MondayUserInfo } from '@/types';

/**
 * Hook pour interagir avec l'API Monday.com
 */

// Récupérer les informations d'un utilisateur depuis Monday
export function useMondayUserInfo(userId?: number) {
  return useQuery({
    queryKey: ['monday-user', userId],
    queryFn: async () => {
      if (!userId) return null;
      return await apiClient.getMondayUserInfo(userId);
    },
    enabled: !!userId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Récupérer tous les utilisateurs depuis Monday
export function useMondayUsers() {
  return useQuery({
    queryKey: ['monday-users'],
    queryFn: async () => {
      return await apiClient.getAllMondayUsers();
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Mettre à jour un utilisateur dans Monday
export function useUpdateMondayUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ userId, data }: { userId: number; data: Partial<MondayUserInfo> }) => {
      return await apiClient.updateMondayUser(userId, data);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['monday-user', variables.userId] });
      queryClient.invalidateQueries({ queryKey: ['monday-users'] });
    },
  });
}

// Récupérer les colonnes d'un board Monday
export function useMondayBoardColumns(boardId?: number) {
  return useQuery({
    queryKey: ['monday-board-columns', boardId],
    queryFn: async () => {
      if (!boardId) return [];
      return await apiClient.getMondayBoardColumns(boardId);
    },
    enabled: !!boardId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// Mettre à jour une colonne d'un item Monday
export function useUpdateMondayItemColumn() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ 
      boardId, 
      itemId, 
      columnId, 
      value 
    }: { 
      boardId: number; 
      itemId: number; 
      columnId: string; 
      value: any 
    }) => {
      return await apiClient.updateMondayItemColumn(boardId, itemId, columnId, value);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monday-user'] });
      queryClient.invalidateQueries({ queryKey: ['monday-users'] });
    },
  });
}

// Archiver un utilisateur dans Monday
export function useArchiveMondayUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (itemId: number) => {
      return await apiClient.archiveMondayItem(itemId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monday-users'] });
    },
  });
}

// Ajouter un log dans Monday
export function useAddMondayLog() {
  return useMutation({
    mutationFn: async ({ 
      itemId, 
      message 
    }: { 
      itemId: number; 
      message: string 
    }) => {
      return await apiClient.addMondayLog(itemId, message);
    },
  });
}

// Synchroniser les données utilisateur avec Monday
export function useSyncUserWithMonday() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (userId: number) => {
      return await apiClient.syncUserWithMonday(userId);
    },
    onSuccess: (_, userId) => {
      queryClient.invalidateQueries({ queryKey: ['user', userId] });
      queryClient.invalidateQueries({ queryKey: ['monday-user', userId] });
    },
  });
}

