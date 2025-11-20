"""Tests pour vérifier l'intégration des updates Monday.com dans la génération de code."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.webhook_service import WebhookService


class TestMondayUpdatesIntegration:
    """Tests pour la récupération et intégration des updates Monday.com."""

    @pytest.fixture
    def webhook_service(self):
        """Crée une instance du WebhookService pour les tests."""
        with patch('services.webhook_service.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                monday_api_token="test_token",
                monday_board_id="12345",
                monday_repository_url_column_id="link"
            )
            service = WebhookService()
            service.monday_tool = MagicMock()
            return service

    @pytest.mark.asyncio
    async def test_updates_are_retrieved_and_added_to_description(self, webhook_service):
        """Test que les updates sont récupérées et ajoutées à la description."""
        
        # Mock des données item Monday.com
        mock_item_data = {
            "success": True,
            "name": "Ajouter méthode count()",
            "column_values": [
                {
                    "id": "status",
                    "text": "Working on it",
                    "value": '{"index": 1}'
                }
            ]
        }
        
        # Mock des updates Monday.com
        mock_updates_result = {
            "success": True,
            "updates": [
                {
                    "id": "1",
                    "body": "La méthode count() doit supporter les conditions WHERE",
                    "creator": {"name": "John Doe", "email": "john@example.com"},
                    "created_at": "2025-10-12T10:00:00Z"
                },
                {
                    "id": "2",
                    "body": "Ajouter aussi un paramètre pour gérer les null values",
                    "creator": {"name": "Jane Smith", "email": "jane@example.com"},
                    "created_at": "2025-10-12T11:00:00Z"
                }
            ]
        }
        
        # Mock des appels API
        webhook_service.monday_tool._get_item_info = AsyncMock(return_value=mock_item_data)
        webhook_service.monday_tool._arun = AsyncMock(return_value=mock_updates_result)
        webhook_service.monday_tool.api_token = "test_token"
        
        # Mock de la fonction enrich_task_with_description_info qui préserve la description
        def mock_enrich_func(task_data, description):
            """Mock qui préserve la description enrichie."""
            enriched = task_data.copy()
            enriched["description"] = description  # ✅ Préserver la description enrichie
            enriched["repository_url"] = "https://github.com/test/repo"
            return enriched
        
        with patch('services.webhook_service.enrich_task_with_description_info', side_effect=mock_enrich_func):
            
            # Données de test
            task_info = {
                "task_id": "5039539867",
                "title": "Ajouter méthode count()",
                "board_id": "12345",
                "status": "Working on it"
            }
            
            # Exécution
            result = await webhook_service._create_task_request(task_info)
        
        # Vérifications
        assert result is not None, "Le résultat ne devrait pas être None"
        assert "description" in result.__dict__, "La description devrait être présente"
        
        description = result.description
        
        # Vérifier que les updates sont dans la description
        assert "--- Commentaires et précisions additionnelles ---" in description, \
            "La section des commentaires devrait être présente"
        assert "[John Doe]" in description, \
            "Le nom du créateur de l'update 1 devrait être présent"
        assert "conditions WHERE" in description, \
            "Le contenu de l'update 1 devrait être présent"
        assert "[Jane Smith]" in description, \
            "Le nom du créateur de l'update 2 devrait être présent"
        assert "null values" in description, \
            "Le contenu de l'update 2 devrait être présent"
        
        # Vérifier que _arun a bien été appelé avec get_item_updates
        webhook_service.monday_tool._arun.assert_called_with(
            action="get_item_updates",
            item_id="5039539867"
        )

    @pytest.mark.asyncio
    async def test_updates_with_html_are_cleaned(self, webhook_service):
        """Test que le HTML dans les updates est nettoyé."""
        
        mock_item_data = {
            "success": True,
            "name": "Test task",
            "column_values": []
        }
        
        # Update avec HTML
        mock_updates_result = {
            "success": True,
            "updates": [
                {
                    "id": "1",
                    "body": "<p>Ajouter <strong>validation</strong> des paramètres</p>",
                    "creator": {"name": "Test User"},
                    "created_at": "2025-10-12T10:00:00Z"
                }
            ]
        }
        
        webhook_service.monday_tool._get_item_info = AsyncMock(return_value=mock_item_data)
        webhook_service.monday_tool._arun = AsyncMock(return_value=mock_updates_result)
        webhook_service.monday_tool.api_token = "test_token"
        
        def mock_enrich_func(task_data, description):
            enriched = task_data.copy()
            enriched["description"] = description
            enriched["repository_url"] = "https://github.com/test/repo"
            return enriched
        
        with patch('services.webhook_service.enrich_task_with_description_info', side_effect=mock_enrich_func):
            
            task_info = {"task_id": "123", "title": "Test task"}
            result = await webhook_service._create_task_request(task_info)
        
        description = result.description
        
        # Vérifier que le HTML a été nettoyé
        assert "<p>" not in description, "Les balises HTML ne devraient pas être présentes"
        assert "<strong>" not in description, "Les balises HTML ne devraient pas être présentes"
        assert "validation" in description, "Le contenu texte devrait être présent"

    @pytest.mark.asyncio
    async def test_empty_updates_dont_break_workflow(self, webhook_service):
        """Test que l'absence d'updates n'empêche pas le workflow."""
        
        mock_item_data = {
            "success": True,
            "name": "Test task",
            "column_values": []
        }
        
        # Pas d'updates
        mock_updates_result = {
            "success": True,
            "updates": []
        }
        
        webhook_service.monday_tool._get_item_info = AsyncMock(return_value=mock_item_data)
        webhook_service.monday_tool._arun = AsyncMock(return_value=mock_updates_result)
        webhook_service.monday_tool.api_token = "test_token"
        
        def mock_enrich_func(task_data, description):
            enriched = task_data.copy()
            enriched["description"] = description
            enriched["repository_url"] = "https://github.com/test/repo"
            return enriched
        
        with patch('services.webhook_service.enrich_task_with_description_info', side_effect=mock_enrich_func):
            task_info = {"task_id": "123", "title": "Test task"}
            result = await webhook_service._create_task_request(task_info)
        
        # Devrait réussir malgré l'absence d'updates
        assert result is not None
        # La description ne devrait PAS contenir de section commentaires
        assert "--- Commentaires et précisions additionnelles ---" not in result.description, \
            "La section des commentaires ne devrait pas être présente sans updates"

    @pytest.mark.asyncio
    async def test_updates_api_error_doesnt_block_workflow(self, webhook_service):
        """Test qu'une erreur API lors de la récupération des updates ne bloque pas le workflow."""
        
        mock_item_data = {
            "success": True,
            "name": "Test task",
            "column_values": []
        }
        
        webhook_service.monday_tool._get_item_info = AsyncMock(return_value=mock_item_data)
        # Simuler une erreur API
        webhook_service.monday_tool._arun = AsyncMock(side_effect=Exception("API Error"))
        webhook_service.monday_tool.api_token = "test_token"
        
        def mock_enrich_func(task_data, description):
            enriched = task_data.copy()
            enriched["description"] = description
            enriched["repository_url"] = "https://github.com/test/repo"
            return enriched
        
        with patch('services.webhook_service.enrich_task_with_description_info', side_effect=mock_enrich_func):
            task_info = {"task_id": "123", "title": "Test task"}
            result = await webhook_service._create_task_request(task_info)
        
        # Le workflow devrait continuer malgré l'erreur
        assert result is not None
        assert "--- Commentaires et précisions additionnelles ---" not in result.description, \
            "Pas de section commentaires en cas d'erreur API"

    @pytest.mark.asyncio
    async def test_short_updates_are_filtered(self, webhook_service):
        """Test que les updates trop courtes (< 15 caractères) sont filtrées."""
        
        mock_item_data = {
            "success": True,
            "name": "Test task",
            "column_values": []
        }
        
        mock_updates_result = {
            "success": True,
            "updates": [
                {
                    "id": "1",
                    "body": "OK",  # Trop court
                    "creator": {"name": "User1"},
                    "created_at": "2025-10-12T10:00:00Z"
                },
                {
                    "id": "2",
                    "body": "Ceci est un commentaire valide avec assez de caractères",
                    "creator": {"name": "User2"},
                    "created_at": "2025-10-12T11:00:00Z"
                },
                {
                    "id": "3",
                    "body": "Yes",  # Trop court
                    "creator": {"name": "User3"},
                    "created_at": "2025-10-12T12:00:00Z"
                }
            ]
        }
        
        webhook_service.monday_tool._get_item_info = AsyncMock(return_value=mock_item_data)
        webhook_service.monday_tool._arun = AsyncMock(return_value=mock_updates_result)
        webhook_service.monday_tool.api_token = "test_token"
        
        def mock_enrich_func(task_data, description):
            enriched = task_data.copy()
            enriched["description"] = description
            enriched["repository_url"] = "https://github.com/test/repo"
            return enriched
        
        with patch('services.webhook_service.enrich_task_with_description_info', side_effect=mock_enrich_func):
            task_info = {"task_id": "123", "title": "Test task"}
            result = await webhook_service._create_task_request(task_info)
        
        description = result.description
        
        # Seule l'update 2 devrait être présente
        assert "OK" not in description, "L'update courte 'OK' ne devrait pas être présente"
        assert "Yes" not in description, "L'update courte 'Yes' ne devrait pas être présente"
        assert "commentaire valide" in description, "L'update longue devrait être présente"
        assert "[User2]" in description, "Le créateur de l'update valide devrait être présent"

    @pytest.mark.asyncio
    async def test_max_10_updates_are_retrieved(self, webhook_service):
        """Test que maximum 10 updates sont récupérées."""
        
        mock_item_data = {
            "success": True,
            "name": "Test task",
            "column_values": []
        }
        
        # Créer 15 updates
        mock_updates_result = {
            "success": True,
            "updates": [
                {
                    "id": str(i),
                    "body": f"Update numéro {i} avec du contenu suffisant",
                    "creator": {"name": f"User{i}"},
                    "created_at": "2025-10-12T10:00:00Z"
                }
                for i in range(15)
            ]
        }
        
        webhook_service.monday_tool._get_item_info = AsyncMock(return_value=mock_item_data)
        webhook_service.monday_tool._arun = AsyncMock(return_value=mock_updates_result)
        webhook_service.monday_tool.api_token = "test_token"
        
        def mock_enrich_func(task_data, description):
            enriched = task_data.copy()
            enriched["description"] = description
            enriched["repository_url"] = "https://github.com/test/repo"
            return enriched
        
        with patch('services.webhook_service.enrich_task_with_description_info', side_effect=mock_enrich_func):
            task_info = {"task_id": "123", "title": "Test task"}
            result = await webhook_service._create_task_request(task_info)
        
        description = result.description
        
        # Vérifier que les 10 premières updates sont présentes
        for i in range(10):
            assert f"Update numéro {i}" in description, \
                f"L'update {i} devrait être présente"
        
        # Vérifier que les updates 10-14 ne sont PAS présentes
        for i in range(10, 15):
            assert f"Update numéro {i}" not in description, \
                f"L'update {i} ne devrait PAS être présente (limite de 10)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

