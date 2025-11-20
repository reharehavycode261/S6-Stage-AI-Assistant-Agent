"""
Service de configuration robuste du logging pour Celery.

Ce service centralise toute la logique de configuration des logs avec :
- Gestion des environnements (dev/prod)
- Rotation automatique avec compression
- Nettoyage automatique des anciens logs
- Filtres spécialisés
- Gestion des permissions et fallbacks
"""

import os
import sys
import logging
import json
import glob
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


class CeleryLoggingService:
    """Service centralisé pour la configuration du logging Celery."""
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development').lower()
        self.is_production = self.environment in ['production', 'prod']
        self.logs_dir = None
        self.handlers = {}
        
    def setup_logging(self) -> bool:
        """
        Configure le logging de Celery de manière robuste.
        
        Returns:
            True si la configuration a réussi, False sinon
        """
        try:
            self.logs_dir = self._ensure_logs_directory()
            if not self.logs_dir:
                return self._setup_fallback_logging()
            
            if not self._create_log_handlers():
                return self._setup_fallback_logging()
            
            self._configure_logger_hierarchy()
            
            self._create_session_metadata()
            
            self._schedule_log_cleanup()
            
            logger.info(f"📊 Logging Celery configuré: {self.logs_dir} (env: {self.environment})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Échec configuration logging avancée: {e}")
            return self._setup_fallback_logging()
    
    def _ensure_logs_directory(self) -> str:
        """Crée et sécurise le répertoire de logs."""
        
        if self.is_production:
            potential_dirs = [
                "/var/log/ai-agent",
                "/opt/ai-agent/logs",
                "/home/ai-agent/logs"
            ]
        else:
            potential_dirs = [
                "logs",
                os.path.expanduser("~/.ai_agent_logs"),
                "/tmp/ai_agent_logs"
            ]
        
        for logs_dir in potential_dirs:
            try:
                os.makedirs(logs_dir, mode=0o755, exist_ok=True)
                
                test_file = os.path.join(logs_dir, '.write_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                
                return logs_dir
                
            except (OSError, PermissionError) as e:
                logger.debug(f"🔍 Échec répertoire {logs_dir}: {e}")
                continue
        
        logger.warning("⚠️ Impossible de créer un répertoire de logs utilisable")
        return None
    
    def _create_log_handlers(self) -> bool:
        """Crée tous les handlers de logging spécialisés."""
        
        try:
            handlers_config = self._get_handlers_config()
            
            detailed_format = logging.Formatter(
                '[%(asctime)s] %(levelname)-8s [%(name)s:%(lineno)d] [%(processName)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            simple_format = logging.Formatter(
                '[%(asctime)s] %(levelname)-8s %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            for name, config in handlers_config.items():
                try:
                    handler = RotatingFileHandler(
                        config['file'],
                        maxBytes=config['max_bytes'],
                        backupCount=config['backup_count']
                    )
                    
                    if name in ['celery', 'error']:
                        handler.setFormatter(detailed_format)
                    else:
                        handler.setFormatter(simple_format)
                    
                    handler.setLevel(config['level'])
                    
                    if name == 'workflow':
                        handler.addFilter(self._create_workflow_filter())
                    elif name == 'performance':
                        handler.addFilter(self._create_performance_filter())
                    
                    self.handlers[name] = handler
                    
                except Exception as e:
                    logger.error(f"❌ Échec création handler {name}: {e}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Échec création handlers: {e}")
            return False
    
    def _get_handlers_config(self) -> Dict[str, Dict]:
        """Retourne la configuration des handlers selon l'environnement."""
        
        if self.is_production:
            return {
                'celery': {
                    'file': os.path.join(self.logs_dir, 'celery.log'),
                    'max_bytes': 100 * 1024 * 1024,
                    'backup_count': 20,
                    'level': logging.INFO
                },
                'error': {
                    'file': os.path.join(self.logs_dir, 'celery_errors.log'),
                    'max_bytes': 50 * 1024 * 1024,
                    'backup_count': 10,
                    'level': logging.ERROR
                },
                'workflow': {
                    'file': os.path.join(self.logs_dir, 'workflows.log'),
                    'max_bytes': 200 * 1024 * 1024,
                    'backup_count': 30,
                    'level': logging.INFO
                },
                'performance': {
                    'file': os.path.join(self.logs_dir, 'performance.log'),
                    'max_bytes': 50 * 1024 * 1024,
                    'backup_count': 15,
                    'level': logging.INFO
                },
                'main_logs': {
                    'file': os.path.join(self.logs_dir, 'logs.txt'),
                    'max_bytes': 200 * 1024 * 1024,
                    'backup_count': 5,
                    'level': logging.INFO
                }
            }
        else:
            return {
                'celery': {
                    'file': os.path.join(self.logs_dir, 'celery.log'),
                    'max_bytes': 10 * 1024 * 1024,
                    'backup_count': 5,
                    'level': logging.DEBUG
                },
                'error': {
                    'file': os.path.join(self.logs_dir, 'celery_errors.log'),
                    'max_bytes': 5 * 1024 * 1024,
                    'backup_count': 3,
                    'level': logging.ERROR
                },
                'workflow': {
                    'file': os.path.join(self.logs_dir, 'workflows.log'),
                    'max_bytes': 20 * 1024 * 1024,
                    'backup_count': 10,
                    'level': logging.DEBUG
                },
                'performance': {
                    'file': os.path.join(self.logs_dir, 'performance.log'),
                    'max_bytes': 10 * 1024 * 1024,
                    'backup_count': 5,
                    'level': logging.INFO
                },
                'main_logs': {
                    'file': os.path.join(self.logs_dir, 'logs.txt'),
                    'max_bytes': 50 * 1024 * 1024,
                    'backup_count': 3,
                    'level': logging.DEBUG
                }
            }
    
    def _create_workflow_filter(self) -> logging.Filter:
        """Crée un filtre pour capturer les logs de workflow."""
        
        class WorkflowFilter(logging.Filter):
            WORKFLOW_KEYWORDS = {
                'workflow', 'task', 'node', 'langgraph', 'execute_workflow',
                'prepare_environment', 'implement_task', 'run_tests', 'debug_code',
                'quality_assurance', 'human_validation', 'monday', 'merge',
                'pull_request', 'github', 'pr_creation', 'validation'
            }
            
            def filter(self, record):
                message = record.getMessage().lower()
                return any(keyword in message for keyword in self.WORKFLOW_KEYWORDS)
        
        return WorkflowFilter()
    
    def _create_performance_filter(self) -> logging.Filter:
        """Crée un filtre pour capturer les logs de performance."""
        
        class PerformanceFilter(logging.Filter):
            PERFORMANCE_KEYWORDS = {
                'performance', 'slow', 'timeout', 'duration', 'memory',
                'cpu', 'latency', 'throughput', 'bottleneck', 'optimization',
                'time', 'ms', 'seconds', 'minutes', 'retry', 'failed'
            }
            
            def filter(self, record):
                message = record.getMessage().lower()
                return any(keyword in message for keyword in self.PERFORMANCE_KEYWORDS)
        
        return PerformanceFilter()
    
    def _configure_logger_hierarchy(self):
        """Configure la hiérarchie des loggers de manière propre."""
        
        loggers_config = [
            ('celery', ['main_logs', 'celery', 'error'], logging.INFO, False),
            ('celery.task', ['main_logs', 'celery', 'workflow', 'error'], logging.INFO, False),
            ('celery.worker', ['main_logs', 'celery', 'error'], logging.INFO, False),
            ('ai_agent_background', ['main_logs', 'celery', 'workflow', 'error'], logging.INFO, False),
            ('utils', ['main_logs', 'workflow'], logging.INFO, False),
            ('nodes', ['main_logs', 'workflow'], logging.INFO, False),
            ('services', ['main_logs', 'workflow', 'performance'], logging.INFO, False),
            ('tools', ['main_logs', 'workflow'], logging.INFO, False),
            ('models', ['main_logs', 'workflow'], logging.INFO, False),
        ]
        
        for logger_name, handler_names, level, propagate in loggers_config:
            logger_obj = logging.getLogger(logger_name)
            
            logger_obj.handlers.clear()
            
            for handler_name in handler_names:
                if handler_name in self.handlers:
                    logger_obj.addHandler(self.handlers[handler_name])
            
            logger_obj.setLevel(level)
            logger_obj.propagate = propagate
    
    def _create_session_metadata(self):
        """Crée un fichier de métadonnées pour la session de logging."""
        
        try:
            from config.settings import get_settings
            settings = get_settings()
            
            metadata = {
                'session_start': datetime.now().isoformat(),
                'worker_pid': os.getpid(),
                'environment': self.environment,
                'is_production': self.is_production,
                'logs_directory': self.logs_dir,
                'broker': getattr(settings, 'celery_broker_url', 'N/A'),
                'backend': getattr(settings, 'celery_result_backend', 'N/A'),
                'python_version': sys.version,
                'handlers_created': list(self.handlers.keys()),
                'retention_days': 30 if self.is_production else 7
            }
            
            metadata_file = os.path.join(self.logs_dir, 'session_metadata.json')
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
                
        except Exception as e:
            logger.debug(f"🔍 Échec création métadonnées: {e}")
    
    def _schedule_log_cleanup(self):
        """Programme et exécute le nettoyage automatique des anciens logs."""
        
        retention_days = 30 if self.is_production else 7
        
        try:
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            files_cleaned = 0
            
            cleanup_patterns = [
                '*.log.*',
                '*.log.*.gz',
                '*.log.*.bz2',
                'session_metadata_*.json'
            ]
            
            for pattern in cleanup_patterns:
                for log_file in glob.glob(os.path.join(self.logs_dir, pattern)):
                    try:
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                        if file_mtime < cutoff_time:
                            file_size = os.path.getsize(log_file)
                            os.remove(log_file)
                            files_cleaned += 1
                            logger.debug(f"🧹 Log nettoyé: {log_file} ({file_size} bytes)")
                    except (OSError, ValueError) as e:
                        logger.debug(f"🔍 Échec nettoyage {log_file}: {e}")
                        continue
            
            if files_cleaned > 0:
                logger.info(f"🧹 Nettoyage terminé: {files_cleaned} fichiers supprimés (> {retention_days} jours)")
                
        except Exception as e:
            logger.debug(f"🔍 Échec nettoyage automatique: {e}")
    
    def _setup_fallback_logging(self) -> bool:
        """Configuration de logging minimale en cas d'échec."""
        
        try:
            fallback_dir = os.path.expanduser("~/.ai_agent_logs_fallback")
            os.makedirs(fallback_dir, exist_ok=True)
            
            log_file = os.path.join(fallback_dir, 'celery_fallback.log')
            handler = RotatingFileHandler(
                log_file, 
                maxBytes=5*1024*1024,
                backupCount=2
            )
            
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s %(name)s: %(message)s'
            )
            handler.setFormatter(formatter)
            handler.setLevel(logging.INFO)
            
            celery_logger = logging.getLogger('celery')
            celery_logger.handlers.clear()
            celery_logger.addHandler(handler)
            celery_logger.setLevel(logging.INFO)
            celery_logger.propagate = False
            
            logger.warning(f"⚠️ Configuration logging fallback: {fallback_dir}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Échec configuration logging fallback: {e}")
            return False
    
    def get_logs_info(self) -> Dict[str, any]:
        """Retourne des informations sur la configuration de logging."""
        
        main_log_file = os.path.join(self.logs_dir, 'logs.txt') if self.logs_dir else None
        
        return {
            'logs_directory': self.logs_dir,
            'main_log_file': main_log_file,
            'environment': self.environment,
            'is_production': self.is_production,
            'handlers_count': len(self.handlers),
            'handlers': list(self.handlers.keys()) if self.handlers else []
        }

logging_service = CeleryLoggingService() 