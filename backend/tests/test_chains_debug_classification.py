"""Tests unitaires pour la chaîne debug_error_classification_chain (Phase 3 LangChain)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai.chains.debug_error_classification_chain import (
    create_debug_error_classification_chain,
    classify_debug_errors,
    extract_classification_metrics,
    get_priority_ordered_groups,
    ErrorClassification,
    ErrorGroup,
    ErrorInstance,
    ErrorCategory,
    ErrorPriority,
    FixStrategy
)


class TestDebugErrorClassificationChain:
    """Tests pour la création et utilisation de la chaîne."""
    
    def test_create_chain_anthropic_success(self):
        """Test création chaîne avec Anthropic."""
        with patch('ai.chains.debug_error_classification_chain.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.openai_api_key = None
            
            chain = create_debug_error_classification_chain(provider="anthropic")
            
            assert chain is not None
            assert hasattr(chain, 'ainvoke')
    
    def test_create_chain_openai_success(self):
        """Test création chaîne avec OpenAI."""
        with patch('ai.chains.debug_error_classification_chain.settings') as mock_settings:
            mock_settings.anthropic_api_key = None
            mock_settings.openai_api_key = "test-key"
            
            chain = create_debug_error_classification_chain(provider="openai")
            
            assert chain is not None
            assert hasattr(chain, 'ainvoke')
    
    def test_create_chain_invalid_provider(self):
        """Test création chaîne avec provider invalide."""
        with pytest.raises(ValueError, match="Provider non supporté"):
            create_debug_error_classification_chain(provider="invalid-provider")
    
    def test_create_chain_missing_api_key(self):
        """Test création chaîne sans clé API."""
        with patch('ai.chains.debug_error_classification_chain.settings') as mock_settings:
            mock_settings.anthropic_api_key = None
            mock_settings.openai_api_key = None
            
            with pytest.raises(Exception, match="ANTHROPIC_API_KEY manquante"):
                create_debug_error_classification_chain(provider="anthropic")


class TestErrorClassificationModels:
    """Tests pour les modèles Pydantic."""
    
    def test_error_instance_model(self):
        """Test modèle ErrorInstance."""
        error = ErrorInstance(
            error_message="ImportError: No module named 'fastapi'",
            file_path="api/routes.py",
            line_number=10,
            test_name="test_api_creation"
        )
        
        assert error.error_message == "ImportError: No module named 'fastapi'"
        assert error.file_path == "api/routes.py"
        assert error.line_number == 10
    
    def test_error_group_model(self):
        """Test modèle ErrorGroup."""
        group = ErrorGroup(
            category=ErrorCategory.IMPORT_ERROR,
            group_summary="Imports manquants",
            files_involved=["test.py", "main.py"],
            probable_root_cause="Module non installé",
            priority=ErrorPriority.CRITICAL,
            suggested_fix_strategy=FixStrategy.ADD_IMPORT,
            fix_description="Ajouter import fastapi",
            error_instances=[
                ErrorInstance(
                    error_message="Import error",
                    file_path="test.py",
                    line_number=1
                )
            ],
            estimated_fix_time_minutes=5,
            dependencies=[],
            impact_scope="module"
        )
        
        assert group.category == ErrorCategory.IMPORT_ERROR
        assert group.priority == ErrorPriority.CRITICAL
        assert len(group.error_instances) == 1
        assert group.estimated_fix_time_minutes == 5
    
    def test_error_classification_model_minimal(self):
        """Test modèle ErrorClassification avec données minimales."""
        classification = ErrorClassification(
            total_errors=3,
            groups=[
                ErrorGroup(
                    category=ErrorCategory.SYNTAX_ERROR,
                    group_summary="Syntax errors",
                    files_involved=["test.py"],
                    probable_root_cause="Missing parenthesis",
                    priority=ErrorPriority.HIGH,
                    suggested_fix_strategy=FixStrategy.FIX_SYNTAX,
                    fix_description="Add missing parenthesis",
                    estimated_fix_time_minutes=2,
                    impact_scope="local"
                )
            ],
            reduction_percentage=66.7,
            recommended_fix_order=[0],
            estimated_total_fix_time=2,
            overall_complexity="simple"
        )
        
        assert classification.total_errors == 3
        assert len(classification.groups) == 1
        assert classification.reduction_percentage == 66.7
        assert len(classification.critical_blockers) == 0
    
    def test_error_classification_model_complete(self):
        """Test modèle ErrorClassification avec données complètes."""
        classification = ErrorClassification(
            total_errors=10,
            groups=[
                ErrorGroup(
                    category=ErrorCategory.IMPORT_ERROR,
                    group_summary="Import errors in 3 files",
                    files_involved=["test1.py", "test2.py", "test3.py"],
                    probable_root_cause="Missing dependency",
                    priority=ErrorPriority.CRITICAL,
                    suggested_fix_strategy=FixStrategy.ADD_DEPENDENCY,
                    fix_description="Install missing package",
                    error_instances=[
                        ErrorInstance(error_message="Import error 1", file_path="test1.py"),
                        ErrorInstance(error_message="Import error 2", file_path="test2.py"),
                        ErrorInstance(error_message="Import error 3", file_path="test3.py")
                    ],
                    estimated_fix_time_minutes=5,
                    impact_scope="global"
                ),
                ErrorGroup(
                    category=ErrorCategory.ASSERTION_ERROR,
                    group_summary="Test assertions failing",
                    files_involved=["test_logic.py"],
                    probable_root_cause="Logic error",
                    priority=ErrorPriority.MEDIUM,
                    suggested_fix_strategy=FixStrategy.REFACTOR_LOGIC,
                    fix_description="Fix business logic",
                    estimated_fix_time_minutes=15,
                    dependencies=["0"],  # Dépend du groupe 0
                    impact_scope="module"
                )
            ],
            reduction_percentage=80.0,
            recommended_fix_order=[0, 1],
            critical_blockers=["Missing dependency blocks execution"],
            estimated_total_fix_time=20,
            overall_complexity="moderate"
        )
        
        assert classification.total_errors == 10
        assert len(classification.groups) == 2
        assert classification.reduction_percentage == 80.0
        assert len(classification.critical_blockers) == 1
        assert classification.estimated_total_fix_time == 20


class TestClassifyDebugErrors:
    """Tests pour la fonction de classification."""
    
    @pytest.mark.asyncio
    async def test_classify_errors_success(self):
        """Test classification d'erreurs avec succès."""
        mock_classification = ErrorClassification(
            total_errors=5,
            groups=[
                ErrorGroup(
                    category=ErrorCategory.IMPORT_ERROR,
                    group_summary="Import errors",
                    files_involved=["test.py"],
                    probable_root_cause="Missing import",
                    priority=ErrorPriority.HIGH,
                    suggested_fix_strategy=FixStrategy.ADD_IMPORT,
                    fix_description="Add import statement",
                    estimated_fix_time_minutes=2,
                    impact_scope="local"
                )
            ],
            reduction_percentage=80.0,
            recommended_fix_order=[0],
            estimated_total_fix_time=2,
            overall_complexity="simple"
        )
        
        with patch('ai.chains.debug_error_classification_chain.create_debug_error_classification_chain') as mock_create:
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = mock_classification
            mock_create.return_value = mock_chain
            
            result = await classify_debug_errors(
                test_logs="ImportError: No module named 'test'"
            )
            
            assert result.total_errors == 5
            assert len(result.groups) == 1
            assert result.reduction_percentage == 80.0
    
    @pytest.mark.asyncio
    async def test_classify_errors_with_fallback(self):
        """Test classification avec fallback vers OpenAI."""
        mock_classification = ErrorClassification(
            total_errors=3,
            groups=[
                ErrorGroup(
                    category=ErrorCategory.SYNTAX_ERROR,
                    group_summary="Syntax",
                    files_involved=["test.py"],
                    probable_root_cause="Syntax",
                    priority=ErrorPriority.MEDIUM,
                    suggested_fix_strategy=FixStrategy.FIX_SYNTAX,
                    fix_description="Fix",
                    estimated_fix_time_minutes=1,
                    impact_scope="local"
                )
            ],
            reduction_percentage=66.7,
            recommended_fix_order=[0],
            estimated_total_fix_time=1,
            overall_complexity="simple"
        )
        
        with patch('ai.chains.debug_error_classification_chain.create_debug_error_classification_chain') as mock_create:
            # Premier appel échoue (Anthropic)
            mock_chain_1 = AsyncMock()
            mock_chain_1.ainvoke.side_effect = Exception("API Error")
            
            # Deuxième appel réussit (OpenAI)
            mock_chain_2 = AsyncMock()
            mock_chain_2.ainvoke.return_value = mock_classification
            
            mock_create.side_effect = [mock_chain_1, mock_chain_2]
            
            result = await classify_debug_errors(
                test_logs="Syntax error",
                provider="anthropic",
                fallback_to_openai=True
            )
            
            assert result.total_errors == 3
            assert mock_create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_classify_errors_no_fallback_fails(self):
        """Test que sans fallback, l'erreur est propagée."""
        with patch('ai.chains.debug_error_classification_chain.create_debug_error_classification_chain') as mock_create:
            mock_chain = AsyncMock()
            mock_chain.ainvoke.side_effect = Exception("API Error")
            mock_create.return_value = mock_chain
            
            with pytest.raises(Exception, match="Classification échouée"):
                await classify_debug_errors(
                    test_logs="Error",
                    fallback_to_openai=False
                )


class TestClassificationMetrics:
    """Tests pour l'extraction de métriques."""
    
    def test_extract_metrics_single_group(self):
        """Test extraction de métriques avec un seul groupe."""
        classification = ErrorClassification(
            total_errors=5,
            groups=[
                ErrorGroup(
                    category=ErrorCategory.IMPORT_ERROR,
                    group_summary="Imports",
                    files_involved=["test.py"],
                    probable_root_cause="Missing",
                    priority=ErrorPriority.CRITICAL,
                    suggested_fix_strategy=FixStrategy.ADD_IMPORT,
                    fix_description="Add",
                    error_instances=[
                        ErrorInstance(error_message="Error 1", file_path="test.py"),
                        ErrorInstance(error_message="Error 2", file_path="test.py")
                    ],
                    estimated_fix_time_minutes=5,
                    impact_scope="module"
                )
            ],
            reduction_percentage=80.0,
            recommended_fix_order=[0],
            critical_blockers=["Blocker"],
            estimated_total_fix_time=5,
            overall_complexity="simple"
        )
        
        metrics = extract_classification_metrics(classification)
        
        assert metrics["total_errors"] == 5
        assert metrics["total_groups"] == 1
        assert metrics["total_error_instances"] == 2
        assert metrics["reduction_percentage"] == 80.0
        assert metrics["actions_before"] == 5
        assert metrics["actions_after"] == 1
        assert metrics["critical_blockers_count"] == 1
        assert metrics["has_critical_errors"] is True
    
    def test_extract_metrics_multiple_groups(self):
        """Test extraction de métriques avec plusieurs groupes."""
        classification = ErrorClassification(
            total_errors=10,
            groups=[
                ErrorGroup(
                    category=ErrorCategory.IMPORT_ERROR,
                    group_summary="Imports",
                    files_involved=["test.py"],
                    probable_root_cause="Missing",
                    priority=ErrorPriority.CRITICAL,
                    suggested_fix_strategy=FixStrategy.ADD_IMPORT,
                    fix_description="Add",
                    error_instances=[ErrorInstance(error_message="E1", file_path="test.py")],
                    estimated_fix_time_minutes=5,
                    impact_scope="global"
                ),
                ErrorGroup(
                    category=ErrorCategory.ASSERTION_ERROR,
                    group_summary="Assertions",
                    files_involved=["test2.py"],
                    probable_root_cause="Logic",
                    priority=ErrorPriority.MEDIUM,
                    suggested_fix_strategy=FixStrategy.REFACTOR_LOGIC,
                    fix_description="Refactor",
                    error_instances=[ErrorInstance(error_message="E2", file_path="test2.py")],
                    estimated_fix_time_minutes=10,
                    impact_scope="module"
                )
            ],
            reduction_percentage=80.0,
            recommended_fix_order=[0, 1],
            estimated_total_fix_time=15,
            overall_complexity="moderate"
        )
        
        metrics = extract_classification_metrics(classification)
        
        assert metrics["total_groups"] == 2
        assert metrics["average_fix_time_per_group"] == 7.5
        assert "import_error" in metrics["category_distribution"]
        assert "assertion_error" in metrics["category_distribution"]


class TestPriorityOrdering:
    """Tests pour l'ordonnancement par priorité."""
    
    def test_get_priority_ordered_groups_with_recommendation(self):
        """Test ordonnancement avec ordre recommandé."""
        groups = [
            ErrorGroup(
                category=ErrorCategory.STYLE_ERROR,
                group_summary="Style",
                files_involved=[],
                probable_root_cause="Style",
                priority=ErrorPriority.LOW,
                suggested_fix_strategy=FixStrategy.FIX_SYNTAX,
                fix_description="Fix",
                estimated_fix_time_minutes=1,
                impact_scope="local"
            ),
            ErrorGroup(
                category=ErrorCategory.IMPORT_ERROR,
                group_summary="Import",
                files_involved=[],
                probable_root_cause="Import",
                priority=ErrorPriority.CRITICAL,
                suggested_fix_strategy=FixStrategy.ADD_IMPORT,
                fix_description="Add",
                estimated_fix_time_minutes=2,
                impact_scope="global"
            )
        ]
        
        classification = ErrorClassification(
            total_errors=5,
            groups=groups,
            reduction_percentage=60.0,
            recommended_fix_order=[1, 0],  # Critique d'abord
            estimated_total_fix_time=3,
            overall_complexity="simple"
        )
        
        ordered = get_priority_ordered_groups(classification)
        
        assert len(ordered) == 2
        assert ordered[0].priority == ErrorPriority.CRITICAL
        assert ordered[1].priority == ErrorPriority.LOW
    
    def test_get_priority_ordered_groups_without_recommendation(self):
        """Test ordonnancement sans ordre recommandé (tri par priorité)."""
        groups = [
            ErrorGroup(
                category=ErrorCategory.STYLE_ERROR,
                group_summary="Style",
                files_involved=[],
                probable_root_cause="Style",
                priority=ErrorPriority.LOW,
                suggested_fix_strategy=FixStrategy.FIX_SYNTAX,
                fix_description="Fix",
                estimated_fix_time_minutes=1,
                impact_scope="local"
            ),
            ErrorGroup(
                category=ErrorCategory.IMPORT_ERROR,
                group_summary="Import",
                files_involved=[],
                probable_root_cause="Import",
                priority=ErrorPriority.CRITICAL,
                suggested_fix_strategy=FixStrategy.ADD_IMPORT,
                fix_description="Add",
                estimated_fix_time_minutes=2,
                impact_scope="global"
            )
        ]
        
        classification = ErrorClassification(
            total_errors=5,
            groups=groups,
            reduction_percentage=60.0,
            recommended_fix_order=[],  # Pas d'ordre recommandé
            estimated_total_fix_time=3,
            overall_complexity="simple"
        )
        
        ordered = get_priority_ordered_groups(classification)
        
        assert len(ordered) == 2
        # Doit être trié par priorité décroissante
        assert ordered[0].priority == ErrorPriority.CRITICAL
        assert ordered[1].priority == ErrorPriority.LOW

