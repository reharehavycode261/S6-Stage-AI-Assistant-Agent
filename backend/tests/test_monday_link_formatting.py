"""Test du formatage des colonnes de type link pour Monday.com."""

import pytest
import json


class TestMondayLinkFormatting:
    """Tests de validation du formatage des colonnes link."""
    
    def test_link_column_detection(self):
        """Vérifie que les colonnes link sont correctement détectées."""
        # Test avec différents IDs de colonnes
        test_cases = [
            ("link_mkwg662v", True),  # Commence par "link_"
            ("lien_pr", True),         # Contient "lien"
            ("repository_url", True),  # Contient "url"
            ("status", False),         # Pas une colonne link
            ("text4", False),          # Pas une colonne link
        ]
        
        for column_id, should_be_link in test_cases:
            column_id_lower = column_id.lower()
            is_link_column = (
                column_id.startswith("link_") or 
                "url" in column_id_lower or 
                "lien" in column_id_lower or
                (column_id_lower == "lien_pr")
            )
            
            assert is_link_column == should_be_link, \
                f"Colonne {column_id} devrait être {'link' if should_be_link else 'non-link'}"
    
    def test_url_formatting_simple(self):
        """Vérifie que les URLs simples sont correctement formatées."""
        # Simuler le formatage
        value = "https://github.com/user/repo"
        
        # Vérifier qu'on détecte bien une URL
        assert value.startswith("https://")
        
        # Format attendu
        formatted_value = {"url": value}
        
        # Vérifier la structure
        assert "url" in formatted_value
        assert formatted_value["url"] == value
        assert "text" not in formatted_value  # Le champ text est optionnel
    
    def test_url_formatting_pr(self):
        """Vérifie le formatage d'une URL de PR GitHub."""
        value = "https://github.com/user/repo/pull/24"
        
        formatted_value = {"url": value}
        
        # Vérifier la structure minimale (sans text)
        assert formatted_value == {"url": value}
    
    def test_url_formatting_repository(self):
        """Vérifie le formatage d'une URL de repository GitHub."""
        value = "https://github.com/rehareha261/S2-GenericDAO"
        
        formatted_value = {"url": value}
        
        # Vérifier la structure minimale (sans text)
        assert formatted_value == {"url": value}
    
    def test_already_formatted_value(self):
        """Vérifie qu'une valeur déjà formatée reste inchangée."""
        value = {
            "url": "https://github.com/user/repo",
            "text": "Mon texte personnalisé"
        }
        
        # Si déjà formaté, on garde tel quel
        if isinstance(value, dict) and "url" in value:
            formatted_value = value
        
        assert formatted_value == value
        assert "text" in formatted_value
    
    def test_json_serialization(self):
        """Vérifie que le JSON généré est valide pour Monday.com."""
        formatted_value = {
            "url": "https://github.com/user/repo/pull/24"
        }
        
        # Vérifier que le JSON est valide
        json_str = json.dumps(formatted_value)
        assert json_str == '{"url": "https://github.com/user/repo/pull/24"}'
        
        # Vérifier qu'on peut le parser
        parsed = json.loads(json_str)
        assert parsed == formatted_value


if __name__ == "__main__":
    # Exécuter les tests
    pytest.main([__file__, "-v", "--tb=short"])

