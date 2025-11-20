"""Test d'intégration pour valider les corrections du workflow Monday.com"""

import pytest
import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from models.schemas import TaskRequest, PullRequestInfo
from services.monday_validation_service import MondayValidationService


class TestMondayValidationFix:
    """Tests d'intégration pour valider les corrections du workflow"""
    
    def test_build_validation_message_with_pr_url(self):
        """Vérifie que le message de validation inclut bien l'URL de la PR"""
        
        # Créer un service de validation
        service = MondayValidationService()
        
        # Workflow results avec PR créée
        workflow_results = {
            "task_title": "Test Task",
            "environment_path": "/tmp/test",
            "modified_files": ["file1.py", "file2.py"],
            "implementation_success": True,
            "test_success": True,
            "test_executed": True,
            "pr_created": True,
            "pr_url": "https://github.com/user/repo/pull/123",
            "pr_info": {
                "url": "https://github.com/user/repo/pull/123",
                "number": 123,
                "title": "Test PR"
            }
        }
        
        # Construire le message
        message = service._build_validation_message(workflow_results)
        
        # Vérifier que l'URL de la PR est dans le message
        assert "https://github.com/user/repo/pull/123" in message
        assert "Pull Request créée" in message
        assert "file1.py" in message
        assert "file2.py" in message
        
    def test_build_validation_message_without_pr_url(self):
        """Vérifie le message quand la PR est créée mais sans URL (fallback)"""
        
        service = MondayValidationService()
        
        workflow_results = {
            "task_title": "Test Task No URL",
            "environment_path": "/tmp/test",
            "modified_files": ["file.py"],
            "implementation_success": True,
            "test_success": False,
            "test_executed": True,
            "pr_created": True,
            # Pas de pr_url fournie
        }
        
        message = service._build_validation_message(workflow_results)
        
        # Doit afficher "PR créée" même sans URL
        assert "Pull Request créée" in message
        assert "Tests exécutés avec des erreurs" in message
        
    def test_build_validation_message_pr_not_created(self):
        """Vérifie le message quand la PR n'est pas créée"""
        
        service = MondayValidationService()
        
        workflow_results = {
            "task_title": "Test No PR",
            "environment_path": "/tmp/test",
            "modified_files": [],
            "implementation_success": False,
            "test_success": False,
            "test_executed": False,
            "pr_created": False,
        }
        
        message = service._build_validation_message(workflow_results)
        
        # Doit indiquer que la PR n'est pas créée
        assert "Pull Request non créée" in message or "❌ Pull Request" in message
        assert "Implémentation échouée" in message
        
    def test_taskrequest_with_description_access(self):
        """Vérifie qu'on peut accéder à la description d'un TaskRequest avec getattr"""
        
        task = TaskRequest(
            task_id="test_001",
            title="Test Task",
            description="Une description de test",
            priority="high"
        )
        
        # Utiliser getattr comme dans le code corrigé
        description = getattr(task, "description", "") or ""
        
        assert description == "Une description de test"
        assert isinstance(description, str)
        
    def test_pr_info_object_access(self):
        """Vérifie l'accès aux attributs de PullRequestInfo"""
        from datetime import datetime
        
        pr_info = PullRequestInfo(
            number=456,
            url="https://github.com/test/repo/pull/456",
            title="Test PR",
            branch="feature/test",
            base_branch="main",
            status="open",
            created_at=datetime.now()
        )
        
        # Accès avec getattr (comme dans le code)
        pr_url = getattr(pr_info, "url", "")
        pr_number = getattr(pr_info, "number", 0)
        
        assert pr_url == "https://github.com/test/repo/pull/456"
        assert pr_number == 456
        
    def test_workflow_results_with_pr_info_dict(self):
        """Vérifie la gestion de pr_info quand c'est un dictionnaire"""
        
        service = MondayValidationService()
        
        workflow_results = {
            "task_title": "Test Dict PR Info",
            "environment_path": "/tmp/test",
            "modified_files": ["test.py"],
            "implementation_success": True,
            "test_success": True,
            "test_executed": True,
            "pr_created": True,
            "pr_info": {  # Dictionnaire au lieu d'objet
                "url": "https://github.com/test/repo/pull/789",
                "number": 789
            }
        }
        
        message = service._build_validation_message(workflow_results)
        
        # Doit extraire l'URL du dictionnaire
        assert "https://github.com/test/repo/pull/789" in message
        
    def test_workflow_results_with_pr_info_object(self):
        """Vérifie la gestion de pr_info quand c'est un objet PullRequestInfo"""
        from datetime import datetime
        
        service = MondayValidationService()
        
        pr_info_obj = PullRequestInfo(
            number=999,
            url="https://github.com/test/repo/pull/999",
            title="Object PR",
            branch="feature/object",
            base_branch="main",
            status="open",
            created_at=datetime.now()
        )
        
        workflow_results = {
            "task_title": "Test Object PR Info",
            "environment_path": "/tmp/test",
            "modified_files": ["object_test.py"],
            "implementation_success": True,
            "test_success": True,
            "test_executed": True,
            "pr_created": True,
            "pr_info": pr_info_obj  # Objet au lieu de dictionnaire
        }
        
        message = service._build_validation_message(workflow_results)
        
        # Doit extraire l'URL de l'objet avec getattr
        assert "https://github.com/test/repo/pull/999" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

