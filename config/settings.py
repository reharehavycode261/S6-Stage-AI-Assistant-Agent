from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }
    
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")  
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    github_token: str = Field(..., env="GITHUB_TOKEN") 
    
    monday_client_id: str = Field(..., env="MONDAY_CLIENT_ID")
    monday_client_key: str = Field(..., env="MONDAY_CLIENT_KEY") 
    monday_app_id: str = Field(..., env="MONDAY_APP_ID")
    
    monday_api_token: str = Field(..., env="MONDAY_API_TOKEN")

    webhook_secret: str = Field(..., env="WEBHOOK_SECRET")
    allowed_origins: str = Field(default="*", env="ALLOWED_ORIGINS")
    
    default_repo_url: Optional[str] = Field(default=None, env="DEFAULT_REPO_URL")  
    default_base_branch: str = Field(default="main", env="DEFAULT_BASE_BRANCH")  
    git_user_name: str = Field(default="AI-Agent", env="GIT_USER_NAME")
    git_user_email: str = Field(default="ai-agent@example.com", env="GIT_USER_EMAIL")
    
    base_branch_rules: Optional[str] = Field(default=None, env="BASE_BRANCH_RULES")
    
    repo_base_branches: Optional[str] = Field(default=None, env="REPO_BASE_BRANCHES")
    
    monday_board_id: str = Field(..., env="MONDAY_BOARD_ID")
    monday_task_column_id: str = Field(..., env="MONDAY_TASK_COLUMN_ID") 
    monday_status_column_id: str = Field(..., env="MONDAY_STATUS_COLUMN_ID")
    monday_repository_url_column_id: Optional[str] = Field(default=None, env="MONDAY_REPOSITORY_URL_COLUMN_ID")
    monday_slack_user_id_column_id: Optional[str] = Field(default=None, env="MONDAY_SLACK_USER_ID_COLUMN_ID")  
    monday_signing_secret: Optional[str] = Field(default=None, env="MONDAY_SIGNING_SECRET")  
    monday_api_url: str = Field(default="https://api.monday.com/v2", env="MONDAY_API_URL")  
    
    vydata_reactivation_v2: bool = Field(default=True, env="VYDATA_REACTIVATION_V2")  
    
    database_url: str = Field(default="postgresql://admin:password@localhost:5432/ai_agent_admin", env="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    secret_key: str = Field(..., env="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    default_ai_provider: str = Field(default="openai", env="DEFAULT_AI_PROVIDER")  
    ai_model_temperature: float = Field(default=0.1, env="AI_MODEL_TEMPERATURE")
    ai_max_tokens: int = Field(default=4000, env="AI_MAX_TOKENS")
    
    enable_smoke_tests: bool = Field(default=True, env="ENABLE_SMOKE_TESTS")
    test_coverage_threshold: int = Field(default=80, env="TEST_COVERAGE_THRESHOLD")
    max_test_retries: int = Field(default=3, env="MAX_TEST_RETRIES")
    
    rabbitmq_host: str = Field(default="localhost", env="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, env="RABBITMQ_PORT")
    rabbitmq_vhost: str = Field(default="ai_agent", env="RABBITMQ_VHOST")
    rabbitmq_user: str = Field(default="ai_agent_user", env="RABBITMQ_USER")
    rabbitmq_password: str = Field(default="secure_password_123", env="RABBITMQ_PASSWORD")
    rabbitmq_management_port: int = Field(default=15672, env="RABBITMQ_MANAGEMENT_PORT")
    rabbitmq_enable_management: bool = Field(default=True, env="RABBITMQ_ENABLE_MANAGEMENT")
    
    @property
    def celery_broker_url(self) -> str:
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"
    
    @property 
    def celery_result_backend(self) -> str:
        return f"db+{self.database_url}"
    
    @property
    def db_host(self) -> str:
        import re
        match = re.search(r'@([^@:]+):\d+/', self.database_url)
        return match.group(1) if match else "localhost"
    
    @property
    def db_port(self) -> int:
        """Extrait le port de database_url."""
        import re
        match = re.search(r':(\d+)/', self.database_url)
        return int(match.group(1)) if match else 5432
    
    @property
    def db_name(self) -> str:
        """Extrait le nom de DB de database_url."""
        import re
        match = re.search(r':\d+/([^?]+)', self.database_url)
        return match.group(1) if match else "ai_agent_admin"
    
    @property
    def db_user(self) -> str:
        """Extrait le user de database_url."""
        import re
        match = re.search(r'://([^:]+):', self.database_url)
        return match.group(1) if match else "admin"
    
    @property
    def db_password(self) -> str:
        """Extrait le password de database_url."""
        import re
        match = re.search(r'://[^:]+:(.+)@[^@]+:\d+/', self.database_url)
        return match.group(1) if match else "password"
    
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    task_timeout: int = Field(default=3600, env="TASK_TIMEOUT")  
    test_timeout: int = Field(default=600, env="TEST_TIMEOUT")  
    
    admin_frontend_url: str = Field(default="http://localhost:3000", env="ADMIN_FRONTEND_URL")
    
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=8080, env="METRICS_PORT")
    
    slack_enabled: bool = Field(default=True, env="SLACK_ENABLED")  
    slack_bot_token: Optional[str] = Field(default=None, env="SLACK_BOT_TOKEN")  
    slack_workspace_id: Optional[str] = Field(default=None, env="SLACK_WORKSPACE_ID")  
    
    validation_timeout_question: int = Field(default=600, env="VALIDATION_TIMEOUT_QUESTION")  
    validation_timeout_command: int = Field(default=20, env="VALIDATION_TIMEOUT_COMMAND")  

    browser_qa_enabled: bool = Field(default=True, env="BROWSER_QA_ENABLED")  
    browser_qa_headless: bool = Field(default=True, env="BROWSER_QA_HEADLESS")      
    browser_qa_viewport: str = Field(default="1920x1080", env="BROWSER_QA_VIEWPORT")  
    browser_qa_isolated: bool = Field(default=True, env="BROWSER_QA_ISOLATED")  
    browser_qa_timeout: int = Field(default=30, env="BROWSER_QA_TIMEOUT")  
    browser_qa_screenshot_on_error: bool = Field(default=True, env="BROWSER_QA_SCREENSHOT_ON_ERROR")  
    browser_qa_dev_server_port: int = Field(default=5173, env="BROWSER_QA_DEV_SERVER_PORT")  
    browser_qa_max_tests_per_file: int = Field(default=5, env="BROWSER_QA_MAX_TESTS_PER_FILE")  
    chrome_mcp_channel: str = Field(default="npx -y chrome-devtools-mcp", env="CHROME_MCP_CHANNEL")  


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings() 