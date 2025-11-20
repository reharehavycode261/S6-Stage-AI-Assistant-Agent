# 🔐 Système d'Authentification et de Sécurité

## Vue d'ensemble

Ce document décrit le système complet d'authentification, d'autorisation et de sécurité implémenté dans l'interface admin AI-Agent VyData.

## ✅ Fonctionnalités implémentées

### 1. Authentication avec JWT

#### Page de Login
- **Emplacement**: `src/pages/LoginPage.tsx`
- **Fonctionnalités**:
  - Formulaire d'authentification avec email/mot de passe
  - Validation des champs
  - Gestion des erreurs
  - Design moderne avec Tailwind CSS
  - Indicateurs visuels des rôles disponibles

#### Store d'authentification
- **Emplacement**: `src/stores/useAuthStore.ts`
- **Fonctionnalités**:
  - Gestion de l'état d'authentification (JWT token)
  - Stockage persistant avec Zustand
  - Auto-refresh du token
  - Déconnexion avec nettoyage complet
  - Logging automatique des événements d'audit

### 2. Authorization (RBAC - Role-Based Access Control)

#### Rôles disponibles

| Rôle | Permissions | Description |
|------|-------------|-------------|
| **Admin** | Toutes | Accès complet à toutes les fonctionnalités |
| **Developer** | Config (lecture), Intégrations, Tasks, Logs | Développeurs avec accès aux tâches et configs |
| **Viewer** | Tasks (lecture), Logs (lecture) | Consultation uniquement |
| **Auditor** | Tasks (lecture), Logs, Audit | Accès aux logs et audits |

#### Permissions détaillées

```typescript
Admin: [
  'config:read', 'config:write',
  'integrations:read', 'integrations:write',
  'users:read', 'users:write',
  'tasks:read', 'tasks:write', 'tasks:execute',
  'logs:read', 'audit:read',
  'secrets:read', 'secrets:write'
]

Developer: [
  'config:read',
  'integrations:read',
  'tasks:read', 'tasks:write', 'tasks:execute',
  'logs:read', 'audit:read'
]

Viewer: [
  'tasks:read', 'logs:read', 'audit:read'
]

Auditor: [
  'tasks:read', 'logs:read',
  'audit:read', 'audit:export'
]
```

### 3. Composants de protection

#### ProtectedRoute
- **Emplacement**: `src/components/auth/ProtectedRoute.tsx`
- Protège les routes nécessitant une authentification
- Redirige vers `/login` si non authentifié

```tsx
<ProtectedRoute>
  <YourProtectedComponent />
</ProtectedRoute>
```

#### RoleGuard
- **Emplacement**: `src/components/auth/RoleGuard.tsx`
- Protège les routes basées sur les rôles
- Affiche un message d'erreur si accès refusé

```tsx
<RoleGuard roles={['Admin', 'Developer']}>
  <ConfigPage />
</RoleGuard>
```

#### PermissionGuard
- **Emplacement**: `src/components/auth/PermissionGuard.tsx`
- Protège des éléments UI basés sur les permissions
- Masque l'élément si permission manquante

```tsx
<PermissionGuard permission="config:write">
  <Button>Sauvegarder</Button>
</PermissionGuard>
```

### 4. Secret Management

#### SecretField Component
- **Emplacement**: `src/components/auth/SecretField.tsx`
- **Fonctionnalités**:
  - Masquage automatique des secrets
  - Affichage/masquage avec bouton œil
  - Copie dans le presse-papiers
  - **Audit logging automatique** pour toute consultation/copie
  - Indicateurs visuels de sécurité

#### Exemple d'utilisation

```tsx
<SecretField
  value={config.github_token}
  label="GitHub Token"
  canView={true}
  canCopy={true}
/>
```

Tout accès à un secret est automatiquement enregistré dans l'audit log avec :
- Utilisateur (ID, email, rôle)
- Action (viewed/copied)
- Timestamp
- Label du secret

### 5. Audit Logs

#### Page d'Audit Logs
- **Emplacement**: `src/pages/AuditLogsPage.tsx`
- **Accès**: Admin et Auditor uniquement (`/audit`)

#### Fonctionnalités
- **Traçabilité complète**: Qui / Quoi / Quand
- **Filtres avancés**:
  - Par date (début/fin)
  - Par action
  - Par sévérité (critical, high, medium, low)
  - Recherche textuelle
- **Statistiques**:
  - Total événements
  - Événements du jour
  - Événements critiques
  - Utilisateurs actifs
- **Export**: CSV des logs filtrés
- **Visualisation**: Table avec statuts et sévérités

#### Types d'événements enregistrés

```typescript
// Authentification
- user_login
- user_logout
- login_failed
- token_refresh

// Secrets
- secret_viewed
- secret_copied
- secret_updated
- secret_deleted

// Configuration
- config_viewed
- config_updated
- config_exported

// Intégrations
- integration_viewed
- integration_updated
- integration_tested

// Tâches
- task_created
- task_updated
- task_deleted
- task_cancelled
- task_retried

// Utilisateurs
- user_created
- user_updated
- user_deleted
- user_role_changed

// Système
- system_shutdown
- system_restart
- backup_created
- backup_restored
```

### 6. Routes protégées

#### Configuration dans App.tsx

```tsx
// Route publique
<Route path="/login" element={<LoginPage />} />

// Routes protégées (authentification requise)
<Route path="/" element={<DashboardPage />} />
<Route path="/tasks" element={<TasksPage />} />

// Routes sensibles (Admin + Developer uniquement)
<Route path="/config" element={
  <RoleGuard roles={['Admin', 'Developer']}>
    <ConfigPage />
  </RoleGuard>
} />

<Route path="/integrations" element={
  <RoleGuard roles={['Admin', 'Developer']}>
    <IntegrationsPage />
  </RoleGuard>
} />

// Audit (Admin + Auditor uniquement)
<Route path="/audit" element={
  <RoleGuard roles={['Admin', 'Auditor']}>
    <AuditLogsPage />
  </RoleGuard>
} />
```

### 7. Navigation intelligente

Le Sidebar filtre automatiquement les liens en fonction des permissions de l'utilisateur :

```typescript
const visibleNavigation = navigation.filter((item) => {
  if (!item.requiresPermission) return true;
  return hasPermission(item.requiresPermission);
});
```

### 8. Header avec profil utilisateur

Le Header affiche :
- **Nom et rôle** de l'utilisateur connecté
- **Badge coloré** selon le rôle
- **Menu déroulant** avec :
  - Lien vers Audit Logs
  - Lien vers Configuration
  - Bouton de déconnexion

## 🔌 Intégration Backend

### Endpoints requis

Le frontend s'attend à ces endpoints dans le backend :

```python
# Authentication
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout

# Audit
GET  /api/audit/logs
GET  /api/audit/stats
GET  /api/audit/export
POST /api/audit/log
```

### Format JWT attendu

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "name": "User Name",
  "role": "Admin",
  "exp": 1234567890
}
```

### Headers HTTP

Toutes les requêtes authentifiées incluent :

```
Authorization: Bearer <jwt_token>
```

## 🎨 Personnalisation des rôles

Pour modifier les permissions d'un rôle, éditez `src/stores/useAuthStore.ts` :

```typescript
const ROLE_PERMISSIONS: Record<UserRole, string[]> = {
  Admin: [
    // Ajoutez/supprimez des permissions ici
  ],
  // ...
};
```

## 📊 Métriques de sécurité

L'audit log permet de suivre :
- Nombre de connexions par utilisateur
- Fréquence d'accès aux secrets
- Modifications de configuration
- Actions critiques
- Tentatives de connexion échouées

## 🚀 Déploiement

### Variables d'environnement

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Considérations de sécurité

1. **HTTPS obligatoire** en production
2. **Tokens JWT** avec expiration courte (15-30 min)
3. **Refresh tokens** pour renouvellement automatique
4. **Rate limiting** sur l'endpoint de login
5. **Rotation des secrets** régulière
6. **Backup des audit logs** quotidien
7. **Alertes** sur actions critiques

## 📝 Exemple de flux complet

1. **Login**:
   ```
   User entre email/password → POST /api/auth/login
   → Backend retourne JWT → Store dans localStorage
   → Redirect vers Dashboard
   ```

2. **Navigation**:
   ```
   User clique sur Config → RoleGuard vérifie rôle
   → Si OK: affiche page → Sinon: message d'erreur
   ```

3. **Consultation secret**:
   ```
   User clique sur "Afficher" → Secret visible
   → Audit log créé automatiquement
   → POST /api/audit/log avec détails
   ```

4. **Logout**:
   ```
   User clique "Se déconnecter" → Audit log créé
   → Token supprimé → Redirect vers /login
   ```

## 🔍 Hooks utiles

```typescript
// Vérifier authentification
const { isAuthenticated, user } = useAuthStore();

// Vérifier permission
const canEdit = usePermission('config:write');

// Vérifier rôle
const isAdmin = useRole('Admin');
const isAdminOrDev = useRole(['Admin', 'Developer']);

// Logger un événement d'audit
const { logAuditEvent } = useAuthStore();
await logAuditEvent('custom_action', { details: 'info' });
```

## 🎯 Best Practices

1. **Toujours** utiliser `ProtectedRoute` pour les routes privées
2. **Toujours** utiliser `SecretField` pour afficher des secrets
3. **Toujours** logger les actions critiques dans l'audit
4. **Ne jamais** stocker de secrets en clair dans le code
5. **Toujours** vérifier les permissions côté backend également
6. **Régulièrement** consulter les audit logs pour détecter anomalies

## 📚 Ressources

- [JWT.io](https://jwt.io/) - Décodeur JWT
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) - Sécurité web
- [React Security Best Practices](https://snyk.io/blog/10-react-security-best-practices/)

---

**Note**: Ce système est conçu pour être évolutif. Vous pouvez facilement ajouter de nouveaux rôles, permissions, ou types d'audit en suivant les patterns existants.

