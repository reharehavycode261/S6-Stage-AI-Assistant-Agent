"""Tests unitaires pour la création de l'état du workflow."""

import pytest
from datetime import datetime
from models.schemas import TaskRequest, TaskPriority, WorkflowStatus
from graph.workflow_graph import _create_initial_state_with_recovery


class TestWorkflowStateCreation:
    """Tests pour la création de l'état initial du workflow."""

    def test_create_initial_state_with_all_ids(self):
        """Test de création d'état avec tous les IDs fournis."""
        # Arrange
        task_request = TaskRequest(
            task_id="12345",
            title="Test Task",
            description="Test Description",
            priority=TaskPriority.MEDIUM,
            repository_url="https://github.com/user/repo",
            base_branch="main"
        )
        workflow_id = "workflow_test_123"
        task_db_id = 42
        actual_task_run_id = 25
        uuid_task_run_id = "run_abc123_1234567890"

        # Act
        state = _create_initial_state_with_recovery(
            task_request,
            workflow_id,
            task_db_id,
            actual_task_run_id,
            uuid_task_run_id
        )

        # Assert - Vérifier les IDs critiques
        assert state["db_task_id"] == task_db_id, "db_task_id doit être défini"
        assert state["db_run_id"] == actual_task_run_id, "db_run_id doit être défini"
        assert state["run_id"] == actual_task_run_id, "run_id pour compatibilité"
        assert state["uuid_run_id"] == uuid_task_run_id, "uuid_run_id pour LangSmith"
        
        # Vérifier les autres champs
        assert state["workflow_id"] == workflow_id
        assert state["task"] == task_request
        assert state["status"] == WorkflowStatus.PENDING
        assert state["current_node"] is None
        assert state["completed_nodes"] == []
        assert state["error"] is None
        
        # Vérifier la structure results
        assert "results" in state
        assert "ai_messages" in state["results"]
        assert "error_logs" in state["results"]
        assert "modified_files" in state["results"]
        assert "test_results" in state["results"]
        assert "debug_attempts" in state["results"]
        
        assert isinstance(state["results"]["ai_messages"], list)
        assert isinstance(state["results"]["error_logs"], list)
        assert isinstance(state["results"]["modified_files"], list)
        assert isinstance(state["results"]["test_results"], list)
        assert state["results"]["debug_attempts"] == 0
        
        # Vérifier les timestamps
        assert "started_at" in state
        assert isinstance(state["started_at"], datetime)
        assert state["completed_at"] is None
        
        # Vérifier les champs de récupération
        assert state["node_retry_count"] == {}
        assert state["recovery_mode"] is False
        assert state["checkpoint_data"] == {}

    def test_create_initial_state_with_none_ids(self):
        """Test de création d'état avec des IDs None (workflow standalone)."""
        # Arrange
        task_request = TaskRequest(
            task_id="12345",
            title="Standalone Task",
            description="Task without DB persistence",
            priority=TaskPriority.HIGH
        )
        workflow_id = "workflow_standalone_456"

        # Act
        state = _create_initial_state_with_recovery(
            task_request,
            workflow_id,
            None,  # task_db_id
            None,  # actual_task_run_id
            None   # uuid_task_run_id
        )

        # Assert - Les IDs doivent être None mais l'état doit être valide
        assert state["db_task_id"] is None, "db_task_id peut être None"
        assert state["db_run_id"] is None, "db_run_id peut être None"
        assert state["run_id"] is None, "run_id peut être None"
        assert state["uuid_run_id"] is None, "uuid_run_id peut être None"
        
        # Mais les autres structures doivent être initialisées
        assert "results" in state
        assert isinstance(state["results"]["ai_messages"], list)
        assert isinstance(state["results"]["error_logs"], list)
        assert state["workflow_id"] == workflow_id
        assert state["task"] == task_request

    def test_state_structure_completeness(self):
        """Test que l'état contient tous les champs requis par GraphState."""
        # Arrange
        task_request = TaskRequest(
            task_id="12345",
            title="Complete Test",
            description="Test for complete state structure",
            priority=TaskPriority.LOW
        )
        workflow_id = "workflow_complete_789"

        # Act
        state = _create_initial_state_with_recovery(
            task_request,
            workflow_id,
            10,
            20,
            "run_test_123"
        )

        # Assert - Vérifier tous les champs requis par GraphState
        required_fields = [
            "workflow_id",
            "status",
            "current_node",
            "completed_nodes",
            "task",
            "results",
            "error",
            "started_at",
            "completed_at",
            "langsmith_session",
            "db_task_id",
            "db_run_id"
        ]
        
        for field in required_fields:
            assert field in state, f"Le champ '{field}' doit être présent dans l'état"

    def test_results_structure_initialization(self):
        """Test que la structure results est correctement initialisée."""
        # Arrange
        task_request = TaskRequest(
            task_id="67890",
            title="Results Structure Test",
            description="Test results initialization",
            priority=TaskPriority.MEDIUM
        )

        # Act
        state = _create_initial_state_with_recovery(
            task_request,
            "workflow_results_test",
            15,
            30,
            "run_results_456"
        )

        # Assert - Vérifier que results est une structure correcte
        results = state["results"]
        
        assert isinstance(results, dict)
        assert isinstance(results["ai_messages"], list)
        assert len(results["ai_messages"]) == 0, "ai_messages doit être vide initialement"
        
        assert isinstance(results["error_logs"], list)
        assert len(results["error_logs"]) == 0, "error_logs doit être vide initialement"
        
        assert isinstance(results["modified_files"], list)
        assert len(results["modified_files"]) == 0, "modified_files doit être vide initialement"
        
        assert isinstance(results["test_results"], list)
        assert len(results["test_results"]) == 0, "test_results doit être vide initialement"
        
        assert isinstance(results["debug_attempts"], int)
        assert results["debug_attempts"] == 0, "debug_attempts doit être 0 initialement"

    def test_recovery_mode_fields(self):
        """Test que les champs de mode récupération sont correctement initialisés."""
        # Arrange
        task_request = TaskRequest(
            task_id="recovery_123",
            title="Recovery Test",
            description="Test recovery mode fields",
            priority=TaskPriority.HIGH
        )

        # Act
        state = _create_initial_state_with_recovery(
            task_request,
            "workflow_recovery_001",
            100,
            200,
            "run_recovery_789"
        )

        # Assert
        assert "node_retry_count" in state
        assert isinstance(state["node_retry_count"], dict)
        assert len(state["node_retry_count"]) == 0, "node_retry_count doit être vide initialement"
        
        assert "recovery_mode" in state
        assert state["recovery_mode"] is False, "recovery_mode doit être False initialement"
        
        assert "checkpoint_data" in state
        assert isinstance(state["checkpoint_data"], dict)
        assert len(state["checkpoint_data"]) == 0, "checkpoint_data doit être vide initialement"

    def test_timestamps_initialization(self):
        """Test que les timestamps sont correctement initialisés."""
        # Arrange
        task_request = TaskRequest(
            task_id="time_123",
            title="Timestamp Test",
            description="Test timestamp initialization",
            priority=TaskPriority.MEDIUM
        )

        before_creation = datetime.now()

        # Act
        state = _create_initial_state_with_recovery(
            task_request,
            "workflow_time_001",
            50,
            75,
            "run_time_111"
        )

        after_creation = datetime.now()

        # Assert
        assert "started_at" in state
        assert isinstance(state["started_at"], datetime)
        assert before_creation <= state["started_at"] <= after_creation, \
            "started_at doit être entre avant et après la création"
        
        assert "completed_at" in state
        assert state["completed_at"] is None, "completed_at doit être None initialement"

    def test_backward_compatibility_fields(self):
        """Test que les champs de compatibilité sont présents."""
        # Arrange
        task_request = TaskRequest(
            task_id="compat_456",
            title="Compatibility Test",
            description="Test backward compatibility",
            priority=TaskPriority.LOW
        )
        actual_task_run_id = 99

        # Act
        state = _create_initial_state_with_recovery(
            task_request,
            "workflow_compat_002",
            88,
            actual_task_run_id,
            "run_compat_333"
        )

        # Assert - Vérifier la présence de run_id pour compatibilité
        assert "run_id" in state
        assert state["run_id"] == actual_task_run_id, \
            "run_id doit être égal à actual_task_run_id pour compatibilité"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
