"""Tests unitaires pour la chaîne implementation_plan_chain (Étape 1 LangChain)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai.chains.implementation_plan_chain import (
    create_implementation_plan_chain,
    generate_implementation_plan,
    extract_plan_metrics,
    ImplementationPlan,
    ImplementationStep,
    RiskLevel
)


class TestImplementationPlanChain:
    """Tests pour la création et utilisation de la chaîne."""
    
    def test_create_chain_anthropic_success(self):
        """Test création chaîne avec Anthropic."""
        with patch('ai.chains.implementation_plan_chain.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.openai_api_key = None
            
            chain = create_implementation_plan_chain(provider="anthropic")
            
            assert chain is not None
            # La chaîne LCEL doit être un objet avec ainvoke
            assert hasattr(chain, 'ainvoke')
    
    def test_create_chain_openai_success(self):
        """Test création chaîne avec OpenAI."""
        with patch('ai.chains.implementation_plan_chain.settings') as mock_settings:
            mock_settings.anthropic_api_key = None
            mock_settings.openai_api_key = "test-key"
            
            chain = create_implementation_plan_chain(provider="openai")
            
            assert chain is not None
            assert hasattr(chain, 'ainvoke')
    
    def test_create_chain_invalid_provider(self):
        """Test création chaîne avec provider invalide."""
        with pytest.raises(ValueError, match="Provider non supporté"):
            create_implementation_plan_chain(provider="invalid-provider")
    
    def test_create_chain_missing_api_key(self):
        """Test création chaîne sans clé API."""
        with patch('ai.chains.implementation_plan_chain.settings') as mock_settings:
            mock_settings.anthropic_api_key = None
            mock_settings.openai_api_key = None
            
            with pytest.raises(Exception, match="API_KEY manquante"):
                create_implementation_plan_chain(provider="anthropic")


class TestImplementationPlanModel:
    """Tests pour les modèles Pydantic."""
    
    def test_implementation_step_validation(self):
        """Test validation d'une étape d'implémentation."""
        step = ImplementationStep(
            step_number=1,
            title="Créer modèle User",
            description="Créer le modèle Pydantic User",
            files_to_modify=["models/user.py"],
            dependencies=["pydantic"],
            estimated_complexity=3,
            risk_level=RiskLevel.LOW,
            validation_criteria=["Modèle valide", "Tests passent"]
        )
        
        assert step.step_number == 1
        assert step.title == "Créer modèle User"
        assert step.estimated_complexity == 3
        assert step.risk_level == RiskLevel.LOW
        assert len(step.files_to_modify) == 1
        assert len(step.validation_criteria) == 2
    
    def test_implementation_step_complexity_bounds(self):
        """Test validation des bornes de complexité."""
        # Complexité valide
        step_valid = ImplementationStep(
            step_number=1,
            title="Test",
            description="Test",
            estimated_complexity=5
        )
        assert step_valid.estimated_complexity == 5
        
        # Complexité invalide (< 1)
        with pytest.raises(ValueError):
            ImplementationStep(
                step_number=1,
                title="Test",
                description="Test",
                estimated_complexity=0
            )
        
        # Complexité invalide (> 10)
        with pytest.raises(ValueError):
            ImplementationStep(
                step_number=1,
                title="Test",
                description="Test",
                estimated_complexity=11
            )
    
    def test_implementation_plan_validation(self):
        """Test validation d'un plan complet."""
        step1 = ImplementationStep(
            step_number=1,
            title="Étape 1",
            description="Description 1",
            estimated_complexity=3,
            risk_level=RiskLevel.LOW
        )
        
        step2 = ImplementationStep(
            step_number=2,
            title="Étape 2",
            description="Description 2",
            estimated_complexity=5,
            risk_level=RiskLevel.MEDIUM
        )
        
        plan = ImplementationPlan(
            task_summary="Créer API REST",
            architecture_approach="FastAPI + PostgreSQL",
            steps=[step1, step2],
            total_estimated_complexity=8,
            overall_risk_assessment="Risque modéré",
            recommended_testing_strategy="Tests unitaires + intégration"
        )
        
        assert len(plan.steps) == 2
        assert plan.total_estimated_complexity == 8
        assert plan.steps[0].title == "Étape 1"
        assert plan.steps[1].risk_level == RiskLevel.MEDIUM
    
    def test_implementation_plan_requires_at_least_one_step(self):
        """Test qu'un plan nécessite au moins une étape."""
        with pytest.raises(ValueError):
            ImplementationPlan(
                task_summary="Test",
                architecture_approach="Test",
                steps=[],  # Liste vide
                total_estimated_complexity=0,
                overall_risk_assessment="Test",
                recommended_testing_strategy="Test"
            )


class TestPlanMetrics:
    """Tests pour l'extraction de métriques."""
    
    def test_extract_metrics_simple_plan(self):
        """Test extraction métriques d'un plan simple."""
        step1 = ImplementationStep(
            step_number=1,
            title="Étape 1",
            description="Description",
            files_to_modify=["file1.py", "file2.py"],
            estimated_complexity=3,
            risk_level=RiskLevel.LOW
        )
        
        step2 = ImplementationStep(
            step_number=2,
            title="Étape 2",
            description="Description",
            files_to_modify=["file3.py"],
            estimated_complexity=7,
            risk_level=RiskLevel.HIGH
        )
        
        plan = ImplementationPlan(
            task_summary="Test",
            architecture_approach="Test",
            steps=[step1, step2],
            total_estimated_complexity=10,
            overall_risk_assessment="Test",
            recommended_testing_strategy="Test",
            potential_blockers=["Blocker 1", "Blocker 2"]
        )
        
        metrics = extract_plan_metrics(plan)
        
        assert metrics["total_steps"] == 2
        assert metrics["total_complexity"] == 10
        assert metrics["average_complexity"] == 5.0
        assert metrics["high_risk_steps_count"] == 1
        assert metrics["high_risk_steps_percentage"] == 50.0
        assert metrics["total_files_to_modify"] == 3  # 3 fichiers uniques
        assert metrics["total_blockers"] == 2
        assert not metrics["has_critical_risks"]
    
    def test_extract_metrics_critical_risk(self):
        """Test détection de risques critiques."""
        step = ImplementationStep(
            step_number=1,
            title="Étape critique",
            description="Description",
            estimated_complexity=9,
            risk_level=RiskLevel.CRITICAL
        )
        
        plan = ImplementationPlan(
            task_summary="Test",
            architecture_approach="Test",
            steps=[step],
            total_estimated_complexity=9,
            overall_risk_assessment="Critique",
            recommended_testing_strategy="Test"
        )
        
        metrics = extract_plan_metrics(plan)
        
        assert metrics["has_critical_risks"] is True
        assert metrics["high_risk_steps_count"] == 1


@pytest.mark.asyncio
class TestGenerateImplementationPlan:
    """Tests pour la génération de plans (mocks)."""
    
    async def test_generate_plan_success(self):
        """Test génération réussie d'un plan."""
        # Créer un plan mock
        mock_step = ImplementationStep(
            step_number=1,
            title="Créer API",
            description="Créer endpoint REST",
            estimated_complexity=5,
            risk_level=RiskLevel.MEDIUM
        )
        
        mock_plan = ImplementationPlan(
            task_summary="API REST pour utilisateurs",
            architecture_approach="FastAPI",
            steps=[mock_step, mock_step],
            total_estimated_complexity=10,
            overall_risk_assessment="Modéré",
            recommended_testing_strategy="Tests unitaires"
        )
        
        # Mock la chaîne
        with patch('ai.chains.implementation_plan_chain.create_implementation_plan_chain') as mock_create:
            mock_chain = AsyncMock()
            mock_chain.ainvoke = AsyncMock(return_value=mock_plan)
            mock_create.return_value = mock_chain
            
            # Appeler la fonction
            result = await generate_implementation_plan(
                task_title="Créer API utilisateurs",
                task_description="Endpoints CRUD pour utilisateurs",
                task_type="feature",
                provider="anthropic",
                fallback_to_openai=False
            )
            
            # Vérifications
            assert result is not None
            assert isinstance(result, ImplementationPlan)
            assert len(result.steps) >= 1
            assert result.total_estimated_complexity > 0
    
    async def test_generate_plan_with_fallback(self):
        """Test génération avec fallback vers OpenAI."""
        mock_step = ImplementationStep(
            step_number=1,
            title="Test",
            description="Test",
            estimated_complexity=3,
            risk_level=RiskLevel.LOW
        )
        
        mock_plan = ImplementationPlan(
            task_summary="Test",
            architecture_approach="Test",
            steps=[mock_step],
            total_estimated_complexity=3,
            overall_risk_assessment="Low",
            recommended_testing_strategy="Unit tests"
        )
        
        with patch('ai.chains.implementation_plan_chain.create_implementation_plan_chain') as mock_create:
            # Premier appel (Anthropic) échoue
            mock_chain_fail = AsyncMock()
            mock_chain_fail.ainvoke = AsyncMock(side_effect=Exception("Anthropic error"))
            
            # Second appel (OpenAI) réussit
            mock_chain_success = AsyncMock()
            mock_chain_success.ainvoke = AsyncMock(return_value=mock_plan)
            
            # Configurer le mock pour retourner les deux chaînes
            mock_create.side_effect = [mock_chain_fail, mock_chain_success]
            
            # Appeler avec fallback
            result = await generate_implementation_plan(
                task_title="Test",
                task_description="Test",
                provider="anthropic",
                fallback_to_openai=True
            )
            
            # Vérifier que le fallback a fonctionné
            assert result is not None
            assert isinstance(result, ImplementationPlan)
            assert mock_create.call_count == 2  # Anthropic puis OpenAI
    
    async def test_generate_plan_both_providers_fail(self):
        """Test échec de tous les providers."""
        with patch('ai.chains.implementation_plan_chain.create_implementation_plan_chain') as mock_create:
            mock_chain = AsyncMock()
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("Provider error"))
            mock_create.return_value = mock_chain
            
            with pytest.raises(Exception, match="Tous les providers ont échoué"):
                await generate_implementation_plan(
                    task_title="Test",
                    task_description="Test",
                    provider="anthropic",
                    fallback_to_openai=True
                )


class TestPlanTextConversion:
    """Tests pour la conversion de plan structuré en texte."""
    
    def test_convert_structured_plan_to_text(self):
        """Test conversion d'un plan structuré en texte lisible."""
        from nodes.implement_node import _convert_structured_plan_to_text
        
        step = ImplementationStep(
            step_number=1,
            title="Créer modèle",
            description="Créer le modèle User",
            files_to_modify=["models/user.py"],
            dependencies=["pydantic"],
            estimated_complexity=3,
            risk_level=RiskLevel.LOW,
            risk_mitigation="Tests unitaires",
            validation_criteria=["Modèle valide", "Tests OK"]
        )
        
        plan = ImplementationPlan(
            task_summary="API REST",
            architecture_approach="FastAPI + PostgreSQL",
            steps=[step],
            total_estimated_complexity=3,
            overall_risk_assessment="Faible",
            recommended_testing_strategy="Tests unitaires",
            potential_blockers=["Schéma DB"]
        )
        
        text = _convert_structured_plan_to_text(plan)
        
        # Vérifications du contenu
        assert "PLAN D'IMPLÉMENTATION STRUCTURÉ" in text
        assert "API REST" in text
        assert "FastAPI + PostgreSQL" in text
        assert "Créer modèle" in text
        assert "models/user.py" in text
        assert "pydantic" in text
        assert "Complexité: 3/10" in text
        assert "Risque: LOW" in text
        assert "Tests unitaires" in text
        assert "Schéma DB" in text
        assert "Bloqueurs potentiels" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

