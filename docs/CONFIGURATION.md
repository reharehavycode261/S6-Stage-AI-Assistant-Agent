# 🔧 Guide de Configuration

## 🚀 Démarrage Immédiat (Sans Configuration)

Bonne nouvelle ! Le backend peut maintenant démarrer **sans fichier `.env`** :

```bash
cd backend
python main.py
```

✅ Le serveur démarrera avec des valeurs par défaut.

⚠️ Cependant, certaines fonctionnalités ne seront pas disponibles sans configuration appropriée :
- Génération de code avec IA (Claude/GPT)
- Intégration GitHub (Pull Requests)
- Intégration Monday.com

## 📝 Configuration Complète (Recommandé)

### Étape 1 : Créer le fichier .env

**Option A : À la racine du projet (Recommandé)**

```bash
cp artifacts/env_template.txt .env
nano .env
```

**Option B : Dans le dossier backend**

```bash
cd backend
cp ../artifacts/env_template.txt .env
nano .env
```

### Étape 2 : Remplir les clés API essentielles

Ouvrez le fichier `.env` et remplissez au minimum :

```env
# IA (au moins une des deux)
ANTHROPIC_API_KEY=sk-ant-...
# ou
OPENAI_API_KEY=sk-...

# GitHub
GITHUB_TOKEN=ghp_...

# Monday.com
MONDAY_API_TOKEN=...
MONDAY_BOARD_ID=...
```

### Étape 3 : Démarrer le backend

```bash
# Option 1 : Avec Docker
./start.sh

# Option 2 : Mode développement
./start-dev.sh

# Option 3 : Manuel
cd backend
python main.py
```

## 🔑 Obtenir les Clés API

### Anthropic (Claude)

1. Allez sur https://console.anthropic.com/
2. Créez un compte ou connectez-vous
3. Allez dans **API Keys**
4. Cliquez sur **Create Key**
5. Copiez la clé (commence par `sk-ant-`)

### OpenAI (GPT)

1. Allez sur https://platform.openai.com/
2. Créez un compte ou connectez-vous
3. Allez dans **API Keys**
4. Cliquez sur **Create new secret key**
5. Copiez la clé (commence par `sk-`)

### GitHub

1. Allez sur https://github.com/settings/tokens
2. Cliquez sur **Generate new token (classic)**
3. Cochez les permissions :
   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
4. Cliquez sur **Generate token**
5. Copiez le token (commence par `ghp_`)

### Monday.com

1. Allez sur votre compte Monday.com
2. Cliquez sur votre avatar → **Admin**
3. Allez dans **API**
4. Copiez votre **API Token**
5. Pour le Board ID : ouvrez votre board, l'ID est dans l'URL

## 📍 Emplacement du fichier .env

Le backend cherche le fichier `.env` dans cet ordre de priorité :

1. **À la racine du projet** : `/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent/.env`
2. **Dans le dossier backend** : `/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent/backend/.env`
3. **Dans le dossier courant**

💡 **Recommandation** : Placez le `.env` à la racine du projet pour qu'il soit accessible par tous les composants.

## 🛡️ Sécurité

### Valeurs par Défaut (Développement uniquement)

Sans fichier `.env`, ces valeurs sont utilisées :

```env
SECRET_KEY=dev_secret_key_change_me_in_production
WEBHOOK_SECRET=dev_webhook_secret_change_me
DATABASE_URL=postgresql://admin:password@localhost:5432/ai_agent_admin
```

⚠️ **IMPORTANT** : Ces valeurs doivent être changées en production !

### Génération de Secrets Sécurisés

```bash
# Pour SECRET_KEY et WEBHOOK_SECRET
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 🗄️ Services Requis

### PostgreSQL

**Avec Docker (Recommandé)** :
```bash
docker-compose up -d postgres
```

**Manuellement** :
```bash
# macOS
brew install postgresql
brew services start postgresql

# Créer la base de données
createdb ai_agent_admin
```

### RabbitMQ

**Avec Docker (Recommandé)** :
```bash
docker-compose up -d rabbitmq
```

**Manuellement** :
```bash
# macOS
brew install rabbitmq
brew services start rabbitmq
```

### Redis

**Avec Docker (Recommandé)** :
```bash
docker-compose up -d redis
```

**Manuellement** :
```bash
# macOS
brew install redis
brew services start redis
```

## ✅ Vérifier la Configuration

### Backend seul

```bash
cd backend
python main.py
```

Si le serveur démarre, vous devriez voir :
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Accédez à http://localhost:8000/docs pour la documentation API.

### Tous les services (Docker)

```bash
./start.sh
```

Vérifiez que tous les services sont en cours d'exécution :
```bash
docker-compose ps
```

## 🐛 Dépannage

### Erreur "Field required"

**Cause** : Variables obligatoires manquantes dans le `.env`

**Solution** : Les modifications récentes ont rendu tous les champs optionnels. Si vous voyez encore cette erreur :

1. Vérifiez que le fichier `backend/config/settings.py` est à jour
2. Redémarrez le serveur
3. Si le problème persiste, créez un fichier `.env` avec les valeurs manquantes

### Le backend ne trouve pas le .env

**Solution** : Vérifiez l'emplacement du fichier :

```bash
# À la racine
ls -la .env

# Dans backend
ls -la backend/.env
```

### Les services externes ne fonctionnent pas

**Cause** : Clés API manquantes

**Solution** : Ajoutez les clés API dans votre `.env` :
- `ANTHROPIC_API_KEY` ou `OPENAI_API_KEY` pour l'IA
- `GITHUB_TOKEN` pour GitHub
- `MONDAY_API_TOKEN` pour Monday.com

### Erreur de connexion à PostgreSQL

**Solution** :

```bash
# Vérifier que PostgreSQL est démarré
docker-compose ps postgres

# Ou localement
pg_isready
```

## 📚 Ressources

- **[QUICKSTART.md](QUICKSTART.md)** - Guide de démarrage rapide
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Guide de migration
- **[backend/README_CONFIG.md](backend/README_CONFIG.md)** - Configuration backend détaillée
- **Templates** : `artifacts/env_template.txt` et `artifacts/env_template_with_slack.txt`

## 💡 Conseils

1. **Développement** : Le backend peut démarrer sans `.env` pour tester la structure
2. **Tests** : Utilisez un `.env` minimal avec seulement les clés nécessaires à vos tests
3. **Production** : Créez un `.env` complet avec tous les secrets sécurisés

---

**Vous êtes prêt !** 🚀 Le backend peut maintenant démarrer avec ou sans configuration.

