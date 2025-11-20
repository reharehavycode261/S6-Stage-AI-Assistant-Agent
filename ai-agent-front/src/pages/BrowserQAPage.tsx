/**
 * Page complète Browser QA - QA Autonome de l'Agent
 * 
 * Cette page affiche les résultats des tests Browser QA automatiques
 * effectués par l'agent sur son propre code généré.
 */

import { useState } from 'react';
import { BrowserQAStats } from '../components/browser-qa/BrowserQAStats';
import { BrowserQAResults } from '../components/browser-qa/BrowserQAResults';

export const BrowserQAPage = () => {
  const [autoRefresh, setAutoRefresh] = useState(false);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 md:p-8">
        <div className="flex items-center justify-between gap-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold font-brand text-gray-900">
              Browser QA autonome
            </h1>
            <p className="text-gray-600 mt-1">
              L'agent contrôle automatiquement la qualité du code généré.
            </p>
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer text-gray-700">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span className="text-sm">Auto‑refresh</span>
            </label>
            {/* Illustration robot minimaliste */}
            <div className="hidden md:block">
              <svg width="120" height="100" viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="20" y="28" width="80" height="52" rx="12" className="fill-gray-100 stroke-gray-300" strokeWidth="2"/>
                <rect x="40" y="12" width="40" height="12" rx="6" className="fill-gray-100 stroke-gray-300" strokeWidth="2"/>
                <line x1="60" y1="12" x2="60" y2="6" className="stroke-gray-400" strokeWidth="2"/>
                <circle cx="60" cy="4" r="3" className="fill-gray-300"/>
                <circle cx="46" cy="48" r="7" className="fill-white stroke-gray-300" strokeWidth="2"/>
                <circle cx="74" cy="48" r="7" className="fill-white stroke-gray-300" strokeWidth="2"/>
                <circle cx="46" cy="48" r="3" className="fill-gray-700"/>
                <circle cx="74" cy="48" r="3" className="fill-gray-700"/>
                <rect x="38" y="62" width="44" height="6" rx="3" className="fill-gray-200"/>
                <rect x="12" y="42" width="8" height="20" rx="4" className="fill-gray-100 stroke-gray-300" strokeWidth="2"/>
                <rect x="100" y="42" width="8" height="20" rx="4" className="fill-gray-100 stroke-gray-300" strokeWidth="2"/>
                <rect x="46" y="80" width="6" height="14" rx="3" className="fill-gray-300"/>
                <rect x="68" y="80" width="6" height="14" rx="3" className="fill-gray-300"/>
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Informations */}
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-6">
        <div className="flex items-start gap-4">
          <span className="text-2xl">ℹ️</span>
          <div>
            <h3 className="font-semibold text-gray-900 mb-2">
              Fonctionnalités principales
            </h3>
            <p className="text-gray-700 mb-3">
              L'agent exécute automatiquement des tests complets via <strong>Chrome DevTools MCP</strong> :
            </p>
            <ul className="space-y-2 text-gray-700">
              <li className="flex items-start gap-2">
                <span>🎯</span>
                <span><strong>Backend/API</strong> — Endpoints via fetch() dans le navigateur</span>
              </li>
              <li className="flex items-start gap-2">
                <span>🎨</span>
                <span><strong>Frontend/UI</strong> — Composants et responsive design</span>
              </li>
              <li className="flex items-start gap-2">
                <span>🔄</span>
                <span><strong>Intégration E2E</strong> — Flux complet frontend → backend</span>
              </li>
              <li className="flex items-start gap-2">
                <span>📚</span>
                <span><strong>Documentation</strong> — Accessibilité des docs et de l'admin</span>
              </li>
            </ul>
            <div className="mt-4 text-sm text-gray-600">
              <strong>Outils</strong> : Navigation, Performance, Réseau, Console, Screenshots
            </div>
          </div>
        </div>
      </div>

      {/* Statistiques */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          📊 Statistiques Globales
        </h2>
        <BrowserQAStats />
      </div>

      {/* Résultats récents */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          📋 Résultats Récents
        </h2>
        <BrowserQAResults 
          limit={20} 
          autoRefresh={autoRefresh}
        />
      </div>

      {/* Légende */}
      <div className="bg-gray-50 rounded-lg p-6">
        <h3 className="font-semibold text-gray-900 mb-4">
          📖 Légende des Types de Tests
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="flex items-start gap-3">
            <span className="text-2xl">🚀</span>
            <div>
              <div className="font-medium text-gray-900">Smoke Test</div>
              <div className="text-sm text-gray-600">Chargement basique de l'application</div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-2xl">🎯</span>
            <div>
              <div className="font-medium text-gray-900">Backend API</div>
              <div className="text-sm text-gray-600">Tests des endpoints et documentation API</div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-2xl">🎨</span>
            <div>
              <div className="font-medium text-gray-900">Frontend Component</div>
              <div className="text-sm text-gray-600">Tests des composants UI modifiés</div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-2xl">📱</span>
            <div>
              <div className="font-medium text-gray-900">Responsive</div>
              <div className="text-sm text-gray-600">Tests mobile, tablet et desktop</div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-2xl">🔄</span>
            <div>
              <div className="font-medium text-gray-900">Integration E2E</div>
              <div className="text-sm text-gray-600">Tests du flux complet</div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-2xl">📚</span>
            <div>
              <div className="font-medium text-gray-900">Documentation</div>
              <div className="text-sm text-gray-600">Accessibilité docs et admin</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

