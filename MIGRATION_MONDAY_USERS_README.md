# Migration: Système de Gestion des Utilisateurs Monday.com

## 📋 Vue d'ensemble

Cette migration crée un système complet de gestion des utilisateurs Monday.com avec **vraies données** depuis la base de données et l'API Monday, remplaçant les données mockées.

## 🎯 Objectifs

1. ✅ Créer une table `monday_users` pour stocker les utilisateurs Monday.com
2. ✅ Synchroniser automatiquement les données depuis Monday.com
3. ✅ Connecter les utilisateurs aux tâches via `monday_item_id`
4. ✅ Tracker l'activité, satisfaction, et statut d'accès
5. ✅ Utiliser les vraies données dans l'API et le frontend

## 📊 Structure de la base de données

### Table `monday_users`

```sql
CREATE TABLE monday_users (
    -- Identifiants
    monday_user_id BIGINT PRIMARY KEY,          -- ID utilisateur Monday.com
    monday_item_id BIGINT UNIQUE,                -- Item Monday représentant l'utilisateur
    
    -- Informations personnelles
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(100),                           -- Rôle dans Monday
    team VARCHAR(100),                           -- Équipe
    
    -- Gestion d'accès
    access_status VARCHAR(20) DEFAULT 'authorized',
    -- Valeurs: 'authorized', 'suspended', 'restricted', 'pending'
    
    -- Satisfaction
    satisfaction_score DECIMAL(2,1),             -- Note de 0 à 5
    satisfaction_comment TEXT,
    
    -- Activité
    last_activity TIMESTAMP WITH TIME ZONE,      -- Dernière utilisation
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Métadonnées
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    monday_metadata JSONB DEFAULT '{}'           -- Données supplémentaires
);
```

### Connexions avec d'autres tables

- **`tasks.monday_item_id`** → **`monday_users.monday_item_id`**
  - Permet de lier chaque tâche à son créateur
  
- **Synchronisation automatique** via triggers
  - `last_activity` mis à jour automatiquement quand une tâche est créée

## 🔄 Synchronisation automatique

### Trigger sur insertion de tâche

```sql
CREATE TRIGGER sync_user_activity_on_task_create
    AFTER INSERT ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION sync_monday_user_activity();
```

Ce trigger met à jour `last_activity` automatiquement quand un utilisateur crée une tâche.

## 🚀 Installation

### 1. Appliquer la migration

```bash
./apply_monday_users_migration.sh
```

Ce script :
1. Crée la table `monday_users`
2. Crée les index et triggers
3. Synchronise les utilisateurs depuis Monday.com API
4. Crée des utilisateurs pour les `monday_item_id` existants dans `tasks`

### 2. Redémarrer le backend

```bash
./restart_backend.sh
```

### 3. Vérifier les données

```bash
# Compter les utilisateurs
psql $DATABASE_URL -c "SELECT COUNT(*) FROM monday_users;"

# Voir les utilisateurs
psql $DATABASE_URL -c "SELECT monday_user_id, name, email, role, access_status FROM monday_users LIMIT 10;"

# Voir les stats
psql $DATABASE_URL -c "
SELECT 
    COUNT(*) as total_users,
    COUNT(*) FILTER (WHERE access_status = 'authorized') as authorized,
    COUNT(*) FILTER (WHERE access_status = 'suspended') as suspended,
    AVG(satisfaction_score) as avg_satisfaction
FROM monday_users;
"
```

## 📡 Modifications de l'API

### Endpoints mis à jour

#### `GET /api/users`

**Avant** : Données mockées depuis `tasks`
**Après** : Vraies données depuis `monday_users` avec jointure sur `tasks`

```python
# Requête SQL
SELECT 
    mu.monday_user_id,
    mu.name,
    mu.email,
    mu.role,
    mu.team,
    mu.access_status,
    mu.satisfaction_score,
    COUNT(t.tasks_id) as total_tasks,
    COUNT(t.tasks_id) FILTER (WHERE t.internal_status = 'completed') as completed_tasks
FROM monday_users mu
LEFT JOIN tasks t ON t.monday_item_id = mu.monday_item_id
GROUP BY mu.monday_user_id, ...
```

#### `GET /api/users/stats/global`

**Avant** : Calculs avec données mockées
**Après** : Vraies statistiques depuis `monday_users`

- `total_users` : Compte depuis `monday_users`
- `active_users` : Utilisateurs actifs ce mois
- `suspended_users` : Filtre sur `access_status = 'suspended'`
- `restricted_users` : Filtre sur `access_status = 'restricted'`
- `avg_satisfaction` : Moyenne réelle des `satisfaction_score`

## 🔧 Script de synchronisation

### `scripts/sync_monday_users.py`

Ce script peut être exécuté manuellement ou via cron pour synchroniser les utilisateurs :

```bash
python3 scripts/sync_monday_users.py
```

**Fonctionnalités** :
1. Récupère les utilisateurs depuis Monday.com API GraphQL
2. Insert/Update dans `monday_users`
3. Synchronise les `monday_item_id` depuis `tasks`
4. Calcule les scores de satisfaction basés sur le taux de succès

### Exécution périodique (optionnel)

```bash
# Ajouter au crontab
crontab -e

# Synchroniser tous les jours à 2h du matin
0 2 * * * cd /path/to/AI-Agent && ./venv/bin/python scripts/sync_monday_users.py >> logs/sync_users.log 2>&1
```

## 📊 Données affichées dans le frontend

### Page `/users`

**Statistiques globales** :
- Total d'utilisateurs
- Utilisateurs actifs ce mois
- Utilisateurs suspendus/restreints
- Satisfaction moyenne (vraie)
- Taux de succès des tâches
- Tendance mensuelle

**Tableau des utilisateurs** :
- Nom réel depuis Monday.com
- Email réel
- Rôle et équipe
- Statut d'accès (authorized/suspended/restricted)
- Score de satisfaction (0-5)
- Nombre de tâches (completed/failed)
- Dernière activité

## 🎨 Avantages de cette approche

### ✅ Données réelles
- Plus de données mockées
- Synchronisation avec Monday.com
- Historique complet des utilisateurs

### ✅ Performance
- Index optimisés sur les colonnes clés
- Cache Redis sur les requêtes
- Requêtes SQL efficaces avec LEFT JOIN

### ✅ Extensibilité
- Colonne `monday_metadata` pour données futures
- Structure flexible pour nouveaux champs
- Triggers pour automatisation

### ✅ Traçabilité
- Tracking de `last_activity`
- Historique des modifications (`updated_at`)
- Lien direct tâches ↔ utilisateurs

## 🔍 Colonnes ajoutées

Comparé aux données mockées :

| Colonne | Type | Description | Source |
|---------|------|-------------|--------|
| `monday_user_id` | BIGINT | ID utilisateur Monday | API Monday |
| `monday_item_id` | BIGINT | Item Monday de l'utilisateur | Tasks |
| `name` | VARCHAR | Nom réel | API Monday |
| `email` | VARCHAR | Email réel | API Monday |
| `role` | VARCHAR | Rôle/titre | API Monday |
| `team` | VARCHAR | Équipe(s) | API Monday |
| `access_status` | VARCHAR | Statut d'accès | Manuel/Admin |
| `satisfaction_score` | DECIMAL | Note 0-5 | Calculé/Manuel |
| `satisfaction_comment` | TEXT | Commentaire | Manuel |
| `last_activity` | TIMESTAMP | Dernière activité | Auto (trigger) |
| `monday_metadata` | JSONB | Données supplémentaires | API Monday |

## 📝 Prochaines étapes recommandées

### 1. Ajouter plus de champs Monday.com
- Photo de profil
- Numéro de téléphone
- Timezone
- Langue préférée

### 2. Enrichir les statistiques
- Temps moyen de réponse par utilisateur
- Taux de validation humaine
- Tendances hebdomadaires

### 3. Notifications automatiques
- Alerter si satisfaction < 3.0
- Notifier les administrateurs si trop d'échecs
- Email de bienvenue aux nouveaux utilisateurs

### 4. Intégration webhook Monday
- Webhook sur changement d'utilisateur
- Mise à jour automatique en temps réel
- Synchronisation bidirectionnelle

## 🐛 Résolution de problèmes

### La table est vide après migration

```bash
# Vérifier les données tasks
psql $DATABASE_URL -c "SELECT COUNT(DISTINCT monday_item_id) FROM tasks WHERE monday_item_id IS NOT NULL;"

# Re-synchroniser
python3 scripts/sync_monday_users.py
```

### Erreur "column monday_user_id does not exist"

Vous devez appliquer la migration :
```bash
./apply_monday_users_migration.sh
```

### Les stats globales sont à 0

Vérifiez que :
1. La table `monday_users` existe et contient des données
2. Les `monday_item_id` correspondent entre `monday_users` et `tasks`
3. Le backend a été redémarré

```bash
# Vérifier les correspondances
psql $DATABASE_URL -c "
SELECT 
    (SELECT COUNT(*) FROM monday_users) as users_count,
    (SELECT COUNT(DISTINCT monday_item_id) FROM tasks) as tasks_items_count,
    (SELECT COUNT(*) FROM monday_users mu 
     INNER JOIN tasks t ON t.monday_item_id = mu.monday_item_id) as linked_count;
"
```

## 📚 Fichiers créés/modifiés

### Nouveaux fichiers
- `sql/create_monday_users_table.sql` - Migration SQL
- `scripts/sync_monday_users.py` - Script de synchronisation
- `apply_monday_users_migration.sh` - Script d'installation
- `MIGRATION_MONDAY_USERS_README.md` - Cette documentation

### Fichiers modifiés
- `admin/backend/routes/users_routes.py` - API utilisateurs
  - `UserService.get_users()` - Utilise `monday_users`
  - `get_global_stats()` - Vraies statistiques

## ✅ Checklist de migration

- [x] Créer la table `monday_users`
- [x] Créer les index et triggers
- [x] Script de synchronisation Monday.com
- [x] Modifier l'API pour utiliser `monday_users`
- [x] Tester les endpoints
- [ ] **Appliquer la migration sur votre environnement**
- [ ] **Vérifier les données dans le frontend**
- [ ] **Configurer la synchronisation périodique (optionnel)**

## 🎉 Résultat attendu

Après migration, la page `/users` affichera :
- **Vrais noms d'utilisateurs** depuis Monday.com
- **Emails réels**
- **Rôles et équipes** réels
- **Statistiques précises** basées sur les vraies données
- **Satisfaction** calculée ou saisie manuellement
- **Statuts d'accès** gérables

---

**Date de création** : 19 novembre 2025  
**Version** : 1.0  
**Auteur** : AI-Agent Team

