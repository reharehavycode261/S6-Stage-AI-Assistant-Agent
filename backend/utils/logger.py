"""Module de logging structuré avec support Rich et couleurs."""

import logging
import sys
import structlog
from rich.console import Console
from rich.logging import RichHandler
from typing import Any, Dict


def configure_logging(debug: bool = False, log_level: str = "INFO") -> None:
    """
    Configure le système de logging avec structlog et Rich.
    
    Args:
        debug: Mode debug activé
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR)
    """
    # ✅ CORRECTION CRITIQUE: Forcer l'encodage UTF-8 pour tous les outputs
    # Cela permet d'afficher correctement les emojis et caractères spéciaux
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
    # ✅ CORRECTION: Configuration du niveau de log
    # Forcer INFO pour éviter que les événements normaux apparaissent en WARNING
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # ✅ AMÉLIORATION: Configurer le logger root à INFO pour Celery
    # Celery utilise WARNING par défaut, ce qui cause tous les logs normaux à être WARNING
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Configuration de Rich pour les logs colorés avec support UTF-8
    console = Console(
        force_terminal=True,
        # ✅ Forcer l'encoding UTF-8 pour Rich Console
        force_interactive=False,
        force_jupyter=False,
        legacy_windows=False,  # Désactiver le mode legacy Windows
        safe_box=False  # Permettre les caractères Unicode avancés
    )
    
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_level=True,
        show_path=debug,
        markup=True,
        rich_tracebacks=True,
        enable_link_path=False,  # Désactiver les liens pour éviter les problèmes d'encodage
        omit_repeated_times=False
    )
    
    # Configuration du logger standard
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler],
        # ✅ Forcer UTF-8 au niveau du basicConfig
        encoding='utf-8',
        errors='replace'  # Remplacer les caractères non-encodables au lieu de crasher
    )
    
    # Configuration de structlog avec support UTF-8
    structlog.configure(
        processors=[
            # Traitement des métadonnées
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            # ✅ AMÉLIORATION: Ajouter un processeur pour gérer les caractères Unicode
            structlog.processors.UnicodeDecoder(),
            
            # Formatage conditionnel
            structlog.dev.ConsoleRenderer(colors=True) if debug 
            else structlog.processors.JSONRenderer(ensure_ascii=False),  # ✅ Permettre Unicode dans JSON
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Récupère un logger structuré pour un module.
    
    Args:
        name: Nom du module (généralement __name__)
        
    Returns:
        Logger structuré configuré
    """
    # Configurer le logging si pas encore fait
    if not hasattr(get_logger, '_configured'):
        configure_logging()
        get_logger._configured = True
    
    # ✅ CORRECTION: Mapper correctement les niveaux de log JSON
    # Celery affiche tout en WARNING par défaut, forcer INFO pour événements normaux
    logger = structlog.get_logger(name)
    
    # Pour Celery worker, forcer niveau INFO
    # Cela évite que les événements normaux apparaissent comme WARNING
    if 'celery' in name.lower() or 'worker' in name.lower():
        # Obtenir le logger standard Python sous-jacent
        import logging
        py_logger = logging.getLogger(name)
        py_logger.setLevel(logging.INFO)
    
    return logger


class LoggerMixin:
    """Mixin pour ajouter facilement un logger à une classe."""
    
    @property
    def logger(self) -> structlog.BoundLogger:
        """Récupère le logger pour cette classe."""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__module__)
        return self._logger


# Logger global pour l'application
app_logger = get_logger("ai-automation-agent")


def log_workflow_step(step_name: str, task_id: str, **kwargs) -> None:
    """
    Log une étape de workflow avec contexte.
    
    Args:
        step_name: Nom de l'étape
        task_id: ID de la tâche
        **kwargs: Métadonnées additionnelles
    """
    app_logger.info(
        f"🔄 Étape: {step_name}",
        step=step_name,
        task_id=task_id,
        **kwargs
    )


def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """
    Log une erreur avec contexte détaillé.
    
    Args:
        error: Exception à logger
        context: Contexte additionnel
    """
    context = context or {}
    
    app_logger.error(
        f"❌ Erreur: {str(error)}",
        error_type=type(error).__name__,
        error_message=str(error),
        **context,
        exc_info=True
    )


def log_success(message: str, **kwargs) -> None:
    """
    Log un succès avec métadonnées.
    
    Args:
        message: Message de succès
        **kwargs: Métadonnées additionnelles
    """
    app_logger.info(f"✅ {message}", **kwargs)


def log_warning(message: str, **kwargs) -> None:
    """
    Log un avertissement avec métadonnées.
    
    Args:
        message: Message d'avertissement
        **kwargs: Métadonnées additionnelles
    """
    app_logger.warning(f"⚠️ {message}", **kwargs) 