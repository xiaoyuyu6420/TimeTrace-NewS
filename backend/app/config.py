"""Application configuration via environment variables."""

import secrets
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TimeTrace"
    APP_SECRET: str = secrets.token_urlsafe(32)
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./timetrace.db"

    # Auth
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 72
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # Crawler
    CRAWL_INTERVAL_MINUTES: int = 30
    SIMILARITY_THRESHOLD: float = 0.25
    AGGREGATE_INTERVAL_SECONDS: int = 300

    # LLM (智谱 GLM)
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "glm-4-flash"
    LLM_API_BASE: str = "https://open.bigmodel.cn/api/paas/v4"

    # Embedding
    EMBEDDING_MODEL: str = "embedding-3"
    EMBEDDING_THRESHOLD: float = 0.55
    EMBEDDING_VERIFY_RANGE: tuple = (0.40, 0.55)

    # Event lifecycle
    EVENT_TIME_WINDOW_DAYS: int = 30
    EVENT_AUTO_CLOSE_DAYS: int = 14

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Persistence file for generated secret
    _SECRET_FILE: Path = Path(__file__).parent.parent / ".secret"

    def get_secret(self) -> str:
        """Load or generate persistent APP_SECRET."""
        if self._SECRET_FILE.exists():
            return self._SECRET_FILE.read_text().strip()
        secret = self.APP_SECRET
        self._SECRET_FILE.write_text(secret)
        return secret

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
