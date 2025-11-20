# 🚨 Notifications de Tentatives Non Autorisées

## Vue d'ensemble

Le système de validation humaine inclut maintenant des **notifications actives** quand un utilisateur non autorisé tente de répondre à une validation.

## Fonctionnement

### 1. Détection automatique 🔍

Lorsqu'un utilisateur tente de répondre à une validation créée par quelqu'un d'autre :
- ✅ Le système **détecte** immédiatement la tentative non autorisée
- 🚫 La réponse est **ignorée** (ne déclenche pas le workflow)
- 📨 Une **notification** est automatiquement postée dans Monday.com

### 2. Format de la notification 📝

Quand RV crée une validation et que SV tente d'y répondre, Monday.com reçoit ce message :

```
@RV ⚠️ Il y a un autre utilisateur qui essaie de répondre à votre place pour "Titre de la tâche".

@SV ❌ Vous ne pouvez pas répondre à ce commentaire car vous n'êtes pas le créateur de la demande de validation.

🔐 Pour des raisons de sécurité, seul le créateur de la validation peut y répondre.
```

### 3. Mentions des utilisateurs 👤

Le message mentionne les deux utilisateurs :
- **@RV** (créateur légitime) : Informé qu'il y a eu une tentative d'usurpation
- **@SV** (intrus) : Informé qu'il n'est pas autorisé à répondre

## Exemple concret

### Scénario

1. **RV** crée une tâche dans Monday.com
2. L'agent AI génère du code et crée une update de validation
3. **SV** voit l'update et décide de répondre "oui"  
4. L'agent détecte que SV n'est pas le créateur

### Ce qui se passe

#### Dans les logs 📋

```
🔐 Protection activée: Seul le créateur de l'update 486465232 pourra répondre
👤 Créateur de l'update de validation: RV (ID: 123456, Email: rv@example.com)
🔐 Seul cet utilisateur pourra répondre à cette validation
...
🚫 Réponse ignorée - Utilisateur non autorisé: SV (ID: 789012, Email: sv@example.com)
   Créateur attendu: RV (ID: 123456, Email: rv@example.com)
🚨 1 tentative(s) non autorisée(s) détectée(s) pour item 5085932287
📨 Envoi notification tentative non autorisée: SV → RV
✅ Notification postée dans Monday.com pour item 5085932287
```

#### Dans Monday.com 💬

Un nouvel update apparaît :

```
@RV ⚠️ Il y a un autre utilisateur qui essaie de répondre à votre place 
pour "Implémenter fonctionnalité X".

@SV ❌ Vous ne pouvez pas répondre à ce commentaire car vous n'êtes 
pas le créateur de la demande de validation.

🔐 Pour des raisons de sécurité, seul le créateur de la validation 
peut y répondre.
```

### Résultat

- ❌ La réponse de SV est complètement ignorée
- ⛔ Le workflow ne s'exécute PAS
- ✅ RV est notifié de la tentative
- ✅ SV comprend pourquoi sa réponse n'est pas prise en compte

## Implémentation technique

### Fichiers modifiés

#### `backend/services/monday_validation_service.py`

1. **Fonction `_find_human_reply` modifiée**
   - Retourne maintenant un tuple : `(reply_valide, liste_tentatives_non_autorisées)`
   - Stocker chaque tentative non autorisée avec les informations complètes

2. **Nouvelle fonction `_notify_unauthorized_attempts`**
   - Poste un update dans Monday.com
   - Mentionne les deux utilisateurs
   - Fournit un message clair et informatif

3. **Appels mis à jour**
   - 3 points d'appel modifiés pour gérer les tentatives non autorisées
   - Notification immédiate lors de la détection

### Code clé

```python
async def _notify_unauthorized_attempts(self, item_id: str, unauthorized_attempts: List[Dict[str, Any]], task_title: str):
    """
    Poste un nouvel update dans Monday.com pour notifier une tentative non autorisée.
    """
    for attempt in unauthorized_attempts:
        legitimate_creator_id = attempt.get("legitimate_creator_id")
        legitimate_creator_name = attempt.get("legitimate_creator_name")
        intruder_id = attempt.get("intruder_id")
        intruder_name = attempt.get("intruder_name")
        
        # Construire le message avec mentions
        message = f'<a href="https://monday.com/users/{legitimate_creator_id}">@{legitimate_creator_name}</a>'
        message += f' ⚠️ Il y a un autre utilisateur qui essaie de répondre à votre place pour'
        message += f' <strong>"{task_title}"</strong>.<br><br>'
        message += f'<a href="https://monday.com/users/{intruder_id}">@{intruder_name}</a>'
        message += ' ❌ Vous ne pouvez pas répondre à ce commentaire car vous n\'êtes pas le créateur de la demande de validation.'
        message += '<br><br>🔐 <em>Pour des raisons de sécurité, seul le créateur de la validation peut y répondre.</em>'
        
        # Poster dans Monday.com
        await self.monday_tool.execute_action(
            action="add_comment",
            item_id=item_id,
            comment=message
        )
```

## Avantages

| Avantage | Description |
|----------|-------------|
| 🔒 **Sécurité renforcée** | Les tentatives non autorisées sont bloquées ET signalées |
| 📢 **Transparence** | Les deux parties sont informées en temps réel |
| ✅ **Clarté** | Messages explicites sur les raisons du blocage |
| 🎯 **Traçabilité** | Toutes les tentatives sont enregistrées dans les logs |
| 🛡️ **Protection du workflow** | Le workflow ne s'exécute PAS sur une tentative non autorisée |

## Tests inclus

### Test de notification

```python
def test_unauthorized_user_reply_ignored():
    # ...mock updates...
    result, unauthorized = service._find_human_reply(
        original_update_id="update_1",
        updates=mock_updates,
        since=now - timedelta(minutes=1)
    )
    
    assert result is None  # Pas de réponse valide
    assert len(unauthorized) == 1  # Une tentative détectée
    assert unauthorized[0]["intruder_name"] == "Jane Smith"
```

## Monitoring

### Commandes de suivi

```bash
# Voir les tentatives non autorisées détectées
grep "🚫 Réponse ignorée" logs/app.log

# Voir les notifications envoyées
grep "📨 Envoi notification tentative non autorisée" logs/app.log

# Voir les notifications réussies
grep "✅ Notification postée dans Monday.com" logs/app.log

# Statistiques
echo "Tentatives non autorisées: $(grep -c '🚫 Réponse ignorée' logs/app.log)"
```

### Alertes recommandées

```bash
# Alerte si trop de tentatives non autorisées
UNAUTHORIZED=$(grep -c '🚨.*tentative.*non autorisée' logs/app.log)
if [ $UNAUTHORIZED -gt 5 ]; then
    echo "⚠️  ALERTE: $UNAUTHORIZED tentatives non autorisées détectées"
    # Envoyer notification Slack/email
fi
```

## Différences avec l'ancienne version

### ❌ Avant (Version 1.0)

- 🔇 Réponses non autorisées ignorées **silencieusement**
- ❓ Utilisateurs pas informés
- 🤷 RV ne sait pas que SV a essayé de répondre
- 🤷 SV ne comprend pas pourquoi sa réponse ne fonctionne pas

### ✅ Maintenant (Version 2.0)

- 📢 Réponses non autorisées **signalées activement**
- ✅ Notification dans Monday.com
- ✅ RV est immédiatement informé de la tentative
- ✅ SV comprend pourquoi et reçoit un message clair

## Configuration

### Aucune configuration requise !

Cette fonctionnalité est **automatiquement active** pour toutes les validations humaines.

### Personnalisation (optionnel)

Si vous souhaitez personnaliser le message de notification, modifiez la fonction `_notify_unauthorized_attempts` dans `backend/services/monday_validation_service.py`.

## FAQ

### Q : La notification apparaît où dans Monday.com ?
**R** : Dans la section updates de l'item, comme un nouveau commentaire.

### Q : Les utilisateurs mentionnés reçoivent-ils une notification Monday.com ?
**R** : Oui, si leurs notifications Monday.com sont actives, ils recevront une notification.

### Q : Que se passe-t-il si plusieurs utilisateurs non autorisés répondent ?
**R** : Une notification séparée est envoyée pour chaque tentative.

### Q : Est-ce que le workflow s'exécute quand même ?
**R** : **NON**. Le workflow ne s'exécute jamais avec une réponse non autorisée.

### Q : Puis-je désactiver les notifications ?
**R** : Oui, commentez les appels à `_notify_unauthorized_attempts` dans le code.

## Notes importantes

- Les notifications sont postées **immédiatement** lors de la détection
- Si l'envoi échoue, une erreur est loguée mais le blocage reste effectif
- Les tentatives non autorisées sont toujours loguées, même si la notification échoue
- La fonction gère les erreurs de manière gracieuse (pas de crash)

---

**Date** : 2025-11-20  
**Version** : 2.0  
**Type** : Amélioration de sécurité + Notification active

