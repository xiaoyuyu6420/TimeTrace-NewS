"""Shared dependencies: DB sessions, auth, service factories."""

import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, get_db

logger = logging.getLogger(__name__)

security = HTTPBearer()


# ─── Auth ──────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.get_secret(), algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.get_secret(), algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency: returns {user_id, username, role}."""
    payload = decode_token(credentials.credentials)
    return {
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
        "role": payload.get("role"),
    }


def require_admin(user=Depends(get_current_user)):
    """Dependency: requires admin role."""
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


# ─── DB ────────────────────────────────────────────────
# get_db 由 database.py 提供，此处不再重复定义


# ─── Service singletons ────────────────────────────────

_llm = None
_nlp = None


def get_llm():
    global _llm
    if _llm is None:
        from .llm import OpenAICompatibleLLM, MockLLMProvider
        if settings.LLM_API_KEY and settings.LLM_MODEL:
            _llm = OpenAICompatibleLLM(
                api_key=settings.LLM_API_KEY,
                api_base=settings.LLM_API_BASE,
                model=settings.LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                top_p=settings.LLM_TOP_P,
                max_tokens=settings.LLM_MAX_TOKENS,
                embedding_model=settings.EMBEDDING_MODEL,
            )
            logger.info(f"Initialized OpenAICompatibleLLM: {settings.LLM_API_BASE} / {settings.LLM_MODEL}")
        else:
            _llm = MockLLMProvider()
            logger.warning("No LLM API key or model, using MockLLMProvider")
    return _llm


def get_nlp():
    global _nlp
    if _nlp is None:
        from .nlp import JiebaProcessor
        _nlp = JiebaProcessor()
    return _nlp


def get_crawl_service(db: Session):
    from .services.crawl import CrawlService
    return CrawlService(db, get_llm(), get_nlp())


def get_process_service(db: Session):
    from .services.process import ProcessService
    return ProcessService(db, get_llm(), get_nlp())


def get_aggregate_service(db: Session):
    from .services.aggregate import AggregateService
    return AggregateService(
        db, get_llm(), get_nlp(),
        embedding_threshold=settings.EMBEDDING_THRESHOLD,
        fallback_threshold=settings.SIMILARITY_THRESHOLD,
        time_window_days=settings.EVENT_TIME_WINDOW_DAYS,
        auto_close_days=settings.EVENT_AUTO_CLOSE_DAYS,
    )


def get_timeline_service(db: Session):
    from .services.timeline import TimelineService
    return TimelineService(db, get_llm(), get_nlp())


def get_pipeline(db: Session):
    from .services.pipeline import Pipeline
    return Pipeline(db, get_llm(), get_nlp())


def get_role_llm(db: Session, role: str):
    """按角色获取 LLM 实例。role: distill | reason | audit | embed。

    优先从 llm_models + llm_providers + llm_routing 读取编排配置；无配置时回退到默认 LLM。
    embed 角色使用独立的 embed_providers + embed_models 表。
    """
    try:
        from .models import LlmModel, LlmProvider, LlmRouting, EmbedModel, EmbedProvider
        from .llm import create_llm_from_model, create_llm_from_embed

        routing = db.query(LlmRouting).first()
        if not routing:
            return get_llm()

        col_map = {
            "distill": routing.distill_model_id,
            "reason": routing.reason_model_id,
            "audit": routing.audit_model_id,
            "embed": routing.embed_model_id,
        }
        model_id = col_map.get(role)
        if not model_id:
            return get_llm()

        # embed 角色走独立的 EmbedProvider → EmbedModel 路径
        if role == "embed":
            embed_model = db.query(EmbedModel).filter(
                EmbedModel.id == model_id, EmbedModel.is_active == True
            ).first()
            if not embed_model:
                return get_llm()
            embed_provider = db.query(EmbedProvider).filter(
                EmbedProvider.id == embed_model.provider_id, EmbedProvider.is_active == True
            ).first()
            if not embed_provider:
                return get_llm()
            return create_llm_from_embed(embed_model, embed_provider)

        # LLM 角色走 LlmProvider → LlmModel 路径
        model_obj = db.query(LlmModel).filter(
            LlmModel.id == model_id, LlmModel.is_active == True
        ).first()
        if not model_obj:
            return get_llm()

        provider = db.query(LlmProvider).filter(
            LlmProvider.id == model_obj.provider_id, LlmProvider.is_active == True
        ).first()
        if not provider:
            return get_llm()

        return create_llm_from_model(model_obj, provider)
    except Exception:
        return get_llm()
