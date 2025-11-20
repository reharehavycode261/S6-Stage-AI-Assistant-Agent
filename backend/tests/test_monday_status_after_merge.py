"""Test de régression pour statut Monday après merge."""
import pytest
from models.state import GraphState
from models.schemas import TaskRequest, WorkflowStatus
from nodes.update_node import _determine_final_status


@pytest.mark.asyncio
async def test_status_done_after_successful_merge():
    """Vérifie que le statut est 'Done' après merge réussi."""
    state = GraphState(
        task=TaskRequest(
            task_id="test_merge_123",
            title="Test merge status",
            task_type="feature",
            priority="normal"
        ),
        status=WorkflowStatus.COMPLETED,
        results={
            "merge_successful": True,
            "merge_commit": "abc123",
            "monday_final_status": "Done"
        }
    )
    
    final_status, success_level = _determine_final_status(state)
    
    assert final_status == "Done", f"Attendu 'Done', reçu '{final_status}'"
    assert success_level == "success"
    print("✅ Test réussi: Statut 'Done' après merge")


@pytest.mark.asyncio
async def test_merge_priority_over_explicit_status():
    """Vérifie que merge_successful a priorité absolue."""
    state = GraphState(
        task=TaskRequest(
            task_id="test_priority_456",
            title="Test priority",
            task_type="feature",
            priority="normal"
        ),
        status=WorkflowStatus.COMPLETED,
        results={
            "merge_successful": True,
            "monday_final_status": "Working on it"  # Conflit intentionnel
        }
    )
    
    final_status, _ = _determine_final_status(state)
    
    assert final_status == "Done", "merge_successful doit avoir priorité"
    print("✅ Test réussi: Priorité de merge_successful")


@pytest.mark.asyncio
async def test_status_without_merge():
    """Vérifie le comportement sans merge."""
    state = GraphState(
        task=TaskRequest(
            task_id="test_no_merge_789",
            title="Test without merge",
            task_type="feature",
            priority="normal"
        ),
        status=WorkflowStatus.COMPLETED,
        results={
            "pr_info": {"pr_url": "https://github.com/test/pr/1"}
        }
    )
    
    final_status, success_level = _determine_final_status(state)
    
    # Sans merge, le statut devrait être "Working on it"
    assert final_status == "Working on it", f"Attendu 'Working on it', reçu '{final_status}'"
    assert success_level == "partial"
    print("✅ Test réussi: Statut 'Working on it' sans merge")


@pytest.mark.asyncio
async def test_merge_successful_false():
    """Vérifie que merge_successful=False ne force pas Done."""
    state = GraphState(
        task=TaskRequest(
            task_id="test_merge_false_101",
            title="Test merge false",
            task_type="feature",
            priority="normal"
        ),
        status=WorkflowStatus.COMPLETED,
        results={
            "merge_successful": False,
            "pr_info": {"pr_url": "https://github.com/test/pr/2"}
        }
    )
    
    final_status, success_level = _determine_final_status(state)
    
    # Avec merge_successful=False, ne devrait pas être Done
    assert final_status != "Done", f"Ne devrait pas être 'Done' avec merge_successful=False"
    print("✅ Test réussi: merge_successful=False ne force pas Done")
