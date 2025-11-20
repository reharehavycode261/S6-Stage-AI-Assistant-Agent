"""Configuration des limites et seuils pour les workflows."""

class WorkflowLimits:
    """Limites et seuils configurables pour les workflows."""
    
    MAX_NODES_SAFETY_LIMIT = 35  
    MAX_DEBUG_ATTEMPTS = 2      
    MAX_RETRY_ATTEMPTS = 2      
    
    WORKFLOW_TIMEOUT = 1200     
    NODE_TIMEOUT = 300          
    API_REQUEST_TIMEOUT = 120   
    
    MAX_FILE_SIZE_MB = 50       
    MAX_LOG_SIZE_MB = 100       
    MAX_CONCURRENT_WORKFLOWS = 10 
    
    MIN_QA_SCORE = 55           
    MAX_CRITICAL_ISSUES = 5     
    MONITORING_INTERVAL = 30    
    ALERT_THRESHOLD_ERROR_RATE = 0.1  
    
    @classmethod
    def get_limits_dict(cls) -> dict:
        """Retourne toutes les limites sous forme de dictionnaire."""
        return {
            "max_nodes": cls.MAX_NODES_SAFETY_LIMIT,
            "max_debug_attempts": cls.MAX_DEBUG_ATTEMPTS,
            "max_retry_attempts": cls.MAX_RETRY_ATTEMPTS,
            "workflow_timeout": cls.WORKFLOW_TIMEOUT,
            "node_timeout": cls.NODE_TIMEOUT,
            "api_timeout": cls.API_REQUEST_TIMEOUT,
            "max_file_size_mb": cls.MAX_FILE_SIZE_MB,
            "max_log_size_mb": cls.MAX_LOG_SIZE_MB,
            "max_concurrent": cls.MAX_CONCURRENT_WORKFLOWS,
            "min_qa_score": cls.MIN_QA_SCORE,
            "max_critical_issues": cls.MAX_CRITICAL_ISSUES,
            "monitoring_interval": cls.MONITORING_INTERVAL,
            "alert_threshold": cls.ALERT_THRESHOLD_ERROR_RATE
        }
        
    @classmethod
    def validate_limits(cls) -> bool:
        """Valide que toutes les limites sont dans des plages acceptables."""
        validations = [
            cls.MAX_NODES_SAFETY_LIMIT > 0,
            cls.MAX_DEBUG_ATTEMPTS > 0,
            cls.WORKFLOW_TIMEOUT > 60,  
            cls.NODE_TIMEOUT > 10,      
            cls.MIN_QA_SCORE >= 0 and cls.MIN_QA_SCORE <= 100,
            cls.MAX_CRITICAL_ISSUES >= 0,
            cls.MONITORING_INTERVAL > 0,
            cls.ALERT_THRESHOLD_ERROR_RATE >= 0 and cls.ALERT_THRESHOLD_ERROR_RATE <= 1
        ]
        return all(validations) 