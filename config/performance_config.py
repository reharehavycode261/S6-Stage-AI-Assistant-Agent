import os
from typing import Dict, Any

class PerformanceConfig:
    """Configuration des optimisations de performance."""

    API_REQUEST_TIMEOUT = 30        
    TEST_EXECUTION_TIMEOUT = 60     
    AI_RESPONSE_TIMEOUT = 45       
    GIT_OPERATION_TIMEOUT = 30      
    QA_ANALYSIS_TIMEOUT = 45        

    MAX_FILES_TO_ANALYZE = 10       
    MAX_TEST_FILES_TO_RUN = 20      
    MAX_QA_TOOLS_PARALLEL = 3       
    MAX_AI_CALLS_PER_NODE = 3       

    ENABLE_AI_RESPONSE_CACHE = True
    CACHE_DURATION_MINUTES = 30
    ENABLE_QA_RESULT_CACHE = True
    ENABLE_TEST_RESULT_CACHE = True
    
    SKIP_EXPENSIVE_QA_TOOLS = ["mypy", "complexity-analysis"]  
    PRIORITIZE_FAST_TESTS = True
    ENABLE_EARLY_SUCCESS = True     
    PARALLEL_OPERATIONS = True      
    
    MAX_MEMORY_MB = 512             
    MAX_CPU_CORES = 2               
    CLEANUP_TEMP_FILES = True       
    
    @classmethod
    def get_optimized_timeout(cls, operation_type: str) -> int:
        """Retourne un timeout optimisé pour un type d'opération."""
        timeouts = {
            "api_request": cls.API_REQUEST_TIMEOUT,
            "test_execution": cls.TEST_EXECUTION_TIMEOUT,
            "ai_response": cls.AI_RESPONSE_TIMEOUT,
            "git_operation": cls.GIT_OPERATION_TIMEOUT,
            "qa_analysis": cls.QA_ANALYSIS_TIMEOUT,
            "file_operation": 15,  
            "database_operation": 10  
        }
        return timeouts.get(operation_type, 30) 
    
    @classmethod
    def should_skip_operation(cls, operation_name: str, estimated_duration: float = 0) -> bool:
        """Détermine si une opération doit être skippée pour les performances."""

        if estimated_duration > 60:  
            return True

        if operation_name in cls.SKIP_EXPENSIVE_QA_TOOLS:
            return True

        if "analyze" in operation_name.lower() and "files" in operation_name.lower():
            return False  
            
        return False
    
    @classmethod
    def get_parallel_limit(cls, operation_type: str) -> int:
        """Retourne la limite de parallélisation pour un type d'opération."""
        limits = {
            "qa_tools": cls.MAX_QA_TOOLS_PARALLEL,
            "ai_calls": cls.MAX_AI_CALLS_PER_NODE,
            "test_files": cls.MAX_TEST_FILES_TO_RUN,
            "file_analysis": cls.MAX_FILES_TO_ANALYZE
        }
        return limits.get(operation_type, 5)  
    
    @classmethod
    def is_caching_enabled(cls, cache_type: str) -> bool:
        """Vérifie si le caching est activé pour un type donné."""
        caching = {
            "ai_response": cls.ENABLE_AI_RESPONSE_CACHE,
            "qa_result": cls.ENABLE_QA_RESULT_CACHE,
            "test_result": cls.ENABLE_TEST_RESULT_CACHE
        }
        return caching.get(cache_type, False)
    
    @classmethod
    def get_performance_profile(cls) -> Dict[str, Any]:
        """Retourne le profil de performance actuel."""
        return {
            "mode": "optimized",
            "timeouts": {
                "api": cls.API_REQUEST_TIMEOUT,
                "tests": cls.TEST_EXECUTION_TIMEOUT,
                "ai": cls.AI_RESPONSE_TIMEOUT
            },
            "limits": {
                "max_files": cls.MAX_FILES_TO_ANALYZE,
                "max_tests": cls.MAX_TEST_FILES_TO_RUN,
                "max_qa_parallel": cls.MAX_QA_TOOLS_PARALLEL
            },
            "optimizations": {
                "caching": cls.ENABLE_AI_RESPONSE_CACHE,
                "parallel": cls.PARALLEL_OPERATIONS,
                "early_success": cls.ENABLE_EARLY_SUCCESS,
                "skip_expensive": len(cls.SKIP_EXPENSIVE_QA_TOOLS) > 0
            },
            "resources": {
                "max_memory_mb": cls.MAX_MEMORY_MB,
                "max_cpu_cores": cls.MAX_CPU_CORES,
                "cleanup_temp": cls.CLEANUP_TEMP_FILES
            }
        }

PERFORMANCE_MODE = os.getenv("AI_AGENT_PERFORMANCE_MODE", "balanced")  

def get_performance_multiplier() -> float:
    """Retourne un multiplicateur basé sur le mode de performance."""
    multipliers = {
        "fast": 0.5,      
        "balanced": 1.0,  
        "thorough": 2.0  
    }
    return multipliers.get(PERFORMANCE_MODE, 1.0) 