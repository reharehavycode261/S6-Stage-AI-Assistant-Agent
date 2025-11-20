# Corrections : Utilisation des Données Réelles

## 🎯 Problème identifié

Les données affichées dans la page `/users` étaient **mockées** (fausses) :
- Noms génériques : "Utilisateur 999777", "Utilisateur 999888"
- Emails générés : "user999777@example.com"
- Rôles identiques : "Développeur" pour tout le monde
- Équipe identique : "Équipe Technique"
- Satisfaction fictive calculée par `(idx % 3) * 0.5`
- Pas de connexion avec les vraies données Monday.com

## ✅ Solution implémentée

### 1. Création de la table `monday_users`

**Fichier** : `sql/create_monday_users_table.sql`

Une vraie table pour stocker les utilisateurs Monday.com avec :

```sql
monday_users
├── monday_user_id (PK)     -- ID utilisateur Monday.com
├── monday_item_id          -- Lien avec tasks
├── name                     -- Nom réel depuis Monday
├── email                    -- Email réel depuis Monday
├── role                     -- Rôle réel depuis Monday
├── team                     -- Équipe réelle depuis Monday
├── access_status            -- authorized/suspended/restricted
├── satisfaction_score       -- Note réelle 0-5
├── satisfaction_comment     -- Commentaire
├── last_activity            -- Auto-synchro via trigger
└── monday_metadata          -- Données supplémentaires JSON
```

**Avantages** :
- ✅ Données persistées en base
- ✅ Synchronisation automatique avec Monday.com
- ✅ Tracking de l'activité via triggers
- ✅ Extensible avec `monday_metadata` JSONB

### 2. Script de synchronisation

**Fichier** : `scripts/sync_monday_users.py`

Ce script :
1. **Récupère les utilisateurs depuis Monday.com** via GraphQL API
   ```graphql
   query {
       users {
           id, name, email, title, teams { name }
       }
   }
   ```

2. **Synchronise dans la base de données**
   - Insert nouveaux utilisateurs
   - Update utilisateurs existants
   - Associe `monday_item_id` depuis `tasks`

3. **Crée des utilisateurs pour les items existants**
   - Parcourt tous les `monday_item_id` dans `tasks`
   - Crée des utilisateurs pour ceux qui n'existent pas encore
   - Calcule un score de satisfaction basé sur le taux de succès

### 3. Modification de l'API

**Fichier** : `admin/backend/routes/users_routes.py`

#### Avant (données mockées)

```python
# ❌ Générait des données fictives
users_query = """
    SELECT DISTINCT monday_item_id, MAX(created_at) as last_activity
    FROM tasks
    WHERE monday_item_id IS NOT NULL
    GROUP BY monday_item_id
"""

# ❌ Nom générique
name = f"Utilisateur {monday_item_id}"

# ❌ Email fictif
email = f"user{monday_item_id}@example.com"

# ❌ Rôle identique pour tous
role = "Développeur"
```

#### Après (vraies données)

```python
# ✅ Récupère depuis monday_users
users_query = """
    SELECT 
        mu.monday_user_id,
        mu.name,              -- ✅ Nom réel
        mu.email,             -- ✅ Email réel
        mu.role,              -- ✅ Rôle réel
        mu.team,              -- ✅ Équipe réelle
        mu.access_status,     -- ✅ Statut réel
        mu.satisfaction_score,-- ✅ Score réel
        COUNT(t.tasks_id) as total_tasks
    FROM monday_users mu
    LEFT JOIN tasks t ON t.monday_item_id = mu.monday_item_id
    GROUP BY mu.monday_user_id, ...
"""
```

### 4. Statistiques globales réelles

#### Avant

```python
# ❌ Valeurs mockées
"suspended_users": 0,  # TODO
"restricted_users": 0,  # TODO
"avg_satisfaction": 4.2,  # Mock
```

#### Après

```python
# ✅ Vraies requêtes SQL
suspended_users = await db.fetchval("""
    SELECT COUNT(*) FROM monday_users 
    WHERE access_status = 'suspended'
""")

restricted_users = await db.fetchval("""
    SELECT COUNT(*) FROM monday_users 
    WHERE access_status = 'restricted'
""")

avg_satisfaction = await db.fetchval("""
    SELECT AVG(satisfaction_score) 
    FROM monday_users 
    WHERE satisfaction_score IS NOT NULL
""")
```

## 🔄 Synchronisation automatique

### Trigger sur création de tâche

```sql
CREATE TRIGGER sync_user_activity_on_task_create
    AFTER INSERT ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION sync_monday_user_activity();
```

**Effet** : Quand un utilisateur crée une tâche, sa `last_activity` est automatiquement mise à jour dans `monday_users`.

## 📊 Comparaison avant/après

| Donnée | Avant (Mockée) | Après (Réelle) |
|--------|----------------|----------------|
| **Nom** | "Utilisateur 999777" | "Jean Dupont" (Monday) |
| **Email** | "user999777@example.com" | "jean.dupont@company.com" (Monday) |
| **Rôle** | "Développeur" (tous) | "Tech Lead" / "Developer" (Monday) |
| **Équipe** | "Équipe Technique" (tous) | "Backend Team" / "DevOps" (Monday) |
| **Satisfaction** | Calculée `(idx % 3) * 0.5` | Score réel ou calculé depuis taux succès |
| **Statut** | "authorized" (tous) | authorized / suspended / restricted (BDD) |
| **Last activity** | Depuis `tasks` | Trigger auto-sync + Monday |
| **Stats globales** | Valeurs fixes | Requêtes SQL en temps réel |

## 🚀 Installation

```bash
# 1. Appliquer la migration
./apply_monday_users_migration.sh

# Ce script va :
# - Créer la table monday_users
# - Synchroniser depuis Monday.com
# - Créer les utilisateurs pour les monday_item_id existants
# - Afficher un résumé

# 2. Redémarrer le backend
./restart_backend.sh

# 3. Vérifier dans le navigateur
# http://localhost:3000/users
```

## 🔍 Vérification

### Avant la migration

```bash
# Les utilisateurs n'existent pas en BDD
psql $DATABASE_URL -c "SELECT * FROM monday_users LIMIT 5;"
# Erreur: relation "monday_users" does not exist
```

### Après la migration

```bash
# Les utilisateurs existent avec vraies données
psql $DATABASE_URL -c "SELECT monday_user_id, name, email, role, team, access_status FROM monday_users LIMIT 5;"

# Exemple de résultat attendu:
#  monday_user_id |     name      |        email           |    role    |    team    | access_status
# ----------------+---------------+------------------------+------------+------------+---------------
#   12345678      | Jean Dupont   | jean@company.com       | Tech Lead  | Backend    | authorized
#   87654321      | Marie Martin  | marie@company.com      | Developer  | Frontend   | authorized
#   ...
```

## 📡 API Endpoints mis à jour

### `GET /api/users`

**Réponse avant** :
```json
{
  "user_id": 999777,
  "name": "Utilisateur 999777",
  "email": "user999777@example.com",
  "role": "Développeur",
  "team": "Équipe Technique"
}
```

**Réponse après** :
```json
{
  "user_id": 12345678,
  "monday_user_id": 12345678,
  "monday_item_id": 999777,
  "name": "Jean Dupont",
  "email": "jean.dupont@company.com",
  "role": "Tech Lead",
  "team": "Backend Team, DevOps",
  "access_status": "authorized",
  "satisfaction_score": 4.5,
  "last_activity": "2025-11-19T10:30:00Z",
  "total_tasks": 45,
  "is_active": true
}
```

### `GET /api/users/stats/global`

**Réponse avant** :
```json
{
  "suspended_users": 0,
  "restricted_users": 0,
  "avg_satisfaction": 4.2
}
```

**Réponse après** :
```json
{
  "suspended_users": 2,
  "restricted_users": 1,
  "avg_satisfaction": 4.3
}
```

## 🎯 Colonnes à vérifier pour données correctes

Dans `monday_users` :

### ✅ Colonnes synchronisées depuis Monday.com API
- `monday_user_id` - ID utilisateur Monday
- `name` - Nom réel de l'utilisateur
- `email` - Email réel
- `role` - Titre/rôle dans Monday
- `team` - Équipe(s) dans Monday

### ✅ Colonnes synchronisées depuis `tasks`
- `monday_item_id` - Item Monday lié
- `last_activity` - Dernière création de tâche

### ⚙️ Colonnes gérées manuellement (ou à implémenter)
- `access_status` - À modifier via l'admin
- `satisfaction_score` - Calculé ou saisi manuellement
- `satisfaction_comment` - Saisi par l'utilisateur
- `is_active` - À gérer via l'admin

## 🔧 Maintenance

### Synchronisation périodique

Pour garder les données à jour, ajoutez au crontab :

```bash
# Synchroniser tous les jours à 2h du matin
0 2 * * * cd /path/to/AI-Agent && ./venv/bin/python scripts/sync_monday_users.py >> logs/sync_users.log 2>&1
```

### Synchronisation manuelle

```bash
python3 scripts/sync_monday_users.py
```

## 📝 Fichiers créés

1. **`sql/create_monday_users_table.sql`**
   - Définition de la table
   - Index et contraintes
   - Triggers de synchronisation

2. **`scripts/sync_monday_users.py`**
   - Récupération depuis Monday.com
   - Synchronisation BDD
   - Logs de progression

3. **`apply_monday_users_migration.sh`**
   - Script d'installation tout-en-un
   - Crée la table + synchronise

4. **`MIGRATION_MONDAY_USERS_README.md`**
   - Documentation complète

5. **`CORRECTIONS_DONNEES_REELLES.md`** (ce fichier)
   - Explication des corrections

## ✅ Résultat final

Après ces corrections, le système :

1. ✅ **Utilise les vraies données Monday.com**
   - Noms réels des utilisateurs
   - Emails réels
   - Rôles et équipes réels

2. ✅ **Données persistées en base**
   - Table `monday_users` dédiée
   - Synchronisation automatique
   - Triggers pour last_activity

3. ✅ **API mise à jour**
   - Plus de données mockées
   - Requêtes SQL sur `monday_users`
   - Statistiques réelles

4. ✅ **Frontend fonctionnel**
   - Affiche les vraies données
   - Filtres et tri fonctionnent
   - Performance optimisée

---

**Date** : 19 novembre 2025  
**Problème** : Données mockées au lieu de données réelles  
**Solution** : Table `monday_users` + Synchronisation Monday.com + API mise à jour  
**Status** : ✅ Résolu


