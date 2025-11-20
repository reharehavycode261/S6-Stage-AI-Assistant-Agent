"""
Optimiseur de performances pour le workflow AI-Agent.
"""

import asyncio
import time
import resource
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from utils.logger import get_logger

logger = get_logger(__name__)


class PerformanceMonitor:
    """Moniteur de performances pour le workflow."""
    
    def __init__(self):
        self.start_times = {}
        self.durations = {}
        self.memory_usage = {}
        self.warning_thresholds = {
            "prepare_environment": 120,  # 2 minutes max pour setup
            "analyze_requirements": 30,   # 30 secondes max pour analyse
            "implement_task": 300,        # 5 minutes max pour implémentation
            "run_tests": 180,             # 3 minutes max pour tests
            "debug_code": 120,            # 2 minutes max pour debug
            "quality_assurance_automation": 60,  # 1 minute max pour QA
            "finalize_pr": 30,            # 30 secondes max pour finalisation
            "monday_validation": 600,     # 10 minutes max pour validation (réduit de 60min)
        }
    
    def start_node_timer(self, node_name: str) -> None:
        """Démarre le timer pour un nœud."""
        self.start_times[node_name] = time.time()
        self.memory_usage[node_name] = self._get_memory_usage()
        logger.debug(f"⏱️ Timer démarré pour {node_name}")
    
    def end_node_timer(self, node_name: str) -> float:
        """Termine le timer pour un nœud et retourne la durée."""
        if node_name not in self.start_times:
            logger.warning(f"⚠️ Timer non démarré pour {node_name}")
            return 0.0
        
        duration = time.time() - self.start_times[node_name]
        self.durations[node_name] = duration
        
        # Vérifier le seuil d'avertissement
        threshold = self.warning_thresholds.get(node_name, 60)
        if duration > threshold:
            logger.warning(f"⚠️ {node_name} prend trop de temps: {duration:.1f}s (seuil: {threshold}s)")
        else:
            logger.info(f"⏱️ {node_name} terminé en {duration:.1f}s")
        
        # Calculer l'usage mémoire
        current_memory = self._get_memory_usage()
        start_memory = self.memory_usage.get(node_name, 0)
        memory_diff = current_memory - start_memory
        
        if memory_diff > 100:  # Plus de 100MB
            logger.warning(f"🐏 {node_name} utilise beaucoup de mémoire: {memory_diff:.1f}MB")
        
        return duration
    
    def _get_memory_usage(self) -> float:
        """Retourne l'usage mémoire actuel en MB."""
        try:
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
        except:
            return 0.0
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des performances."""
        total_time = sum(self.durations.values())
        slowest_node = max(self.durations.items(), key=lambda x: x[1]) if self.durations else ("unknown", 0)
        
        return {
            "total_workflow_time": total_time,
            "node_durations": dict(self.durations),
            "slowest_node": {"name": slowest_node[0], "duration": slowest_node[1]},
            "nodes_over_threshold": [
                {"name": name, "duration": duration, "threshold": self.warning_thresholds.get(name, 60)}
                for name, duration in self.durations.items()
                if duration > self.warning_thresholds.get(name, 60)
            ]
        }


def performance_decorator(node_name: str, monitor: PerformanceMonitor):
    """Décorateur pour mesurer les performances d'un nœud."""
    def decorator(func: Callable) -> Callable:
        async def wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            monitor.start_node_timer(node_name)
            
            try:
                result = await func(state, *args, **kwargs)
                return result
            finally:
                duration = monitor.end_node_timer(node_name)
                
                # Ajouter les métriques de performance à l'état
                if "results" not in result:
                    result["results"] = {}
                if "performance_metrics" not in result["results"]:
                    result["results"]["performance_metrics"] = {}
                
                result["results"]["performance_metrics"][node_name] = {
                    "duration": duration,
                    "timestamp": datetime.now().isoformat()
                }
        
        return wrapper
    return decorator


class GitOptimizer:
    """Optimisations pour les opérations Git."""
    
    @staticmethod
    def get_optimized_clone_command(repo_url: str, branch: str = None) -> list:
        """
        Génère une commande de clonage Git optimisée.
        
        Args:
            repo_url: URL du repository
            branch: Branche à cloner (optionnel)
            
        Returns:
            Liste des arguments pour la commande git clone
        """
        cmd = [
            "git", "clone",
            "--depth", "1",           # Clone superficiel
            "--single-branch",        # Une seule branche
            "--no-tags",             # Pas de tags
            "--recurse-submodules=no", # Pas de sous-modules
        ]
        
        if branch:
            cmd.extend(["--branch", branch])
        
        cmd.append(repo_url)
        cmd.append(".")
        
        return cmd
    
    @staticmethod
    def get_optimized_fetch_command(branch: str = None) -> list:
        """
        Génère une commande de fetch optimisée.
        
        Args:
            branch: Branche à récupérer (optionnel)
            
        Returns:
            Liste des arguments pour la commande git fetch
        """
        cmd = ["git", "fetch", "--depth=1"]
        
        if branch:
            cmd.extend(["origin", f"{branch}:{branch}"])
        
        return cmd


class TestOptimizer:
    """Optimisations pour l'exécution des tests."""
    
    @staticmethod
    def should_skip_slow_tests(modified_files: list, test_files: list) -> bool:
        """
        Détermine si on peut ignorer les tests lents.
        
        Args:
            modified_files: Fichiers modifiés
            test_files: Fichiers de test disponibles
            
        Returns:
            True si on peut ignorer les tests lents
        """
        # Si moins de 3 fichiers modifiés et tests simples, ignorer les tests longs
        if len(modified_files) < 3 and len(test_files) < 10:
            return True
        
        # Si pas de fichiers critiques modifiés
        critical_patterns = ["auth", "payment", "security", "database"]
        for file in modified_files:
            for pattern in critical_patterns:
                if pattern in file.lower():
                    return False
        
        return True
    
    @staticmethod
    def get_fast_test_command(test_files: list) -> str:
        """
        Génère une commande de test optimisée.
        
        Args:
            test_files: Liste des fichiers de test
            
        Returns:
            Commande de test optimisée
        """
        if not test_files:
            return ""
        
        # Limiter à 5 fichiers de test max pour la vitesse
        limited_files = test_files[:5]
        
        # Utiliser pytest avec options rapides
        return f"python -m pytest {' '.join(limited_files)} -x --tb=short --no-header -q"


class WorkflowOptimizer:
    """Optimiseur global du workflow."""
    
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
        self.git_optimizer = GitOptimizer()
        self.test_optimizer = TestOptimizer()
    
    def optimize_task_priority(self, state: Dict[str, Any]) -> str:
        """
        Détermine la priorité d'optimisation pour une tâche.
        
        Args:
            state: État du workflow
            
        Returns:
            Niveau de priorité ('high', 'medium', 'low')
        """
        task = state.get("task")
        if not task:
            return "medium"
        
        # Facteurs de priorité
        priority_score = 0
        
        # 1. Priorité explicite de la tâche
        task_priority = getattr(task, 'priority', 'medium')
        if task_priority == 'high':
            priority_score += 3
        elif task_priority == 'medium':
            priority_score += 2
        else:
            priority_score += 1
        
        # 2. Taille de la tâche (estimation)
        description = getattr(task, 'description', '')
        try:
            if isinstance(description, str) and len(description) > 500:
                priority_score += 1
        except (TypeError, AttributeError):
            # Ignorer si description n'est pas une chaîne (ex: Mock)
            pass
        
        # 3. Fichiers à modifier
        files_to_modify = state.get("results", {}).get("modified_files", [])
        try:
            if isinstance(files_to_modify, list) and len(files_to_modify) > 5:
                priority_score += 1
        except (TypeError, AttributeError):
            # Ignorer si modified_files n'est pas une liste
            pass
        
        # Déterminer la priorité finale
        if priority_score >= 5:
            return "high"
        elif priority_score >= 3:
            return "medium"
        else:
            return "low"
    
    def get_optimization_config(self, task_priority: str) -> Dict[str, Any]:
        """
        Retourne la configuration d'optimisation selon la priorité.
        
        Args:
            task_priority: Priorité de la tâche
            
        Returns:
            Configuration d'optimisation
        """
        if task_priority == "high":
            return {
                "git_shallow_clone": True,
                "skip_slow_tests": False,
                "max_debug_attempts": 3,
                "validation_timeout_minutes": 15,
                "enable_parallel_processing": True
            }
        elif task_priority == "medium":
            return {
                "git_shallow_clone": True,
                "skip_slow_tests": True,
                "max_debug_attempts": 2,
                "validation_timeout_minutes": 10,
                "enable_parallel_processing": True
            }
        else:  # low
            return {
                "git_shallow_clone": True,
                "skip_slow_tests": True,
                "max_debug_attempts": 1,
                "validation_timeout_minutes": 5,
                "enable_parallel_processing": False
            }
    
    async def apply_optimizations(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applique les optimisations au workflow.
        
        Args:
            state: État du workflow
            
        Returns:
            État mis à jour avec les optimisations
        """
        task_priority = self.optimize_task_priority(state)
        optimization_config = self.get_optimization_config(task_priority)
        
        logger.info(f"🚀 Optimisations appliquées - Priorité: {task_priority}")
        logger.info(f"   Configuration: {optimization_config}")
        
        # Stocker la configuration dans l'état
        if "results" not in state:
            state["results"] = {}
        
        state["results"]["optimization_config"] = optimization_config
        state["results"]["task_priority"] = task_priority
        
        return state


# Instance globale pour utilisation dans le workflow
workflow_optimizer = WorkflowOptimizer() 