"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=6, max_length=100)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    avatar: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RssSourceCreate(BaseModel):
    name: str
    url: str
    category: str = "tech"


class RssSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class RssSourceOut(BaseModel):
    id: int
    name: str
    url: str
    category: str
    is_active: bool
    last_crawled: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ArticleOut(BaseModel):
    id: int
    title: str
    content: str = ""
    summary: str = ""
    source_url: str = ""
    keywords: list = []
    entities: list = []
    rss_source_id: Optional[int] = None
    rss_source_name: str = ""
    credibility_score: float = 0.0
    pipeline_state: str = "raw"
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: int
    title: str
    summary: str = ""
    category: str = ""
    importance: int = 3
    status: str = "active"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    article_count: int = 0
    follow_count: int = 0
    is_followed: bool = False

    model_config = {"from_attributes": True}


class EventDetail(EventOut):
    articles: list[ArticleOut] = []
    timeline: list["TimelinePhase"] = []


class TimelinePhase(BaseModel):
    """事件时间线中的阶段（起因/经过/结果）。"""
    phase: str  # trigger | development | outcome | followup
    phase_label: str  # 起因 | 经过 | 结果 | 后续
    date: Optional[str] = None
    articles: list[ArticleOut] = []


class CategoryItem(BaseModel):
    name: str
    count: int


class FollowOut(BaseModel):
    event_id: int
    event_title: str
    event_status: str
    followed_at: Optional[datetime] = None


class AdminStats(BaseModel):
    total_users: int
    total_articles: int
    total_events: int
    active_events: int
    total_sources: int
    articles_today: int


class PageResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseModel):
    message: str


class MergeEventsRequest(BaseModel):
    source_id: int
    target_id: int


class AssignArticleRequest(BaseModel):
    event_id: int


class UpdateEventRequest(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    importance: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=6, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


# ─── LLM 供应商管理 ─────────────────────────────────────

class LlmProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    api_base: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1, max_length=500)


class LlmProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None


class LlmModelOut(BaseModel):
    id: int
    provider_id: int
    name: str
    model: str
    temperature: float
    top_p: float
    max_tokens: int
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LlmProviderOut(BaseModel):
    id: int
    name: str
    api_base: str
    api_key_set: bool
    is_active: bool
    created_at: Optional[datetime] = None
    models: list[LlmModelOut] = []

    model_config = {"from_attributes": True}


class LlmModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    top_p: float = Field(0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(300, ge=1, le=32000)


class LlmModelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    is_active: Optional[bool] = None


class LlmModelItem(BaseModel):
    """从 API /models 端点获取的可用模型条目。"""
    id: str
    owned_by: str = ""


class LlmRoutingOut(BaseModel):
    distill_model_id: Optional[int] = None
    distill_model_name: Optional[str] = None
    distill_provider_name: Optional[str] = None
    reason_model_id: Optional[int] = None
    reason_model_name: Optional[str] = None
    reason_provider_name: Optional[str] = None
    audit_model_id: Optional[int] = None
    audit_model_name: Optional[str] = None
    audit_provider_name: Optional[str] = None
    embed_model_id: Optional[int] = None
    embed_model_name: Optional[str] = None
    embed_provider_name: Optional[str] = None


class LlmRoutingUpdate(BaseModel):
    distill_model_id: Optional[int] = None
    reason_model_id: Optional[int] = None
    audit_model_id: Optional[int] = None
    embed_model_id: Optional[int] = None


# ─── 向量模型供应商管理 ─────────────────────────────────────

class EmbedProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    api_base: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1, max_length=500)


class EmbedProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None


class EmbedModelOut(BaseModel):
    id: int
    provider_id: int
    name: str
    model: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EmbedProviderOut(BaseModel):
    id: int
    name: str
    api_base: str
    api_key_set: bool
    is_active: bool
    created_at: Optional[datetime] = None
    models: list[EmbedModelOut] = []

    model_config = {"from_attributes": True}


class EmbedModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)


class EmbedModelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    model: Optional[str] = None
    is_active: Optional[bool] = None


# ─── 管线统计 ─────────────────────────────────────────────

class PipelineStats(BaseModel):
    """管线各阶段统计数据，供可视化页面使用。"""
    raw: int = 0
    distilled: int = 0
    reasoned: int = 0
    audited: int = 0
    safe_mode: int = 0
    active_events: int = 0
    resolved_events: int = 0
    audit_pass: int = 0
    audit_manual_review: int = 0
    total_articles: int = 0
    total_events: int = 0


# ─── 审计日志 ─────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: int
    article_id: int
    event_id: Optional[int] = None
    stage: str
    status: str
    confidence: float
    entity_check: Optional[dict] = None
    issues: Optional[list] = None
    raw_snapshot: Optional[dict] = None
    result_snapshot: Optional[dict] = None
    created_at: Optional[datetime] = None
    # 关联信息
    article_title: str = ""
    event_title: str = ""

    model_config = {"from_attributes": True}


# ─── 蒸馏产物 ─────────────────────────────────────────────

class DistillationOut(BaseModel):
    """蒸馏结果 — 每篇文章一条记录。"""
    id: int
    article_id: int
    facts: list = []
    core_entities: list = []
    key_numbers: list = []
    primary_action: str = ""
    summary_line: str = ""
    confidence: float = 0.0
    model_used: str = ""
    is_llm_generated: bool = False
    processing_time_ms: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── 推演产物 ─────────────────────────────────────────────

class ReasoningOut(BaseModel):
    """推演结果 — 每篇文章一条记录。"""
    id: int
    article_id: int
    distillation_id: Optional[int] = None
    action: str = "new"
    target_event_id: Optional[int] = None
    target_event_title: str = ""
    phase: str = "trigger"
    suggested_category: str = ""
    suggested_importance: int = 3
    event_title: str = ""
    event_summary: str = ""
    has_conflict: bool = False
    conflict_details: str = ""
    confidence: float = 0.0
    needs_review: bool = False
    safe_mode: bool = False
    model_used: str = ""
    processing_time_ms: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ArticlePipelineData(BaseModel):
    """单篇文章的完整管线数据（原始 → 蒸馏 → 推演 → 审计）。"""
    article: ArticleOut
    distillation: Optional[DistillationOut] = None
    reasoning: Optional[ReasoningOut] = None
    audit_logs: list[AuditLogOut] = []
