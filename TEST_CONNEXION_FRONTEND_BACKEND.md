# 🧪 Guide de Test - Connexion Frontend ↔ Backend

## 🎯 Objectif

Vérifier que le frontend React communique correctement avec le backend FastAPI et la base de données PostgreSQL.

---

## ⚡ Test Rapide (5 minutes)

### Prérequis

1. ✅ PostgreSQL en cours d'exécution (Docker)
2. ✅ Variables d'environnement configurées (`.env`)

### Étape 1 : Démarrer le Backend

```bash
# Depuis la racine du projet
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Vérification:**
- Console affiche: `Uvicorn running on http://0.0.0.0:8000`
- Aucune erreur au démarrage

### Étape 2 : Tester l'API Backend

Ouvrir un nouveau terminal:

```bash
# Test 1: Health check
curl http://localhost:8000/

# Réponse attendue:
# {
#   "message": "Agent d'Automatisation IA",
#   "version": "2.0.0",
#   "status": "running"
# }

# Test 2: Dashboard metrics
curl http://localhost:8000/api/dashboard/metrics

# Réponse attendue:
# {
#   "tasks_active": 0,
#   "tasks_today": 0,
#   "success_rate_today": 0,
#   "avg_execution_time": 0,
#   "ai_cost_today": 0,
#   "workers_active": 3,
#   "queue_size": 0
# }

# Test 3: Liste des tâches
curl http://localhost:8000/api/tasks

# Réponse attendue:
# {
#   "items": [...],
#   "total": X,
#   "page": 1,
#   "per_page": 20,
#   "pages": Y
# }
```

**✅ Si toutes les requêtes retournent du JSON sans erreur, le backend fonctionne !**

### Étape 3 : Démarrer le Frontend

Nouveau terminal:

```bash
cd ai-agent-front
npm run dev
```

**Vérification:**
- Console affiche: `Local: http://localhost:3000`
- Aucune erreur de compilation

### Étape 4 : Tester l'Interface

1. **Ouvrir dans le navigateur:** http://localhost:3000

2. **Ouvrir la Console Développeur (F12)**

3. **Vérifier:**
   - ✅ Page se charge sans erreur
   - ✅ Dashboard affiche les métriques
   - ✅ Pas d'erreurs dans la console
   - ✅ Pas d'erreurs réseau (onglet Network)

### Étape 5 : Navigation

**Tester chaque page:**

- ✅ Dashboard (`/`) - Métriques et graphiques
- ✅ Workflow (`/workflow`) - Visualisation
- ✅ Tâches (`/tasks`) - Liste des tâches
- ✅ Tests (`/tests`) - Dashboard des tests
- ✅ Utilisateurs (`/users`) - Liste des utilisateurs
- ✅ Langages (`/languages`) - Stats de détection
- ✅ Modèles IA (`/ai-models`) - Usage des modèles
- ✅ Intégrations (`/integrations`) - Monday/GitHub/Slack
- ✅ Analytics (`/analytics`) - Rapports
- ✅ Logs (`/logs`) - Logs système
- ✅ Configuration (`/config`) - Configuration

---

## 🔍 Tests Détaillés

### Test 1 : Chargement des Métriques Dashboard

**Action:**
1. Ouvrir http://localhost:3000
2. Observer le dashboard

**Vérifications:**
- [ ] Les 4 cartes de métriques s'affichent
- [ ] Les valeurs sont chargées (même si 0)
- [ ] Le graphique "Évolution des tâches" s'affiche
- [ ] Le graphique "Langages détectés" s'affiche
- [ ] Pas d'erreurs dans la console

**Console Network (F12):**
```
GET http://localhost:8000/api/dashboard/metrics
Status: 200 OK
Response Time: < 100ms
```

### Test 2 : Liste des Tâches avec Filtres

**Action:**
1. Naviguer vers `/tasks`
2. Observer la liste des tâches

**Vérifications:**
- [ ] La liste se charge
- [ ] Pagination fonctionne
- [ ] Filtres par statut fonctionnent
- [ ] Filtres par priorité fonctionnent
- [ ] Clic sur une tâche ouvre le détail

**Console Network:**
```
GET http://localhost:8000/api/tasks?page=1&per_page=20
Status: 200 OK
```

### Test 3 : Détail d'une Tâche

**Action:**
1. Depuis `/tasks`, cliquer sur une tâche
2. Observer la page de détail

**Vérifications:**
- [ ] Détails de la tâche s'affichent
- [ ] Historique des exécutions visible
- [ ] Timeline affichée
- [ ] Liens GitHub fonctionnent (si disponibles)
- [ ] Section validation visible (si applicable)

**Console Network:**
```
GET http://localhost:8000/api/tasks/123
Status: 200 OK
```

### Test 4 : Validations En Attente

**Action:**
1. Naviguer vers une page qui utilise les validations
2. Observer les données

**Vérifications:**
- [ ] Les validations se chargent
- [ ] Pas d'erreurs de format
- [ ] Dates formatées correctement

**Console Network:**
```
GET http://localhost:8000/api/validations/pending
Status: 200 OK
```

### Test 5 : Intégrations Externes

**Action:**
1. Naviguer vers `/integrations`
2. Observer les données des intégrations

**Vérifications:**
- [ ] Monday.com board s'affiche
- [ ] GitHub repos s'affichent
- [ ] Slack workspace s'affiche
- [ ] Pas d'erreurs

**Console Network:**
```
GET http://localhost:8000/api/integrations/monday/boards
GET http://localhost:8000/api/integrations/github/repos
GET http://localhost:8000/api/integrations/slack/workspace
```

### Test 6 : Configuration Système

**Action:**
1. Naviguer vers `/config`
2. Observer la configuration

**Vérifications:**
- [ ] Configuration se charge
- [ ] Secrets sont masqués (`****`)
- [ ] Toutes les variables s'affichent
- [ ] Pas d'erreurs

**Console Network:**
```
GET http://localhost:8000/api/config
Status: 200 OK
```

---

## 🐛 Résolution de Problèmes

### Erreur : "Failed to fetch"

**Symptôme:**
```
Error: Failed to fetch
TypeError: NetworkError when attempting to fetch resource
```

**Causes possibles:**
1. Backend pas démarré
2. Mauvaise URL dans `.env`
3. CORS mal configuré

**Solution:**
```bash
# 1. Vérifier que le backend tourne
curl http://localhost:8000/

# 2. Vérifier .env dans ai-agent-front/
cat ai-agent-front/.env
# VITE_API_BASE_URL=http://localhost:8000

# 3. Vérifier CORS dans main.py
# allow_origins=["*", "http://localhost:3000"]
```

### Erreur : "Connection refused"

**Symptôme:**
```
Error: connect ECONNREFUSED 127.0.0.1:8000
```

**Solution:**
```bash
# Backend pas démarré, le démarrer:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Erreur : "500 Internal Server Error"

**Symptôme:**
```
GET /api/dashboard/metrics
Status: 500
```

**Causes possibles:**
1. Erreur de connexion à la base de données
2. Table manquante
3. Erreur dans le code backend

**Solution:**
```bash
# 1. Vérifier les logs backend
# Regarder dans le terminal où uvicorn tourne

# 2. Tester la connexion DB
curl http://localhost:8000/api/tasks

# 3. Vérifier PostgreSQL
docker ps | grep postgres
```

### Erreur : "404 Not Found"

**Symptôme:**
```
GET /api/some-endpoint
Status: 404
```

**Solution:**
```bash
# Vérifier que l'endpoint existe dans api_admin_routes.py
# Vérifier que les routes sont incluses dans main.py:
# app.include_router(api_admin_router, tags=["Admin API"])
```

### Données Vides (Mais Pas d'Erreur)

**Symptôme:**
- Les pages se chargent
- Mais aucune donnée n'apparaît
- Pas d'erreurs dans la console

**Solution:**
```bash
# C'est normal si la base de données est vide !
# Créer une tâche test depuis Monday.com pour voir des données

# Ou vérifier qu'il y a des données dans la DB:
curl http://localhost:8000/api/tasks
# Si {"items": [], "total": 0} => DB vide, c'est normal
```

---

## ✅ Checklist de Validation Finale

### Backend

- [ ] `curl http://localhost:8000/` retourne JSON
- [ ] `curl http://localhost:8000/api/dashboard/metrics` retourne des métriques
- [ ] `curl http://localhost:8000/api/tasks` retourne une liste paginée
- [ ] Aucune erreur dans les logs uvicorn
- [ ] Swagger UI accessible : http://localhost:8000/docs

### Frontend

- [ ] http://localhost:3000 se charge sans erreur
- [ ] Dashboard affiche les métriques
- [ ] Navigation entre les pages fonctionne
- [ ] Aucune erreur dans la console navigateur
- [ ] Aucune erreur 404 dans l'onglet Network

### Intégration

- [ ] Les données du backend s'affichent dans le frontend
- [ ] Les filtres et la pagination fonctionnent
- [ ] Les liens sont cliquables
- [ ] Le temps de chargement est acceptable (< 2s)
- [ ] Le rafraîchissement automatique fonctionne (dashboard)

---

## 📊 Résultats Attendus

### Si Tout Fonctionne

**Backend (Terminal):**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Started reloader process
INFO:     Started server process
INFO:     Application startup complete
```

**Frontend (Terminal):**
```
  VITE v5.4.8  ready in 523 ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

**Navigateur (Console):**
```
✅ Dashboard metrics loaded
✅ Tasks list loaded
✅ No errors
```

**Navigateur (Network Tab):**
```
GET /api/dashboard/metrics     200 OK  45ms
GET /api/tasks                 200 OK  67ms
GET /api/validations/pending   200 OK  32ms
```

---

## 🎯 Scénario de Test Complet

### Scénario : Créer et Suivre une Tâche

**1. Créer une tâche depuis Monday.com**
- Aller sur Monday.com
- Créer un nouvel item dans le board AI Agent
- Remplir titre et description
- Définir le repository URL

**2. Vérifier dans le Frontend**
- Rafraîchir le dashboard
- Observer `tasks_today` qui passe de 0 à 1
- Aller dans `/tasks`
- La nouvelle tâche doit apparaître dans la liste

**3. Suivre l'Exécution**
- Cliquer sur la tâche
- Observer le détail
- Voir la timeline des étapes
- Suivre les logs en temps réel

**4. Vérifier la Validation**
- Si la tâche nécessite validation
- Elle doit apparaître dans les validations en attente
- Les détails du code généré sont visibles

**5. Vérifier les Métriques**
- Retourner au dashboard
- Observer les graphiques mis à jour
- Vérifier le coût IA
- Vérifier le temps d'exécution moyen

**✅ Si toutes ces étapes fonctionnent, l'intégration est parfaite !**

---

## 📝 Rapport de Test

Utiliser ce template pour documenter vos tests:

```markdown
## Test Date: 2025-11-03

### Backend
- [ ] ✅ Démarré sans erreur
- [ ] ✅ API répond correctement
- [ ] ✅ Base de données accessible

### Frontend
- [ ] ✅ Compile sans erreur
- [ ] ✅ Pages se chargent
- [ ] ✅ Données affichées

### Intégration
- [ ] ✅ Backend ↔ Frontend connectés
- [ ] ✅ Frontend ↔ Database cohérents
- [ ] ✅ Nomenclature cohérente

### Performance
- Dashboard load time: XX ms
- Tasks list load time: XX ms
- Task detail load time: XX ms

### Issues Found
- None / [List issues]

### Overall Status
✅ PASSED / ❌ FAILED

### Notes
[Additional notes]
```

---

## 🎉 Conclusion

Si tous les tests passent, **l'intégration est complète et fonctionnelle !**

**Statut:** ✅ **READY FOR USE**

Pour utilisation quotidienne:
```bash
./start_admin_full.sh
```

---

**Version:** 1.0.0  
**Date:** 3 novembre 2025  
**Statut:** ✅ Validé

