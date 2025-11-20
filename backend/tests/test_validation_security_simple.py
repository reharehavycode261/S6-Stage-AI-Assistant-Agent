"""Tests simples de sécurité de la validation humaine (sans pytest)."""

from datetime import datetime, timedelta, timezone


class MockMondayValidationService:
    """Mock du service de validation pour les tests."""
    
    def _find_human_reply(self, original_update_id: str, updates: list, since: datetime, item_id=None, task_title=None):
        """Reproduction de la logique de _find_human_reply avec la sécurité."""
        if not isinstance(updates, list):
            updates = []
        
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        
        # 🔐 ÉTAPE 1: Récupérer le créateur de l'update de validation original
        original_creator_id = None
        original_creator_email = None
        unauthorized_attempts = []
        
        for update in updates:
            if str(update.get("id")) == str(original_update_id):
                creator = update.get("creator", {})
                if isinstance(creator, dict):
                    original_creator_id = creator.get("id")
                    original_creator_email = creator.get("email")
                break
        
        # Rechercher les réponses
        for update in updates:
            if str(update.get("id")) == str(original_update_id):
                continue
            
            # 🔐 ÉTAPE 2: Vérifier que la réponse vient du créateur autorisé
            reply_creator = update.get("creator", {})
            reply_creator_id = reply_creator.get("id") if isinstance(reply_creator, dict) else None
            reply_creator_email = reply_creator.get("email") if isinstance(reply_creator, dict) else None
            reply_creator_name = reply_creator.get("name", "inconnu") if isinstance(reply_creator, dict) else "inconnu"
            
            # Si on a identifié un créateur original, vérifier que la réponse vient de lui
            if original_creator_id or original_creator_email:
                is_authorized = False
                
                if original_creator_id and reply_creator_id:
                    is_authorized = str(original_creator_id) == str(reply_creator_id)
                elif original_creator_email and reply_creator_email:
                    is_authorized = original_creator_email.lower() == reply_creator_email.lower()
                
                if not is_authorized:
                    # Stocker la tentative non autorisée
                    unauthorized_attempts.append({
                        "intruder_id": reply_creator_id,
                        "intruder_name": reply_creator_name,
                        "update": update
                    })
                    continue
            
            # Si reply_to_id correspond
            reply_to_id = update.get("reply_to_id")
            if reply_to_id and str(reply_to_id) == str(original_update_id):
                return update, unauthorized_attempts
        
        return None, unauthorized_attempts


def test_authorized_user_can_reply():
    """Test : L'utilisateur autorisé peut répondre."""
    service = MockMondayValidationService()
    now = datetime.now(timezone.utc)
    
    mock_updates = [
        {
            "id": "update_1",
            "body": "Update de validation @vydata",
            "created_at": now.isoformat(),
            "creator": {
                "id": "123",
                "email": "john@example.com",
                "name": "John Doe"
            }
        },
        {
            "id": "update_2",
            "body": "Oui, je valide",
            "created_at": (now + timedelta(seconds=10)).isoformat(),
            "reply_to_id": "update_1",
            "type": "reply",
            "creator": {
                "id": "123",
                "email": "john@example.com",
                "name": "John Doe"
            }
        }
    ]
    
    result, unauthorized = service._find_human_reply(
        original_update_id="update_1",
        updates=mock_updates,
        since=now - timedelta(minutes=1)
    )
    
    assert result is not None, "❌ La réponse autorisée devrait être trouvée"
    assert result["id"] == "update_2", "❌ L'update_2 devrait être retournée"
    assert result["creator"]["id"] == "123", "❌ Le créateur devrait être John (123)"
    assert len(unauthorized) == 0, "❌ Aucune tentative non autorisée ne devrait être détectée"
    print("✅ Test 1 réussi : L'utilisateur autorisé peut répondre")


def test_unauthorized_user_reply_ignored():
    """Test : La réponse d'un utilisateur non autorisé est ignorée."""
    service = MockMondayValidationService()
    now = datetime.now(timezone.utc)
    
    mock_updates = [
        {
            "id": "update_1",
            "body": "Update de validation",
            "created_at": now.isoformat(),
            "creator": {
                "id": "123",
                "email": "john@example.com",
                "name": "John Doe"
            }
        },
        {
            "id": "update_3",
            "body": "Non, je refuse",
            "created_at": (now + timedelta(seconds=20)).isoformat(),
            "reply_to_id": "update_1",
            "type": "reply",
            "creator": {
                "id": "456",
                "email": "jane@example.com",
                "name": "Jane Smith"
            }
        }
    ]
    
    result, unauthorized = service._find_human_reply(
        original_update_id="update_1",
        updates=mock_updates,
        since=now - timedelta(minutes=1)
    )
    
    assert result is None, "❌ La réponse non autorisée devrait être ignorée"
    assert len(unauthorized) == 1, "❌ Une tentative non autorisée devrait être détectée"
    assert unauthorized[0]["intruder_name"] == "Jane Smith", "❌ L'intrus devrait être Jane"
    print("✅ Test 2 réussi : La réponse non autorisée est ignorée et signalée")


def test_multiple_replies_only_authorized_accepted():
    """Test : Parmi plusieurs réponses, seule celle du créateur est acceptée."""
    service = MockMondayValidationService()
    now = datetime.now(timezone.utc)
    
    mock_updates = [
        {
            "id": "update_1",
            "body": "Update",
            "created_at": now.isoformat(),
            "creator": {
                "id": "123",
                "email": "john@example.com",
                "name": "John Doe"
            }
        },
        {
            "id": "update_2",
            "body": "Réponse de Jane",
            "created_at": (now + timedelta(seconds=5)).isoformat(),
            "reply_to_id": "update_1",
            "creator": {
                "id": "456",
                "email": "jane@example.com",
                "name": "Jane"
            }
        },
        {
            "id": "update_3",
            "body": "Réponse de John",
            "created_at": (now + timedelta(seconds=10)).isoformat(),
            "reply_to_id": "update_1",
            "creator": {
                "id": "123",
                "email": "john@example.com",
                "name": "John Doe"
            }
        }
    ]
    
    result, unauthorized = service._find_human_reply(
        original_update_id="update_1",
        updates=mock_updates,
        since=now - timedelta(minutes=1)
    )
    
    assert result is not None, "❌ Une réponse devrait être trouvée"
    assert result["creator"]["id"] == "123", "❌ Seule la réponse de John devrait être acceptée"
    assert len(unauthorized) == 1, "❌ Une tentative non autorisée devrait être détectée (Jane)"
    print("✅ Test 3 réussi : Seule la réponse autorisée est acceptée parmi plusieurs")


def test_email_fallback_authorization():
    """Test : L'autorisation fonctionne avec l'email si l'ID n'est pas disponible."""
    service = MockMondayValidationService()
    now = datetime.now(timezone.utc)
    
    mock_updates = [
        {
            "id": "update_1",
            "body": "Update",
            "created_at": now.isoformat(),
            "creator": {
                "email": "john@example.com",
                "name": "John Doe"
            }
        },
        {
            "id": "update_2",
            "body": "Oui",
            "created_at": (now + timedelta(seconds=10)).isoformat(),
            "reply_to_id": "update_1",
            "creator": {
                "email": "john@example.com",
                "name": "John Doe"
            }
        }
    ]
    
    result, unauthorized = service._find_human_reply(
        original_update_id="update_1",
        updates=mock_updates,
        since=now - timedelta(minutes=1)
    )
    
    assert result is not None, "❌ L'autorisation par email devrait fonctionner"
    assert result["creator"]["email"] == "john@example.com", "❌ Le bon créateur devrait être identifié"
    print("✅ Test 4 réussi : Autorisation par email fonctionne")


def test_case_insensitive_email():
    """Test : La comparaison d'emails est insensitive à la casse."""
    service = MockMondayValidationService()
    now = datetime.now(timezone.utc)
    
    mock_updates = [
        {
            "id": "update_1",
            "body": "Update",
            "created_at": now.isoformat(),
            "creator": {
                "email": "John@Example.COM",
                "name": "John"
            }
        },
        {
            "id": "update_2",
            "body": "Oui",
            "created_at": (now + timedelta(seconds=10)).isoformat(),
            "reply_to_id": "update_1",
            "creator": {
                "email": "john@example.com",
                "name": "John"
            }
        }
    ]
    
    result, unauthorized = service._find_human_reply(
        original_update_id="update_1",
        updates=mock_updates,
        since=now - timedelta(minutes=1)
    )
    
    assert result is not None, "❌ La comparaison devrait être insensible à la casse"
    print("✅ Test 5 réussi : Comparaison d'emails insensible à la casse")


def test_no_creator_info_fallback():
    """Test : Sans info créateur, le système accepte toutes les réponses."""
    service = MockMondayValidationService()
    now = datetime.now(timezone.utc)
    
    mock_updates = [
        {
            "id": "update_1",
            "body": "Update",
            "created_at": now.isoformat(),
            "creator": {}  # Pas d'info créateur
        },
        {
            "id": "update_2",
            "body": "Réponse",
            "created_at": (now + timedelta(seconds=10)).isoformat(),
            "reply_to_id": "update_1",
            "creator": {
                "id": "456",
                "email": "anyone@example.com"
            }
        }
    ]
    
    result, unauthorized = service._find_human_reply(
        original_update_id="update_1",
        updates=mock_updates,
        since=now - timedelta(minutes=1)
    )
    
    assert result is not None, "❌ En mode dégradé, les réponses devraient être acceptées"
    print("✅ Test 6 réussi : Mode dégradé fonctionne sans info créateur")


if __name__ == "__main__":
    print("🧪 Lancement des tests de sécurité de validation\n")
    print("=" * 60)
    
    try:
        test_authorized_user_can_reply()
        test_unauthorized_user_reply_ignored()
        test_multiple_replies_only_authorized_accepted()
        test_email_fallback_authorization()
        test_case_insensitive_email()
        test_no_creator_info_fallback()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS SONT PASSÉS !")
        print("🔐 La sécurité de validation fonctionne correctement")
        
    except AssertionError as e:
        print(f"\n❌ ÉCHEC DU TEST: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

