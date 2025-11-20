"""
Module des collecteurs d'informations GitHub.

Chaque collecteur est responsable d'un type spécifique d'informations.
"""

from services.github.collectors.repository_collector import RepositoryCollector
from services.github.collectors.pullrequest_collector import PullRequestCollector
from services.github.collectors.issue_collector import IssueCollector
from services.github.collectors.commit_collector import CommitCollector, BranchCollector
from services.github.collectors.release_collector import ReleaseCollector, TagCollector
from services.github.collectors.contributor_collector import ContributorCollector, CollaboratorCollector
from services.github.collectors.metadata_collector import (
    LabelCollector,
    MilestoneCollector,
    WorkflowCollector,
    SecurityCollector
)

__all__ = [
    "RepositoryCollector",
    "PullRequestCollector",
    "IssueCollector",
    "CommitCollector",
    "BranchCollector",
    "ReleaseCollector",
    "TagCollector",
    "ContributorCollector",
    "CollaboratorCollector",
    "LabelCollector",
    "MilestoneCollector",
    "WorkflowCollector",
    "SecurityCollector"
]

