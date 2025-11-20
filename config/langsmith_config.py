import os
from typing import Optional
from langsmith import Client
from utils.logger import get_logger
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)


class LangSmithConfig:
    
    def __init__(self):
        self.api_key = os.getenv("LANGSMITH_API_KEY")
        self.project = os.getenv("LANGSMITH_PROJECT", "ai-agent-production")
        self.endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
        self.tracing_enabled = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"
        self.log_level = os.getenv("LANGSMITH_LOG_LEVEL", "INFO")
        
        self._client: Optional[Client] = None
        
    @property
    def client(self) -> Optional[Client]:
        if not self.is_configured:
            return None
            
        if self._client is None:
            try:
                self._client = Client(
                    api_key=self.api_key,
                    api_url=self.endpoint
                )
                logger.info("✅ Client LangSmith initialisé", project=self.project)
            except Exception as e:
                logger.error(f"❌ Erreur initialisation LangSmith: {e}")
                return None
                
        return self._client
    
    @property
    def is_configured(self) -> bool:
        """Vérifier si LangSmith est configuré."""
        return bool(self.api_key and self.tracing_enabled)
    
    def setup_environment(self):
        """Configurer les variables d'environnement LangSmith."""
        if not self.is_configured:
            logger.warning("⚠️ LangSmith non configuré - tracing désactivé")
            return
            
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = self.api_key
        os.environ["LANGCHAIN_PROJECT"] = self.project
        os.environ["LANGCHAIN_ENDPOINT"] = self.endpoint
        
        logger.info(
            "🚀 LangSmith configuré",
            project=self.project,
            endpoint=self.endpoint,
            tracing=self.tracing_enabled
        )
    
    def create_run_session(self, session_name: str) -> str:
        """Créer une session de tracing pour un workflow."""
        if not self.client:
            return f"local_{session_name}"
            
        try:
            session_id = f"{self.project}_{session_name}"
            logger.info(f"📊 Session LangSmith créée: {session_id}")
            return session_id
        except Exception as e:
            logger.error(f"❌ Erreur création session: {e}")
            return f"fallback_{session_name}"


# Instance globale
langsmith_config = LangSmithConfig() 