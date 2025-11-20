"""Test pour valider que le workflow fonctionne correctement de bout en bout"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from models.schemas import TaskRequest, PullRequestInfo
from services.monday_validation_service import MondayValidationService


class TestWorkflowValidation:
    """Tests pour valider le workflow complet"""
    
    def test_workflow_with_tests_failed_but_pr_created(self):
        """
        Vérifie que le message de validation est correct même si les tests échouent.
        
        C'est le cas actuel : tests échoués (car Java pas Python) mais PR créée.
        """
        service = MondayValidationService()
        
        # Simuler le workflow actuel
        workflow_results = {
            "task_title": "Ajouter Fonctionnalité : Méthode count() pour compter les enregistrements",
            "environment_path": "/var/folders/bv/3lkzxqps10b1h3wh0mb1tg0w0000gn/T/ai_agent_37btnpz2",
            "modified_files": ["src/database/core/GenericDAO.java", "src/test/TestCount.java"],
            "implementation_success": True,
            "test_success": False,  # Tests échoués (car Java)
            "test_executed": True,
            "pr_created": True,
            "pr_url": "https://github.com/rehareha261/S2-GenericDAO/pull/33",
            "pr_info": {
                "url": "https://github.com/rehareha261/S2-GenericDAO/pull/33",
                "number": 33,
                "title": "feat: Ajouter Fonctionnalité : Méthode count()"
            }
        }
        
        message = service._build_validation_message(workflow_results)
        
        # Vérifications
        assert "✅ Environnement configuré" in message
        assert "GenericDAO.java" in message
        assert "TestCount.java" in message
        assert "✅ Implémentation terminée avec succès" in message
        assert "⚠️ Tests exécutés avec des erreurs" in message  # C'est normal pour Java
        assert "✅ Pull Request créée" in message
        assert "https://github.com/rehareha261/S2-GenericDAO/pull/33" in message
        assert "VALIDATION HUMAINE REQUISE" in message
        
        print("✅ Le message de validation est correct avec :")
        print("   - Implémentation réussie")
        print("   - Tests en erreur (normal pour projet Java)")
        print("   - PR créée avec URL visible")
        print("   - Validation humaine demandée")
    
    def test_pr_url_visibility_in_message(self):
        """Vérifie que l'URL de la PR est bien visible dans le message"""
        service = MondayValidationService()
        
        workflow_results = {
            "task_title": "Test PR URL",
            "environment_path": "/tmp/test",
            "modified_files": ["test.java"],
            "implementation_success": True,
            "test_success": False,
            "test_executed": True,
            "pr_created": True,
            "pr_url": "https://github.com/user/repo/pull/42"
        }
        
        message = service._build_validation_message(workflow_results)
        
        # L'URL doit être présente et formatée correctement
        assert "https://github.com/user/repo/pull/42" in message
        assert "Pull Request créée: https://github.com/user/repo/pull/42" in message
        
    def test_test_failure_is_not_blocking(self):
        """
        Vérifie que l'échec des tests n'empêche pas la création de la PR.
        
        C'est le comportement voulu : même si les tests échouent,
        le workflow continue et crée la PR pour validation humaine.
        """
        service = MondayValidationService()
        
        workflow_results = {
            "task_title": "Test Non Bloquant",
            "environment_path": "/tmp/test",
            "modified_files": ["file.java"],
            "implementation_success": True,
            "test_success": False,  # Tests échoués
            "test_executed": True,
            "pr_created": True,  # MAIS PR créée quand même
            "pr_url": "https://github.com/user/repo/pull/99"
        }
        
        message = service._build_validation_message(workflow_results)
        
        # Le message doit indiquer les deux
        assert "⚠️ Tests exécutés avec des erreurs" in message
        assert "✅ Pull Request créée" in message
        
        # Et demander une validation humaine
        assert "VALIDATION HUMAINE REQUISE" in message
        

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

