import { useState } from 'react';
import { Eye, EyeOff, Copy, Check } from 'lucide-react';
import { useAuthStore } from '@/stores/useAuthStore';

interface SecretFieldProps {
  value: string;
  label: string;
  canView?: boolean;
  canCopy?: boolean;
}

export function SecretField({ 
  value, 
  label, 
  canView = true, 
  canCopy = true 
}: SecretFieldProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const { user, logAuditEvent } = useAuthStore();

  const maskSecret = (secret: string): string => {
    if (secret.length <= 8) {
      return '••••••••';
    }
    return secret.substring(0, 4) + '••••••••' + secret.substring(secret.length - 4);
  };

  const handleToggleVisibility = async () => {
    const newVisibility = !isVisible;
    setIsVisible(newVisibility);

    if (newVisibility) {
      await logAuditEvent('secret_viewed', {
        secret_label: label,
        user_id: user?.id,
        timestamp: new Date().toISOString(),
      });
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setIsCopied(true);
      
      await logAuditEvent('secret_copied', {
        secret_label: label,
        user_id: user?.id,
        timestamp: new Date().toISOString(),
      });

      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      
      <div className="flex items-center gap-2">
        <div className="flex-1 relative">
          <input
            type="text"
            readOnly
            value={isVisible ? value : maskSecret(value)}
            className="block w-full px-4 py-2 pr-24 border border-gray-300 rounded-lg bg-gray-50 font-mono text-sm"
          />
          
          <div className="absolute inset-y-0 right-0 flex items-center pr-2 gap-1">
            {canView && (
              <button
                type="button"
                onClick={handleToggleVisibility}
                className="p-2 hover:bg-gray-200 rounded-md transition-colors"
                title={isVisible ? 'Masquer' : 'Afficher'}
              >
                {isVisible ? (
                  <EyeOff className="w-4 h-4 text-gray-600" />
                ) : (
                  <Eye className="w-4 h-4 text-gray-600" />
                )}
              </button>
            )}
            
            {canCopy && (
              <button
                type="button"
                onClick={handleCopy}
                className="p-2 hover:bg-gray-200 rounded-md transition-colors"
                title="Copier"
              >
                {isCopied ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className="w-4 h-4 text-gray-600" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>
      
      <p className="text-xs text-gray-500">
        🔒 Secret protégé - Toute consultation est enregistrée dans l'audit log
      </p>
    </div>
  );
}

