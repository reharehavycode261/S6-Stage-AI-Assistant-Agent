# 🚀 Guide de Démarrage Rapide - Interface Admin AI-Agent

## ✅ Installation Terminée !

Toutes les dépendances ont été installées avec succès. L'application est prête à être lancée.

## 🏃 Lancer l'Application

### 1. Backend (FastAPI)

Assurez-vous que votre backend FastAPI est en cours d'exécution :

```bash
# Depuis la racine du projet
python main.py

# Ou avec uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Le backend doit être accessible sur `http://localhost:8000`

### 2. Frontend (React)

Dans un nouveau terminal :

```bash
cd ai-agent-front
npm run dev
```

L'application sera accessible sur **`http://localhost:3000`**

## 📋 Fonctionnalités Disponibles

### 🎯 Navigation Principale

Toutes les pages sont accessibles via la sidebar :

1. **Dashboard** (`/`) - Vue d'ensemble avec KPIs en temps réel
2. **Workflow** (`/workflow`) - Visualisation du graphe LangGraph
3. **Tâches** (`/tasks`) - Liste et gestion des tâches
4. **Tests** (`/tests`) - Monitoring des tests par langage
5. **Utilisateurs** (`/users`) - Statistiques des utilisateurs
6. **Langages** (`/languages`) - Détection automatique des langages
7. **Modèles IA** (`/ai-models`) - Usage et coûts IA
8. **Intégrations** (`/integrations`) - Monday, GitHub, Slack
9. **Analytics** (`/analytics`) - Analyses approfondies
10. **Logs** (`/logs`) - Logs système en temps réel
11. **Playground** (`/playground`) - Test manuel du workflow
12. **Configuration** (`/config`) - Paramètres système

### 📊 Dashboard Principal

**Affiche en temps réel :**
- Nombre de tâches actives
- Taux de succès du jour
- Temps moyen d'exécution
- Coût IA du jour
- Graphiques d'évolution (7 derniers jours)
- Distribution des langages détectés
- Santé du système (Celery, RabbitMQ, PostgreSQL, Redis)
- Workflows en cours avec progression

### 🔄 Visualisation Workflow

**Graphe interactif montrant :**
- Les 9 nœuds du workflow LangGraph
- Statut en temps réel (pending, running, completed, failed)
- Durée de chaque étape
- Progression globale en %
- Détails de la tâche en cours

**Nœuds du workflow :**
1. **prepare** - Préparation de l'environnement
2. **analyze** - Analyse de la tâche
3. **implement** - Implémentation du code
4. **test** - Exécution des tests
5. **QA** - Assurance qualité
6. **finalize** - Finalisation
7. **validation** - Validation humaine
8. **merge** - Merge du code
9. **update** - Mise à jour Monday.com

### 📋 Gestion des Tâches

**Fonctionnalités :**
- ✅ Liste paginée avec filtres
- 🔍 Recherche full-text
- 📊 Tri par statut, type, priorité
- 👁️ Vue détaillée par tâche
- 🔄 Actions : Retry, Cancel
- 🔗 Liens directs vers les PRs GitHub
- 📅 Historique complet des exécutions

**Détail d'une tâche :**
- Informations générales
- Statut actuel avec badge coloré
- Type et priorité
- Dernière exécution (durée, branche, PR)
- Historique de toutes les exécutions
- Lien vers Monday.com
- Lien vers le repository GitHub

### 🧪 Tests & Qualité

**Dashboard complet :**
- Taux de succès global
- Total des tests exécutés
- Tests par langage (Python, Java, JavaScript, etc.)
- Graphique de succès/échecs par langage
- Liste des échecs récents avec détails
- Durée moyenne par langage

### 👥 Utilisateurs

**Statistiques par utilisateur :**
- Tâches créées / terminées
- Validations approuvées / rejetées
- Temps moyen de validation
- Langages préférés
- Mapping email ↔ Slack ID

### 🤖 Monitoring IA

**Par modèle (Claude, GPT-4) :**
- Nombre de requêtes
- Tokens consommés
- Coût total
- Temps de réponse moyen
- Taux d'erreur

### 🔗 Intégrations

**Connexions aux services externes :**
- **Monday.com** : Board ID, nombre d'items
- **GitHub** : Repositories, PRs ouvertes
- **Slack** : Workspace, nombre de membres
- Boutons de test de connexion

## ⚙️ Configuration

### Variables d'Environnement

Le fichier `.env` doit contenir :

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# App Configuration
VITE_APP_NAME=AI-Agent VyData Admin
VITE_APP_VERSION=3.0.0
```

**Note :** Le fichier `.env` doit être créé manuellement dans `ai-agent-front/` si ce n'est pas déjà fait.

### Backend API

L'application utilise un proxy Vite pour communiquer avec le backend :

- Requêtes vers `/api/*` → `http://localhost:8000/*`
- WebSocket vers `ws://localhost:8000`

## 🔴 Temps Réel avec WebSocket

### Événements Écoutés

L'application écoute automatiquement :

- `workflow:progress` - Progression d'un workflow
- `workflow:completed` - Workflow terminé
- `workflow:failed` - Workflow échoué
- `log:new` - Nouveau log
- `metrics:update` - Mise à jour des métriques
- `task:status` - Changement de statut
- `validation:pending` - Nouvelle validation
- `validation:completed` - Validation terminée

### Indicateur de Connexion

Un indicateur dans le header montre :
- 🟢 **Vert** (pulsant) : Connecté au WebSocket
- 🔴 **Rouge** : Déconnecté

**Note :** Si le backend n'expose pas de serveur Socket.io, les mises à jour seront faites par polling (React Query refresh automatique).

## 🎨 Interface Utilisateur

### Thème

- Design moderne et épuré
- Couleurs cohérentes avec le branding
- Tailwind CSS pour un styling rapide
- Icônes Lucide React
- Composants réutilisables

### Composants

Tous les composants de base sont dans `src/components/common/` :
- `Button` - Boutons avec variants (primary, secondary, danger, ghost)
- `Card` - Cartes avec titre et sous-titre
- `Badge` - Badges colorés
- `StatusBadge` - Badge avec statut coloré
- `LoadingSpinner` - Spinner de chargement

### Responsive

L'interface est **entièrement responsive** :
- Mobile : Navigation simplifiée
- Tablette : Layout adapté
- Desktop : Expérience complète

## 🐛 Debug & Développement

### Hot Module Replacement (HMR)

Vite offre un HMR ultra-rapide : les modifications sont visibles instantanément.

### DevTools

React Query DevTools peut être activé en ajoutant dans `App.tsx` :

```typescript
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

// Ajouter dans le return
<ReactQueryDevtools initialIsOpen={false} />
```

### Console Logs

L'application log automatiquement :
- ✅ Connexions WebSocket
- 📨 Événements reçus
- 🔄 Requêtes API
- ❌ Erreurs

## 📦 Build Production

### Créer le build

```bash
npm run build
```

Les fichiers optimisés seront dans `dist/`

### Tester le build

```bash
npm run preview
```

## 🔧 Dépannage

### Port 3000 déjà utilisé ?

Changez le port dans `vite.config.ts` :

```typescript
server: {
  port: 3001,  // Changez ici
  // ...
}
```

### Backend non accessible ?

Vérifiez que :
1. Le backend est bien lancé sur `http://localhost:8000`
2. Le endpoint `/health` répond
3. CORS est bien configuré dans le backend

### WebSocket ne se connecte pas ?

Le backend doit exposer un serveur Socket.io. Si non disponible, l'application fonctionnera quand même avec du polling (légèrement moins temps réel).

## 📝 Nomenclature Backend

**IMPORTANT** : Tous les types et champs respectent la nomenclature du backend Python :

- `tasks_id` (et non `taskId`)
- `monday_item_id` (et non `mondayItemId`)
- `task_db_id` (et non `taskDbId`)
- `run_id` (et non `runId`)
- etc.

Cette cohérence garantit une intégration parfaite avec l'API FastAPI.

## 🎯 Prochaines Étapes

1. ✅ **Vérifier la connexion au backend** (`/health` doit répondre)
2. ✅ **Lancer l'application** (`npm run dev`)
3. ✅ **Explorer le Dashboard**
4. ✅ **Tester les différentes pages**
5. ✅ **Créer une tâche depuis le Playground**
6. ✅ **Visualiser le workflow en temps réel**

## 🆘 Support

Pour toute question ou problème :
- Consulter le `README.md` complet
- Vérifier les logs de la console
- Vérifier les logs du backend
- Consulter la documentation FastAPI sur `/docs`

---

## ✨ Fonctionnalités Implémentées

✅ Dashboard avec métriques temps réel  
✅ Visualisation workflow LangGraph interactif  
✅ Gestion complète des tâches  
✅ Monitoring des tests par langage  
✅ Gestion des utilisateurs  
✅ Détection de langages  
✅ Monitoring IA et coûts  
✅ Intégrations (Monday, GitHub, Slack)  
✅ Analytics de base  
✅ Logs système  
✅ Playground de test  
✅ Configuration système  
✅ WebSocket temps réel  
✅ Types TypeScript complets  
✅ Responsive design  
✅ Dark mode compatible  

---

**🎉 Bon développement avec AI-Agent VyData Admin ! 🚀**

