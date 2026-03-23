"""
app/core/config.py — Microsoft Azure Stack
All services powered by Microsoft:
  - Azure App Service     → FastAPI backend
  - Azure Cosmos DB       → MongoDB-compatible database  
  - Azure OpenAI          → LLM (GPT-4o)
  - Azure Blob Storage    → File uploads
  - Azure Static Web Apps → Frontend
  - GitHub Actions        → CI/CD (Microsoft)
"""
from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    APP_NAME: str = "IntelliHire"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"
    ALLOWED_ORIGINS: str = "http://localhost:3000,https://student-cybrarians.github.io"

    # ── Azure Cosmos DB (MongoDB API) ────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"   # Set to Cosmos DB connection string
    MONGODB_DB_NAME: str = "intellihire"

    # ── Azure OpenAI ─────────────────────────────────
    LLM_PROVIDER: str = "azure_openai"              # azure_openai | openai | anthropic
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""                 # https://YOUR-RESOURCE.openai.azure.com/
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o"
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Fallback: standard OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # ── Azure Blob Storage ────────────────────────────
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER: str = "intellihire-uploads"
    USE_AZURE_STORAGE: bool = False                  # False = use local /tmp

    # ── Local fallback paths ─────────────────────────
    UPLOAD_DIR: Path = Path("/tmp/uploads")
    REPORTS_DIR: Path = Path("/tmp/reports")
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx"]

    SCORE_WEIGHTS: dict = {
        "keyword_match": 0.30, "skills_match": 0.20,
        "experience_relevance": 0.20, "formatting": 0.10,
        "readability": 0.10, "section_completeness": 0.10,
    }

    def get_allowed_origins(self) -> List[str]:
        if isinstance(self.ALLOWED_ORIGINS, list):
            return self.ALLOWED_ORIGINS
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    def ensure_dirs(self):
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s

settings = get_settings()
