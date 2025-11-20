# 🔄 Guide de Redémarrage des Workers Celery

## ⚠️ IMPORTANT

Les modifications de sécurité et la correction de la mention du créateur **NE SONT PAS ACTIVES** tant que les workers Celery ne sont pas redémarrés.

---

## 🎯 Modifications à Activer

### 1. **Correction Mention Créateur** ✅
- **Avant** : L'agent mentionnait "Rehareha Ranaivo" (owner du board)
- **Après** : L'agent mentionne "Stagiaire Virtuocode Smartelia" (vrai créateur de l'update @vydata)
- **Fichier modifié** : `backend/nodes/monday_validation_node.py`

### 2. **Sécurité Validation Humaine** 🔒
- **Avant** : N'importe quel utilisateur pouvait répondre à la validation
- **Après** : 
  - Seul le créateur de l'update peut répondre
  - Les réponses non autorisées sont ignorées
  - Notification automatique en cas de tentative non autorisée
- **Fichiers modifiés** : `backend/services/monday_validation_service.py`

---

## 📋 Instructions de Redémarrage

### Option 1 : Redémarrage avec Docker Compose (RECOMMANDÉ)

```bash
cd "/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent"

# Arrêter tous les services
docker-compose down

# Redémarrer tous les services
docker-compose up -d

# Vérifier les logs
docker-compose logs -f celery_workflows
```

### Option 2 : Redémarrage Sélectif des Workers

Si vous ne voulez pas tout redémarrer :

```bash
cd "/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent"

# Arrêter seulement les workers
docker-compose stop celery_workflows celery_webhooks celery_ai

# Redémarrer seulement les workers
docker-compose up -d celery_workflows celery_webhooks celery_ai

# Vérifier que ça tourne
docker-compose ps
```

### Option 3 : Redémarrage Manuel (si pas Docker)

```bash
cd "/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent/backend"

# Trouver et tuer les processus Celery
ps aux | grep celery | grep -v grep | awk '{print $2}' | xargs kill -9

# Redémarrer les workers
celery -A ai_agent_background worker -Q webhooks -n webhooks@%h --loglevel=info &
celery -A ai_agent_background worker -Q workflows -n workflows@%h --loglevel=info &
celery -A ai_agent_background worker -Q ai_requests -n ai@%h --loglevel=info &
```

---

## ✅ Vérification que c'est Actif

### 1. Vérifier les Workers

```bash
# Dans le terminal
docker-compose logs --tail=50 celery_workflows | grep "🔐"
```

**Ce que vous devriez voir** si c'est actif :
```
🔐 Seul cet utilisateur pourra répondre à cette validation
✅ Réponse autorisée de Stagiaire Virtuocode Smartelia
```

### 2. Test Rapide

1. **Créez une tâche** avec un compte (ex: SV)
2. **L'agent répond** et demande validation
3. **Vérifiez la mention** : devrait être `@Stagiaire Virtuocode Smartelia` (pas Rehareha)
4. **Essayez de répondre avec un autre compte** (ex: RV)
5. **Résultat attendu** : 
   - L'agent **ignore** la réponse de RV
   - L'agent **poste un nouvel update** mentionnant SV et RV
   - Le workflow **continue d'attendre** la vraie réponse de SV

---

## 🔍 Logs de Sécurité

Si la sécurité est active, vous verrez ces logs :

### ✅ Logs Positifs (Réponse Autorisée)
```
👤 Créateur de l'update de validation: Stagiaire Virtuocode Smartelia (ID: 12345, Email: stagiaire@...)
🔐 Seul cet utilisateur pourra répondre à cette validation
✅ Réponse autorisée de Stagiaire Virtuocode Smartelia (ID: 12345)
```

### 🚫 Logs Négatifs (Tentative Non Autorisée)
```
🚫 Réponse ignorée - Utilisateur non autorisé: Rehareha Ranaivo (ID: 67890, Email: rehareha@...)
   Créateur attendu: Stagiaire Virtuocode Smartelia (ID: 12345, Email: stagiaire@...)
📢 Notification d'accès non autorisé envoyée pour item 5085932287
```

---

## 🚨 Problèmes Courants

### Problème 1 : "Aucun log de sécurité visible"
**Cause** : Les workers n'ont pas été redémarrés
**Solution** : Suivre les instructions de redémarrage ci-dessus

### Problème 2 : "L'agent mentionne toujours le owner"
**Cause** : Les workers tournent encore avec l'ancien code
**Solution** : 
```bash
docker-compose restart celery_workflows
```

### Problème 3 : "Erreur au démarrage des workers"
**Cause** : Port déjà utilisé ou configuration incorrecte
**Solution** : 
```bash
# Tuer tous les processus Celery
pkill -9 celery
# Redémarrer
docker-compose up -d
```

---

## 📊 Résumé des Changements

| Aspect | Avant | Après |
|--------|-------|-------|
| **Mention** | Owner du board | Créateur update @vydata |
| **Sécurité** | Tous peuvent répondre | Seul créateur peut répondre |
| **Notification** | Aucune | Notification automatique |
| **Logs** | Basiques | Logs sécurité détaillés |

---

## 🎯 Prochaines Étapes

1. ✅ **Redémarrer les workers** (voir instructions ci-dessus)
2. ✅ **Tester avec une vraie tâche**
3. ✅ **Vérifier les logs de sécurité**
4. ✅ **Confirmer que tout fonctionne**

---

**💡 Conseil** : Gardez un terminal ouvert avec `docker-compose logs -f celery_workflows` pour voir les logs en temps réel pendant le test.

