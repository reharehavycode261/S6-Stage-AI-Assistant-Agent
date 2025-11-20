"""
Modèles Pydantic pour le système d'évaluation de l'agent IA.

Architecture:
    - GoldenDatasetItem: Un test individuel (input + output attendu)
    - GoldenDataset: Collection de tests
    - EvaluationResult: Résultat d'un test
    - EvaluationReport: Rapport global d'évaluation
"""

from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class GoldenDatasetItem(BaseModel):
    """
    Un item du Golden Dataset - Version simplifiée.
    
    Structure simplifiée pour l'évaluation:
    - input_reference: La question/commande de test
    - output_reference: La réponse attendue ou instruction d'évaluation pour le LLM-as-judge
    """
    input_reference: str = Field(
        ..., 
        description="Question ou commande de test à envoyer au système"
    )
    
    output_reference: str = Field(
        ..., 
        description="Réponse parfaite attendue ou instruction d'évaluation pour le LLM-as-judge"
    )


class GoldenDataset(BaseModel):
    """
    Collection de tests - Version simplifiée.
    
    Contient uniquement une liste d'items avec input_reference et output_reference.
    """
    items: List[GoldenDatasetItem] = Field(
        default_factory=list,
        description="Liste des tests (input_reference + output_reference)"
    )
    
    @property
    def total_items(self) -> int:
        """Nombre total de tests dans le dataset."""
        return len(self.items)


class EvaluationResult(BaseModel):
    """
    Résultat de l'évaluation d'un test individuel - Version simplifiée.
    """
    input_reference: str = Field(..., description="Input de test")
    output_reference: str = Field(..., description="Output attendu de référence")
    agent_output: str = Field(..., description="Output généré par l'agent")
    
    score: float = Field(..., ge=0, le=100, description="Score /100 attribué par le LLM Judge")
    reasoning: str = Field(..., description="Raisonnement du LLM Judge")
    
    passed: bool = Field(..., description="Test réussi (score >= seuil)")
    threshold: float = Field(default=70.0, description="Seuil de réussite utilisé")
    
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    evaluation_duration_seconds: Optional[float] = Field(None)
    error: Optional[str] = Field(None, description="Erreur si échec de l'évaluation")


class EvaluationReport(BaseModel):
    """
    Rapport global d'une évaluation complète - Version simplifiée.
    """
    results: List[EvaluationResult] = Field(
        default_factory=list,
        description="Résultats individuels"
    )
    
    total_tests: int = Field(0, description="Nombre total de tests")
    tests_passed: int = Field(0, description="Nombre de tests réussis")
    tests_failed: int = Field(0, description="Nombre de tests échoués")
    average_score: float = Field(0.0, description="Score moyen /100")
    
    evaluation_started_at: datetime = Field(default_factory=datetime.utcnow)
    evaluation_completed_at: Optional[datetime] = Field(None)
    
    def compute_statistics(self):
        """Calcule les statistiques du rapport."""
        self.total_tests = len(self.results)
        
        if self.total_tests == 0:
            return
        
        self.tests_passed = sum(1 for r in self.results if r.passed)
        self.tests_failed = self.total_tests - self.tests_passed
        
        total_score = sum(r.score for r in self.results)
        self.average_score = round(total_score / self.total_tests, 2)


class AgentEvaluationConfig(BaseModel):
    """
    Configuration pour l'évaluation de l'agent - Version simplifiée.
    """
    pass_threshold: float = Field(
        default=70.0,
        ge=0,
        le=100,
        description="Score minimum pour considérer un test comme réussi"
    )
    
    judge_provider: Literal["anthropic", "openai"] = Field(
        default="anthropic",
        description="Provider LLM pour le juge"
    )
    
    judge_model: Optional[str] = Field(
        None,
        description="Modèle spécifique pour le juge"
    )

