"""Tests de sécurité de la validation humaine."""

import pytest
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path

# Ajouter le répertoire backend au path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


class MockMondayValidationService:
    """Mock du service de validation pour les tests."""
    
    def __init__(self):
        self.pending_validations = {}
        self.monday_tool = MagicMock()
    
    def _find_human_reply(self, original_update_id: str, updates: list, since: datetime):
        """Reproduction de la logique de _find_human_reply avec la sécurité."""
        from datetime import timezone, timedelta
        
        if not isinstance(updates, list):
            updates = []
        
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        
        # 🔐 ÉTAPE 1: Récupérer le créateur de l'update de validation original
        original_creator_id = None
        original_creator_email = None
        
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
            
            # Si on a identifié un créateur original, vérifier que la réponse vient de lui
            if original_creator_id or original_creator_email:
                is_authorized = False
                
                if original_creator_id and reply_creator_id:
                    is_authorized = str(original_creator_id) == str(reply_creator_id)
                elif original_creator_email and reply_creator_email:
                    is_authorized = original_creator_email.lower() == reply_creator_email.lower()
                
                if not is_authorized:
                    continue
            
            # Si reply_to_id correspond
            reply_to_id = update.get("reply_to_id")
            if reply_to_id and str(reply_to_id) == str(original_update_id):
                return update
        
        return None


class TestValidationSecurity:
    """Tests de sécurité pour la validation humaine."""
    
    @pytest.fixture
    def service(self):
        """Instance du service de validation mocké."""
        return MockMondayValidationService()
    
    @pytest.fixture
    def mock_updates(self):
        """Mock des updates Monday.com avec différents créateurs."""
        now = datetime.now()
        
        return [
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
    
    def test_authorized_user_can_reply(self, service, mock_updates):
        """Test : L'utilisateur autorisé peut répondre."""
        # L'update 2 est du même créateur que l'update 1
        result = service._find_human_reply(
            original_update_id="update_1",
            updates=mock_updates,
            since=datetime.now() - timedelta(minutes=1)
        )
        
        # Devrait trouver la réponse du créateur autorisé (update_2)
        assert result is not None
        assert result["id"] == "update_2"
        assert result["body"] == "Oui, je valide"
        assert result["creator"]["id"] == "123"
    
    def test_unauthorized_user_reply_ignored(self, service, mock_updates):
        """Test : La réponse d'un utilisateur non autorisé est ignorée."""
        # Créer un scénario où seul l'utilisateur non autorisé répond
        filtered_updates = [mock_updates[0], mock_updates[2]]  # update_1 et update_3 (Jane)
        
        result = service._find_human_reply(
            original_update_id="update_1",
            updates=filtered_updates,
            since=datetime.now() - timedelta(minutes=1)
        )
        
        # Ne devrait PAS trouver la réponse de Jane (non autorisée)
        assert result is None or result["creator"]["id"] != "456"
    
    def test_multiple_replies_only_authorized_accepted(self, service, mock_updates):
        """Test : Parmi plusieurs réponses, seule celle du créateur est acceptée."""
        result = service._find_human_reply(
            original_update_id="update_1",
            updates=mock_updates,
            since=datetime.now() - timedelta(minutes=1)
        )
        
        # Devrait trouver la réponse de John (autorisé), pas celle de Jane
        assert result is not None
        assert result["creator"]["id"] == "123"
        assert result["creator"]["name"] == "John Doe"
    
    def test_email_fallback_authorization(self, service):
        """Test : L'autorisation fonctionne avec l'email si l'ID n'est pas disponible."""
        now = datetime.now()
        
        updates_with_email_only = [
            {
                "id": "update_1",
                "body": "Update de validation",
                "created_at": now.isoformat(),
                "creator": {
                    "email": "john@example.com",
                    "name": "John Doe"
                }
            },
            {
                "id": "update_2",
                "body": "Oui, validé",
                "created_at": (now + timedelta(seconds=10)).isoformat(),
                "reply_to_id": "update_1",
                "type": "reply",
                "creator": {
                    "email": "john@example.com",
                    "name": "John Doe"
                }
            },
            {
                "id": "update_3",
                "body": "Autre réponse",
                "created_at": (now + timedelta(seconds=15)).isoformat(),
                "reply_to_id": "update_1",
                "type": "reply",
                "creator": {
                    "email": "other@example.com",
                    "name": "Other User"
                }
            }
        ]
        
        result = service._find_human_reply(
            original_update_id="update_1",
            updates=updates_with_email_only,
            since=now - timedelta(minutes=1)
        )
        
        # Devrait autoriser basé sur l'email
        assert result is not None
        assert result["creator"]["email"] == "john@example.com"
    
    def test_no_creator_info_fallback_to_open(self, service):
        """Test : Sans info créateur, le système accepte toutes les réponses (mode dégradé)."""
        now = datetime.now()
        
        updates_no_creator = [
            {
                "id": "update_1",
                "body": "Update de validation",
                "created_at": now.isoformat(),
                "creator": {}  # Pas d'info créateur
            },
            {
                "id": "update_2",
                "body": "Oui",
                "created_at": (now + timedelta(seconds=10)).isoformat(),
                "reply_to_id": "update_1",
                "type": "reply",
                "creator": {
                    "id": "456",
                    "email": "anyone@example.com",
                    "name": "Anyone"
                }
            }
        ]
        
        result = service._find_human_reply(
            original_update_id="update_1",
            updates=updates_no_creator,
            since=now - timedelta(minutes=1)
        )
        
        # En mode dégradé, devrait accepter la réponse
        assert result is not None
    
    def test_case_insensitive_email_comparison(self, service):
        """Test : La comparaison d'emails est insensible à la casse."""
        now = datetime.now()
        
        updates_mixed_case = [
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
                "type": "reply",
                "creator": {
                    "email": "john@example.com",  # Même email, casse différente
                    "name": "John"
                }
            }
        ]
        
        result = service._find_human_reply(
            original_update_id="update_1",
            updates=updates_mixed_case,
            since=now - timedelta(minutes=1)
        )
        
        # Devrait matcher malgré la différence de casse
        assert result is not None
        assert result["id"] == "update_2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

