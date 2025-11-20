# 📋 Système de Gestion des Utilisateurs - AI-Agent VyData

## 🎯 Vue d'ensemble

Ce document décrit le nouveau système de gestion des utilisateurs intégré au dashboard AI-Agent VyData. Le système permet de gérer, surveiller et administrer tous les utilisateurs de la plateforme avec une intégration complète à Monday.com.

---

## ✨ Fonctionnalités principales

### 1. 📊 Carte de Statistiques Globales (UserStatsCard)

Affiche un aperçu complet des statistiques utilisateurs :

- **Total utilisateurs** avec tendance d'évolution
- **Utilisateurs actifs** (pourcentage du total)
- **Utilisateurs suspendus** (avec ratio)
- **Utilisateurs restreints** (avec ratio)
- **Satisfaction moyenne** (notation sur 5 étoiles)
- **Tâches par utilisateur** (moyenne)
- **Taux de succès global** (ratio succès/échec)
- **Barre de progression visuelle** de la répartition des statuts

**Emplacement** : Intégré directement dans le Dashboard principal

---

### 2. 🗂️ Sidebar Historique Utilisateurs (UserHistorySidebar)

Interface latérale dédiée à la navigation et filtrage des utilisateurs.

#### Fonctionnalités :
- **Recherche en temps réel** par nom ou email
- **Filtres avancés** :
  - Par statut (Autorisé / Suspendu / Restreint / En attente)
  - Par critère de tri (Nom / Dernière activité / Tâches / Satisfaction)
  - Ordre croissant/décroissant
- **Cartes utilisateur** affichant :
  - Nom et email
  - Rôle dans l'équipe
  - Statut d'accès avec badge coloré
  - Nombre de tâches complétées
  - Score de satisfaction
  - Dernière activité (formatée intelligemment)
- **Sélection interactive** pour ouvrir les détails

**Accès** : Bouton "Utilisateurs" dans le header du Dashboard

---

### 3. 🔧 Modal de Gestion Utilisateur (UserManagementModal)

Interface complète de gestion avec 4 onglets principaux.

#### 📝 Onglet "Informations"

**Actions rapides** :
- ✅ **Activer** un utilisateur suspendu
- 🚫 **Suspendre** un utilisateur (avec raison obligatoire)
- ⚠️ **Restreindre** l'accès (avec raison)
- 🗑️ **Supprimer** définitivement (avec confirmation et raison)
- 🔄 **Synchroniser** avec Monday.com

**Formulaire d'édition** :
- Nom
- Email (non modifiable)
- Rôle
- Équipe
- Score de satisfaction (0-5)
- Commentaire de satisfaction
- Date de dernière activité (lecture seule)

#### 📈 Onglet "Statistiques"

Affiche les métriques détaillées :
- Tâches complétées ✓
- Tâches échouées ✗
- Validations approuvées ✓
- Validations rejetées ✗
- Temps moyen de validation
- Score de satisfaction
- Langages préférés (badges)

#### 🕒 Onglet "Historique"

Liste chronologique des activités :
- Titre de la tâche
- ID de la tâche
- Type de tâche
- Date et heure
- Durée d'exécution
- Statut (Réussi/Échoué)

#### 🔗 Onglet "Monday.com"

Intégration complète avec Monday.com :
- **Informations synchronisées** :
  - ID Monday
  - Nom
  - Email
  - Rôle
  - Équipe
  - Statut
- **Champs personnalisés** du board Monday
- **Bouton de synchronisation** pour rafraîchir les données

---

## 🔌 Intégration API Monday.com

### Fonctionnalités API

Le système communique avec Monday.com pour :

1. **Récupérer les informations utilisateur**
   - Extraction automatique depuis le board
   - Champs standards et personnalisés

2. **Mettre à jour les données**
   - Synchronisation bidirectionnelle
   - Mise à jour de colonnes (statut, texte, dropdown, etc.)

3. **Gestion des items**
   - Archivage d'utilisateurs
   - Ajout de logs d'activité
   - Suivi des modifications

4. **Vérification des permissions**
   - Contrôle d'accès via Monday
   - Synchronisation des rôles

### Endpoints API disponibles

```typescript
// Récupérer un utilisateur Monday
GET /api/integrations/monday/users/:userId

// Récupérer tous les utilisateurs
GET /api/integrations/monday/users

// Mettre à jour un utilisateur
PUT /api/integrations/monday/users/:userId

// Colonnes d'un board
GET /api/integrations/monday/boards/:boardId/columns

// Mettre à jour une colonne
PUT /api/integrations/monday/boards/:boardId/items/:itemId/columns/:columnId

// Archiver un item
POST /api/integrations/monday/items/:itemId/archive

// Ajouter un log
POST /api/integrations/monday/items/:itemId/updates

// Synchroniser
POST /api/users/:userId/sync-monday
```

---

## 🎨 États et Statuts Utilisateur

### Statuts d'accès

| Statut | Badge | Description | Actions possibles |
|--------|-------|-------------|-------------------|
| **Autorisé** | 🟢 Vert | Accès complet | Suspendre, Restreindre, Modifier |
| **Suspendu** | 🔴 Rouge | Accès bloqué temporairement | Activer, Supprimer |
| **Restreint** | 🟠 Orange | Accès limité | Activer, Suspendre, Modifier |
| **En attente** | ⚪ Gris | En cours de validation | Activer, Rejeter |

### Transitions d'état

```
Autorisé ←→ Suspendu
Autorisé ←→ Restreint
En attente → Autorisé / Rejeté (Suspendu)
Tous → Supprimé (irréversible)
```

---

## 🔐 Sécurité et Permissions

### Confirmation obligatoire

- ⚠️ **Suppression** : Requiert une raison obligatoire + confirmation
- 🚫 **Suspension** : Requiert une raison
- ⚠️ **Restriction** : Requiert une raison

### Traçabilité

Toutes les actions sont :
- ✅ Enregistrées dans la base de données
- ✅ Synchronisées avec Monday.com
- ✅ Tracées avec date, heure et raison
- ✅ Associées à l'administrateur qui les effectue

---

## 📊 Filtres et Recherche Avancée

### Filtres disponibles

1. **Recherche textuelle**
   - Par nom
   - Par email
   - Recherche instantanée (pas de bouton requis)

2. **Filtre de statut**
   - Tous les statuts
   - Autorisés uniquement
   - Suspendus uniquement
   - Restreints uniquement
   - En attente uniquement

3. **Tri intelligent**
   - Par nom (A-Z ou Z-A)
   - Par dernière activité (récent → ancien ou inverse)
   - Par nombre de tâches (croissant/décroissant)
   - Par score de satisfaction (croissant/décroissant)

### Performance

- ⚡ Requêtes optimisées avec cache (2-5 minutes)
- 🔄 Rechargement automatique après modifications
- 💾 Invalidation intelligente du cache

---

## 🚀 Utilisation

### Accéder à la gestion des utilisateurs

1. Ouvrir le **Dashboard**
2. Cliquer sur le bouton **"Utilisateurs"** (icône violette)
3. La sidebar s'ouvre sur la droite

### Consulter un utilisateur

1. Utiliser la recherche ou les filtres
2. Cliquer sur la carte d'un utilisateur
3. Le modal de détails s'ouvre

### Modifier un utilisateur

1. Ouvrir le modal utilisateur
2. Onglet **"Informations"**
3. Cliquer sur **"Modifier"**
4. Éditer les champs
5. Cliquer sur **"Enregistrer"**

### Suspendre un utilisateur

1. Ouvrir le modal utilisateur
2. Onglet **"Informations"**
3. Cliquer sur **"Suspendre"**
4. Entrer une raison
5. Confirmer

### Synchroniser avec Monday

1. Ouvrir le modal utilisateur
2. Onglet **"Informations"** ou **"Monday.com"**
3. Cliquer sur **"Sync Monday"**
4. Les données sont rafraîchies automatiquement

---

## 🛠️ Architecture Technique

### Structure des fichiers

```
ai-agent-front/src/
├── components/users/
│   ├── UserHistorySidebar.tsx      # Sidebar de navigation
│   ├── UserManagementModal.tsx     # Modal de gestion
│   └── UserStatsCard.tsx           # Carte de statistiques
├── hooks/
│   ├── useUserData.ts              # Hooks pour données utilisateurs
│   └── useMondayApi.ts             # Hooks pour API Monday
├── types/
│   └── index.ts                    # Types TypeScript étendus
└── services/
    └── api.ts                      # Client API avec nouvelles méthodes
```

### Hooks React Query

Tous les hooks utilisent **React Query** pour :
- Cache intelligent
- Invalidation automatique
- Rechargement en arrière-plan
- États de chargement/erreur
- Optimisation des requêtes

### Types TypeScript

```typescript
// Nouveau statut d'accès
enum UserAccessStatus {
  AUTHORIZED = 'authorized',
  SUSPENDED = 'suspended',
  RESTRICTED = 'restricted',
  PENDING = 'pending',
}

// Interface utilisateur étendue
interface User {
  user_id: number;
  email: string;
  name?: string;
  role?: string;
  team?: string;
  last_activity?: string;
  access_status?: UserAccessStatus;
  satisfaction_score?: number;
  satisfaction_comment?: string;
  // ... autres champs
}
```

---

## 📈 Statistiques et Métriques

### Métriques calculées

- **Taux de réussite** = (Tâches complétées) / (Total tâches)
- **Satisfaction moyenne** = Moyenne des scores utilisateurs
- **Tâches par utilisateur** = Total tâches / Nombre utilisateurs
- **Pourcentage actifs** = (Actifs / Total) × 100

### Graphiques et visualisations

- 📊 Barres de progression colorées
- ⭐ Étoiles de notation
- 🎨 Badges avec icônes
- 📈 Tendances avec flèches (↑↓)

---

## 🎁 Fonctionnalités Bonus Implémentées

✅ **Filtres et recherche avancée**
- Recherche instantanée
- Multi-critères
- Tri dynamique

✅ **Timeline des actions**
- Historique détaillé par utilisateur
- Dates formatées intelligemment

✅ **Système de rôles**
- Rôle éditable
- Affichage dans les cartes

✅ **Statistiques globales**
- Dashboard complet
- Métriques en temps réel

✅ **Alertes visuelles**
- Badges colorés par statut
- Indicateurs de performance

---

## 🔮 Évolutions futures possibles

1. **Notifications en temps réel**
   - WebSocket pour alertes instantanées
   - Notifications push navigateur

2. **Export de rapports**
   - PDF/Excel des statistiques
   - Rapport périodique automatique

3. **Analyse prédictive**
   - Prédiction des risques de départ
   - Recommandations d'amélioration

4. **Gamification**
   - Badges de performance
   - Classements
   - Objectifs personnalisés

5. **Intégration Slack**
   - Notifications directes
   - Commandes slash
   - Statuts synchronisés

---

## 📞 Support

Pour toute question ou problème :
- 📧 Email : support@vydata.com
- 💬 Slack : #ai-agent-support
- 📚 Documentation : [lien vers doc complète]

---

**Créé le** : 19 novembre 2025  
**Version** : 1.0.0  
**Auteur** : Équipe AI-Agent VyData


