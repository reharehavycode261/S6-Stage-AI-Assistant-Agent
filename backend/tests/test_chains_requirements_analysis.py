"""Tests unitaires pour la chaîne requirements_analysis_chain (Phase 2 LangChain)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai.chains.requirements_analysis_chain import (
    create_requirements_analysis_chain,
    generate_requirements_analysis,
    extract_analysis_metrics,
    _calculate_quality_score,
    RequirementsAnalysis,
    CandidateFile,
    TaskDependency,
    IdentifiedRisk,
    Ambiguity,
    TaskComplexity,
    RiskLevel,
    FileValidationStatus
)


class TestRequirementsAnalysisChain:
    """Tests pour la création et utilisation de la chaîne."""
    
    def test_create_chain_anthropic_success(self):
        """Test création chaîne avec Anthropic."""
        with patch('ai.chains.requirements_analysis_chain.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.openai_api_key = None
            
            chain = create_requirements_analysis_chain(provider="anthropic")
            
            assert chain is not None
            assert hasattr(chain, 'ainvoke')
    
    def test_create_chain_openai_success(self):
        """Test création chaîne avec OpenAI."""
        with patch('ai.chains.requirements_analysis_chain.settings') as mock_settings:
            mock_settings.anthropic_api_key = None
            mock_settings.openai_api_key = "test-key"
            
            chain = create_requirements_analysis_chain(provider="openai")
            
            assert chain is not None
            assert hasattr(chain, 'ainvoke')
    
    def test_create_chain_invalid_provider(self):
        """Test création chaîne avec provider invalide."""
        with pytest.raises(ValueError, match="Provider non supporté"):
            create_requirements_analysis_chain(provider="invalid-provider")
    
    def test_create_chain_missing_api_key(self):
        """Test création chaîne sans clé API."""
        with patch('ai.chains.requirements_analysis_chain.settings') as mock_settings:
            mock_settings.anthropic_api_key = None
            mock_settings.openai_api_key = None
            
            with pytest.raises(Exception, match="ANTHROPIC_API_KEY manquante"):
                create_requirements_analysis_chain(provider="anthropic")


class TestRequirementsAnalysisModels:
    """Tests pour les modèles Pydantic."""
    
    def test_candidate_file_model(self):
        """Test modèle CandidateFile."""
        file = CandidateFile(
            path="api/routes/users.py",
            action="create",
            reason="Nouvelles routes API"
        )
        
        assert file.path == "api/routes/users.py"
        assert file.action == "create"
        assert file.validation_status == FileValidationStatus.UNCERTAIN
    
    def test_task_dependency_model(self):
        """Test modèle TaskDependency."""
        dep = TaskDependency(
            name="fastapi",
            type="package",
            version=">=0.104.0",
            required=True
        )
        
        assert dep.name == "fastapi"
        assert dep.type == "package"
        assert dep.required is True
    
    def test_identified_risk_model(self):
        """Test modèle IdentifiedRisk."""
        risk = IdentifiedRisk(
            description="Conflit avec code existant",
            level=RiskLevel.HIGH,
            mitigation="Vérifier avant implémentation",
            probability=7
        )
        
        assert risk.description == "Conflit avec code existant"
        assert risk.level == RiskLevel.HIGH
        assert risk.probability == 7
    
    def test_ambiguity_model(self):
        """Test modèle Ambiguity."""
        ambiguity = Ambiguity(
            question="Quel format de date utiliser?",
            impact="Peut affecter l'API",
            suggested_assumption="ISO 8601"
        )
        
        assert ambiguity.question == "Quel format de date utiliser?"
        assert ambiguity.suggested_assumption == "ISO 8601"
    
    def test_requirements_analysis_model_minimal(self):
        """Test modèle RequirementsAnalysis avec données minimales."""
        analysis = RequirementsAnalysis(
            task_summary="Créer une API",
            complexity=TaskComplexity.MODERATE,
            complexity_score=5,
            estimated_duration_minutes=30,
            implementation_approach="API REST avec FastAPI",
            test_strategy="Tests unitaires"
        )
        
        assert analysis.schema_version == 1
        assert analysis.complexity == TaskComplexity.MODERATE
        assert len(analysis.candidate_files) == 0
        assert len(analysis.risks) == 0
        assert analysis.quality_score is None
    
    def test_requirements_analysis_model_complete(self):
        """Test modèle RequirementsAnalysis avec données complètes."""
        analysis = RequirementsAnalysis(
            task_summary="Créer une API utilisateurs",
            complexity=TaskComplexity.COMPLEX,
            complexity_score=7,
            estimated_duration_minutes=60,
            candidate_files=[
                CandidateFile(
                    path="api/routes/users.py",
                    action="create",
                    reason="Routes API",
                    validation_status=FileValidationStatus.VALID
                )
            ],
            dependencies=[
                TaskDependency(
                    name="fastapi",
                    type="package",
                    required=True
                )
            ],
            risks=[
                IdentifiedRisk(
                    description="Performance",
                    level=RiskLevel.MEDIUM,
                    mitigation="Optimiser requêtes",
                    probability=5
                )
            ],
            ambiguities=[
                Ambiguity(
                    question="Format de pagination?",
                    impact="API design"
                )
            ],
            missing_info=["Schéma de base de données"],
            implementation_approach="API REST",
            test_strategy="Tests complets",
            breaking_changes_risk=True,
            requires_external_deps=True,
            quality_score=0.85
        )
        
        assert len(analysis.candidate_files) == 1
        assert len(analysis.dependencies) == 1
        assert len(analysis.risks) == 1
        assert len(analysis.ambiguities) == 1
        assert analysis.breaking_changes_risk is True
        assert analysis.quality_score == 0.85


class TestGenerateRequirementsAnalysis:
    """Tests pour la génération d'analyse de requirements."""
    
    @pytest.mark.asyncio
    async def test_generate_analysis_success(self):
        """Test génération d'analyse avec succès."""
        # Mock de la chaîne
        mock_analysis = RequirementsAnalysis(
            task_summary="Test task",
            complexity=TaskComplexity.SIMPLE,
            complexity_score=3,
            estimated_duration_minutes=20,
            implementation_approach="Simple implementation",
            test_strategy="Unit tests"
        )
        
        with patch('ai.chains.requirements_analysis_chain.create_requirements_analysis_chain') as mock_create:
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = mock_analysis
            mock_create.return_value = mock_chain
            
            result = await generate_requirements_analysis(
                task_title="Test Task",
                task_description="Description",
                validate_files=False
            )
            
            assert result.task_summary == "Test task"
            assert result.complexity == TaskComplexity.SIMPLE
            assert result.quality_score is not None
    
    @pytest.mark.asyncio
    async def test_generate_analysis_with_fallback(self):
        """Test génération avec fallback vers OpenAI."""
        mock_analysis = RequirementsAnalysis(
            task_summary="Test task",
            complexity=TaskComplexity.SIMPLE,
            complexity_score=3,
            estimated_duration_minutes=20,
            implementation_approach="Simple",
            test_strategy="Tests"
        )
        
        with patch('ai.chains.requirements_analysis_chain.create_requirements_analysis_chain') as mock_create:
            # Premier appel échoue (Anthropic)
            mock_chain_1 = AsyncMock()
            mock_chain_1.ainvoke.side_effect = Exception("API Error")
            
            # Deuxième appel réussit (OpenAI)
            mock_chain_2 = AsyncMock()
            mock_chain_2.ainvoke.return_value = mock_analysis
            
            mock_create.side_effect = [mock_chain_1, mock_chain_2]
            
            result = await generate_requirements_analysis(
                task_title="Test Task",
                task_description="Description",
                provider="anthropic",
                fallback_to_openai=True,
                validate_files=False
            )
            
            assert result.task_summary == "Test task"
            assert mock_create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_generate_analysis_no_fallback_fails(self):
        """Test que sans fallback, l'erreur est propagée."""
        with patch('ai.chains.requirements_analysis_chain.create_requirements_analysis_chain') as mock_create:
            mock_chain = AsyncMock()
            mock_chain.ainvoke.side_effect = Exception("API Error")
            mock_create.return_value = mock_chain
            
            with pytest.raises(Exception, match="Génération analyse échouée"):
                await generate_requirements_analysis(
                    task_title="Test Task",
                    task_description="Description",
                    fallback_to_openai=False,
                    validate_files=False
                )


class TestQualityScoreCalculation:
    """Tests pour le calcul du score de qualité."""
    
    def test_quality_score_empty_analysis(self):
        """Test score de qualité pour analyse vide."""
        analysis = RequirementsAnalysis(
            task_summary="Test",
            complexity=TaskComplexity.SIMPLE,
            complexity_score=3,
            estimated_duration_minutes=20,
            implementation_approach="Simple",
            test_strategy="Tests"
        )
        
        score = _calculate_quality_score(analysis)
        
        # Devrait avoir au moins les points de completeness (0.3)
        assert 0.0 <= score <= 1.0
        assert score >= 0.3  # implementation_approach + test_strategy + duration
    
    def test_quality_score_with_files(self):
        """Test score de qualité avec fichiers valides."""
        analysis = RequirementsAnalysis(
            task_summary="Test",
            complexity=TaskComplexity.SIMPLE,
            complexity_score=3,
            estimated_duration_minutes=20,
            candidate_files=[
                CandidateFile(
                    path="test.py",
                    action="create",
                    reason="Test",
                    validation_status=FileValidationStatus.VALID
                )
            ],
            implementation_approach="Simple",
            test_strategy="Tests"
        )
        
        score = _calculate_quality_score(analysis)
        
        assert score > 0.3  # Plus que la baseline grâce aux fichiers
    
    def test_quality_score_complete_analysis(self):
        """Test score de qualité pour analyse complète."""
        analysis = RequirementsAnalysis(
            task_summary="Test",
            complexity=TaskComplexity.COMPLEX,
            complexity_score=7,
            estimated_duration_minutes=60,
            candidate_files=[
                CandidateFile(
                    path="test1.py",
                    action="create",
                    reason="Test",
                    validation_status=FileValidationStatus.VALID
                ),
                CandidateFile(
                    path="test2.py",
                    action="modify",
                    reason="Test",
                    validation_status=FileValidationStatus.VALID
                )
            ],
            dependencies=[
                TaskDependency(name="dep1", type="package", required=True),
                TaskDependency(name="dep2", type="package", required=True)
            ],
            risks=[
                IdentifiedRisk(
                    description="Risk",
                    level=RiskLevel.MEDIUM,
                    mitigation="Mitigate",
                    probability=5
                )
            ],
            implementation_approach="Complex",
            test_strategy="Full tests"
        )
        
        score = _calculate_quality_score(analysis)
        
        assert score >= 0.7  # Devrait être élevé avec tout complet


class TestExtractAnalysisMetrics:
    """Tests pour l'extraction de métriques."""
    
    def test_extract_metrics_basic(self):
        """Test extraction de métriques basiques."""
        analysis = RequirementsAnalysis(
            task_summary="Test",
            complexity=TaskComplexity.MODERATE,
            complexity_score=5,
            estimated_duration_minutes=30,
            implementation_approach="Standard",
            test_strategy="Unit tests",
            quality_score=0.75
        )
        
        metrics = extract_analysis_metrics(analysis)
        
        assert metrics["schema_version"] == 1
        assert metrics["complexity"] == "moderate"
        assert metrics["complexity_score"] == 5
        assert metrics["estimated_duration_minutes"] == 30
        assert metrics["total_files"] == 0
        assert metrics["quality_score"] == 0.75
    
    def test_extract_metrics_with_files_and_risks(self):
        """Test extraction de métriques avec fichiers et risques."""
        analysis = RequirementsAnalysis(
            task_summary="Test",
            complexity=TaskComplexity.COMPLEX,
            complexity_score=7,
            estimated_duration_minutes=60,
            candidate_files=[
                CandidateFile(
                    path="test1.py",
                    action="create",
                    reason="Test",
                    validation_status=FileValidationStatus.VALID
                ),
                CandidateFile(
                    path="test2.py",
                    action="modify",
                    reason="Test",
                    validation_status=FileValidationStatus.NOT_FOUND
                )
            ],
            risks=[
                IdentifiedRisk(
                    description="Low risk",
                    level=RiskLevel.LOW,
                    mitigation="Monitor",
                    probability=3
                ),
                IdentifiedRisk(
                    description="High risk",
                    level=RiskLevel.HIGH,
                    mitigation="Careful implementation",
                    probability=7
                )
            ],
            dependencies=[
                TaskDependency(name="dep1", type="package", required=True)
            ],
            ambiguities=[
                Ambiguity(question="Question?", impact="Impact")
            ],
            missing_info=["Info1", "Info2"],
            implementation_approach="Complex",
            test_strategy="Full",
            breaking_changes_risk=True,
            requires_external_deps=True,
            quality_score=0.85
        )
        
        metrics = extract_analysis_metrics(analysis)
        
        assert metrics["total_files"] == 2
        assert metrics["valid_files"] == 1
        assert metrics["invalid_files"] == 1
        assert metrics["file_coverage"] == 0.5
        assert metrics["total_risks"] == 2
        assert metrics["high_risks"] == 1
        assert metrics["risk_percentage"] == 50.0
        assert metrics["total_dependencies"] == 1
        assert metrics["required_dependencies"] == 1
        assert metrics["total_ambiguities"] == 1
        assert metrics["missing_info_count"] == 2
        assert metrics["breaking_changes_risk"] is True
        assert metrics["requires_external_deps"] is True


class TestAmbiguityDetection:
    """Tests pour la détection d'ambiguïtés."""
    
    @pytest.mark.asyncio
    async def test_analysis_with_ambiguities(self):
        """Test que les ambiguïtés sont bien détectées."""
        mock_analysis = RequirementsAnalysis(
            task_summary="Vague task",
            complexity=TaskComplexity.MODERATE,
            complexity_score=5,
            estimated_duration_minutes=30,
            ambiguities=[
                Ambiguity(
                    question="Format de sortie non spécifié",
                    impact="Peut affecter l'API",
                    suggested_assumption="JSON par défaut"
                )
            ],
            missing_info=["Schéma exact de données"],
            implementation_approach="TBD",
            test_strategy="TBD"
        )
        
        with patch('ai.chains.requirements_analysis_chain.create_requirements_analysis_chain') as mock_create:
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = mock_analysis
            mock_create.return_value = mock_chain
            
            result = await generate_requirements_analysis(
                task_title="Vague Task",
                task_description="Do something with data",
                validate_files=False
            )
            
            assert len(result.ambiguities) > 0
            assert len(result.missing_info) > 0

