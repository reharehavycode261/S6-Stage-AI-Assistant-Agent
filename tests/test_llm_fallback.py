"""Tests unitaires pour llm_factory (Phase 4 LangChain)."""

import pytest
from unittest.mock import MagicMock, patch
from ai.llm.llm_factory import (
    get_llm,
    get_llm_with_fallback,
    get_llm_chain,
    get_default_llm_with_fallback,
    LLMConfig,
    LLMFallbackTracker,
    DEFAULT_MODELS
)


class TestLLMConfig:
    """Tests pour la configuration LLM."""
    
    def test_llm_config_creation(self):
        """Test création de configuration LLM."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            temperature=0.1,
            max_tokens=4000
        )
        
        assert config.provider == "anthropic"
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.temperature == 0.1
        assert config.max_tokens == 4000
    
    def test_llm_config_defaults(self):
        """Test valeurs par défaut de la configuration."""
        config = LLMConfig(provider="openai")
        
        assert config.provider == "openai"
        assert config.model is None
        assert config.temperature == 0.1
        assert config.max_tokens == 4000
        assert config.max_retries == 2


class TestGetLLM:
    """Tests pour la création de LLM."""
    
    def test_get_llm_anthropic(self):
        """Test création LLM Anthropic."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            llm = get_llm(provider="anthropic")
            
            assert llm is not None
            assert hasattr(llm, 'invoke')
    
    def test_get_llm_openai(self):
        """Test création LLM OpenAI."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            
            llm = get_llm(provider="openai")
            
            assert llm is not None
            assert hasattr(llm, 'invoke')
    
    def test_get_llm_invalid_provider(self):
        """Test création LLM avec provider invalide."""
        with pytest.raises(ValueError, match="Provider non supporté"):
            get_llm(provider="invalid-provider")
    
    def test_get_llm_missing_api_key_anthropic(self):
        """Test création LLM Anthropic sans clé API."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = None
            
            with pytest.raises(Exception, match="ANTHROPIC_API_KEY manquante"):
                get_llm(provider="anthropic")
    
    def test_get_llm_missing_api_key_openai(self):
        """Test création LLM OpenAI sans clé API."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.openai_api_key = None
            
            with pytest.raises(Exception, match="OPENAI_API_KEY manquante"):
                get_llm(provider="openai")
    
    def test_get_llm_with_custom_model(self):
        """Test création LLM avec modèle personnalisé."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            llm = get_llm(
                provider="anthropic",
                model="claude-3-opus-20240229",
                temperature=0.5,
                max_tokens=2000
            )
            
            assert llm is not None


class TestGetLLMWithFallback:
    """Tests pour la création de LLM avec fallback."""
    
    def test_get_llm_with_fallback_anthropic_to_openai(self):
        """Test fallback Anthropic vers OpenAI."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key-anthropic"
            mock_settings.openai_api_key = "test-key-openai"
            
            llm = get_llm_with_fallback(
                primary_provider="anthropic",
                fallback_providers=["openai"]
            )
            
            assert llm is not None
            assert hasattr(llm, 'invoke')
    
    def test_get_llm_with_fallback_openai_to_anthropic(self):
        """Test fallback OpenAI vers Anthropic."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key-anthropic"
            mock_settings.openai_api_key = "test-key-openai"
            
            llm = get_llm_with_fallback(
                primary_provider="openai",
                fallback_providers=["anthropic"]
            )
            
            assert llm is not None
    
    def test_get_llm_with_fallback_no_fallback_configured(self):
        """Test LLM sans fallback configuré."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            llm = get_llm_with_fallback(
                primary_provider="anthropic",
                fallback_providers=[]
            )
            
            assert llm is not None
    
    def test_get_llm_with_fallback_primary_fails(self):
        """Test que l'erreur est propagée si le primaire échoue."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = None
            
            with pytest.raises(Exception):
                get_llm_with_fallback(
                    primary_provider="anthropic",
                    fallback_providers=["openai"]
                )
    
    def test_get_llm_with_fallback_custom_models(self):
        """Test fallback avec modèles personnalisés."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key-anthropic"
            mock_settings.openai_api_key = "test-key-openai"
            
            llm = get_llm_with_fallback(
                primary_provider="anthropic",
                primary_model="claude-3-opus-20240229",
                fallback_providers=["openai"],
                fallback_models={"openai": "gpt-4-turbo"}
            )
            
            assert llm is not None


class TestGetLLMChain:
    """Tests pour la création de chaîne LLM."""
    
    def test_get_llm_chain_single_provider(self):
        """Test chaîne avec un seul provider."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            llm = get_llm_chain(model_priority=["anthropic"])
            
            assert llm is not None
    
    def test_get_llm_chain_multiple_providers(self):
        """Test chaîne avec plusieurs providers."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key-anthropic"
            mock_settings.openai_api_key = "test-key-openai"
            
            llm = get_llm_chain(
                model_priority=["anthropic", "openai"]
            )
            
            assert llm is not None
    
    def test_get_llm_chain_empty_priority(self):
        """Test chaîne avec liste de priorité vide."""
        with pytest.raises(ValueError, match="model_priority ne peut pas être vide"):
            get_llm_chain(model_priority=[])
    
    def test_get_llm_chain_with_custom_models(self):
        """Test chaîne avec modèles personnalisés."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key-anthropic"
            mock_settings.openai_api_key = "test-key-openai"
            
            llm = get_llm_chain(
                model_priority=["anthropic", "openai"],
                models={
                    "anthropic": "claude-3-opus-20240229",
                    "openai": "gpt-4-turbo"
                }
            )
            
            assert llm is not None


class TestGetDefaultLLMWithFallback:
    """Tests pour la fonction de LLM par défaut."""
    
    def test_get_default_llm_anthropic_primary(self):
        """Test LLM par défaut avec Anthropic comme primaire."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.default_ai_provider = "anthropic"
            mock_settings.anthropic_api_key = "test-key-anthropic"
            mock_settings.openai_api_key = "test-key-openai"
            
            llm = get_default_llm_with_fallback()
            
            assert llm is not None
    
    def test_get_default_llm_openai_primary(self):
        """Test LLM par défaut avec OpenAI comme primaire."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.default_ai_provider = "openai"
            mock_settings.anthropic_api_key = "test-key-anthropic"
            mock_settings.openai_api_key = "test-key-openai"
            
            llm = get_default_llm_with_fallback()
            
            assert llm is not None
    
    def test_get_default_llm_unknown_provider(self):
        """Test LLM par défaut avec provider inconnu (utilise anthropic par défaut)."""
        with patch('ai.llm.llm_factory.settings') as mock_settings:
            mock_settings.default_ai_provider = "unknown"
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.openai_api_key = "test-key-openai"
            
            llm = get_default_llm_with_fallback()
            
            assert llm is not None


class TestLLMFallbackTracker:
    """Tests pour le tracker de fallback."""
    
    def test_tracker_initialization(self):
        """Test initialisation du tracker."""
        tracker = LLMFallbackTracker()
        
        assert tracker.fallback_count == 0
        assert tracker.primary_success_count == 0
        assert tracker.fallback_success_count == 0
        assert tracker.total_failures == 0
        assert len(tracker.provider_stats) == 0
    
    def test_tracker_record_primary_success(self):
        """Test enregistrement d'un succès primaire."""
        tracker = LLMFallbackTracker()
        tracker.record_primary_success("anthropic")
        
        assert tracker.primary_success_count == 1
        assert "anthropic" in tracker.provider_stats
        assert tracker.provider_stats["anthropic"]["success"] == 1
    
    def test_tracker_record_fallback_success(self):
        """Test enregistrement d'un succès de fallback."""
        tracker = LLMFallbackTracker()
        tracker.record_fallback_success("openai")
        
        assert tracker.fallback_count == 1
        assert tracker.fallback_success_count == 1
        assert "openai" in tracker.provider_stats
        assert tracker.provider_stats["openai"]["fallback_uses"] == 1
    
    def test_tracker_record_failure(self):
        """Test enregistrement d'un échec."""
        tracker = LLMFallbackTracker()
        tracker.record_failure("anthropic")
        
        assert tracker.total_failures == 1
        assert "anthropic" in tracker.provider_stats
        assert tracker.provider_stats["anthropic"]["failures"] == 1
    
    def test_tracker_get_metrics(self):
        """Test récupération des métriques."""
        tracker = LLMFallbackTracker()
        tracker.record_primary_success("anthropic")
        tracker.record_primary_success("anthropic")
        tracker.record_fallback_success("openai")
        tracker.record_failure("anthropic")
        
        metrics = tracker.get_metrics()
        
        assert metrics["total_calls"] == 4
        assert metrics["primary_success_count"] == 2
        assert metrics["fallback_count"] == 1
        assert metrics["total_failures"] == 1
        assert metrics["fallback_rate"] == 25.0  # 1/4 * 100
        assert metrics["success_rate"] == 75.0  # 3/4 * 100
    
    def test_tracker_reset(self):
        """Test réinitialisation du tracker."""
        tracker = LLMFallbackTracker()
        tracker.record_primary_success("anthropic")
        tracker.record_fallback_success("openai")
        
        tracker.reset()
        
        assert tracker.fallback_count == 0
        assert tracker.primary_success_count == 0
        assert tracker.fallback_success_count == 0
        assert tracker.total_failures == 0
        assert len(tracker.provider_stats) == 0
    
    def test_tracker_multiple_providers(self):
        """Test tracker avec plusieurs providers."""
        tracker = LLMFallbackTracker()
        tracker.record_primary_success("anthropic")
        tracker.record_primary_success("anthropic")
        tracker.record_fallback_success("openai")
        tracker.record_failure("anthropic")
        
        metrics = tracker.get_metrics()
        
        assert "anthropic" in metrics["provider_stats"]
        assert "openai" in metrics["provider_stats"]
        assert metrics["provider_stats"]["anthropic"]["success"] == 2
        assert metrics["provider_stats"]["anthropic"]["failures"] == 1
        assert metrics["provider_stats"]["openai"]["success"] == 1
        assert metrics["provider_stats"]["openai"]["fallback_uses"] == 1


class TestDefaultModels:
    """Tests pour les modèles par défaut."""
    
    def test_default_models_exist(self):
        """Test que les modèles par défaut sont définis."""
        assert "anthropic" in DEFAULT_MODELS
        assert "openai" in DEFAULT_MODELS
    
    def test_default_models_values(self):
        """Test les valeurs des modèles par défaut."""
        assert DEFAULT_MODELS["anthropic"] == "claude-3-5-sonnet-20241022"
        assert "gpt-4" in DEFAULT_MODELS["openai"]

