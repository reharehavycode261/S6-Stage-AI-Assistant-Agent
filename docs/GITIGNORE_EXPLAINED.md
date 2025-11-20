# 📝 Explication du .gitignore

Ce document explique la stratégie du `.gitignore` pour la nouvelle structure du projet.

## 🎯 Stratégie Globale

Le `.gitignore` est organisé pour :
1. ✅ **Ignorer** les fichiers générés automatiquement
2. ✅ **Préserver** les fichiers importants pour le projet
3. ✅ **Protéger** les informations sensibles (.env)
4. ✅ **Maintenir** une structure propre dans Git

## 📂 Fichiers Ignorés par Catégorie

### 🐍 Python
```
__pycache__/          # Cache Python
*.pyc, *.pyo         # Bytecode compilé
*.egg-info/          # Métadonnées des packages
venv/                # Environnement virtuel
```

### 📦 Node / Frontend
```
node_modules/        # Dépendances Node.js
dist/                # Build de production
.next/               # Cache Next.js (si utilisé)
```

### 🔐 Environnement & Secrets
```
.env                 # Variables d'environnement (SENSIBLE!)
.env.local           # Config locale
backend/.env         # Config backend
```

⚠️ **CRITIQUE** : Les fichiers `.env` ne doivent JAMAIS être commités car ils contiennent des clés API et secrets !

### 📊 Logs
```
*.log                # Tous les fichiers de logs
logs/*.log           # Logs à la racine
artifacts/logs/*.log # Logs dans artifacts
```

✅ Le dossier `artifacts/logs/` est préservé grâce à `.gitkeep`

### 🗄️ Base de Données & Backups
```
# Ignorés
*.db, *.sqlite       # Bases de données locales
artifacts/backups/*.sql  # Backups SQL générés

# Préservés (avec !)
!artifacts/data/*.sql         # Données initiales importantes
!artifacts/migrations/*.sql   # Migrations de BD
!artifacts/sql/*.sql          # Scripts SQL utiles
!artifacts/docker/postgres/**/*.sql  # Scripts Docker
```

### 💻 IDE & Éditeurs
```
.vscode/             # VS Code
.idea/               # IntelliJ/PyCharm
*.swp, *.swo        # Vim
.DS_Store            # macOS
```

### 🐳 Docker
```
.docker/                      # Cache Docker
docker-compose.override.yml   # Overrides locaux
```

## ✅ Fichiers Importants PRÉSERVÉS

Ces fichiers sont **explicitement préservés** malgré les patterns d'exclusion :

```gitignore
# Migrations SQL (IMPORTANT)
!artifacts/data/*.sql
!artifacts/migrations/*.sql
!artifacts/sql/*.sql
!artifacts/docker/postgres/**/*.sql

# Structure des dossiers
!artifacts/logs/.gitkeep
```

## 🔍 Pourquoi Cette Organisation ?

### 1. Sécurité
- ✅ Tous les fichiers `.env` sont ignorés
- ✅ Les backups SQL (qui peuvent contenir des données sensibles) sont ignorés
- ✅ Les logs (qui peuvent contenir des infos sensibles) sont ignorés

### 2. Performance
- ✅ `node_modules/` ignoré (peut contenir 100k+ fichiers)
- ✅ `venv/` ignoré (dépendances Python)
- ✅ `__pycache__/` ignoré (cache Python)

### 3. Propreté
- ✅ Pas de fichiers temporaires ou de cache dans Git
- ✅ Pas de fichiers spécifiques à l'IDE
- ✅ Pas de fichiers de build

### 4. Collaboration
- ✅ Chaque développeur peut avoir son propre `.env`
- ✅ Les IDE différents n'interfèrent pas
- ✅ Les logs locaux restent locaux

## 📋 Checklist Avant de Commit

Avant de faire un `git add .`, vérifiez :

- [ ] Aucun fichier `.env` n'est staged
- [ ] Aucun fichier de log n'est staged
- [ ] Aucun backup SQL n'est staged (sauf s'il est intentionnel)
- [ ] Aucun `__pycache__/` ou `node_modules/` n'est staged
- [ ] Les fichiers SQL dans `artifacts/` sont bien les bons

## 🛠️ Commandes Utiles

### Vérifier ce qui sera commité
```bash
git status
git diff --cached
```

### Voir ce qui est ignoré
```bash
git status --ignored
```

### Forcer l'ajout d'un fichier ignoré (si nécessaire)
```bash
git add -f chemin/vers/fichier
```

### Nettoyer les fichiers ignorés
```bash
# Dry run (voir ce qui sera supprimé)
git clean -Xdn

# Suppression effective
git clean -Xdf
```

## 🚨 Attention aux Erreurs Courantes

### ❌ Ne PAS faire ça :
```bash
# Ajouter le .env par accident
git add .env

# Ajouter tous les logs
git add artifacts/logs/*.log

# Ajouter node_modules
git add frontend/ai-agent-front/node_modules/
```

### ✅ Faire plutôt :
```bash
# Vérifier avant d'ajouter
git status

# Ajouter sélectivement
git add backend/models/
git add frontend/ai-agent-front/src/

# Utiliser .gitignore
# Les fichiers seront automatiquement ignorés
```

## 📝 Modifier le .gitignore

Si vous devez modifier le `.gitignore` :

1. **Tester localement** :
   ```bash
   git status --ignored
   ```

2. **Vérifier l'impact** :
   ```bash
   git ls-files --others --ignored --exclude-standard
   ```

3. **Commiter le changement** :
   ```bash
   git add .gitignore
   git commit -m "chore: mettre à jour .gitignore"
   ```

## 🔗 Ressources

- [Documentation Git sur .gitignore](https://git-scm.com/docs/gitignore)
- [Templates .gitignore](https://github.com/github/gitignore)
- [.gitignore.io](https://www.toptal.com/developers/gitignore)

## 💡 Bonnes Pratiques

1. ✅ **Toujours** vérifier `git status` avant de commiter
2. ✅ **Ne jamais** commiter de fichiers `.env`
3. ✅ **Garder** le `.gitignore` à jour avec la structure du projet
4. ✅ **Utiliser** `.gitkeep` pour préserver les dossiers vides
5. ✅ **Documenter** les exceptions importantes

---

**Dernière mise à jour** : 2025-11-20  
**Version** : 2.0 (Structure réorganisée)

