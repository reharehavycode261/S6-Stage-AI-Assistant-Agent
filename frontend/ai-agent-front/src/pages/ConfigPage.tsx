/**
 * ConfigPage - Page de configuration avancée avec sécurité renforcée
 * Fonctionnalités:
 * - Masquage des secrets par défaut
 * - Validation avant sauvegarde
 * - Backup automatique avant modification
 * - Historique des changements
 * - Import/Export configuration
 * - Rotation automatique des secrets
 */
import { useState, useEffect } from 'react';
import { 
  Save, 
  AlertCircle, 
  CheckCircle, 
  Shield, 
  History, 
  Download, 
  Upload,
  RefreshCw,
  Eye,
  EyeOff,
  Copy,
  Check,
  RotateCw,
  Archive,
  AlertTriangle,
  Key
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { SecretField } from '@/components/auth/SecretField';
import { PermissionGuard } from '@/components/auth/PermissionGuard';
import { useAuthStore } from '@/stores/useAuthStore';

interface ConfigData {
  monday_board_id: string;
  github_token: string;
  anthropic_api_key: string;
  openai_api_key: string;
  slack_bot_token: string;
  monday_api_token: string;
  webhook_secret: string;
  database_url: string;
  redis_url: string;
  rabbitmq_url: string;
}

interface ConfigBackup {
  id: string;
  timestamp: string;
  config: ConfigData;
  user: string;
  reason: string;
}

interface ConfigHistory {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  field: string;
  oldValue?: string;
  newValue?: string;
}

interface ValidationError {
  field: string;
  message: string;
}

export function ConfigPage() {
  const { user, logAuditEvent } = useAuthStore();
  
  // État de la configuration
  const [config, setConfig] = useState<ConfigData>({
    monday_board_id: '5084415062',
    github_token: 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    anthropic_api_key: 'sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    openai_api_key: 'sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    slack_bot_token: 'xoxb-xxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    monday_api_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
    webhook_secret: 'whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    database_url: 'postgresql://user:pass@localhost:5432/db',
    redis_url: 'redis://localhost:6379/0',
    rabbitmq_url: 'amqp://guest:guest@localhost:5672/',
  });
  
  const [originalConfig, setOriginalConfig] = useState<ConfigData>(config);
  const [backups, setBackups] = useState<ConfigBackup[]>([]);
  const [history, setHistory] = useState<ConfigHistory[]>([]);
  
  // États UI
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showBackups, setShowBackups] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [rotatingSecrets, setRotatingSecrets] = useState<string[]>([]);

  // Charger la configuration au démarrage
  useEffect(() => {
    loadConfig();
    loadHistory();
    loadBackups();
  }, []);

  const loadConfig = async () => {
    try {
      // TODO: Remplacer par vrai appel API
      // const response = await apiClient.getConfig();
      // setConfig(response.data);
      // setOriginalConfig(response.data);
      
      // Données mockées
      setOriginalConfig(config);
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  const loadHistory = async () => {
    try {
      // TODO: Remplacer par vrai appel API
      // const response = await apiClient.getConfigHistory();
      
      // Historique mocké
      const mockHistory: ConfigHistory[] = [
        {
          id: '1',
          timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
          user: 'admin@vydata.com',
          action: 'update',
          field: 'anthropic_api_key',
          oldValue: 'sk-ant-old***',
          newValue: 'sk-ant-new***'
        },
        {
          id: '2',
          timestamp: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
          user: 'admin@vydata.com',
          action: 'rotate',
          field: 'github_token',
          oldValue: 'ghp_old***',
          newValue: 'ghp_new***'
        },
      ];
      
      setHistory(mockHistory);
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  };

  const loadBackups = async () => {
    try {
      // TODO: Remplacer par vrai appel API
      // const response = await apiClient.getConfigBackups();
      
      // Backups mockés
      const mockBackups: ConfigBackup[] = [
        {
          id: '1',
          timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
          config: originalConfig,
          user: 'admin@vydata.com',
          reason: 'Automatic backup before modification'
        },
      ];
      
      setBackups(mockBackups);
    } catch (error) {
      console.error('Failed to load backups:', error);
    }
  };

  // Validation de la configuration
  const validateConfig = (): ValidationError[] => {
    const errors: ValidationError[] = [];

    // Monday Board ID
    if (!config.monday_board_id || !/^\d+$/.test(config.monday_board_id)) {
      errors.push({
        field: 'monday_board_id',
        message: 'Le Board ID doit être un nombre'
      });
    }

    // GitHub Token
    if (!config.github_token || !config.github_token.startsWith('ghp_')) {
      errors.push({
        field: 'github_token',
        message: 'Le token GitHub doit commencer par "ghp_"'
      });
    }

    // Anthropic API Key
    if (!config.anthropic_api_key || !config.anthropic_api_key.startsWith('sk-ant-')) {
      errors.push({
        field: 'anthropic_api_key',
        message: 'La clé API Anthropic doit commencer par "sk-ant-"'
      });
    }

    // OpenAI API Key
    if (!config.openai_api_key || !config.openai_api_key.startsWith('sk-')) {
      errors.push({
        field: 'openai_api_key',
        message: 'La clé API OpenAI doit commencer par "sk-"'
      });
    }

    // Slack Bot Token
    if (!config.slack_bot_token || !config.slack_bot_token.startsWith('xoxb-')) {
      errors.push({
        field: 'slack_bot_token',
        message: 'Le token Slack doit commencer par "xoxb-"'
      });
    }

    // Database URL
    if (!config.database_url || !config.database_url.startsWith('postgresql://')) {
      errors.push({
        field: 'database_url',
        message: 'L\'URL de la base de données doit commencer par "postgresql://"'
      });
    }

    // Redis URL
    if (!config.redis_url || !config.redis_url.startsWith('redis://')) {
      errors.push({
        field: 'redis_url',
        message: 'L\'URL Redis doit commencer par "redis://"'
      });
    }

    // RabbitMQ URL
    if (!config.rabbitmq_url || !config.rabbitmq_url.startsWith('amqp://')) {
      errors.push({
        field: 'rabbitmq_url',
        message: 'L\'URL RabbitMQ doit commencer par "amqp://"'
      });
    }

    return errors;
  };

  // Créer un backup automatique
  const createBackup = async (reason: string = 'Manual backup') => {
    const backup: ConfigBackup = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      config: originalConfig,
      user: user?.email || 'unknown',
      reason
    };

    // TODO: Sauvegarder via API
    // await apiClient.createConfigBackup(backup);
    
    setBackups([backup, ...backups]);
    
    await logAuditEvent('config_backup_created', {
      backup_id: backup.id,
      reason
    });
  };

  // Sauvegarder la configuration
  const handleSave = async () => {
    // Validation
    const errors = validateConfig();
    setValidationErrors(errors);

    if (errors.length > 0) {
      return;
    }

    setShowConfirmDialog(true);
  };

  const confirmSave = async () => {
    setIsSaving(true);
    setShowConfirmDialog(false);

    try {
      // Créer un backup automatique avant modification
      await createBackup('Automatic backup before modification');

      // Détecter les changements
      const changes: ConfigHistory[] = [];
      for (const key in config) {
        if (config[key as keyof ConfigData] !== originalConfig[key as keyof ConfigData]) {
          changes.push({
            id: Date.now().toString() + Math.random(),
            timestamp: new Date().toISOString(),
            user: user?.email || 'unknown',
            action: 'update',
            field: key,
            oldValue: maskSecret(originalConfig[key as keyof ConfigData]),
            newValue: maskSecret(config[key as keyof ConfigData])
          });
        }
      }

      // TODO: Sauvegarder via API
      // await apiClient.updateConfig(config);
      
      // Simuler la sauvegarde
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Mettre à jour l'historique
      setHistory([...changes, ...history]);
      setOriginalConfig(config);

      // Logger dans l'audit
      await logAuditEvent('config_updated', {
        fields_modified: changes.map(c => c.field),
        timestamp: new Date().toISOString(),
      });

      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (error) {
      console.error('Failed to save config:', error);
    } finally {
      setIsSaving(false);
    }
  };

  // Restaurer un backup
  const restoreBackup = async (backup: ConfigBackup) => {
    if (!confirm(`Êtes-vous sûr de vouloir restaurer la configuration du ${new Date(backup.timestamp).toLocaleString()} ?`)) {
      return;
    }

    // Créer un backup avant restauration
    await createBackup('Backup before restore');

    setConfig(backup.config);
    setOriginalConfig(backup.config);

    await logAuditEvent('config_restored', {
      backup_id: backup.id,
      backup_timestamp: backup.timestamp
    });
  };

  // Export de la configuration
  const exportConfig = () => {
    const exportData = {
      version: '1.0',
      timestamp: new Date().toISOString(),
      config: config,
      metadata: {
        exported_by: user?.email,
        exported_at: new Date().toISOString()
      }
    };

    const json = JSON.stringify(exportData, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `config-${Date.now()}.json`;
    a.click();
    window.URL.revokeObjectURL(url);

    logAuditEvent('config_exported', {
      timestamp: new Date().toISOString()
    });
  };

  // Import de la configuration
  const importConfig = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported = JSON.parse(e.target?.result as string);
        
        if (imported.config) {
          setConfig(imported.config);
          
          logAuditEvent('config_imported', {
            timestamp: new Date().toISOString(),
            source: file.name
          });
        }
      } catch (error) {
        console.error('Failed to import config:', error);
        alert('Erreur lors de l\'import du fichier');
      }
    };
    reader.readAsText(file);
  };

  // Rotation d'un secret
  const rotateSecret = async (field: keyof ConfigData) => {
    if (!confirm(`Êtes-vous sûr de vouloir générer un nouveau secret pour "${field}" ?`)) {
      return;
    }

    setRotatingSecrets([...rotatingSecrets, field]);

    try {
      // TODO: Appeler l'API pour générer un nouveau secret
      // const newSecret = await apiClient.rotateSecret(field);
      
      // Simuler la génération
      await new Promise((resolve) => setTimeout(resolve, 1500));
      
      const prefixes: Record<string, string> = {
        github_token: 'ghp_',
        anthropic_api_key: 'sk-ant-',
        openai_api_key: 'sk-',
        slack_bot_token: 'xoxb-',
        monday_api_token: 'eyJ',
        webhook_secret: 'whsec_'
      };

      const prefix = prefixes[field] || '';
      const newSecret = prefix + generateRandomString(32);

      setConfig({ ...config, [field]: newSecret });

      await logAuditEvent('secret_rotated', {
        field,
        timestamp: new Date().toISOString()
      });

    } catch (error) {
      console.error('Failed to rotate secret:', error);
    } finally {
      setRotatingSecrets(rotatingSecrets.filter(f => f !== field));
    }
  };

  // Helper pour masquer les secrets
  const maskSecret = (value: string): string => {
    if (value.length <= 8) return '***';
    return value.substring(0, 4) + '***' + value.substring(value.length - 4);
  };

  // Helper pour générer une string aléatoire
  const generateRandomString = (length: number): string => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  };

  // Vérifier si la config a changé
  const hasChanges = () => {
    return JSON.stringify(config) !== JSON.stringify(originalConfig);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-purple-100 rounded-xl">
            <Shield className="w-6 h-6 text-purple-600" />
          </div>
      <div>
            <h1 className="text-2xl font-bold text-gray-900">Configuration système</h1>
            <p className="text-gray-600">Paramètres et secrets de l'application</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button onClick={() => setShowHistory(!showHistory)} variant="secondary" className="flex items-center gap-2">
            <History className="w-4 h-4" />
            Historique
          </Button>
          <Button onClick={() => setShowBackups(!showBackups)} variant="secondary" className="flex items-center gap-2">
            <Archive className="w-4 h-4" />
            Backups
          </Button>
        </div>
      </div>

      {/* Alert de sécurité */}
      <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-medium text-red-900">
            ⚠️ Zone hautement sensible
          </p>
          <p className="text-sm text-red-700 mt-1">
            Toutes les actions sont tracées et enregistrées dans l'audit log. 
            Un backup automatique est créé avant chaque modification.
            Seuls les administrateurs ont accès à cette page.
          </p>
        </div>
      </div>

      {/* Changements non sauvegardés */}
      {hasChanges() && (
        <div className="flex items-start gap-3 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-yellow-900">
              Modifications non sauvegardées
            </p>
            <p className="text-sm text-yellow-700 mt-1">
              Vous avez des modifications non sauvegardées. Pensez à sauvegarder votre configuration.
            </p>
          </div>
        </div>
      )}

      {/* Erreurs de validation */}
      {validationErrors.length > 0 && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <XCircle className="w-5 h-5 text-red-600" />
            <p className="text-sm font-medium text-red-900">
              Erreurs de validation
            </p>
          </div>
          <ul className="space-y-1">
            {validationErrors.map((error, index) => (
              <li key={index} className="text-sm text-red-700">
                • <strong>{error.field}</strong>: {error.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions Import/Export */}
      <Card>
        <div className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Download className="w-5 h-5 text-gray-600" />
            Import / Export
          </h3>
          <div className="flex items-center gap-2">
            <Button onClick={exportConfig} variant="secondary" className="flex items-center gap-2">
              <Download className="w-4 h-4" />
              Exporter (JSON)
            </Button>
            <label className="cursor-pointer">
              <Button variant="secondary" className="flex items-center gap-2" as="span">
                <Upload className="w-4 h-4" />
                Importer (JSON)
              </Button>
              <input
                type="file"
                accept=".json"
                onChange={importConfig}
                className="hidden"
              />
            </label>
          </div>
        </div>
      </Card>

      {/* Configuration générale */}
      <Card>
        <div className="p-6 space-y-4">
          <h3 className="text-lg font-semibold text-gray-900">Configuration générale</h3>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Monday Board ID
            </label>
            <input
              type="text"
              value={config.monday_board_id}
              onChange={(e) => setConfig({ ...config, monday_board_id: e.target.value })}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 ${
                validationErrors.find(e => e.field === 'monday_board_id')
                  ? 'border-red-500'
                  : 'border-gray-300'
              }`}
            />
          </div>
        </div>
      </Card>

      {/* Secrets & API Keys */}
      <PermissionGuard permission="secrets:read">
        <Card>
          <div className="p-6 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Key className="w-5 h-5 text-gray-600" />
                Secrets & API Keys
              </h3>
            </div>

            {/* GitHub Token */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-gray-700">
                  GitHub Token
                </label>
                <Button
                  onClick={() => rotateSecret('github_token')}
                  variant="secondary"
                  size="sm"
                  disabled={rotatingSecrets.includes('github_token')}
                  className="flex items-center gap-1"
                >
                  <RotateCw className={`w-3 h-3 ${rotatingSecrets.includes('github_token') ? 'animate-spin' : ''}`} />
                  Renouveler
                </Button>
              </div>
              <SecretField
                value={config.github_token}
                canView={true}
                canCopy={true}
              />
            </div>

            {/* Anthropic API Key */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-gray-700">
                  Anthropic API Key (Claude)
                </label>
                <Button
                  onClick={() => rotateSecret('anthropic_api_key')}
                  variant="secondary"
                  size="sm"
                  disabled={rotatingSecrets.includes('anthropic_api_key')}
                  className="flex items-center gap-1"
                >
                  <RotateCw className={`w-3 h-3 ${rotatingSecrets.includes('anthropic_api_key') ? 'animate-spin' : ''}`} />
                  Renouveler
                </Button>
              </div>
              <SecretField
                value={config.anthropic_api_key}
                canView={true}
                canCopy={true}
              />
            </div>

            {/* OpenAI API Key */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-gray-700">
                  OpenAI API Key
                </label>
                <Button
                  onClick={() => rotateSecret('openai_api_key')}
                  variant="secondary"
                  size="sm"
                  disabled={rotatingSecrets.includes('openai_api_key')}
                  className="flex items-center gap-1"
                >
                  <RotateCw className={`w-3 h-3 ${rotatingSecrets.includes('openai_api_key') ? 'animate-spin' : ''}`} />
                  Renouveler
                </Button>
              </div>
              <SecretField
                value={config.openai_api_key}
                canView={true}
                canCopy={true}
              />
            </div>

            {/* Monday API Token */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-gray-700">
                  Monday.com API Token
                </label>
                <Button
                  onClick={() => rotateSecret('monday_api_token')}
                  variant="secondary"
                  size="sm"
                  disabled={rotatingSecrets.includes('monday_api_token')}
                  className="flex items-center gap-1"
                >
                  <RotateCw className={`w-3 h-3 ${rotatingSecrets.includes('monday_api_token') ? 'animate-spin' : ''}`} />
                  Renouveler
                </Button>
              </div>
              <SecretField
                value={config.monday_api_token}
                canView={true}
                canCopy={true}
              />
            </div>

            {/* Slack Bot Token */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-gray-700">
                  Slack Bot Token
                </label>
                <Button
                  onClick={() => rotateSecret('slack_bot_token')}
                  variant="secondary"
                  size="sm"
                  disabled={rotatingSecrets.includes('slack_bot_token')}
                  className="flex items-center gap-1"
                >
                  <RotateCw className={`w-3 h-3 ${rotatingSecrets.includes('slack_bot_token') ? 'animate-spin' : ''}`} />
                  Renouveler
                </Button>
              </div>
              <SecretField
                value={config.slack_bot_token}
                canView={true}
                canCopy={true}
              />
            </div>

            {/* Webhook Secret */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-gray-700">
                  Webhook Secret
                </label>
                <Button
                  onClick={() => rotateSecret('webhook_secret')}
                  variant="secondary"
                  size="sm"
                  disabled={rotatingSecrets.includes('webhook_secret')}
                  className="flex items-center gap-1"
                >
                  <RotateCw className={`w-3 h-3 ${rotatingSecrets.includes('webhook_secret') ? 'animate-spin' : ''}`} />
                  Renouveler
                </Button>
              </div>
              <SecretField
                value={config.webhook_secret}
                canView={true}
                canCopy={true}
              />
            </div>
          </div>
        </Card>
      </PermissionGuard>

      {/* Infrastructure URLs */}
      <Card>
        <div className="p-6 space-y-4">
          <h3 className="text-lg font-semibold text-gray-900">URLs d'infrastructure</h3>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Database URL
            </label>
            <SecretField
              value={config.database_url}
              canView={true}
              canCopy={true}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Redis URL
            </label>
            <SecretField
              value={config.redis_url}
              canView={true}
              canCopy={true}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              RabbitMQ URL
            </label>
            <SecretField
              value={config.rabbitmq_url}
              canView={true}
              canCopy={true}
            />
          </div>
        </div>
      </Card>

      {/* Historique des modifications */}
      {showHistory && (
        <Card>
          <div className="p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <History className="w-5 h-5 text-gray-600" />
              Historique des modifications
            </h3>
            
            <div className="space-y-2">
              {history.length === 0 ? (
                <p className="text-sm text-gray-600">Aucun historique disponible</p>
              ) : (
                history.map((entry) => (
                  <div key={entry.id} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-900">{entry.field}</span>
                      <span className="text-xs text-gray-500">
                        {new Date(entry.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-600">
                      <span>{entry.user}</span>
                      <span>•</span>
                      <span>{entry.action}</span>
                      {entry.oldValue && entry.newValue && (
                        <>
                          <span>•</span>
                          <span className="font-mono">{entry.oldValue} → {entry.newValue}</span>
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Backups */}
      {showBackups && (
        <Card>
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Archive className="w-5 h-5 text-gray-600" />
                Backups de configuration
              </h3>
              <Button onClick={() => createBackup('Manual backup')} variant="secondary" size="sm">
                Créer un backup
              </Button>
          </div>

            <div className="space-y-2">
              {backups.length === 0 ? (
                <p className="text-sm text-gray-600">Aucun backup disponible</p>
              ) : (
                backups.map((backup) => (
                  <div key={backup.id} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {new Date(backup.timestamp).toLocaleString()}
                        </p>
                        <p className="text-xs text-gray-600">
                          Par {backup.user} • {backup.reason}
                        </p>
                      </div>
                      <Button
                        onClick={() => restoreBackup(backup)}
                        variant="secondary"
                        size="sm"
                      >
                        Restaurer
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Save button */}
      <PermissionGuard permission="config:write">
        <div className="flex items-center gap-4">
          <Button
            onClick={handleSave}
            disabled={isSaving || !hasChanges()}
            className="flex items-center gap-2"
          >
            {isSaving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                Enregistrement...
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                Sauvegarder les modifications
              </>
            )}
          </Button>

          {saveSuccess && (
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle className="w-5 h-5" />
              <span className="text-sm font-medium">Configuration enregistrée avec succès</span>
            </div>
          )}
        </div>
      </PermissionGuard>

      {/* Confirmation Dialog */}
      {showConfirmDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-md">
            <div className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Confirmer la sauvegarde
              </h3>
              <p className="text-sm text-gray-600 mb-6">
                Un backup automatique sera créé avant de sauvegarder les modifications. 
                Êtes-vous sûr de vouloir continuer ?
              </p>
              <div className="flex gap-2 justify-end">
                <Button
                  onClick={() => setShowConfirmDialog(false)}
                  variant="secondary"
                >
                  Annuler
                </Button>
                <Button onClick={confirmSave}>
                  Confirmer
                </Button>
              </div>
        </div>
      </Card>
        </div>
      )}
    </div>
  );
}
