"""Tests pour le système de déclenchement de workflow depuis des updates Monday.com."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from models.schemas import UpdateIntent, UpdateType, TaskRequest
from services.update_analyzer_service import UpdateAnalyzerService
from services.workflow_trigger_service import WorkflowTriggerService


class TestUpdateAnalyzer:
    """Tests pour l'analyse des updates Monday."""
    
    @pytest.mark.asyncio
    async def test_detect_new_request(self):
        """Test: Détecter une nouvelle demande."""
        analyzer = UpdateAnalyzerService()
        
        # Mock du LLM
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = """{
            "type": "new_request",
            "confidence": 0.92,
            "requires_workflow": true,
            "reasoning": "L'utilisateur demande une nouvelle fonctionnalité",
            "extracted_requirements": {
                "title": "Ajouter export CSV",
                "description": "Bouton d'export CSV sur la page utilisateurs",
                "task_type": "feature",
                "priority": "medium",
                "files_mentioned": ["users.py", "export.py"]
            }
        }"""
        mock_llm.ainvoke.return_value = mock_response
        analyzer.llm = mock_llm
        
        update_text = "Bonjour, j'aimerais ajouter un bouton d'export CSV sur la page des utilisateurs"
        context = {
            "task_title": "Créer dashboard admin",
            "task_status": "completed",
            "original_description": "Dashboard avec liste des utilisateurs"
        }
        
        result = await analyzer.analyze_update_intent(update_text, context)
        
        assert result.type == UpdateType.NEW_REQUEST
        assert result.requires_workflow == True
        assert result.confidence > 0.7
        assert result.extracted_requirements is not None
        assert "export" in result.extracted_requirements['description'].lower()
    
    @pytest.mark.asyncio
    async def test_detect_affirmation(self):
        """Test: Détecter une affirmation (pas de workflow)."""
        analyzer = UpdateAnalyzerService()
        
        # Mock du LLM
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = """{
            "type": "affirmation",
            "confidence": 0.98,
            "requires_workflow": false,
            "reasoning": "Simple remerciement, aucune action requise",
            "extracted_requirements": null
        }"""
        mock_llm.ainvoke.return_value = mock_response
        analyzer.llm = mock_llm
        
        update_text = "Merci beaucoup, ça fonctionne parfaitement !"
        context = {"task_title": "Test", "task_status": "completed", "original_description": "Test"}
        
        result = await analyzer.analyze_update_intent(update_text, context)
        
        assert result.type == UpdateType.AFFIRMATION
        assert result.requires_workflow == False
    
    @pytest.mark.asyncio
    async def test_detect_bug_report(self):
        """Test: Détecter un signalement de bug."""
        analyzer = UpdateAnalyzerService()
        
        # Mock du LLM
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = """{
            "type": "bug_report",
            "confidence": 0.89,
            "requires_workflow": true,
            "reasoning": "Signalement d'un bug nécessitant correction",
            "extracted_requirements": {
                "title": "Corriger bug bouton mobile",
                "description": "Le bouton ne fonctionne plus sur mobile",
                "task_type": "bugfix",
                "priority": "high",
                "files_mentioned": ["button.js"]
            }
        }"""
        mock_llm.ainvoke.return_value = mock_response
        analyzer.llm = mock_llm
        
        update_text = "Il y a un bug, le bouton ne fonctionne plus sur mobile"
        context = {"task_title": "Feature", "task_status": "completed", "original_description": "Feature"}
        
        result = await analyzer.analyze_update_intent(update_text, context)
        
        assert result.type == UpdateType.BUG_REPORT
        assert result.requires_workflow == True
        assert result.extracted_requirements['task_type'] == "bugfix"
    
    @pytest.mark.asyncio
    async def test_detect_question(self):
        """Test: Détecter une simple question."""
        analyzer = UpdateAnalyzerService()
        
        # Mock du LLM
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = """{
            "type": "question",
            "confidence": 0.87,
            "requires_workflow": false,
            "reasoning": "Simple question d'information, pas d'action requise",
            "extracted_requirements": null
        }"""
        mock_llm.ainvoke.return_value = mock_response
        analyzer.llm = mock_llm
        
        update_text = "Comment je peux configurer cette feature ?"
        context = {"task_title": "Feature", "task_status": "completed", "original_description": "Feature"}
        
        result = await analyzer.analyze_update_intent(update_text, context)
        
        assert result.type == UpdateType.QUESTION
        assert result.requires_workflow == False
    
    @pytest.mark.asyncio
    async def test_empty_update_text(self):
        """Test: Gestion d'un texte vide."""
        analyzer = UpdateAnalyzerService()
        
        update_text = ""
        context = {"task_title": "Test", "task_status": "completed", "original_description": "Test"}
        
        result = await analyzer.analyze_update_intent(update_text, context)
        
        assert result.type == UpdateType.AFFIRMATION
        assert result.requires_workflow == False
        assert result.confidence == 1.0
    
    @pytest.mark.asyncio
    async def test_llm_error_fallback(self):
        """Test: Fallback en cas d'erreur LLM."""
        analyzer = UpdateAnalyzerService()
        
        # Mock du LLM qui génère une erreur
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM error")
        analyzer.llm = mock_llm
        
        update_text = "Test error handling"
        context = {"task_title": "Test", "task_status": "completed", "original_description": "Test"}
        
        result = await analyzer.analyze_update_intent(update_text, context)
        
        # En cas d'erreur, ne pas déclencher de workflow par sécurité
        assert result.requires_workflow == False
        assert result.confidence == 0.0
    
    def test_classify_update_type_keyword_based(self):
        """Test: Classification basée sur des mots-clés (sans LLM)."""
        analyzer = UpdateAnalyzerService()
        
        # Affirmation
        assert analyzer.classify_update_type("Merci beaucoup !") == UpdateType.AFFIRMATION
        assert analyzer.classify_update_type("Ok, parfait 👍") == UpdateType.AFFIRMATION
        
        # Question
        assert analyzer.classify_update_type("Comment faire ?") == UpdateType.QUESTION
        assert analyzer.classify_update_type("Why is this happening?") == UpdateType.QUESTION
        
        # Bug report
        assert analyzer.classify_update_type("Il y a un bug dans le code") == UpdateType.BUG_REPORT
        assert analyzer.classify_update_type("Error: ne fonctionne pas") == UpdateType.BUG_REPORT
        
        # New request
        assert analyzer.classify_update_type("Ajouter une nouvelle feature") == UpdateType.NEW_REQUEST
        assert analyzer.classify_update_type("Créer un bouton d'export") == UpdateType.NEW_REQUEST
        
        # Modification
        assert analyzer.classify_update_type("Modifier la couleur du bouton") == UpdateType.MODIFICATION
        assert analyzer.classify_update_type("Change the text here") == UpdateType.MODIFICATION


class TestWorkflowTrigger:
    """Tests pour le déclenchement de workflow."""
    
    @pytest.mark.asyncio
    async def test_create_task_request_from_update(self):
        """Test: Créer un TaskRequest depuis une analyse d'update."""
        trigger_service = WorkflowTriggerService()
        
        original_task = {
            'tasks_id': 1,
            'monday_item_id': 12345,
            'title': 'Tâche originale',
            'description': 'Description originale',
            'repository_url': 'https://github.com/user/repo',
            'internal_status': 'completed',
            'monday_status': 'Done',
            'priority': 'medium',
            'task_type': 'feature'
        }
        
        update_analysis = UpdateIntent(
            type=UpdateType.NEW_REQUEST,
            confidence=0.92,
            requires_workflow=True,
            reasoning="Nouvelle fonctionnalité demandée",
            extracted_requirements={
                'title': 'Ajouter export CSV',
                'description': 'Bouton d\'export CSV',
                'task_type': 'feature',
                'priority': 'high',
                'files_mentioned': ['export.py']
            }
        )
        
        task_request = await trigger_service.create_task_request_from_update(
            original_task, 
            update_analysis
        )
        
        assert task_request is not None
        assert task_request.title == 'Ajouter export CSV'
        assert task_request.task_type == 'feature'
        assert task_request.priority == 'high'
        assert task_request.repository_url == 'https://github.com/user/repo'
        assert 'export.py' in task_request.files_to_modify
    
    def test_determine_priority(self):
        """Test: Détermination de la priorité Celery."""
        trigger_service = WorkflowTriggerService()
        
        # Urgent
        analysis = UpdateIntent(
            type=UpdateType.BUG_REPORT,
            confidence=0.9,
            requires_workflow=True,
            reasoning="Bug critique",
            extracted_requirements={'priority': 'urgent'}
        )
        assert trigger_service._determine_priority(analysis) == 9
        
        # High
        analysis.extracted_requirements = {'priority': 'high'}
        assert trigger_service._determine_priority(analysis) == 7
        
        # Medium
        analysis.extracted_requirements = {'priority': 'medium'}
        assert trigger_service._determine_priority(analysis) == 5
        
        # Low
        analysis.extracted_requirements = {'priority': 'low'}
        assert trigger_service._determine_priority(analysis) == 3
        
        # Default (sans priority)
        analysis.extracted_requirements = {}
        assert trigger_service._determine_priority(analysis) == 5


class TestIntegration:
    """Tests d'intégration du système complet."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_workflow_trigger_from_update(self):
        """Test d'intégration: Workflow complet depuis un update."""
        # Ce test nécessiterait une DB de test et Celery
        # À implémenter avec des fixtures appropriées
        pass
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_webhook_to_workflow_pipeline(self):
        """Test: Pipeline complet webhook → analyse → workflow."""
        # Ce test nécessiterait un environnement de test complet
        # À implémenter avec mocks pour Monday.com, DB et Celery
        pass


# Fixtures pour les tests
@pytest.fixture
def mock_db_persistence():
    """Mock du service de persistence DB."""
    with patch('services.database_persistence_service.db_persistence') as mock:
        mock.pool = MagicMock()
        mock.create_update_trigger = AsyncMock(return_value=1)
        mock.mark_trigger_as_processed = AsyncMock()
        mock.log_application_event = AsyncMock()
        mock._find_task_by_monday_id = AsyncMock(return_value=1)
        yield mock


@pytest.fixture
def mock_celery():
    """Mock de Celery."""
    with patch('services.celery_app.submit_task') as mock:
        mock_task = MagicMock()
        mock_task.id = 'celery_task_123'
        mock.return_value = mock_task
        yield mock


@pytest.fixture
def sample_update_payload():
    """Payload exemple d'un update Monday.com."""
    return {
        "pulseId": 12345,
        "textBody": "Bonjour, pouvez-vous ajouter un bouton d'export CSV ?",
        "updateId": "update_123",
        "userId": 98765
    }


@pytest.fixture
def sample_completed_task():
    """Exemple de tâche terminée."""
    return {
        'tasks_id': 1,
        'monday_item_id': 12345,
        'title': 'Dashboard admin',
        'description': 'Créer un dashboard admin',
        'internal_status': 'completed',
        'monday_status': 'Done',
        'repository_url': 'https://github.com/user/repo',
        'priority': 'medium',
        'task_type': 'feature'
    }


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

