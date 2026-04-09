"""Application configuration via environment variables."""

import secrets
import warnings
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "TimeTrace"
    APP_SECRET: str = secrets.token_urlsafe(32)
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite:///./timetrace.db"

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""  # 必须通过 .env 或环境变量设置

    CRAWL_INTERVAL_MINUTES: int = 1440  # 每天一次（24小时）
    SIMILARITY_THRESHOLD: float = 0.25
    AGGREGATE_INTERVAL_SECONDS: int = 300

    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://open.bigmodel.cn/api/paas/v4"
    LLM_MODEL: str = ""
    LLM_TEMPERATURE: float = 0.3
    LLM_TOP_P: float = 0.7
    LLM_MAX_TOKENS: int = 300

    EMBEDDING_MODEL: str = "embedding-3"
    EMBEDDING_THRESHOLD: float = 0.55
    EMBEDDING_VERIFY_RANGE: tuple = (0.40, 0.55)

    EVENT_TIME_WINDOW_DAYS: int = 30
    EVENT_AUTO_CLOSE_DAYS: int = 14

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:3001"

    _SECRET_FILE: Path = Path(__file__).parent.parent / ".secret"

    def get_secret(self) -> str:
        if self._SECRET_FILE.exists():
            return self._SECRET_FILE.read_text().strip()
        secret = self.APP_SECRET
        self._SECRET_FILE.write_text(secret)
        return secret

    def get_admin_password(self) -> str:
        """获取管理员密码，未设置时生成随机密码并提示。"""
        if self.ADMIN_PASSWORD:
            return self.ADMIN_PASSWORD
        # 首次部署：生成随机密码
        generated = secrets.token_urlsafe(12)
        warnings.warn(
            f"\n{'='*60}\n"
            f"⚠️  未设置管理员密码！已自动生成：{generated}\n"
            f"   请在 .env 文件中设置 ADMIN_PASSWORD=<你的密码>\n"
            f"{'='*60}",
            stacklevel=2,
        )
        return generated

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
