# 🚀 Démarrage Rapide - Agent IA

Ce guide vous permet de démarrer rapidement avec l'Agent d'Automatisation IA.

## ⚡ Installation en 3 étapes

### 1️⃣ Configurer l'environnement

```bash
# Copier le fichier de configuration
cp artifacts/env_template.txt .env

# Éditer le fichier .env et remplir les clés API
nano .env
```

**Clés minimales requises :**
- `ANTHROPIC_API_KEY` - Votre clé API Claude
- `GITHUB_TOKEN` - Token GitHub avec permissions `repo`
- `MONDAY_API_KEY` - Clé API Monday.com
- `WEBHOOK_SECRET` - Un secret aléatoire pour les webhooks
- `SECRET_KEY` - Un secret aléatoire pour JWT

### 2️⃣ Démarrer les services

**Option A : Docker (Recommandé)**
```bash
chmod +x start.sh
./start.sh
```

**Option B : Développement Local**
```bash
chmod +x start-dev.sh
./start-dev.sh
```

### 3️⃣ Vérifier que tout fonctionne

Ouvrez votre navigateur et accédez à :

- **API** : http://localhost:8000
- **Documentation** : http://localhost:8000/docs
- **RabbitMQ** : http://localhost:15672 (ai_agent_user/secure_password_123)
- **Flower** : http://localhost:5555 (admin/flower123)

## 📋 Configuration Monday.com

### Créer les colonnes requises

Dans votre board Monday.com, créez ces colonnes :

1. **Description Technique** (Texte long)
2. **Branche Git** (Texte)
3. **Statut** (Étiquettes) avec les valeurs :
   - À faire
   - En cours
   - Validé
   - Terminé
   - Erreur
4. **Priorité** (Étiquettes)

### Configurer le webhook

1. Allez dans **Intégrations → Webhooks**
2. Créez un nouveau webhook :
   - **URL** : `https://votre-domaine.com/webhook/monday`
   - **Événement** : "Item created" et "Item updated"
   - **Secret** : Le même que `WEBHOOK_SECRET` dans votre `.env`

## 🔑 Configuration GitHub

### Créer un Personal Access Token

1. Allez dans **Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Cliquez sur **Generate new token (classic)**
3. Cochez les permissions suivantes :
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
4. Copiez le token et ajoutez-le dans votre `.env` comme `GITHUB_TOKEN`

## 🧪 Tester l'agent

### Test manuel via l'API

```bash
curl -X POST http://localhost:8000/webhook/monday \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_WEBHOOK_SECRET" \
  -d '{
    "event": {
      "type": "create_pulse"
    },
    "pulse": {
      "id": "123456",
      "name": "Ajouter validation d'email",
      "column_values": [
        {
          "id": "task_description",
          "text": "Implémenter une validation d'email pour le formulaire"
        },
        {
          "id": "branch",
          "text": "feature/email-validation"
        }
      ]
    }
  }'
```

### Créer une tâche dans Monday.com

1. Créez une nouvelle tâche dans votre board
2. Remplissez :
   - **Titre** : "Ajouter validation d'email"
   - **Description Technique** : "Implémenter une validation d'email côté client et serveur"
   - **Branche Git** : "feature/email-validation"
   - **Priorité** : "High"

3. L'agent devrait :
   - ✅ Recevoir le webhook
   - ✅ Analyser la tâche
   - ✅ Créer une branche
   - ✅ Implémenter le code
   - ✅ Exécuter les tests
   - ✅ Créer une Pull Request
   - ✅ Mettre à jour Monday.com

## 📊 Surveiller l'exécution

### Logs en temps réel

```bash
# Voir tous les logs
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f app
docker-compose logs -f celery-worker-workflows
```

### Interface Flower (Celery)

Accédez à http://localhost:5555 pour voir :
- Les tâches en cours
- Les tâches terminées
- Les erreurs
- Les statistiques

### Logs fichiers

Les logs sont également sauvegardés dans `artifacts/logs/` :
- `celery.log` - Logs Celery
- `workflows.log` - Logs des workflows
- `performance.log` - Métriques de performance

## 🛠️ Commandes utiles

### Docker

```bash
# Démarrer
docker-compose up -d

# Arrêter
docker-compose down

# Redémarrer un service
docker-compose restart app

# Voir les logs
docker-compose logs -f app

# Reconstruire les images
docker-compose build --no-cache
```

### Backend (développement local)

```bash
# Démarrer le backend
cd backend
python main.py

# Exécuter les tests
cd backend
pytest

# Lancer Celery
cd backend
celery -A services.celery_app worker --loglevel=info
```

### Frontend

```bash
# Installer les dépendances
cd frontend/ai-agent-front
npm install

# Démarrer le serveur de développement
npm run dev

# Build de production
npm run build
```

## ❓ Problèmes courants

### Port déjà utilisé

```bash
# Trouver le processus utilisant le port 8000
lsof -i :8000

# Tuer le processus
kill -9 <PID>
```

### Docker ne démarre pas

```bash
# Nettoyer Docker
docker system prune -a

# Redémarrer Docker Desktop
```

### Erreur "Module not found"

```bash
# Vérifier que vous êtes dans le bon dossier
cd backend
python main.py

# Ou ajouter backend au PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}/backend"
```

### Les logs ne s'affichent pas

```bash
# Créer le dossier logs s'il n'existe pas
mkdir -p artifacts/logs
chmod 755 artifacts/logs
```

## 📚 Documentation complète

- [README Principal](README.md) - Vue d'ensemble complète
- [Guide de Migration](MIGRATION_GUIDE.md) - Détails sur la nouvelle structure
- [Structure du Projet](README_STRUCTURE.md) - Organisation des dossiers

## 🆘 Support

Si vous rencontrez des problèmes :

1. Vérifiez que tous les services Docker sont en cours d'exécution : `docker-compose ps`
2. Consultez les logs : `docker-compose logs -f`
3. Vérifiez votre fichier `.env`
4. Consultez le [Guide de Migration](MIGRATION_GUIDE.md)

---

**Prêt à automatiser vos développements !** 🚀

