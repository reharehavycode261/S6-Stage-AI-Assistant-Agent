# -*- coding: utf-8 -*-
"""
Module d'évaluation de l'agent IA.

Ce module fournit un système complet d'évaluation basé sur des Golden Datasets
et un LLM as Judge pour vérifier la fiabilité de l'agent.
"""

from .golden_dataset_manager import GoldenDatasetManager
from .llm_judge_service import LLMJudgeService
# NOTE: agent_evaluation_service a été renommé en agent_evaluation_service_OLD_DEPRECATED
# Il est incompatible avec la nouvelle structure simplifiée du Golden Dataset
# from .agent_evaluation_service import AgentEvaluationService

__all__ = [
    "GoldenDatasetManager",
    "LLMJudgeService",
]

