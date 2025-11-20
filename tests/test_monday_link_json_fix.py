# -*- coding: utf-8 -*-
"""
Test de validation de la correction JSON pour les colonnes link Monday.com.

Ce test verifie que:
1. Les colonnes link sont correctement formatees en JSON string
2. La conversion dict -> JSON string fonctionne
3. L'erreur GraphQL "Invalid JSON type" est resolue
"""

import pytest
import json
import sys
import os

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import Mock, AsyncMock, patch
from tools.monday_tool import MondayTool


class TestMondayLinkJsonFix:
    """Tests de validation de la correction JSON pour colonnes link."""

    @pytest.fixture
    def monday_tool(self):
        """Crée une instance de MondayTool pour les tests."""
        with patch.dict('os.environ', {
            'MONDAY_API_TOKEN': 'test_token',
            'MONDAY_BOARD_ID': '123456789',
            'MONDAY_STATUS_COLUMN_ID': 'status'
        }):
            tool = MondayTool()
            return tool

    @pytest.mark.asyncio
    async def test_link_column_formatting_simple_url(self, monday_tool):
        """Test: Formatage d'une URL simple en JSON string."""
        
        test_url = "https://github.com/user/repo/pull/26"
        expected_json_obj = {"url": test_url}
        expected_json_string = json.dumps(expected_json_obj)
        
        # Mock de _make_request pour capturer les variables
        captured_variables = {}
        
        async def mock_make_request(query, variables):
            captured_variables.update(variables)
            return {"success": True, "data": {"change_column_value": {"id": "123"}}}
        
        monday_tool._make_request = mock_make_request
        
        # Exécuter la mise à jour de colonne
        result = await monday_tool._update_column_value(
            item_id="5032158919",
            column_id="link_mkwg662v",  # Colonne de type link
            value=test_url
        )
        
        # Vérifications
        assert result["success"] is True
        assert "value" in captured_variables
        
        # ✅ VALIDATION CRITIQUE: La valeur doit être une chaîne JSON
        assert isinstance(captured_variables["value"], str), \
            f"La valeur doit être une chaîne JSON, pas {type(captured_variables['value'])}"
        
        # Vérifier que c'est un JSON valide
        parsed_value = json.loads(captured_variables["value"])
        assert parsed_value == expected_json_obj
        assert parsed_value["url"] == test_url
        
        print(f"✅ Test réussi: URL formatée en JSON string: {captured_variables['value']}")

    @pytest.mark.asyncio
    async def test_link_column_formatting_with_dict(self, monday_tool):
        """Test: Formatage d'un dict avec URL en JSON string."""
        
        test_dict = {
            "url": "https://github.com/user/repo/pull/26",
            "text": "PR #26"
        }
        expected_json_string = json.dumps(test_dict)
        
        captured_variables = {}
        
        async def mock_make_request(query, variables):
            captured_variables.update(variables)
            return {"success": True, "data": {"change_column_value": {"id": "123"}}}
        
        monday_tool._make_request = mock_make_request
        
        # Exécuter la mise à jour
        result = await monday_tool._update_column_value(
            item_id="5032158919",
            column_id="link_mkwg662v",
            value=test_dict
        )
        
        # Vérifications
        assert result["success"] is True
        assert isinstance(captured_variables["value"], str)
        
        parsed_value = json.loads(captured_variables["value"])
        assert parsed_value == test_dict
        
        print(f"✅ Test réussi: Dict formaté en JSON string: {captured_variables['value']}")

    @pytest.mark.asyncio
    async def test_non_link_column_no_json_conversion(self, monday_tool):
        """Test: Les colonnes non-link ne sont pas converties en JSON."""
        
        test_value = "Simple text value"
        
        captured_variables = {}
        
        async def mock_make_request(query, variables):
            captured_variables.update(variables)
            return {"success": True, "data": {"change_column_value": {"id": "123"}}}
        
        monday_tool._make_request = mock_make_request
        
        # Exécuter la mise à jour sur une colonne text normale
        result = await monday_tool._update_column_value(
            item_id="5032158919",
            column_id="text_column",  # Pas une colonne link
            value=test_value
        )
        
        # Vérifications
        assert result["success"] is True
        
        # Pour les colonnes non-link, la valeur reste telle quelle
        assert captured_variables["value"] == test_value
        
        print(f"✅ Test réussi: Colonne non-link conservée telle quelle: {captured_variables['value']}")

    @pytest.mark.asyncio
    async def test_link_column_detection(self, monday_tool):
        """Test: Détection correcte des colonnes de type link."""
        
        link_column_ids = [
            "link_mkwg662v",
            "link_abc123",
            "repository_url",
            "lien_pr",
            "url_column"
        ]
        
        for column_id in link_column_ids:
            captured_variables = {}
            
            async def mock_make_request(query, variables):
                captured_variables.update(variables)
                return {"success": True, "data": {"change_column_value": {"id": "123"}}}
            
            monday_tool._make_request = mock_make_request
            
            result = await monday_tool._update_column_value(
                item_id="5032158919",
                column_id=column_id,
                value="https://example.com"
            )
            
            # Toutes ces colonnes doivent être détectées comme link et convertie en JSON
            assert isinstance(captured_variables["value"], str)
            parsed = json.loads(captured_variables["value"])
            assert "url" in parsed
            
            print(f"✅ Colonne '{column_id}' correctement détectée comme link")

    @pytest.mark.asyncio
    async def test_graphql_variables_format(self, monday_tool):
        """Test: Format des variables GraphQL conforme à Monday.com."""
        
        test_url = "https://github.com/rehareha261/S2-GenericDAO/pull/26"
        
        captured_query = None
        captured_variables = None
        
        async def mock_make_request(query, variables):
            nonlocal captured_query, captured_variables
            captured_query = query
            captured_variables = variables
            return {"success": True, "data": {"change_column_value": {"id": "123"}}}
        
        monday_tool._make_request = mock_make_request
        
        result = await monday_tool._update_column_value(
            item_id="5032158919",
            column_id="link_mkwg662v",
            value=test_url
        )
        
        # Vérifications du format GraphQL
        assert captured_variables is not None
        assert "itemId" in captured_variables
        assert "boardId" in captured_variables
        assert "columnId" in captured_variables
        assert "value" in captured_variables
        
        # ✅ VALIDATION: La valeur doit être une chaîne JSON
        assert isinstance(captured_variables["value"], str)
        
        # Vérifier que c'est un JSON valide
        value_obj = json.loads(captured_variables["value"])
        assert value_obj["url"] == test_url
        
        # Vérifier la mutation GraphQL
        assert "mutation UpdateColumnValue" in captured_query
        assert "$value: JSON!" in captured_query
        
        print(f"✅ Format GraphQL validé:")
        print(f"   - itemId: {captured_variables['itemId']}")
        print(f"   - columnId: {captured_variables['columnId']}")
        print(f"   - value (type): {type(captured_variables['value'])}")
        print(f"   - value (contenu): {captured_variables['value']}")

    @pytest.mark.asyncio
    async def test_real_scenario_from_logs(self, monday_tool):
        """Test: Reproduire le scénario exact des logs Celery."""
        
        # Scénario exact des logs:
        # - Item ID: 5032158919
        # - Column ID: link_mkwg662v
        # - URL: https://github.com/rehareha261/S2-GenericDAO/pull/26
        
        item_id = "5032158919"
        column_id = "link_mkwg662v"
        pr_url = "https://github.com/rehareha261/S2-GenericDAO/pull/26"
        
        captured_variables = {}
        
        async def mock_make_request(query, variables):
            captured_variables.update(variables)
            
            # Simuler la validation Monday.com
            if not isinstance(variables.get("value"), str):
                # C'était l'erreur avant la correction
                return {
                    "success": False,
                    "errors": [{
                        "message": "Variable $value of type JSON! was provided invalid value",
                        "extensions": {
                            "problems": [{"explanation": "Invalid type, expected a JSON string"}]
                        }
                    }]
                }
            
            # Vérifier que c'est un JSON valide
            try:
                json.loads(variables["value"])
                return {"success": True, "data": {"change_column_value": {"id": item_id}}}
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "errors": [{"message": "Invalid JSON format"}]
                }
        
        monday_tool._make_request = mock_make_request
        
        # Exécuter exactement comme dans le workflow
        result = await monday_tool._update_column_value(
            item_id=item_id,
            column_id=column_id,
            value=pr_url
        )
        
        # ✅ VALIDATION: Le résultat doit être un succès (plus d'erreur GraphQL)
        assert result["success"] is True, \
            f"La mise à jour a échoué: {result.get('errors', 'Erreur inconnue')}"
        
        # Vérifier le format de la valeur
        assert isinstance(captured_variables["value"], str)
        value_obj = json.loads(captured_variables["value"])
        assert value_obj["url"] == pr_url
        
        print(f"✅ Scénario réel validé - Plus d'erreur GraphQL!")
        print(f"   Avant: dict {{'url': '...'}} → ❌ Erreur GraphQL")
        print(f"   Après: '{captured_variables['value']}' → ✅ Succès")


def test_json_dumps_behavior():
    """Test: Comportement de json.dumps pour vérification."""
    
    # Test 1: Dict simple
    obj = {"url": "https://example.com"}
    json_str = json.dumps(obj)
    assert isinstance(json_str, str)
    assert json_str == '{"url": "https://example.com"}'
    
    # Test 2: Dict avec text
    obj_with_text = {"url": "https://example.com", "text": "Example"}
    json_str_with_text = json.dumps(obj_with_text)
    assert isinstance(json_str_with_text, str)
    assert '"url"' in json_str_with_text
    assert '"text"' in json_str_with_text
    
    # Test 3: Vérifier que c'est réversible
    parsed = json.loads(json_str)
    assert parsed == obj
    
    print("✅ Comportement json.dumps validé")


if __name__ == "__main__":
    print("🧪 Exécution des tests de validation de la correction JSON...")
    print("=" * 70)
    
    # Test synchrone
    test_json_dumps_behavior()
    
    # Les tests async doivent être exécutés avec pytest
    print("\n💡 Pour exécuter les tests async, utilisez:")
    print("   pytest tests/test_monday_link_json_fix.py -v")

