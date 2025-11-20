import { useState, useEffect } from 'react';
import {
  X,
  Save,
  Shield,
  ShieldOff,
  Trash2,
  AlertTriangle,
  RefreshCw,
  CheckCircle,
  Clock,
  Star,
  User,
  Mail,
  Calendar,
  Activity,
  TrendingUp,
  ExternalLink,
  Settings,
  History,
} from 'lucide-react';
import { User as UserType, UserAccessStatus } from '@/types';
import { 
  useUser, 
  useUserStats, 
  useUserHistory,
  useUpdateUser, 
  useSuspendUser, 
  useActivateUser, 
  useRestrictUser,
  useDeleteUser,
  useUpdateSatisfaction
} from '@/hooks/useUserData';
import { useMondayUserInfo, useUpdateMondayUser, useSyncUserWithMonday } from '@/hooks/useMondayApi';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { Badge } from '@/components/common/Badge';
import { Card } from '@/components/common/Card';

interface UserManagementModalProps {
  userId: number | null;
  isOpen: boolean;
  onClose: () => void;
}

export function UserManagementModal({ userId, isOpen, onClose }: UserManagementModalProps) {
  const [activeTab, setActiveTab] = useState<'info' | 'stats' | 'history' | 'monday'>('info');
  const [isEditing, setIsEditing] = useState(false);
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);
  const [deleteReason, setDeleteReason] = useState('');
  const [actionReason, setActionReason] = useState('');

  // État du formulaire
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    role: '',
    team: '',
    satisfaction_score: 0,
    satisfaction_comment: '',
  });

  // Hooks de données
  const { data: user, isLoading: userLoading } = useUser(userId || undefined);
  const { data: userStats } = useUserStats(userId || undefined);
  const { data: userHistory } = useUserHistory(userId || undefined);
  const { data: mondayUser } = useMondayUserInfo(user?.monday_user_id);

  // Hooks de mutation
  const updateUserMutation = useUpdateUser();
  const suspendUserMutation = useSuspendUser();
  const activateUserMutation = useActivateUser();
  const restrictUserMutation = useRestrictUser();
  const deleteUserMutation = useDeleteUser();
  const updateSatisfactionMutation = useUpdateSatisfaction();
  const updateMondayMutation = useUpdateMondayUser();
  const syncMondayMutation = useSyncUserWithMonday();

  // Mettre à jour le formulaire quand les données changent
  useEffect(() => {
    if (user) {
      setFormData({
        name: user.name || '',
        email: user.email || '',
        role: user.role || '',
        team: user.team || '',
        satisfaction_score: user.satisfaction_score || 0,
        satisfaction_comment: user.satisfaction_comment || '',
      });
    }
  }, [user]);

  if (!isOpen || !userId) return null;

  const handleSave = async () => {
    try {
      await updateUserMutation.mutateAsync({
        userId,
        data: {
          name: formData.name,
          role: formData.role,
          team: formData.team,
        },
      });

      if (formData.satisfaction_score !== user?.satisfaction_score) {
        await updateSatisfactionMutation.mutateAsync({
          userId,
          score: formData.satisfaction_score,
          comment: formData.satisfaction_comment,
        });
      }

      setIsEditing(false);
    } catch (error) {
      console.error('Erreur lors de la mise à jour:', error);
    }
  };

  const handleSuspend = async () => {
    try {
      await suspendUserMutation.mutateAsync({ userId, reason: actionReason });
      setActionReason('');
    } catch (error) {
      console.error('Erreur lors de la suspension:', error);
    }
  };

  const handleActivate = async () => {
    try {
      await activateUserMutation.mutateAsync(userId);
    } catch (error) {
      console.error('Erreur lors de l\'activation:', error);
    }
  };

  const handleRestrict = async () => {
    try {
      await restrictUserMutation.mutateAsync({ userId, reason: actionReason });
      setActionReason('');
    } catch (error) {
      console.error('Erreur lors de la restriction:', error);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteUserMutation.mutateAsync({ userId, reason: deleteReason });
      setShowConfirmDelete(false);
      onClose();
    } catch (error) {
      console.error('Erreur lors de la suppression:', error);
    }
  };

  const handleSyncMonday = async () => {
    try {
      await syncMondayMutation.mutateAsync(userId);
    } catch (error) {
      console.error('Erreur lors de la synchronisation:', error);
    }
  };

  const getStatusColor = (status?: UserAccessStatus) => {
    switch (status) {
      case UserAccessStatus.AUTHORIZED: return 'text-green-600';
      case UserAccessStatus.SUSPENDED: return 'text-red-600';
      case UserAccessStatus.RESTRICTED: return 'text-orange-600';
      case UserAccessStatus.PENDING: return 'text-gray-600';
      default: return 'text-gray-600';
    }
  };

  const formatDate = (date?: string) => {
    if (!date) return 'N/A';
    return new Date(date).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (userLoading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
        <div className="bg-white rounded-xl p-8">
          <LoadingSpinner size="lg" />
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">Gestion de l'utilisateur</h2>
              <p className="text-blue-100 mt-1">{user?.email}</p>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:bg-white/20 rounded-lg p-2 transition-colors"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-2 mt-4">
            {['info', 'stats', 'history', 'monday'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === tab
                    ? 'bg-white text-blue-600'
                    : 'bg-white/20 text-white hover:bg-white/30'
                }`}
              >
                {tab === 'info' && 'Informations'}
                {tab === 'stats' && 'Statistiques'}
                {tab === 'history' && 'Historique'}
                {tab === 'monday' && 'Monday.com'}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Tab Info */}
          {activeTab === 'info' && (
            <div className="space-y-6">
              {/* Statut et actions rapides */}
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold">Statut et actions</h3>
                  <div className={`flex items-center gap-2 font-semibold ${getStatusColor(user?.access_status)}`}>
                    {user?.access_status === UserAccessStatus.AUTHORIZED && <Shield className="h-5 w-5" />}
                    {user?.access_status === UserAccessStatus.SUSPENDED && <ShieldOff className="h-5 w-5" />}
                    {user?.access_status === UserAccessStatus.RESTRICTED && <AlertTriangle className="h-5 w-5" />}
                    {user?.access_status?.toUpperCase() || 'AUTORISÉ'}
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {user?.access_status !== UserAccessStatus.SUSPENDED && (
                    <button
                      onClick={() => {
                        const reason = prompt('Raison de la suspension :');
                        if (reason) {
                          setActionReason(reason);
                          handleSuspend();
                        }
                      }}
                      className="flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                    >
                      <ShieldOff className="h-4 w-4" />
                      Suspendre
                    </button>
                  )}

                  {user?.access_status === UserAccessStatus.SUSPENDED && (
                    <button
                      onClick={handleActivate}
                      className="flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                    >
                      <Shield className="h-4 w-4" />
                      Activer
                    </button>
                  )}

                  <button
                    onClick={() => {
                      const reason = prompt('Raison de la restriction :');
                      if (reason) {
                        setActionReason(reason);
                        handleRestrict();
                      }
                    }}
                    className="flex items-center justify-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors"
                  >
                    <AlertTriangle className="h-4 w-4" />
                    Restreindre
                  </button>

                  <button
                    onClick={() => setShowConfirmDelete(true)}
                    className="flex items-center justify-center gap-2 px-4 py-2 bg-red-700 text-white rounded-lg hover:bg-red-800 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                    Supprimer
                  </button>

                  <button
                    onClick={handleSyncMonday}
                    disabled={syncMondayMutation.isPending}
                    className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                  >
                    <RefreshCw className={`h-4 w-4 ${syncMondayMutation.isPending ? 'animate-spin' : ''}`} />
                    Sync Monday
                  </button>
                </div>
              </Card>

              {/* Formulaire d'édition */}
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold">Informations personnelles</h3>
                  {!isEditing ? (
                    <button
                      onClick={() => setIsEditing(true)}
                      className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                    >
                      <Settings className="h-4 w-4" />
                      Modifier
                    </button>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={() => setIsEditing(false)}
                        className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors text-sm"
                      >
                        Annuler
                      </button>
                      <button
                        onClick={handleSave}
                        disabled={updateUserMutation.isPending}
                        className="flex items-center gap-2 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm disabled:opacity-50"
                      >
                        <Save className="h-4 w-4" />
                        Enregistrer
                      </button>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      <User className="inline h-4 w-4 mr-1" />
                      Nom
                    </label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      disabled={!isEditing}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      <Mail className="inline h-4 w-4 mr-1" />
                      Email
                    </label>
                    <input
                      type="email"
                      value={formData.email}
                      disabled
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 cursor-not-allowed"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      <Shield className="inline h-4 w-4 mr-1" />
                      Rôle
                    </label>
                    <input
                      type="text"
                      value={formData.role}
                      onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                      disabled={!isEditing}
                      placeholder="Ex: Développeur, Manager..."
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      <Activity className="inline h-4 w-4 mr-1" />
                      Équipe
                    </label>
                    <input
                      type="text"
                      value={formData.team}
                      onChange={(e) => setFormData({ ...formData, team: e.target.value })}
                      disabled={!isEditing}
                      placeholder="Ex: Frontend, Backend..."
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      <Star className="inline h-4 w-4 mr-1" />
                      Score de satisfaction (0-5)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="5"
                      step="0.1"
                      value={formData.satisfaction_score}
                      onChange={(e) => setFormData({ ...formData, satisfaction_score: parseFloat(e.target.value) })}
                      disabled={!isEditing}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      <Calendar className="inline h-4 w-4 mr-1" />
                      Dernière activité
                    </label>
                    <input
                      type="text"
                      value={formatDate(user?.last_activity)}
                      disabled
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 cursor-not-allowed"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Commentaire de satisfaction
                    </label>
                    <textarea
                      value={formData.satisfaction_comment}
                      onChange={(e) => setFormData({ ...formData, satisfaction_comment: e.target.value })}
                      disabled={!isEditing}
                      rows={3}
                      placeholder="Commentaire sur l'expérience utilisateur..."
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 resize-none"
                    />
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* Tab Stats */}
          {activeTab === 'stats' && userStats && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <div className="flex items-center gap-3 mb-3">
                  <CheckCircle className="h-6 w-6 text-green-600" />
                  <div>
                    <p className="text-sm text-gray-600">Tâches complétées</p>
                    <p className="text-2xl font-bold text-gray-900">{userStats.tasks_completed}</p>
                  </div>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-3 mb-3">
                  <X className="h-6 w-6 text-red-600" />
                  <div>
                    <p className="text-sm text-gray-600">Tâches échouées</p>
                    <p className="text-2xl font-bold text-gray-900">{userStats.tasks_failed}</p>
                  </div>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-3 mb-3">
                  <CheckCircle className="h-6 w-6 text-blue-600" />
                  <div>
                    <p className="text-sm text-gray-600">Validations approuvées</p>
                    <p className="text-2xl font-bold text-gray-900">{userStats.validations_approved}</p>
                  </div>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-3 mb-3">
                  <X className="h-6 w-6 text-orange-600" />
                  <div>
                    <p className="text-sm text-gray-600">Validations rejetées</p>
                    <p className="text-2xl font-bold text-gray-900">{userStats.validations_rejected}</p>
                  </div>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-3 mb-3">
                  <Clock className="h-6 w-6 text-purple-600" />
                  <div>
                    <p className="text-sm text-gray-600">Temps moyen de validation</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {Math.round(userStats.avg_validation_time / 60)}min
                    </p>
                  </div>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-3 mb-3">
                  <Star className="h-6 w-6 text-yellow-500" />
                  <div>
                    <p className="text-sm text-gray-600">Score de satisfaction</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {userStats.satisfaction_score?.toFixed(1) || 'N/A'}/5
                    </p>
                  </div>
                </div>
              </Card>

              <Card className="md:col-span-2">
                <h4 className="font-semibold text-gray-900 mb-3">Langages préférés</h4>
                <div className="flex flex-wrap gap-2">
                  {userStats.preferred_languages.map((lang) => (
                    <Badge key={lang} variant="primary">
                      {lang}
                    </Badge>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* Tab History */}
          {activeTab === 'history' && (
            <div className="space-y-3">
              {userHistory && userHistory.length > 0 ? (
                userHistory.map((item) => (
                  <Card key={item.id}>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900">{item.task_title}</h4>
                        <p className="text-sm text-gray-600 mt-1">ID: {item.task_id}</p>
                        <div className="flex items-center gap-4 mt-2 text-sm">
                          <span className="text-gray-500">
                            <Calendar className="inline h-4 w-4 mr-1" />
                            {formatDate(item.created_at)}
                          </span>
                          {item.duration && (
                            <span className="text-gray-500">
                              <Clock className="inline h-4 w-4 mr-1" />
                              {Math.round(item.duration / 60)}min
                            </span>
                          )}
                        </div>
                      </div>
                      <div>
                        {item.success ? (
                          <Badge variant="success">Réussi</Badge>
                        ) : (
                          <Badge variant="danger">Échoué</Badge>
                        )}
                      </div>
                    </div>
                  </Card>
                ))
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <History className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>Aucun historique disponible</p>
                </div>
              )}
            </div>
          )}

          {/* Tab Monday */}
          {activeTab === 'monday' && (
            <div className="space-y-4">
              {mondayUser ? (
                <>
                  <Card>
                    <h3 className="text-lg font-semibold mb-4">Informations Monday.com</h3>
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-gray-600">ID Monday :</span>
                        <span className="font-semibold">{mondayUser.id}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Nom :</span>
                        <span className="font-semibold">{mondayUser.name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Email :</span>
                        <span className="font-semibold">{mondayUser.email}</span>
                      </div>
                      {mondayUser.role && (
                        <div className="flex justify-between">
                          <span className="text-gray-600">Rôle :</span>
                          <span className="font-semibold">{mondayUser.role}</span>
                        </div>
                      )}
                      {mondayUser.team && (
                        <div className="flex justify-between">
                          <span className="text-gray-600">Équipe :</span>
                          <span className="font-semibold">{mondayUser.team}</span>
                        </div>
                      )}
                      {mondayUser.status && (
                        <div className="flex justify-between">
                          <span className="text-gray-600">Statut :</span>
                          <Badge variant="primary">{mondayUser.status}</Badge>
                        </div>
                      )}
                    </div>
                  </Card>

                  {mondayUser.custom_fields && Object.keys(mondayUser.custom_fields).length > 0 && (
                    <Card>
                      <h3 className="text-lg font-semibold mb-4">Champs personnalisés</h3>
                      <div className="space-y-2">
                        {Object.entries(mondayUser.custom_fields).map(([key, value]) => (
                          <div key={key} className="flex justify-between text-sm">
                            <span className="text-gray-600">{key} :</span>
                            <span className="font-medium">{String(value)}</span>
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}
                </>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <ExternalLink className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>Aucune donnée Monday.com disponible</p>
                  <button
                    onClick={handleSyncMonday}
                    className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Synchroniser avec Monday.com
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Confirmation de suppression */}
        {showConfirmDelete && (
          <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl p-6 max-w-md w-full">
              <div className="flex items-center gap-3 mb-4 text-red-600">
                <AlertTriangle className="h-8 w-8" />
                <h3 className="text-xl font-bold">Confirmer la suppression</h3>
              </div>
              <p className="text-gray-700 mb-4">
                Êtes-vous sûr de vouloir supprimer cet utilisateur ? Cette action est irréversible.
              </p>
              <textarea
                value={deleteReason}
                onChange={(e) => setDeleteReason(e.target.value)}
                placeholder="Raison de la suppression (obligatoire)..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg mb-4 resize-none"
                rows={3}
              />
              <div className="flex gap-3">
                <button
                  onClick={() => setShowConfirmDelete(false)}
                  className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                >
                  Annuler
                </button>
                <button
                  onClick={handleDelete}
                  disabled={!deleteReason || deleteUserMutation.isPending}
                  className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
                >
                  Supprimer définitivement
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

