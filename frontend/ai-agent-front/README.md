# Interface Admin AI-Agent VyData

Interface d'administration complète pour le système AI-Agent VyData, développée en React 18 + TypeScript avec Vite.

## 🚀 Fonctionnalités

### ✅ Implémentées

#### 📊 Dashboard Principal
- Métriques temps réel (tâches actives, taux de succès, temps moyen, coûts IA)
- Graphiques d'évolution des tâches
- Distribution des langages détectés
- Santé du système (Celery, RabbitMQ, PostgreSQL, Redis)
- Workflows en cours avec progression

#### 🔄 Visualisation Workflow LangGraph
- Graphe interactif avec React Flow
- 9 nœuds du workflow (prepare → analyze → implement → test → QA → finalize → validation → merge → update)
- Progression en temps réel
- Statut coloré par nœud (completed, running, pending, failed)
- Durées d'exécution par nœud
- Timeline détaillée

#### 📋 Gestion des Tâches
- Liste paginée avec filtres (statut, type, priorité)
- Recherche full-text
- Détail complet d'une tâche
- Historique des exécutions
- Liens vers PRs GitHub
- Actions : Retry, Cancel

#### 🧪 Tests & Qualité
- Dashboard des tests par langage
- Statistiques de succès/échecs
- Liste des tests échoués récents
- Graphiques de tendances
- Configuration des commandes de test par langage

#### 👥 Gestion des Utilisateurs
- Liste des utilisateurs avec statistiques
- Mapping email ↔ Slack ID
- Métriques par utilisateur :
  - Tâches créées/terminées
  - Validations approuvées/rejetées
  - Temps moyen de validation
  - Langages préférés

#### 🌐 Détection de Langages
- Répartition des langages (pie chart)
- Statistiques par langage
- Taux de confiance moyen
- Échecs de détection

#### 🤖 Monitoring IA
- Usage par modèle (Claude, GPT-4)
- Coûts détaillés
- Tokens consommés
- Temps de réponse moyen
- Taux d'erreur

#### 🔗 Intégrations
- **Monday.com** : Status, nombre d'items
- **GitHub** : Repos connectés, PRs ouvertes
- **Slack** : Workspace, membres

#### 📊 Analytics
- Section dédiée (à enrichir selon besoins)

#### 📝 Logs & Debugging
- Logs en temps réel
- Filtres par niveau (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Code couleur par niveau
- Export des logs

#### 🎮 Playground
- Test manuel du workflow
- Formulaire de création de tâche
- Exécution directe sans passer par Monday.com

#### ⚙️ Configuration
- Édition des variables d'environnement
- Tokens API
- IDs Monday.com, GitHub, etc.

## 🛠️ Stack Technique

- **React 18.2** - Framework UI
- **TypeScript 5.3** - Type safety
- **Vite 5.0** - Build tool ultra-rapide
- **React Router 6** - Routing
- **TanStack Query 5** - Data fetching & caching
- **Zustand 4** - State management léger
- **Axios** - Client HTTP
- **Socket.io Client 4** - WebSocket temps réel
- **React Flow 11** - Visualisation de graphes
- **Recharts 2** - Graphiques & charts
- **Tailwind CSS 3** - Styling utility-first
- **Lucide React** - Icônes modernes
- **React Hot Toast** - Notifications toast
- **Framer Motion 10** - Animations
- **date-fns 3** - Manipulation de dates

## 📦 Installation

```bash
cd ai-agent-front
npm install
```

## 🔧 Configuration

Créez un fichier `.env` à la racine de `ai-agent-front/` :

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# App Configuration
VITE_APP_NAME=AI-Agent VyData Admin
VITE_APP_VERSION=3.0.0
```

## 🚀 Démarrage

### Mode Développement

```bash
npm run dev
```

L'application sera accessible sur `http://localhost:3000`

### Build Production

```bash
npm run build
npm run preview  # Pour tester le build
```

## 📁 Structure du Projet

```
ai-agent-front/
├── src/
│   ├── components/
│   │   ├── common/          # Composants réutilisables (Button, Card, Badge, etc.)
│   │   ├── layout/          # Layout principal (Sidebar, Header, Layout)
│   │   ├── dashboard/       # Composants spécifiques au dashboard
│   │   ├── workflow/        # Visualisation workflow
│   │   ├── tasks/           # Gestion des tâches
│   │   ├── tests/           # Tests & qualité
│   │   ├── users/           # Utilisateurs
│   │   ├── ai/              # Monitoring IA
│   │   ├── integrations/    # Intégrations externes
│   │   ├── config/          # Configuration
│   │   └── logs/            # Logs
│   │
│   ├── pages/               # Pages principales (routing)
│   │   ├── DashboardPage.tsx
│   │   ├── WorkflowPage.tsx
│   │   ├── TasksPage.tsx
│   │   ├── TaskDetailPage.tsx
│   │   ├── TestsPage.tsx
│   │   ├── UsersPage.tsx
│   │   ├── LanguagesPage.tsx
│   │   ├── AIModelsPage.tsx
│   │   ├── IntegrationsPage.tsx
│   │   ├── AnalyticsPage.tsx
│   │   ├── LogsPage.tsx
│   │   ├── PlaygroundPage.tsx
│   │   └── ConfigPage.tsx
│   │
│   ├── services/            # Services API
│   │   ├── api.ts           # Client API REST
│   │   └── websocket.ts     # Client WebSocket
│   │
│   ├── stores/              # Stores Zustand
│   │   ├── useAppStore.ts
│   │   ├── useTaskStore.ts
│   │   └── useWebSocketStore.ts
│   │
│   ├── hooks/               # Custom hooks
│   │   └── useApi.ts        # Hooks React Query
│   │
│   ├── types/               # Types TypeScript
│   │   └── index.ts         # Types basés sur backend
│   │
│   ├── utils/               # Utilitaires
│   │   ├── format.ts        # Formatage (dates, durées, monnaie)
│   │   └── colors.ts        # Gestion des couleurs & classes
│   │
│   ├── styles/              # Styles globaux
│   │   └── index.css        # Tailwind + styles custom
│   │
│   ├── App.tsx              # App principale avec routing
│   ├── main.tsx             # Point d'entrée
│   └── vite-env.d.ts        # Types Vite
│
├── public/                  # Assets statiques
├── index.html               # HTML principal
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── README.md
```

## 🎨 Design System

### Couleurs

- **Primary** : Bleu (#0ea5e9 - sky-500)
- **Success** : Vert (#22c55e - green-500)
- **Warning** : Jaune (#f59e0b - amber-500)
- **Error** : Rouge (#ef4444 - red-500)

### Composants de Base

Tous les composants suivent les nomenclatures backend :

- `TaskType`, `TaskPriority`, `WorkflowStatus`, `HumanValidationStatus`
- Champs : `tasks_id`, `monday_item_id`, `task_db_id`, `run_id`, etc.

## 🔄 WebSocket Events

L'application écoute les événements en temps réel :

- `workflow:progress` - Progression d'un workflow
- `workflow:completed` - Workflow terminé
- `workflow:failed` - Workflow échoué
- `log:new` - Nouveau log
- `metrics:update` - Mise à jour des métriques
- `task:status` - Changement de statut de tâche
- `validation:pending` - Nouvelle validation en attente
- `validation:completed` - Validation terminée

## 📊 API Endpoints Utilisés

### Core
- `GET /health` - Health check
- `GET /celery/status` - Status Celery workers

### Dashboard
- `GET /api/dashboard/metrics` - Métriques principales
- `GET /costs/{period}` - Coûts IA

### Tasks
- `GET /api/tasks` - Liste des tâches
- `GET /api/tasks/{id}` - Détail d'une tâche
- `GET /tasks/{id}/status` - Status Celery task
- `POST /api/tasks/{id}/retry` - Relancer une tâche
- `POST /api/tasks/{id}/cancel` - Annuler une tâche

### Workflow
- `GET /api/workflows/{id}/progress` - Progression workflow
- `GET /api/workflows/history` - Historique workflows
- `GET /api/queue/{id}/status` - Status de la queue

### Validation
- `GET /api/validations/pending` - Validations en attente
- `GET /api/validations/{id}` - Détail validation
- `POST /api/validations/{id}/respond` - Répondre à validation

### Tests
- `GET /api/tests/dashboard` - Dashboard tests
- `GET /api/tests/language/{lang}` - Tests par langage
- `POST /api/tests/{id}/{type}/retry` - Retry test

### Users
- `GET /api/users` - Liste utilisateurs
- `GET /api/users/{id}/stats` - Stats utilisateur
- `PUT /api/users/{id}/slack` - Update Slack ID

### AI Models
- `GET /api/ai/usage` - Usage modèles IA
- `GET /api/languages/stats` - Stats langages

### Integrations
- `GET /api/integrations/monday/boards` - Boards Monday
- `POST /api/integrations/monday/test` - Test Monday
- `GET /api/integrations/github/repos` - Repos GitHub
- `POST /api/integrations/github/test` - Test GitHub
- `GET /api/integrations/slack/workspace` - Workspace Slack
- `POST /api/integrations/slack/test` - Test Slack
- `GET /api/webhooks/events` - Événements webhooks

### Logs
- `GET /api/logs` - Liste des logs
- `GET /api/logs/download` - Télécharger logs

### Config
- `GET /api/config` - Configuration système
- `PUT /api/config` - Update configuration

### Admin
- `POST /admin/cleanup` - Nettoyage
- `POST /api/admin/workers/{name}/restart` - Restart worker
- `POST /api/admin/queues/{name}/purge` - Purge queue

### Evaluation
- `POST /evaluation/run` - Lancer évaluation
- `GET /evaluation/reports` - Liste des rapports
- `GET /evaluation/reports/{id}` - Détail rapport

## 🔐 Sécurité

- Tokens JWT stockés dans `localStorage`
- Interceptors Axios pour authentification automatique
- Redirection automatique vers `/login` sur 401
- CORS configuré dans le proxy Vite

## 🐛 Debugging

### Logs Console

Les stores et services loggent automatiquement :

```javascript
console.log('✅ WebSocket connecté');
console.log('📨 Nouveau log reçu:', log);
console.log('📊 Métriques mises à jour:', metrics);
```

### React Query DevTools

Ajouter dans `App.tsx` :

```typescript
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

// Dans le render
<ReactQueryDevtools initialIsOpen={false} />
```

## 🚧 Améliorations Futures

### Phase 2 (Should Have)
- Gestion avancée des permissions utilisateurs
- Historique détaillé des notifications Slack
- Comparaisons temporelles (vs semaine précédente)
- Alertes configurables

### Phase 3 (Nice to Have)
- Analytics prédictifs (ML)
- Rules engine pour automatisation
- A/B testing des prompts IA
- API Management avancé
- Dashboards personnalisables
- Rapports automatiques planifiés

## 📝 Notes Importantes

1. **Nomenclature Backend** : Tous les types et champs respectent exactement la nomenclature du backend Python (ex: `tasks_id`, `monday_item_id`, etc.)

2. **WebSocket** : La connexion WebSocket nécessite que le backend expose un serveur Socket.io. Si non disponible, les updates temps réel ne fonctionneront pas (fallback sur polling via React Query).

3. **Mock Data** : Certaines pages utilisent des données mockées car les endpoints backend correspondants ne sont pas encore implémentés. Remplacer par de vraies requêtes API quand disponibles.

4. **TypeScript Strict** : Le projet utilise TypeScript en mode strict pour une sécurité maximale des types.

## 🤝 Contribution

Le code est structuré pour être facilement extensible :

1. Ajouter un nouveau type dans `src/types/index.ts`
2. Créer les hooks API dans `src/hooks/useApi.ts`
3. Créer les composants dans `src/components/`
4. Créer la page dans `src/pages/`
5. Ajouter la route dans `App.tsx`
6. Ajouter le lien dans `Sidebar.tsx`

## 📄 Licence

Propriétaire - VyCode / Smartelia

---

**Version** : 3.0.0  
**Dernière mise à jour** : 3 novembre 2025  
**Développé avec** ❤️ par l'équipe VyData

