# 🚀 Quick Start - Système de Sécurité

## 🎯 Démarrage rapide en 5 minutes

### 1. Lancer l'application

```bash
cd ai-agent-front
npm install
npm run dev
```

L'application sera accessible sur `http://localhost:5173`

### 2. Se connecter

**Étape 1**: Ouvrez l'application dans votre navigateur

**Étape 2**: Vous serez automatiquement redirigé vers `/login`

**Étape 3**: Entrez vos identifiants de test:

```
Email: admin@vydata.com
Password: admin123

OU

Email: dev@vydata.com  
Password: dev123
```

**Étape 4**: Cliquez sur "Se connecter"

✅ Vous êtes maintenant authentifié et redirigé vers le Dashboard

---

## 🔍 Explorer les fonctionnalités

### A. Tester la protection des routes

#### Route accessible à tous (authentifiés)
1. Cliquez sur "Tâches" dans le menu → ✅ Accès autorisé
2. Cliquez sur "Dashboard" → ✅ Accès autorisé

#### Route protégée (Admin/Developer uniquement)
1. Connectez-vous en tant que **Viewer**
2. Essayez d'accéder à `/config` → ❌ Accès refusé
3. Message affiché: "Vous n'avez pas les permissions nécessaires"

---

### B. Tester le masquage des secrets

1. Connectez-vous en tant que **Admin** ou **Developer**
2. Allez dans "Configuration" (`/config`)
3. Scrollez jusqu'à la section "🔐 Secrets & API Keys"

**Vous verrez**:
- Tous les secrets sont masqués: `ghp_••••••••xxxx`
- Bouton œil pour afficher/masquer
- Bouton copier pour copier

**Testez**:
1. Cliquez sur l'icône **œil** → Le secret s'affiche
   - ⚠️ Un événement `secret_viewed` est créé dans l'audit log
2. Cliquez sur l'icône **copier** → Le secret est copié
   - ⚠️ Un événement `secret_copied` est créé dans l'audit log

---

### C. Consulter les Audit Logs

1. Connectez-vous en tant que **Admin** ou **Auditor**
2. Cliquez sur votre **profil** en haut à droite
3. Sélectionnez "Audit Logs"

**Vous verrez**:
- Dashboard avec statistiques
- Liste de tous les événements
- Vos actions précédentes (login, secret_viewed, etc.)

**Filtrez les logs**:
1. Sélectionnez une date de début
2. Choisissez une action (ex: "Secret consulté")
3. Sélectionnez une sévérité
4. Recherchez dans la barre de recherche

**Exportez les logs**:
1. Cliquez sur "Exporter"
2. Un fichier CSV est téléchargé avec les logs filtrés

---

### D. Tester les rôles

#### Rôle Admin 🟣
```bash
Email: admin@vydata.com
Password: admin123
```
**Accès**:
- ✅ Dashboard, Tâches, Workflow, Browser QA
- ✅ Modèles IA, Performance
- ✅ **Intégrations** (protégé)
- ✅ Logs, Playground
- ✅ **Configuration** (protégé)
- ✅ **Audit Logs** (protégé)

#### Rôle Developer 🔵
```bash
Email: dev@vydata.com
Password: dev123
```
**Accès**:
- ✅ Dashboard, Tâches, Workflow, Browser QA
- ✅ Modèles IA, Performance
- ✅ **Intégrations** (protégé)
- ✅ Logs, Playground
- ✅ **Configuration** (protégé) - Lecture seule
- ❌ Audit Logs (pas d'accès)

#### Rôle Viewer 🟢
```bash
Email: viewer@vydata.com
Password: viewer123
```
**Accès**:
- ✅ Dashboard, Tâches (lecture seule), Workflow (lecture seule)
- ✅ Browser QA, Modèles IA, Performance
- ✅ Logs (lecture seule)
- ❌ Intégrations (pas d'accès)
- ❌ Configuration (pas d'accès)
- ❌ Audit Logs (pas d'accès)

#### Rôle Auditor 🟠
```bash
Email: auditor@vydata.com
Password: auditor123
```
**Accès**:
- ✅ Dashboard, Tâches (lecture seule)
- ✅ Logs
- ✅ **Audit Logs** (protégé)
- ✅ **Export logs** (permission spéciale)
- ❌ Intégrations (pas d'accès)
- ❌ Configuration (pas d'accès)

---

## 🎓 Exemples de code

### Utiliser le store d'authentification

```tsx
import { useAuthStore } from '@/stores/useAuthStore';

function MyComponent() {
  const { user, isAuthenticated, logout } = useAuthStore();

  if (!isAuthenticated) {
    return <p>Non connecté</p>;
  }

  return (
    <div>
      <h1>Bonjour {user?.name}</h1>
      <p>Rôle: {user?.role}</p>
      <button onClick={logout}>Se déconnecter</button>
    </div>
  );
}
```

### Vérifier une permission

```tsx
import { usePermission } from '@/stores/useAuthStore';

function EditButton() {
  const canEdit = usePermission('config:write');

  if (!canEdit) {
    return null; // N'affiche pas le bouton
  }

  return <button>Modifier</button>;
}
```

### Vérifier un rôle

```tsx
import { useRole } from '@/stores/useAuthStore';

function AdminPanel() {
  const isAdmin = useRole('Admin');

  if (!isAdmin) {
    return <p>Accès réservé aux administrateurs</p>;
  }

  return <div>Panel Admin</div>;
}
```

### Protéger une route

```tsx
import { RoleGuard } from '@/components/auth/RoleGuard';

<Route
  path="/admin"
  element={
    <RoleGuard roles={['Admin']}>
      <AdminPage />
    </RoleGuard>
  }
/>
```

### Masquer un secret

```tsx
import { SecretField } from '@/components/auth/SecretField';

function ConfigPage() {
  return (
    <SecretField
      value="sk-ant-1234567890abcdef"
      label="Anthropic API Key"
      canView={true}
      canCopy={true}
    />
  );
}
```

### Logger un événement d'audit

```tsx
import { useAuthStore } from '@/stores/useAuthStore';

function MyComponent() {
  const { logAuditEvent } = useAuthStore();

  const handleCriticalAction = async () => {
    // Effectuer l'action
    await doSomethingCritical();

    // Logger l'événement
    await logAuditEvent('critical_action_performed', {
      action_type: 'delete',
      resource_id: '123',
      timestamp: new Date().toISOString(),
    });
  };

  return <button onClick={handleCriticalAction}>Action critique</button>;
}
```

---

## 🔥 Scénarios de test

### Scénario 1: Tentative d'accès non autorisé
1. Connectez-vous en tant que **Viewer**
2. Modifiez l'URL manuellement: `/config`
3. ✅ Vous voyez la page d'erreur "Accès refusé"
4. ✅ L'événement est enregistré dans l'audit log

### Scénario 2: Consultation de secrets
1. Connectez-vous en tant que **Admin**
2. Allez dans Configuration
3. Cliquez sur "Afficher" pour un secret
4. Allez dans Audit Logs
5. ✅ Vous voyez l'événement `secret_viewed` avec votre nom

### Scénario 3: Export des audit logs
1. Connectez-vous en tant que **Auditor**
2. Allez dans Audit Logs
3. Filtrez par date (dernière semaine)
4. Cliquez sur "Exporter"
5. ✅ Un fichier CSV est téléchargé avec les logs filtrés

### Scénario 4: Session expirée
1. Connectez-vous normalement
2. Supprimez le token du localStorage manuellement
3. Rafraîchissez la page
4. ✅ Vous êtes redirigé vers `/login`

---

## 🐛 Dépannage

### Problème: "Identifiants invalides"
**Solution**: Vérifiez que le backend est en cours d'exécution et que l'endpoint `/api/auth/login` fonctionne

### Problème: "Accès refusé" pour Admin
**Solution**: Vérifiez que le JWT contient le bon rôle. Décodez le token sur [jwt.io](https://jwt.io)

### Problème: Audit logs vides
**Solution**: Vérifiez que l'endpoint `/api/audit/logs` retourne des données

### Problème: Secrets ne se masquent pas
**Solution**: Vérifiez que le composant `SecretField` est bien utilisé et non un input classique

---

## 📊 Métriques à surveiller

### Sécurité
- Nombre de tentatives de login échouées
- Fréquence d'accès aux secrets
- Actions critiques par utilisateur

### Performance
- Temps de chargement de la page de login
- Temps de refresh du token
- Temps de chargement des audit logs

### Conformité
- Tous les secrets sont masqués
- Toutes les actions critiques sont loggées
- Tous les accès sont enregistrés

---

## ✅ Checklist avant mise en production

- [ ] Tous les secrets sont masqués dans l'interface
- [ ] Les routes sensibles sont protégées
- [ ] Les audit logs fonctionnent correctement
- [ ] Les rôles sont correctement configurés
- [ ] Le token JWT expire après X minutes
- [ ] Le refresh token fonctionne
- [ ] HTTPS est activé
- [ ] Rate limiting est configuré sur le login
- [ ] Les logs sont sauvegardés quotidiennement
- [ ] Les alertes de sécurité sont configurées

---

## 🎉 Félicitations !

Vous avez maintenant un système de sécurité complet avec :
- ✅ Authentification JWT
- ✅ Autorisation RBAC
- ✅ Masquage des secrets
- ✅ Audit logs complets
- ✅ Protection des routes
- ✅ Traçabilité complète

**Besoin d'aide ?** Consultez `AUTHENTICATION_SECURITY.md` pour la documentation complète.

---

**Version**: 1.0.0  
**Dernière mise à jour**: 17 Novembre 2025  
**Status**: Production Ready ✅


