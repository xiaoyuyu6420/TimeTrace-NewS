"""ORM models with SQLAlchemy declarative base."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer,
    JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), default="user")
    avatar = Column(String(256), default="")
    created_at = Column(DateTime, default=_now)

    follows = relationship("UserFollow", back_populates="user", cascade="all, delete-orphan")


class RssSource(Base):
    __tablename__ = "rss_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    category = Column(String(50), default="tech")
    is_active = Column(Boolean, default=True)
    last_crawled = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    credibility_tier = Column(String(1), default="C")
    source_reputation = Column(Float, default=50.0)

    articles = relationship("Article", back_populates="rss_source")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, default="")
    summary = Column(Text, default="")
    source_url = Column(String(500), default="")
    rss_source_id = Column(Integer, ForeignKey("rss_sources.id"), nullable=True)
    keywords = Column(JSON, default=list)
    entities = Column(JSON, default=list)
    embedding = Column(JSON, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    credibility_score = Column(Float, default=0.0)
    credibility_factors = Column(JSON, nullable=True)
    duplicate_of = Column(Integer, ForeignKey("articles.id"), nullable=True)
    is_duplicate = Column(Boolean, default=False)

    # ─── 管线状态 ───
    pipeline_state = Column(String(20), default="raw")
    # raw → distilled → reasoned → audited → safe_mode
    distilled_facts = Column(JSON, nullable=True)
    reasoning_result = Column(JSON, nullable=True)

    rss_source = relationship("RssSource", back_populates="articles")
    event_links = relationship("EventArticle", back_populates="article", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text, default="")
    category = Column(String(50), default="")
    importance = Column(Integer, default=3)
    status = Column(String(20), default="active")
    embedding = Column(JSON, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    last_enhanced_at = Column(DateTime, nullable=True)

    article_links = relationship("EventArticle", back_populates="event", cascade="all, delete-orphan")
    follows = relationship("UserFollow", back_populates="event", cascade="all, delete-orphan")


class EventArticle(Base):
    __tablename__ = "event_articles"

    event_id = Column(Integer, ForeignKey("events.id"), primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), primary_key=True)
    relevance_score = Column(Float, default=0.0)
    phase = Column(String(20), default="development")

    event = relationship("Event", back_populates="article_links")
    article = relationship("Article", back_populates="event_links")


class UserFollow(Base):
    __tablename__ = "user_follows"
    __table_args__ = (UniqueConstraint("user_id", "event_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="follows")
    event = relationship("Event", back_populates="follows")


class AuditLog(Base):
    """审计日志 — 记录每条新闻处理过程中的审计结果。"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    stage = Column(String(20), nullable=False)
    # distill | reason | audit
    status = Column(String(20), nullable=False)
    # pass | fail | manual_review | safe_mode
    confidence = Column(Float, default=1.0)
    # 0.0~1.0 置信度
    entity_check = Column(JSON, nullable=True)
    # {"matched": [...], "unmatched": [...], "missing": [...]}
    issues = Column(JSON, nullable=True)
    # ["实体不匹配: ...", "数值冲突: ..."]
    raw_snapshot = Column(JSON, nullable=True)
    # 原始数据快照（标题+关键实体）
    result_snapshot = Column(JSON, nullable=True)
    # 处理后数据快照
    created_at = Column(DateTime, default=_now)

    article = relationship("Article")
    event = relationship("Event")


class ArticleDistillation(Base):
    """蒸馏产物 — 每篇文章一条记录，独立于原始数据。"""
    __tablename__ = "article_distillations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), unique=True, nullable=False)
    facts = Column(JSON, default=list)                    # 原子事实列表
    core_entities = Column(JSON, default=list)            # 核心实体
    key_numbers = Column(JSON, default=list)              # 关键数值
    primary_action = Column(Text, default="")             # 主要动作词
    summary_line = Column(Text, default="")               # 一句话摘要
    confidence = Column(Float, default=0.0)               # 整体置信度
    model_used = Column(Text, default="")                 # 使用的 LLM 模型名
    is_llm_generated = Column(Boolean, default=False)     # 是否由 LLM 生成
    processing_time_ms = Column(Integer, default=0)       # 处理耗时
    created_at = Column(DateTime, default=_now)

    article = relationship("Article")


class ArticleReasoning(Base):
    """推演产物 — 每篇文章一条记录，独立于原始数据。"""
    __tablename__ = "article_reasonings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), unique=True, nullable=False)
    distillation_id = Column(Integer, ForeignKey("article_distillations.id"), nullable=True)
    action = Column(String(20), default="new")            # link | new | skip
    target_event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    target_event_title = Column(Text, default="")
    phase = Column(String(20), default="trigger")         # trigger | development | outcome | followup
    suggested_category = Column(String(50), default="")
    suggested_importance = Column(Integer, default=3)
    event_title = Column(Text, default="")
    event_summary = Column(Text, default="")
    has_conflict = Column(Boolean, default=False)
    conflict_details = Column(Text, default="")
    confidence = Column(Float, default=0.0)
    needs_review = Column(Boolean, default=False)
    safe_mode = Column(Boolean, default=False)
    model_used = Column(Text, default="")
    processing_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)

    article = relationship("Article")
    distillation = relationship("ArticleDistillation")
    target_event = relationship("Event")


class LlmProvider(Base):
    """LLM 供应商 — API 端点 + 密钥。一个供应商下可有多个模型。"""
    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)           # 供应商名，如"智谱AI"
    api_base = Column(String(500), nullable=False)       # OpenAI 兼容 base_url
    api_key = Column(String(500), nullable=False)        # API Key
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)

    models = relationship("LlmModel", back_populates="provider", cascade="all, delete-orphan")


class LlmModel(Base):
    """LLM 模型 — 属于某个供应商下的对话模型配置。"""
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, ForeignKey("llm_providers.id"), nullable=False)
    name = Column(String(100), nullable=False)           # 显示名，如"GLM-4-Flash"
    model = Column(String(200), nullable=False)          # 实际模型 ID，如 glm-4-flash
    temperature = Column(Float, default=0.3)
    top_p = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=300)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)

    provider = relationship("LlmProvider", back_populates="models")


class EmbedProvider(Base):
    """向量模型供应商 — 与 LLM 供应商完全独立。"""
    __tablename__ = "embed_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    api_base = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)

    models = relationship("EmbedModel", back_populates="provider", cascade="all, delete-orphan")


class EmbedModel(Base):
    """向量模型 — 属于某个 Embedding 供应商。"""
    __tablename__ = "embed_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, ForeignKey("embed_providers.id"), nullable=False)
    name = Column(String(100), nullable=False)           # 显示名，如"BGE-M3"
    model = Column(String(200), nullable=False)          # 实际模型 ID，如 BAAI/bge-m3
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)

    provider = relationship("EmbedProvider", back_populates="models")


class LlmRouting(Base):
    """LLM 编排 — 指定哪个模型做哪个任务。"""
    __tablename__ = "llm_routing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 拆解层（Distiller）用的 LLM 模型
    distill_model_id = Column(Integer, ForeignKey("llm_models.id"), nullable=True)
    # 推演层（ReasoningEngine）用的 LLM 模型
    reason_model_id = Column(Integer, ForeignKey("llm_models.id"), nullable=True)
    # 审计层（Auditor）用的 LLM 模型
    audit_model_id = Column(Integer, ForeignKey("llm_models.id"), nullable=True)
    # Embedding 用的向量模型（独立表）
    embed_model_id = Column(Integer, ForeignKey("embed_models.id"), nullable=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    distill_model = relationship("LlmModel", foreign_keys=[distill_model_id])
    reason_model = relationship("LlmModel", foreign_keys=[reason_model_id])
    audit_model = relationship("LlmModel", foreign_keys=[audit_model_id])
    embed_model = relationship("EmbedModel", foreign_keys=[embed_model_id])
