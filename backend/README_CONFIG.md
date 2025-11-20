# Configuration du Backend

## ⚠️ Important

Le backend peut maintenant démarrer **sans fichier `.env`** grâce aux valeurs par défaut, mais certaines fonctionnalités nécessiteront une configuration appropriée pour fonctionner correctement.

## 🚀 Démarrage Rapide

### Option 1 : Démarrage sans configuration (Développement)

Le backend démarrera avec des valeurs par défaut :

```bash
cd backend
python main.py
```

### Option 2 : Configuration complète (Production)

1. **Créer le fichier `.env`** :
   ```bash
   cp .env.template .env
   nano .env
   ```

2. **Remplir les clés API essentielles** :
   - `ANTHROPIC_API_KEY` - Pour utiliser Claude
   - `OPENAI_API_KEY` - Pour utiliser GPT
   - `GITHUB_TOKEN` - Pour interagir avec GitHub
   - `MONDAY_API_TOKEN` - Pour interagir avec Monday.com

3. **Démarrer le backend** :
   ```bash
   python main.py
   ```

## 📍 Emplacement du fichier .env

Le backend cherche le fichier `.env` dans cet ordre :

1. **À la racine du projet** : `../../../.env`
2. **Dans le dossier backend** : `.env`
3. **Dans le dossier courant** : `.env`

Vous pouvez donc placer votre `.env` :
- Soit à la racine du projet : `/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent/.env`
- Soit dans backend : `/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent/backend/.env`

## 🔑 Variables Essentielles

### Pour le développement minimum :

```env
# Aucune variable requise - tout a des valeurs par défaut
```

### Pour utiliser l'IA :

```env
ANTHROPIC_API_KEY=sk-ant-...
# OU
OPENAI_API_KEY=sk-...
```

### Pour l'intégration GitHub :

```env
GITHUB_TOKEN=ghp_...
```

### Pour l'intégration Monday.com :

```env
MONDAY_API_TOKEN=...
MONDAY_BOARD_ID=...
```

## 🛡️ Sécurité

Les valeurs par défaut pour le développement sont :

- `SECRET_KEY` : "dev_secret_key_change_me_in_production"
- `WEBHOOK_SECRET` : "dev_webhook_secret_change_me"

**⚠️ ATTENTION** : Ces valeurs doivent être changées en production !

## 🗄️ Base de Données

Par défaut, le backend se connecte à :

```
postgresql://admin:password@localhost:5432/ai_agent_admin
```

Assurez-vous que PostgreSQL est démarré :

```bash
# Avec Docker
docker-compose up -d postgres

# Ou localement
brew services start postgresql
```

## 🐰 RabbitMQ

Par défaut, le backend se connecte à :

```
amqp://ai_agent_user:secure_password_123@localhost:5672/ai_agent
```

Assurez-vous que RabbitMQ est démarré :

```bash
# Avec Docker
docker-compose up -d rabbitmq

# Ou localement
brew services start rabbitmq
```

## 📝 Logs

En cas d'erreur, consultez les logs :

```bash
# Dans le terminal
# Les erreurs s'afficheront directement

# Logs fichiers
tail -f ../artifacts/logs/celery.log
tail -f ../artifacts/logs/workflows.log
```

## ❓ Dépannage

### Erreur "Field required"

Si vous voyez encore des erreurs "Field required", vérifiez :

1. Que vous avez bien redémarré le serveur après avoir modifié settings.py
2. Que le fichier settings.py est à jour avec les modifications

### Le backend ne trouve pas le .env

Le backend cherche maintenant le .env à plusieurs endroits. Vérifiez :

```bash
# À la racine
ls -la ../../../.env

# Dans backend
ls -la .env
```

### Les services externes ne fonctionnent pas

Sans clés API, les fonctionnalités suivantes ne fonctionneront pas :
- Génération de code avec IA
- Création de Pull Requests GitHub
- Mise à jour de Monday.com

C'est normal en mode développement. Ajoutez les clés API dans `.env` pour activer ces fonctionnalités.

## 📚 Documentation Complète

Pour plus d'informations, consultez :

- [Guide de Démarrage Rapide](../QUICKSTART.md)
- [Guide de Migration](../MIGRATION_GUIDE.md)
- [README Principal](../README.md)

