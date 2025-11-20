"""
Module de collecte d'informations GitHub orienté objet.

Architecture extensible permettant d'ajouter facilement de nouveaux collecteurs.
"""

from services.github.base_collector import (
    GitHubDataCollector,
    GitHubCollectorConfig
)
from services.github.github_orchestrator import GitHubInformationOrchestrator

__all__ = [
    "GitHubDataCollector",
    "GitHubCollectorConfig",
    "GitHubInformationOrchestrator"
]

