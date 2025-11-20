"""Modeles de donnees pour l'agent IA."""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, field_validator, field_serializer
from enum import Enum


class TaskType(str, Enum):
    """Types de tâches supportées."""
    FEATURE = "feature"
    BUGFIX = "bugfix" 
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    UI_CHANGE = "ui_change"
    PERFORMANCE = "performance"
    ANALYSIS = "analysis"  


class TaskPriority(str, Enum):
    """Niveaux de priorité des tâches."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskRequest(BaseModel):
    """Requête de tâche pour l'agent IA."""
    task_id: str = Field(..., description="ID unique de la tâche (Monday item ID ou task_db_id)")
    title: str = Field(..., description="Titre de la tâche")
    description: str = Field(..., description="Description détaillée")
    task_type: TaskType = Field(default=TaskType.FEATURE, description="Type de tâche")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Priorité")
    repository_url: Optional[str] = Field(None, description="URL du repository")
    branch_name: Optional[str] = Field(None, description="Nom de la branche")
    base_branch: Optional[str] = Field(None, description="Branche de base (sera résolu intelligemment si None)")
    acceptance_criteria: Optional[str] = Field(None, description="Critères d'acceptation")
    technical_context: Optional[str] = Field(None, description="Contexte technique")
    files_to_modify: Optional[List[str]] = Field(None, description="Fichiers à modifier")
    estimated_complexity: Optional[str] = Field(None, description="Complexité estimée")
    
    monday_item_id: Optional[int] = Field(None, description="ID de l'item Monday.com")
    board_id: Optional[int] = Field(None, description="ID du board Monday.com")
    task_db_id: Optional[int] = Field(None, description="ID de la tâche dans la base de données (tasks_id)")
    
    creator_name: Optional[str] = Field(None, description="Nom du créateur du ticket Monday.com (pour tagging)")
    creator_id: Optional[int] = Field(None, description="ID Monday.com du créateur du ticket")
    
    is_reactivation: bool = Field(default=False, description="True si cette tâche est une réactivation d'une tâche terminée")
    reactivation_context: Optional[str] = Field(None, description="Contexte de la réactivation - texte du commentaire Monday.com qui a déclenché la réactivation")
    reactivation_count: int = Field(default=0, description="Numéro de la réactivation (0 pour premier workflow, 1+ pour réactivations)")
    source_branch: str = Field(default="main", description="Branche source pour le clonage (main pour réactivations)")
    run_id: Optional[int] = Field(None, description="ID du run dans la base de données")
    
    queue_id: Optional[str] = Field(None, description="ID de la queue pour gestion de workflows concurrents")
    
    task_context: Optional[Dict[str, Any]] = Field(None, description="Contexte additionnel de la tâche (user_language, project_language, etc.)")
    
    @field_validator('task_id', mode='before')
    @classmethod
    def convert_task_id_to_str(cls, v):
        """Convertit task_id en string si c'est un int (validation)."""
        return str(v) if v is not None else v
    
    @field_validator('estimated_complexity', mode='before')
    @classmethod
    def convert_complexity_to_str(cls, v):
        """Convertit estimated_complexity en string si c'est un int ou float."""
        if v is None:
            return v
        return str(v)
    
    @field_serializer('task_id')
    def serialize_task_id(self, value: Any) -> str:
        """Sérialise task_id en string (évite les warnings Pydantic)."""
        return str(value) if value is not None else value
    
    @field_serializer('estimated_complexity')
    def serialize_complexity(self, value: Any) -> Optional[str]:
        """Sérialise estimated_complexity en string."""
        return str(value) if value is not None else value
    
    model_config = {
        "ser_json_inf_nan": 'constants',
            "validate_assignment": True  
    }
    
    
class WorkflowStatus(str, Enum):
    """Statuts du workflow."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def add_to_list(left: List[str], right: List[str]) -> List[str]:
    """Fonction de réduction pour fusionner les listes sans doublons."""
    if not left:
        return right
    if not right:
        return left
    result = left.copy()
    for item in right:
        if item not in result:
            result.append(item)
    return result

def merge_results(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Fonction de réduction pour fusionner les dictionnaires de résultats."""
    if not left:
        return right
    if not right:
        return left
    result = left.copy()
    result.update(right)
    return result

class WorkflowStateModel(BaseModel):
    """Modèle Pydantic pour validation de WorkflowState."""
    workflow_id: str = Field(..., description="ID du workflow")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING)
    current_node: Optional[str] = Field(None, description="Nœud actuel")
    completed_nodes: List[str] = Field(default_factory=list)
    task: Optional[TaskRequest] = Field(None, description="Tâche en cours")
    results: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = Field(None, description="Erreur éventuelle")
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)

    @field_validator('workflow_id', mode='before')
    @classmethod
    def convert_workflow_id_to_str(cls, v):
        """Convertit workflow_id en string si c'est un int pour éviter les warnings Pydantic."""
        if v is None:
            return v
        return str(v)
    
    @field_serializer('workflow_id')
    def serialize_workflow_id(self, value: Any) -> str:
        """Sérialise workflow_id en string (évite les warnings Pydantic)."""
        return str(value) if value is not None else value

    model_config = {
        "use_enum_values": True
    }


class MondayColumnValue(BaseModel):
    """Structure d'une valeur de colonne Monday.com."""
    text: Optional[str] = Field(None, description="Valeur textuelle")
    value: Optional[Any] = Field(None, description="Valeur structurée")
    changed_at: Optional[str] = Field(None, description="Timestamp du changement")


# class MondayEvent(BaseModel):
#     """Structure de l'événement Monday.com dans le webhook."""
#     pulseId: str = Field(..., description="ID de l'item Monday.com")  # Corrigé: str au lieu de int
#     boardId: str = Field(..., description="ID du board Monday.com")   # Corrigé: str au lieu de int
#     pulseName: str = Field(..., description="Nom/titre de l'item")
#     columnValues: Dict[str, MondayColumnValue] = Field(default_factory=dict, description="Valeurs des colonnes")
#     previousColumnValues: Optional[Dict[str, MondayColumnValue]] = Field(None, description="Anciennes valeurs")
#     newColumnValues: Optional[Dict[str, MondayColumnValue]] = Field(None, description="Nouvelles valeurs")
#     userId: Optional[int] = Field(None, description="ID de l'utilisateur qui a fait le changement")
#     triggeredAt: Optional[str] = Field(None, description="Timestamp du déclenchement")
class MondayEvent(BaseModel):
    """Structure de l'événement Monday.com dans le webhook."""
    pulseId: int = Field(..., description="ID de l'item Monday.com")  # ← Changé en int
    boardId: int = Field(..., description="ID du board Monday.com")   # ← Changé en int
    pulseName: Optional[str] = Field(None, description="Nom/titre de l'item - optionnel pour create_update")
    columnValues: Dict[str, MondayColumnValue] = Field(default_factory=dict, description="Valeurs des colonnes")
    previousColumnValues: Optional[Dict[str, MondayColumnValue]] = Field(None, description="Anciennes valeurs")
    newColumnValues: Optional[Dict[str, MondayColumnValue]] = Field(None, description="Nouvelles valeurs")
    userId: Optional[int] = Field(None, description="ID de l'utilisateur qui a fait le changement")
    triggeredAt: Optional[str] = Field(None, description="Timestamp du déclenchement")
    
    @field_validator('pulseId', 'boardId', 'userId', mode='before')
    @classmethod
    def convert_monday_ids_to_int(cls, v):
        """Convertit les IDs Monday.com en int si c'est un string."""
        if v is None:
            return v
        if isinstance(v, str):
            return int(v)
        return v

class WebhookPayload(BaseModel):
    """Payload complet reçu du webhook Monday.com avec exemples concrets."""
    
    challenge: Optional[str] = Field(None, description="Challenge pour validation webhook")
    
    event: Optional[MondayEvent] = Field(None, description="Données de l'événement Monday.com")
    
    type: Optional[str] = Field(None, description="Type d'événement (create_pulse, column_value_changed, etc.)")
    
    triggerUuid: Optional[str] = Field(None, description="UUID unique du trigger")
    timestamp: Optional[str] = Field(None, description="Timestamp de l'événement")
    subscriptionId: Optional[str] = Field(None, description="ID de la subscription webhook")
    
    @classmethod
    def example_button_color_change(cls) -> "WebhookPayload":
        """Exemple : Changement de couleur de bouton."""
        return cls(
            event=MondayEvent(
                pulseId="1234567890",
                boardId="987654321",
                pulseName="Changer la couleur du bouton 'S'inscrire' en #4CAF50",
                columnValues={
                    "task_type": MondayColumnValue(text="Feature"),
                    "priority": MondayColumnValue(text="Medium"),
                    "repository_url": MondayColumnValue(text="https://github.com/user/frontend-app"),
                    "branch_name": MondayColumnValue(text="feature/green-signup-button"),
                    "description": MondayColumnValue(
                        text="Le designer demande de changer la couleur du bouton principal de #007bff (bleu) vers #4CAF50 (vert) pour améliorer la visibilité"
                    ),
                    "files_to_modify": MondayColumnValue(text="src/components/Button.css, src/components/SignupButton.tsx")
                },
                previousColumnValues={
                    "status": MondayColumnValue(text="Backlog")
                },
                newColumnValues={
                    "status": MondayColumnValue(text="À faire")
                }
            ),
            type="column_value_changed",
            triggerUuid="webhook-trigger-123",
            timestamp="2024-01-15T10:30:00Z"
        )
    
    @classmethod 
    def example_oauth_feature(cls) -> "WebhookPayload":
        """Exemple : Feature OAuth2 complexe."""
        return cls(
            event=MondayEvent(
                pulseId="2345678901",
                boardId="987654321",
                pulseName="Implémenter authentification OAuth2 avec Google",
                columnValues={
                    "task_type": MondayColumnValue(text="Feature"),
                    "priority": MondayColumnValue(text="High"),
                    "repository_url": MondayColumnValue(text="https://github.com/user/backend-api"),
                    "branch_name": MondayColumnValue(text="feature/oauth2-google"),
                    "description": MondayColumnValue(
                        text="Ajouter l'authentification OAuth2 avec Google dans l'API backend. "
                             "Inclure: 1) Endpoint /auth/google 2) Middleware de validation JWT "
                             "3) Tests d'intégration 4) Documentation API"
                    ),
                    "acceptance_criteria": MondayColumnValue(
                        text="- L'utilisateur peut se connecter avec Google\n"
                             "- JWT valide généré\n" 
                             "- Tests coverage > 90%\n"
                             "- Documentation Swagger mise à jour"
                    ),
                    "estimated_complexity": MondayColumnValue(text="High"),
                    "files_to_modify": MondayColumnValue(
                        text="src/auth/oauth.py, src/middleware/jwt.py, tests/test_oauth.py, docs/api.md"
                    )
                }
            ),
            type="create_pulse",
            triggerUuid="webhook-trigger-456",
            timestamp="2024-01-15T14:45:00Z"
        )
    
    @classmethod
    def example_bug_fix(cls) -> "WebhookPayload":
        """Exemple : Correction de bug."""
        return cls(
            event=MondayEvent(
                pulseId="3456789012", 
                boardId="987654321",
                pulseName="Corriger le bug de validation email",
                columnValues={
                    "task_type": MondayColumnValue(text="Bug"),
                    "priority": MondayColumnValue(text="Urgent"),
                    "repository_url": MondayColumnValue(text="https://github.com/user/frontend-app"),
                    "branch_name": MondayColumnValue(text="bugfix/email-validation"),
                    "description": MondayColumnValue(
                        text="La validation d'email échoue pour les domaines avec des tirets. "
                             "Erreur: 'Invalid email format' pour test-user@sub-domain.com"
                    ),
                    "technical_context": MondayColumnValue(
                        text="Le regex actuel ne prend pas en compte les tirets dans les domaines. "
                             "Localisation: src/utils/validation.js ligne 45"
                    ),
                    "acceptance_criteria": MondayColumnValue(
                        text="- Emails avec tirets dans le domaine acceptés\n"
                             "- Tests unitaires mis à jour\n"
                             "- Pas de régression sur validation existante"
                    )
                }
            ),
            type="create_pulse",
            triggerUuid="webhook-trigger-789",
            timestamp="2024-01-15T16:20:00Z"
        )
    
    def extract_task_info(self) -> Optional[Dict[str, Any]]:
        """Extrait les informations de tâche du payload webhook."""
        if not self.event:
            return None
            
        raw_columns = self.event.columnValues
        
        if isinstance(raw_columns, list):
            columns = {}
            for col in raw_columns:
                if isinstance(col, dict) and "id" in col:
                    columns[col["id"]] = col
        elif isinstance(raw_columns, dict):
            columns = raw_columns
        else:
            columns = {}
        
        def safe_get_column_text(col_id: str, default: str = "") -> str:
            """Extrait le texte d'une colonne de manière sécurisée."""
            if not isinstance(columns, dict):
                return default
            col_data = columns.get(col_id, {})
            if isinstance(col_data, dict):
                return (col_data.get("text") or 
                       col_data.get("value") or 
                       str(col_data.get("display_value", "")) or 
                       default).strip()
            return default
        
        task_info = {
            "task_id": str(self.event.pulseId),  
            "title": self.event.pulseName,
            "description": safe_get_column_text("description"),
            "task_type": safe_get_column_text("task_type", "feature"),
            "priority": safe_get_column_text("priority", "medium"), 
            "repository_url": safe_get_column_text("repository_url"),
            "branch_name": safe_get_column_text("branch_name"),
            "acceptance_criteria": safe_get_column_text("acceptance_criteria"),
            "technical_context": safe_get_column_text("technical_context"),
            "estimated_complexity": safe_get_column_text("estimated_complexity"),
        }
        
        files_text = safe_get_column_text("files_to_modify")
        if files_text:
            task_info["files_to_modify"] = [f.strip() for f in files_text.split(",")]
        
        return task_info

class ErrorResponse(BaseModel):
    """Réponse d'erreur standardisée."""
    error: str = Field(..., description="Message d'erreur")
    details: Optional[str] = Field(None, description="Détails supplémentaires")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskStatusResponse(BaseModel):
    """Réponse de statut de tâche."""
    task_id: str = Field(..., description="ID de la tâche")
    status: WorkflowStatus = Field(..., description="Statut actuel")
    progress: int = Field(default=0, description="Progression en %")
    current_step: Optional[str] = Field(None, description="Étape actuelle")
    estimated_completion: Optional[datetime] = Field(None, description="Completion estimée")
    result_url: Optional[str] = Field(None, description="URL du résultat")
    
    @field_validator('task_id', mode='before')
    @classmethod
    def convert_task_id_to_str(cls, v):
        """Convertit task_id en string si c'est un int."""
        return str(v) if v is not None else v
    
    @field_serializer('task_id')
    def serialize_task_id(self, value: Any) -> str:
        """Sérialise task_id en string (évite les warnings Pydantic)."""
        return str(value) if value is not None else value


class GitOperationResult(BaseModel):
    """Résultat d'une opération Git."""
    success: bool = Field(..., description="Succès de l'opération")
    message: str = Field(..., description="Message de résultat")
    branch: Optional[str] = Field(None, description="Branche concernée")
    commit_hash: Optional[str] = Field(None, description="Hash du commit")
    error: Optional[str] = Field(None, description="Message d'erreur si échec")


class PullRequestInfo(BaseModel):
    """Informations d'une Pull Request."""
    number: int = Field(..., description="Numéro de la PR")
    title: str = Field(..., description="Titre de la PR")
    url: str = Field(..., description="URL de la PR")
    branch: str = Field(..., description="Branche source")
    base_branch: str = Field(..., description="Branche de destination")
    status: str = Field(..., description="Statut de la PR")
    created_at: datetime = Field(..., description="Date de création")


class TestResult(BaseModel):
    """Résultat de tests."""
    success: bool = Field(..., description="Tests réussis")
    test_type: str = Field(..., description="Type de test")
    total_tests: int = Field(default=0, description="Nombre total de tests")
    passed_tests: int = Field(default=0, description="Tests réussis")
    failed_tests: int = Field(default=0, description="Tests échoués")
    coverage_percentage: Optional[float] = Field(None, description="Pourcentage de couverture")
    output: str = Field(default="", description="Sortie des tests")
    error: Optional[str] = Field(None, description="Message d'erreur")


class HumanValidationStatus(str, Enum):
    """Statuts de validation humaine."""
    PENDING = "pending"          
    APPROVED = "approved"        
    REJECTED = "rejected"        
    ABANDONED = "abandoned"      
    EXPIRED = "expired"          
    CANCELLED = "cancelled"      


class HumanValidationRequest(BaseModel):
    """Demande de validation humaine pour le code généré."""
    validation_id: str = Field(..., description="ID unique de la validation")
    workflow_id: str = Field(..., description="ID du workflow parent")
    task_id: str = Field(..., description="ID de la tâche")
    task_title: str = Field(..., description="Titre de la tâche")
    
    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True
    }
    
    @field_validator('validation_id', 'workflow_id', 'task_id', mode='before')
    @classmethod
    def convert_ids_to_str(cls, v):
        """Convertit tous les IDs en string si c'est un int pour éviter les warnings Pydantic."""
        if v is None:
            return v
        return str(v)
    
    @field_serializer('validation_id', 'workflow_id', 'task_id')
    def serialize_ids(self, value: Any) -> str:
        """Sérialise les IDs en string (évite les warnings Pydantic)."""
        return str(value) if value is not None else value
    
    generated_code: Union[Dict[str, str], str] = Field(..., description="Code généré par fichier (JSON string ou dict)")
    
    @field_validator('generated_code', mode='before')
    @classmethod
    def normalize_generated_code(cls, v):
        """
        Normalise generated_code pour accepter dict ou string.
        Si c'est un dict, on le convertit en JSON string pour la DB.
        Si c'est déjà un string, on le garde tel quel.
        """
        if v is None:
            return json.dumps({"summary": "Code généré - voir fichiers modifiés"})
        
        if isinstance(v, dict):
            return json.dumps(v, ensure_ascii=False, indent=2)
        
        if isinstance(v, str):
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                return json.dumps({"summary": v})
        
        return json.dumps({"raw": str(v)})
    
    code_summary: str = Field(..., description="Résumé des modifications")
    files_modified: List[str] = Field(..., description="Liste des fichiers modifiés")
    
    @field_validator('files_modified', mode='before')
    @classmethod
    def normalize_files_modified(cls, v):
        """
        Normalise files_modified pour s'assurer que c'est toujours une liste de strings.
        Gère les cas dict, list, string unique, None.
        """
        if v is None:
            return []
        
        if isinstance(v, list):
            return [str(f) for f in v if f]
        
        if isinstance(v, dict):
            return list(v.keys())
        
        if isinstance(v, str):
            return [v]
        
        return []
    
    original_request: str = Field(..., description="Demande originale")
    implementation_notes: Optional[str] = Field(None, description="Notes d'implémentation")
    
    test_results: Optional[Union[Dict[str, Any], str]] = Field(None, description="Résultats des tests (JSON string ou dict)")
    
    @field_validator('test_results', mode='before')
    @classmethod
    def normalize_test_results(cls, v):
        """
        Normalise test_results pour accepter dict ou string.
        Si c'est un dict, on le convertit en JSON string pour la DB.
        Si c'est déjà un string, on le garde tel quel.
        """
        if v is None:
            return None
        
        if isinstance(v, dict):
            return json.dumps(v, ensure_ascii=False, indent=2)
        
        if isinstance(v, str):
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                return json.dumps({"raw": v})
        
        return json.dumps({"raw": str(v)})
    
    pr_info: Optional[Union[PullRequestInfo, str]] = Field(None, description="Informations de la PR (JSON string ou objet)")
    
    @field_validator('pr_info', mode='before')
    @classmethod
    def normalize_pr_info(cls, v):
        """
        Normalise pr_info pour accepter objet PullRequestInfo ou string.
        Si c'est un objet, on le convertit en JSON string pour la DB.
        Si c'est déjà un string, on le garde tel quel.
        """
        if v is None:
            return None
        
        if hasattr(v, 'model_dump'):
            return json.dumps(v.model_dump(), ensure_ascii=False, indent=2, default=str)
        elif hasattr(v, 'dict'):
            return json.dumps(v.dict(), ensure_ascii=False, indent=2, default=str)
        elif isinstance(v, dict):
            return json.dumps(v, ensure_ascii=False, indent=2, default=str)
        elif isinstance(v, str):
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                return json.dumps({"raw": v})
        
        return json.dumps({"raw": str(v)})
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Date de création")
    expires_at: Optional[datetime] = Field(None, description="Date d'expiration")
    requested_by: Optional[str] = Field(None, description="Demandeur")


class HumanValidationResponse(BaseModel):
    """Réponse de validation humaine."""
    validation_id: str = Field(..., description="ID de la validation")
    status: HumanValidationStatus = Field(..., description="Statut de la validation")
    
    comments: Optional[str] = Field(None, description="Commentaires du validateur")
    suggested_changes: Optional[str] = Field(None, description="Modifications suggérées")
    approval_notes: Optional[str] = Field(None, description="Notes d'approbation")
    
    rejection_count: int = Field(default=0, description="Nombre de rejets (max 3)")
    modification_instructions: Optional[str] = Field(None, description="Instructions de modification pour relancer le workflow")
    should_retry_workflow: bool = Field(default=False, description="Relancer le workflow avec les instructions de modification")
    
    validated_by: Optional[str] = Field(None, description="Validateur")
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Date de validation")
    
    should_merge: bool = Field(default=False, description="Doit merger automatiquement")
    should_continue_workflow: bool = Field(default=True, description="Continuer le workflow")
    
    analysis_confidence: Optional[float] = Field(None, description="Confiance de l'analyse IA (0-1)")
    analysis_method: Optional[str] = Field(None, description="Méthode d'analyse utilisée")
    specific_concerns: Optional[List[str]] = Field(default_factory=list, description="Préoccupations spécifiques détectées")
    suggested_action: Optional[str] = Field(None, description="Action suggérée par l'IA")
    requires_clarification: Optional[bool] = Field(False, description="Si une clarification est requise")
    
    @field_validator('validation_id', mode='before')
    @classmethod
    def convert_validation_id_to_str(cls, v):
        """Convertit validation_id en string si c'est un int."""
        return str(v) if v is not None else v
    
    @field_serializer('validation_id')
    def serialize_validation_id(self, value: Any) -> str:
        """Sérialise validation_id en string (évite les warnings Pydantic)."""
        return str(value) if value is not None else value


class HumanValidationSummary(BaseModel):
    """Résumé d'une validation pour l'interface admin."""
    validation_id: str = Field(..., description="ID de la validation")
    task_title: str = Field(..., description="Titre de la tâche")
    status: HumanValidationStatus = Field(..., description="Statut")
    created_at: datetime = Field(..., description="Date de création")
    expires_at: Optional[datetime] = Field(None, description="Date d'expiration")
    files_count: int = Field(..., description="Nombre de fichiers modifiés")
    pr_url: Optional[str] = Field(None, description="URL de la PR")
    
    # Indicateurs visuels
    is_urgent: bool = Field(default=False, description="Validation urgente")
    has_test_failures: bool = Field(default=False, description="A des échecs de tests")
    
    @field_validator('validation_id', mode='before')
    @classmethod
    def convert_validation_id_to_str(cls, v):
        """Convertit validation_id en string si c'est un int."""
        return str(v) if v is not None else v
    
    @field_serializer('validation_id')
    def serialize_validation_id(self, value: Any) -> str:
        """Sérialise validation_id en string (évite les warnings Pydantic)."""
        return str(value) if value is not None else value


# ==================== NOUVEAUX MODÈLES POUR WORKFLOW DEPUIS UPDATES ====================

class UpdateType(str, Enum):
    """Types d'updates Monday détectés."""
    NEW_REQUEST = "new_request"
    MODIFICATION = "modification"
    BUG_REPORT = "bug_report"
    QUESTION = "question"
    AFFIRMATION = "affirmation"
    VALIDATION_RESPONSE = "validation_response"


class UpdateIntent(BaseModel):
    """Intention détectée dans un update Monday."""
    type: UpdateType
    confidence: float = Field(ge=0.0, le=1.0, description="Confiance du LLM (0-1)")
    requires_workflow: bool
    reasoning: str
    extracted_requirements: Optional[Dict[str, Any]] = None
    
    model_config = {
        "use_enum_values": True
    }


class UpdateAnalysisContext(BaseModel):
    """Contexte pour l'analyse d'un update."""
    task_title: str
    task_status: str
    monday_status: Optional[str] = None
    original_description: str
    task_type: Optional[str] = None
    priority: Optional[str] = None


# ==================== MODÈLE POUR WORKFLOW REACTIVATION ====================

class WorkflowReactivationStatus(str, Enum):
    """Statuts de réactivation de workflow."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowReactivationTrigger(str, Enum):
    """Types de déclencheurs de réactivation."""
    UPDATE = "update"
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class WorkflowReactivation(BaseModel):
    """Modèle pour l'enregistrement des réactivations de workflow."""
    id: Optional[int] = Field(None, description="ID unique de la réactivation")
    workflow_id: int = Field(..., description="ID du workflow/tâche réactivé")
    reactivated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Date de réactivation")
    trigger_type: WorkflowReactivationTrigger = Field(default=WorkflowReactivationTrigger.UPDATE, description="Type de déclencheur")
    update_data: Optional[Dict[str, Any]] = Field(None, description="Données de l'update Monday.com")
    task_id: Optional[str] = Field(None, description="ID de la tâche Celery")
    status: WorkflowReactivationStatus = Field(default=WorkflowReactivationStatus.PENDING, description="Statut de la réactivation")
    error_message: Optional[str] = Field(None, description="Message d'erreur éventuel")
    completed_at: Optional[datetime] = Field(None, description="Date de complétion")
    
    @field_validator('workflow_id', mode='before')
    @classmethod
    def convert_workflow_id_to_int(cls, v):
        """Convertit workflow_id en int si c'est un string."""
        if v is None:
            return v
        return int(v) if isinstance(v, str) else v
    
    @field_validator('task_id', mode='before')
    @classmethod
    def convert_task_id_to_str(cls, v):
        """Convertit task_id en string si c'est un int."""
        return str(v) if v is not None else v
    
    @field_serializer('task_id')
    def serialize_task_id(self, value: Any) -> Optional[str]:
        """Sérialise task_id en string."""
        return str(value) if value is not None else value
    
    model_config = {
        "use_enum_values": True,
        "validate_assignment": True
    }