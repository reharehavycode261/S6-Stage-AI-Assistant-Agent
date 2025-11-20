/**
 * Point d'entrée optimisé de l'application
 * - Configuration TanStack Query optimisée
 * - Gestion d'erreurs
 * - Performance monitoring
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
// import { ReactQueryDevtools } from '@tanstack/react-query-devtools' // Désactivé pour éviter erreur de build
import App from './App.tsx'
import './styles/index.css'

// Configuration optimale du QueryClient
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Durée pendant laquelle les données sont considérées comme fraîches
      staleTime: 5 * 60 * 1000, // 5 minutes par défaut
      
      // Durée de conservation en cache (anciennement cacheTime)
      gcTime: 10 * 60 * 1000, // 10 minutes
      
      // Retry automatique en cas d'erreur
      retry: (failureCount, error: any) => {
        // Ne pas retry sur 404 ou 401
        if (error?.response?.status === 404 || error?.response?.status === 401) {
          return false;
        }
        // Retry max 2 fois pour les autres erreurs
        return failureCount < 2;
      },
      
      // Délai entre les retries (backoff exponentiel)
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      
      // Refetch automatique au focus de la fenêtre
      refetchOnWindowFocus: import.meta.env.PROD, // Seulement en production
      
      // Refetch au reconnect réseau
      refetchOnReconnect: true,
      
      // Ne pas refetch automatiquement au mount si les données sont fraîches
      refetchOnMount: false,
    },
    mutations: {
      // Retry 1 fois pour les mutations
      retry: 1,
      
      // Délai avant retry
      retryDelay: 1000,
    },
  },
});

// Error boundary pour capturer les erreurs
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error?: Error }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Application Error:', error, errorInfo);
    // TODO: Envoyer à Sentry ou autre service de monitoring
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-6">
            <h1 className="text-2xl font-bold text-red-600 mb-4">
              Oups ! Une erreur s'est produite
            </h1>
            <p className="text-gray-600 mb-4">
              L'application a rencontré une erreur inattendue.
            </p>
            <pre className="bg-gray-100 p-3 rounded text-sm overflow-auto max-h-40">
              {this.state.error?.message}
            </pre>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 w-full bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600 transition"
            >
              Recharger l'application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Rendu de l'application
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <App />
        {/* DevTools uniquement en développement */}
        {/* {import.meta.env.DEV && (
          <ReactQueryDevtools 
            initialIsOpen={false} 
            position="bottom-right"
            buttonPosition="bottom-right"
          />
        )} */}
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

// Performance monitoring (optionnel)
if (import.meta.env.DEV) {
  // Log des métriques de performance en dev
  if ('performance' in window && 'PerformanceObserver' in window) {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === 'navigation') {
          console.log('📊 Performance Metrics:', {
            'DOM Content Loaded': `${(entry as any).domContentLoadedEventEnd}ms`,
            'Load Complete': `${(entry as any).loadEventEnd}ms`,
          });
        }
      }
    });
    observer.observe({ entryTypes: ['navigation'] });
  }
}

