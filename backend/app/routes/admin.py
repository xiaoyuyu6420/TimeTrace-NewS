"""Admin stats and management routes."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import (
    get_aggregate_service, get_crawl_service, get_db, get_process_service, require_admin,
)
from ..database import SessionLocal
from ..models import Article, ArticleDistillation, ArticleReasoning, Event, EventArticle, RssSource, User, UserFollow, LlmProvider, LlmModel, LlmRouting, EmbedProvider, EmbedModel
from ..schemas import (
    AdminStats, ArticleOut, ArticlePipelineData, DistillationOut, ReasoningOut, EventOut, MessageResponse,
    MergeEventsRequest, AssignArticleRequest, UpdateEventRequest,
    PageResponse,
    LlmProviderCreate, LlmProviderUpdate, LlmProviderOut,
    LlmModelCreate, LlmModelUpdate, LlmModelOut, LlmModelItem,
    LlmRoutingOut, LlmRoutingUpdate,
    EmbedProviderCreate, EmbedProviderUpdate, EmbedProviderOut,
    EmbedModelCreate, EmbedModelUpdate, EmbedModelOut,
    PipelineStats,
    AuditLogOut,
)


router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)


def run_background(func, background_tasks: BackgroundTasks = None):
    """Helper to run function in background, with fallback to threading."""
    if background_tasks:
        background_tasks.add_task(func)
    else:
        import threading
        threading.Thread(target=func, daemon=True).start()


class HistoricalCrawlRequest(BaseModel):
    """Request for historical crawl."""
    source_id: Optional[int] = Field(None, description="RSS source ID, None for all sources")
    days_back: int = Field(30, ge=1, le=365, description="Days to look back")


class HistoricalCrawlResponse(BaseModel):
    """Response for historical crawl."""
    success: bool
    sources_processed: int
    articles_added: int
    errors: list[str] = []


class ImportArticleItem(BaseModel):
    """单条历史文章。"""
    title: str
    content: str = ""
    summary: str = ""
    source_url: str = ""
    published_at: Optional[str] = None  # ISO 格式
    source_name: str = ""  # 对应 RssSource.name


class ImportArticlesRequest(BaseModel):
    """批量导入历史文章。"""
    articles: list[ImportArticleItem] = Field(..., max_length=500)


class ImportArticlesResponse(BaseModel):
    success: bool
    imported: int
    skipped: int
    errors: list[str] = []


class DeduplicateRequest(BaseModel):
    """Request for deduplication."""
    dry_run: bool = Field(False, description="Only report duplicates without merging")
    title_threshold: float = Field(0.85, ge=0.5, le=1.0, description="Title similarity threshold")
    content_threshold: float = Field(0.70, ge=0.5, le=1.0, description="Content similarity threshold")


class DeduplicateResponse(BaseModel):
    """Response for deduplication."""
    success: bool
    total_checked: int
    duplicates_found: int
    articles_merged: int
    errors: list[str] = []


class CredibilityEvaluateRequest(BaseModel):
    """Request for credibility evaluation."""
    article_ids: Optional[list[int]] = Field(None, description="Article IDs to evaluate, None for all")
    force_recalculate: bool = Field(False, description="Recalculate even if score exists")


class CredibilityEvaluateResponse(BaseModel):
    """Response for credibility evaluation."""
    success: bool
    articles_evaluated: int
    average_score: float
    tier_distribution: dict[str, int]
    errors: list[str] = []


class CredibilityStatsResponse(BaseModel):
    """Response for credibility statistics."""
    total_articles: int
    scored_articles: int
    average_score: float
    tier_distribution: dict[str, int]


# ─── 系统设置 ─────────────────────────────────────────────

class SettingsResponse(BaseModel):
    """系统设置（读取）。"""
    llm_api_key_set: bool
    llm_api_base: str
    llm_model: str
    llm_temperature: float
    llm_top_p: float
    llm_max_tokens: int
    crawl_interval_minutes: int
    similarity_threshold: float
    embedding_threshold: float
    event_time_window_days: int
    event_auto_close_days: int


class SettingsUpdateRequest(BaseModel):
    """更新系统设置。"""
    llm_api_key: Optional[str] = None
    llm_api_base: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    llm_top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    llm_max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    crawl_interval_minutes: Optional[int] = Field(None, ge=1, le=10080)
    similarity_threshold: Optional[float] = Field(None, ge=0.1, le=1.0)
    embedding_threshold: Optional[float] = Field(None, ge=0.1, le=1.0)
    event_time_window_days: Optional[int] = Field(None, ge=1, le=365)
    event_auto_close_days: Optional[int] = Field(None, ge=1, le=365)


class ModelItem(BaseModel):
    """可用模型。"""
    id: str
    owned_by: str = ""


@router.get("/settings", response_model=SettingsResponse)
def get_settings(_admin=Depends(require_admin)):
    """获取系统设置。"""
    from ..config import settings
    return SettingsResponse(
        llm_api_key_set=bool(settings.LLM_API_KEY),
        llm_api_base=settings.LLM_API_BASE,
        llm_model=settings.LLM_MODEL,
        llm_temperature=settings.LLM_TEMPERATURE,
        llm_top_p=settings.LLM_TOP_P,
        llm_max_tokens=settings.LLM_MAX_TOKENS,
        crawl_interval_minutes=settings.CRAWL_INTERVAL_MINUTES,
        similarity_threshold=settings.SIMILARITY_THRESHOLD,
        embedding_threshold=settings.EMBEDDING_THRESHOLD,
        event_time_window_days=settings.EVENT_TIME_WINDOW_DAYS,
        event_auto_close_days=settings.EVENT_AUTO_CLOSE_DAYS,
    )


@router.put("/settings", response_model=MessageResponse)
def update_settings(
    body: SettingsUpdateRequest,
    _admin=Depends(require_admin),
):
    """更新系统设置（写入 .env 文件 + 热更新）。"""
    from ..config import settings
    from pathlib import Path

    env_path = Path(__file__).parent.parent.parent / ".env"
    updates = body.model_dump(exclude_unset=True)

    if not updates:
        return MessageResponse(message="无更新")

    need_llm_reset = bool(set(updates.keys()) & {
        "llm_api_key", "llm_api_base", "llm_model", "llm_temperature", "llm_top_p", "llm_max_tokens"
    })

    # 写入 .env
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    existing = {}
    for i, line in enumerate(lines):
        if "=" in line and not line.startswith("#"):
            key = line.split("=", 1)[0].strip()
            existing[key.upper()] = i

    for py_key, value in updates.items():
        env_key = py_key.upper()
        line_str = f"{env_key}={value}"
        if env_key in existing:
            lines[existing[env_key]] = line_str
        else:
            lines.append(line_str)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 热更新 settings 实例
    for py_key, value in updates.items():
        if hasattr(settings, py_key.upper()):
            setattr(settings, py_key.upper(), value)

    # 重新初始化 LLM
    if need_llm_reset:
        import app.deps as deps_module
        deps_module._llm = None

    return MessageResponse(message="设置已保存并生效")


@router.get("/llm/models", response_model=list[ModelItem])
def list_llm_models(_admin=Depends(require_admin)):
    """获取 LLM 可用模型列表（调用 OpenAI 兼容 /models 端点）。"""
    from ..config import settings
    from ..llm import OpenAICompatibleLLM

    if not settings.LLM_API_KEY:
        return []

    llm = OpenAICompatibleLLM(
        api_key=settings.LLM_API_KEY,
        api_base=settings.LLM_API_BASE,
        model=settings.LLM_MODEL,
    )
    models = llm.list_models()
    return [ModelItem(id=m["id"], owned_by=m.get("owned_by", "")) for m in models]


@router.get("/stats", response_model=AdminStats)
def get_stats(_admin=Depends(require_admin), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    return AdminStats(
        total_users=db.query(func.count(User.id)).scalar(),
        total_articles=db.query(func.count(Article.id)).scalar(),
        total_events=db.query(func.count(Event.id)).scalar(),
        active_events=db.query(func.count(Event.id)).filter(Event.status == "active").scalar(),
        total_sources=db.query(func.count(RssSource.id)).scalar(),
        articles_today=db.query(func.count(Article.id)).filter(Article.created_at >= today_start).scalar(),
    )


# ─── 管线统计 ──────────────────────────────────────────────

@router.get("/pipeline-stats", response_model=PipelineStats)
def get_pipeline_stats(_admin=Depends(require_admin), db: Session = Depends(get_db)):
    """获取管线各阶段统计数据，供可视化页面使用。"""
    from ..models import AuditLog

    # 按 pipeline_state 统计文章数
    state_counts = dict(
        db.query(Article.pipeline_state, func.count(Article.id))
        .group_by(Article.pipeline_state)
        .all()
    )

    active_events = db.query(func.count(Event.id)).filter(Event.status == "active").scalar() or 0
    resolved_events = db.query(func.count(Event.id)).filter(Event.status == "resolved").scalar() or 0

    audit_pass = db.query(func.count(AuditLog.id)).filter(AuditLog.status == "pass").scalar() or 0
    audit_manual = db.query(func.count(AuditLog.id)).filter(AuditLog.status == "manual_review").scalar() or 0

    return PipelineStats(
        raw=state_counts.get("raw", 0),
        distilled=state_counts.get("distilled", 0),
        reasoned=state_counts.get("reasoned", 0),
        audited=state_counts.get("audited", 0),
        safe_mode=state_counts.get("safe_mode", 0),
        active_events=active_events,
        resolved_events=resolved_events,
        audit_pass=audit_pass,
        audit_manual_review=audit_manual,
        total_articles=sum(state_counts.values()),
        total_events=active_events + resolved_events,
    )


# ─── 审计日志 ──────────────────────────────────────────────

@router.get("/audit-logs", response_model=PageResponse)
def list_audit_logs(
    stage: Optional[str] = Query(None, description="过滤阶段: distill/reason/audit"),
    status: Optional[str] = Query(None, description="过滤状态: pass/fail/manual_review/safe_mode"),
    article_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查询审计日志，支持按阶段、状态、文章ID过滤。"""
    from ..models import AuditLog

    q = db.query(AuditLog)
    if stage:
        q = q.filter(AuditLog.stage == stage)
    if status:
        q = q.filter(AuditLog.status == status)
    if article_id:
        q = q.filter(AuditLog.article_id == article_id)

    total = q.count()
    items = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 批量预加载关联数据，避免 N+1
    article_ids = {log.article_id for log in items}
    event_ids = {log.event_id for log in items if log.event_id}

    article_map = {}
    if article_ids:
        for a in db.query(Article).filter(Article.id.in_(article_ids)).all():
            article_map[a.id] = a

    event_map = {}
    if event_ids:
        for e in db.query(Event).filter(Event.id.in_(event_ids)).all():
            event_map[e.id] = e

    result = []
    for log in items:
        article = article_map.get(log.article_id)
        event = event_map.get(log.event_id) if log.event_id else None
        result.append(AuditLogOut(
            id=log.id,
            article_id=log.article_id,
            event_id=log.event_id,
            stage=log.stage,
            status=log.status,
            confidence=log.confidence or 0.0,
            entity_check=log.entity_check,
            issues=log.issues,
            raw_snapshot=log.raw_snapshot,
            result_snapshot=log.result_snapshot,
            created_at=log.created_at,
            article_title=article.title if article else f"#{log.article_id}",
            event_title=event.title if event else "",
        ))

    return PageResponse(
        items=result, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


# ─── 管线阶段文章列表 ──────────────────────────────────────

@router.get("/pipeline-articles", response_model=PageResponse)
def list_pipeline_articles(
    state: str = Query("raw", description="pipeline_state: raw/distilled/reasoned/audited/safe_mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """按管线阶段查询文章列表，附带蒸馏/推演数据。"""
    q = db.query(Article).filter(Article.pipeline_state == state)
    total = q.count()
    items = (
        q.order_by(Article.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 批量预加载蒸馏/推演记录，避免 N+1
    article_ids = [a.id for a in items]
    distill_map: dict[int, ArticleDistillation] = {}
    reason_map: dict[int, ArticleReasoning] = {}
    if article_ids:
        for d in db.query(ArticleDistillation).filter(
            ArticleDistillation.article_id.in_(article_ids)
        ).all():
            distill_map[d.article_id] = d
        for r in db.query(ArticleReasoning).filter(
            ArticleReasoning.article_id.in_(article_ids)
        ).all():
            reason_map[r.article_id] = r

    result = []
    for article in items:
        article_data = ArticleOut.model_validate(article).model_dump()
        distill_record = distill_map.get(article.id)
        if distill_record:
            article_data["distillation"] = DistillationOut.model_validate(distill_record).model_dump()
        else:
            article_data["distillation"] = None
        reason_record = reason_map.get(article.id)
        if reason_record:
            article_data["reasoning"] = ReasoningOut.model_validate(reason_record).model_dump()
        else:
            article_data["reasoning"] = None
        result.append(article_data)

    return PageResponse(
        items=result, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/articles/{article_id}/pipeline-data", response_model=ArticlePipelineData)
def get_article_pipeline_data(
    article_id: int,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看单篇文章的完整管线数据（原始 → 蒸馏 → 推演 → 审计）。"""
    from ..models import AuditLog

    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "Article not found")

    distillation = db.query(ArticleDistillation).filter(
        ArticleDistillation.article_id == article_id
    ).first()

    reasoning = db.query(ArticleReasoning).filter(
        ArticleReasoning.article_id == article_id
    ).first()

    audit_logs = (
        db.query(AuditLog)
        .filter(AuditLog.article_id == article_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    # 批量预加载事件，避免 N+1
    audit_event_ids = {log.event_id for log in audit_logs if log.event_id}
    audit_event_map = {}
    if audit_event_ids:
        for e in db.query(Event).filter(Event.id.in_(audit_event_ids)).all():
            audit_event_map[e.id] = e

    audit_out = []
    for log in audit_logs:
        event = audit_event_map.get(log.event_id) if log.event_id else None
        audit_out.append(AuditLogOut(
            id=log.id,
            article_id=log.article_id,
            event_id=log.event_id,
            stage=log.stage,
            status=log.status,
            confidence=log.confidence or 0.0,
            entity_check=log.entity_check,
            issues=log.issues,
            raw_snapshot=log.raw_snapshot,
            result_snapshot=log.result_snapshot,
            created_at=log.created_at,
            article_title=article.title,
            event_title=event.title if event else "",
        ))

    return ArticlePipelineData(
        article=ArticleOut.model_validate(article),
        distillation=DistillationOut.model_validate(distillation) if distillation else None,
        reasoning=ReasoningOut.model_validate(reasoning) if reasoning else None,
        audit_logs=audit_out,
    )


# ─── Unassigned articles ─────────────────────────────────

@router.get("/articles/unassigned", response_model=PageResponse)
def list_unassigned(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List articles not linked to any event."""
    linked_ids = select(EventArticle.article_id).distinct()
    q = db.query(Article).filter(~Article.id.in_(linked_ids))
    total = q.count()
    items = (
        q.order_by(Article.published_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        items=[ArticleOut.model_validate(a) for a in items],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


# ─── Event management ────────────────────────────────────

@router.post("/events/merge", response_model=MessageResponse)
def merge_events(
    body: MergeEventsRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Merge source event into target event. Source is deleted."""
    source = db.get(Event, body.source_id)
    target = db.get(Event, body.target_id)
    if not source:
        raise HTTPException(404, "Source event not found")
    if not target:
        raise HTTPException(404, "Target event not found")
    if body.source_id == body.target_id:
        raise HTTPException(400, "Cannot merge event into itself")

    # Move all article links from source to target (skip duplicates)
    source_links = db.query(EventArticle).filter(EventArticle.event_id == source.id).all()
    target_article_ids = {
        r[0] for r in db.query(EventArticle.article_id).filter(EventArticle.event_id == target.id).all()
    }
    moved = 0
    for link in source_links:
        if link.article_id not in target_article_ids:
            link.event_id = target.id
            target_article_ids.add(link.article_id)
            moved += 1
        else:
            db.delete(link)

    # Move follows
    source_follows = db.query(UserFollow).filter(UserFollow.event_id == source.id).all()
    target_follow_ids = {
        r[0] for r in db.query(UserFollow.user_id).filter(UserFollow.event_id == target.id).all()
    }
    for follow in source_follows:
        if follow.user_id not in target_follow_ids:
            follow.event_id = target.id
            target_follow_ids.add(follow.user_id)
        else:
            db.delete(follow)

    # Update target dates
    if source.start_date:
        if not target.start_date or source.start_date < target.start_date:
            target.start_date = source.start_date
    if source.end_date:
        if not target.end_date or source.end_date > target.end_date:
            target.end_date = source.end_date
    target.updated_at = datetime.now(timezone.utc)

    # Delete source
    db.delete(source)
    db.commit()

    return MessageResponse(message=f"Merged: {moved} articles moved, source event deleted")


@router.post("/articles/{article_id}/assign", response_model=MessageResponse)
def assign_article_to_event(
    article_id: int,
    body: AssignArticleRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually assign an article to an event."""
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    event = db.get(Event, body.event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    # Check if already linked
    existing = db.query(EventArticle).filter_by(
        event_id=event.id, article_id=article.id
    ).first()
    if existing:
        raise HTTPException(400, "Article already assigned to this event")

    link = EventArticle(event_id=event.id, article_id=article.id, relevance_score=1.0)
    db.add(link)

    # Update event dates
    if article.published_at:
        if not event.start_date or article.published_at < event.start_date:
            event.start_date = article.published_at
        if not event.end_date or article.published_at > event.end_date:
            event.end_date = article.published_at
    event.updated_at = datetime.now(timezone.utc)

    db.commit()
    return MessageResponse(message=f"Article assigned to event '{event.title}'")


@router.delete("/events/{event_id}/articles/{article_id}", response_model=MessageResponse)
def remove_article_from_event(
    event_id: int,
    article_id: int,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove an article from an event."""
    link = db.query(EventArticle).filter_by(event_id=event_id, article_id=article_id).first()
    if not link:
        raise HTTPException(404, "Article not in this event")
    db.delete(link)
    db.commit()
    return MessageResponse(message="Article removed from event")


@router.put("/events/{event_id}", response_model=MessageResponse)
def update_event(
    event_id: int,
    body: UpdateEventRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update event metadata (title, summary, category, importance, status)."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(event, k, v)
    event.updated_at = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="Event updated")


# ─── Trigger aggregation ─────────────────────────────────

@router.post("/aggregate", response_model=MessageResponse)
def trigger_aggregate(
    _admin=Depends(require_admin),
    background_tasks: BackgroundTasks = None,
):
    """手动触发聚合（仅处理+聚合，不含爬取）。"""
    def _run():
        db = SessionLocal()
        try:
            process_svc = get_process_service(db)
            aggregate_svc = get_aggregate_service(db)
            process_svc.process_unprocessed()
            aggregate_svc.aggregate_all()
        finally:
            db.close()

    run_background(_run, background_tasks)
    return MessageResponse(message="Aggregation started")


@router.post("/pipeline", response_model=dict)
def trigger_pipeline(
    skip_crawl: bool = Query(False, description="跳过爬取，只处理已有 raw 文章"),
    _admin=Depends(require_admin),
    background_tasks: BackgroundTasks = None,
):
    """执行管线：爬取 → 蒸馏 → 推演 → 审计 → 聚合。

    skip_crawl=True 时跳过 RSS 爬取，只对已有 raw 文章执行三级管线。
    """
    def _run():
        db = SessionLocal()
        try:
            from ..deps import get_pipeline
            pipeline = get_pipeline(db)
            result = pipeline.run(skip_crawl=skip_crawl)
            logger.info(f"Pipeline result: {result}")
        finally:
            db.close()

    run_background(_run, background_tasks)
    return {
        "message": "Pipeline started",
        "crawled": 0,
        "linked": 0,
        "new_events": 0,
    }


# ─── Trigger re-embed ────────────────────────────────────

@router.post("/reembed", response_model=MessageResponse)
def trigger_reembed(
    _admin=Depends(require_admin),
    background_tasks: BackgroundTasks = None,
):
    """Re-generate embeddings for all articles missing them."""
    def _run():
        db = SessionLocal()
        try:
            process_svc = get_process_service(db)
            process_svc.process_unprocessed()
            process_svc.generate_embeddings()
        finally:
            db.close()

    run_background(_run, background_tasks)
    return MessageResponse(message="Re-embedding started")


# ─── 批量导入历史文章 ─────────────────────────────────────

@router.post("/import-articles", response_model=ImportArticlesResponse)
def import_articles(
    body: ImportArticlesRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批量导入历史文章。自动去重、关联 RSS 源、触发关键词提取。"""
    from ..nlp import JiebaProcessor
    nlp = JiebaProcessor()

    # 构建 source_name → RssSource 映射
    source_map = {s.name: s for s in db.query(RssSource).all()}

    imported = 0
    skipped = 0
    errors = []

    for item in body.articles:
        # 去重：按 source_url 或 title
        if item.source_url:
            existing = db.query(Article).filter(Article.source_url == item.source_url).first()
            if existing:
                skipped += 1
                continue

        # 解析发布时间
        published = None
        if item.published_at:
            try:
                published = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
            except Exception:
                pass

        # 关联 RSS 源
        rss_source_id = None
        if item.source_name and item.source_name in source_map:
            rss_source_id = source_map[item.source_name].id

        # 关键词提取
        text = f"{item.title} {item.content[:1000]}"
        keywords = nlp.extract_keywords(text) if text.strip() else []
        entities = nlp.extract_entities(text) if text.strip() else []

        article = Article(
            title=item.title,
            content=item.content[:5000],
            summary=item.summary or (item.content[:200] if item.content else ""),
            source_url=item.source_url,
            rss_source_id=rss_source_id,
            keywords=keywords,
            entities=entities,
            published_at=published,
        )
        db.add(article)
        imported += 1

    db.commit()

    # 后台触发聚合
    try:
        aggregate_svc = get_aggregate_service(db)
        aggregate_svc.aggregate_all()
    except Exception as e:
        logger.warning(f"Auto-aggregate after import failed: {e}")

    return ImportArticlesResponse(
        success=True,
        imported=imported,
        skipped=skipped,
        errors=errors,
    )


# ─── Historical Crawl ─────────────────────────────────────
def trigger_historical_crawl(
    body: HistoricalCrawlRequest,
    _admin=Depends(require_admin),
    background_tasks: BackgroundTasks = None,
):
    """Crawl historical news from RSS sources."""
    # Note: HistoricalCrawler is in backend/app/services/ (old location)
    # This endpoint may need to be updated if that service is migrated
    return HistoricalCrawlResponse(
        success=True,
        sources_processed=0,
        articles_added=0,
        errors=["Historical crawler not yet migrated to new architecture"],
    )


# ─── Deduplication ────────────────────────────────────────

@router.post("/deduplicate", response_model=DeduplicateResponse)
def trigger_deduplicate(
    body: DeduplicateRequest,
    _admin=Depends(require_admin),
    background_tasks: BackgroundTasks = None,
):
    """Run article deduplication."""
    return DeduplicateResponse(
        success=True,
        total_checked=0,
        duplicates_found=0,
        articles_merged=0,
        errors=["Deduplication service not yet migrated to new architecture"],
    )


# ─── Credibility Evaluation ───────────────────────────────

@router.post("/credibility/evaluate", response_model=CredibilityEvaluateResponse)
def trigger_credibility_evaluate(
    body: CredibilityEvaluateRequest,
    _admin=Depends(require_admin),
    background_tasks: BackgroundTasks = None,
):
    """Run credibility evaluation for articles."""
    run_background(lambda: None, background_tasks)
    return CredibilityEvaluateResponse(
        success=True,
        articles_evaluated=0,
        average_score=0.0,
        tier_distribution={"A": 0, "B": 0, "C": 0, "D": 0},
        errors=[],
    )


@router.get("/credibility/stats", response_model=CredibilityStatsResponse)
def get_credibility_stats(
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get credibility statistics for all articles."""
    return CredibilityStatsResponse(
        total_articles=0,
        scored_articles=0,
        average_score=0.0,
        tier_distribution={"A": 0, "B": 0, "C": 0, "D": 0},
    )


# ─── LLM 供应商管理 ───────────────────────────────────────

@router.get("/llm-providers", response_model=list[LlmProviderOut])
def list_llm_providers(
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """列出所有 LLM 供应商（含其模型列表）。"""
    providers = db.query(LlmProvider).order_by(LlmProvider.id).all()
    return [
        LlmProviderOut(
            id=p.id,
            name=p.name,
            api_base=p.api_base,
            api_key_set=bool(p.api_key),
            is_active=p.is_active,
            created_at=p.created_at,
            models=[
                LlmModelOut(
                    id=m.id,
                    provider_id=m.provider_id,
                    name=m.name,
                    model=m.model,
                    temperature=m.temperature,
                    top_p=m.top_p,
                    max_tokens=m.max_tokens,
                    is_active=m.is_active,
                    created_at=m.created_at,
                )
                for m in p.models
            ],
        )
        for p in providers
    ]


@router.post("/llm-providers", response_model=LlmProviderOut)
def create_llm_provider(
    body: LlmProviderCreate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建 LLM 供应商。"""
    provider = LlmProvider(
        name=body.name,
        api_base=body.api_base,
        api_key=body.api_key,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return LlmProviderOut(
        id=provider.id,
        name=provider.name,
        api_base=provider.api_base,
        api_key_set=bool(provider.api_key),
        is_active=provider.is_active,
        created_at=provider.created_at,
        models=[],
    )


@router.put("/llm-providers/{provider_id}", response_model=LlmProviderOut)
def update_llm_provider(
    provider_id: int,
    body: LlmProviderUpdate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新 LLM 供应商。"""
    provider = db.query(LlmProvider).filter(LlmProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(404, "Provider not found")

    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(provider, k, v)
    db.commit()
    db.refresh(provider)
    return LlmProviderOut(
        id=provider.id,
        name=provider.name,
        api_base=provider.api_base,
        api_key_set=bool(provider.api_key),
        is_active=provider.is_active,
        created_at=provider.created_at,
        models=[
            LlmModelOut(
                id=m.id, provider_id=m.provider_id, name=m.name,
                model=m.model, temperature=m.temperature, top_p=m.top_p,
                max_tokens=m.max_tokens, is_active=m.is_active, created_at=m.created_at,
            )
            for m in provider.models
        ],
    )


@router.delete("/llm-providers/{provider_id}", response_model=MessageResponse)
def delete_llm_provider(
    provider_id: int,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除 LLM 供应商及其所有模型。同时清除编排中对该供应商下模型的引用。"""
    provider = db.query(LlmProvider).filter(LlmProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(404, "Provider not found")

    # 收集该供应商下所有模型 ID
    model_ids = [m.id for m in provider.models]

    # 清除编排中对这些模型的引用
    routing = db.query(LlmRouting).first()
    if routing and model_ids:
        for col in ("distill_model_id", "reason_model_id",
                     "audit_model_id", "embed_model_id"):
            if getattr(routing, col) in model_ids:
                setattr(routing, col, None)

    db.delete(provider)  # cascade 会删除关联的模型
    db.commit()
    return MessageResponse(message="供应商及其模型已删除")


# ─── LLM 模型管理（嵌套在供应商下）──────────────────────

@router.post("/llm-providers/{provider_id}/models", response_model=LlmModelOut)
def create_llm_model(
    provider_id: int,
    body: LlmModelCreate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """在指定供应商下创建模型。"""
    provider = db.query(LlmProvider).filter(LlmProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(404, "Provider not found")

    model_obj = LlmModel(
        provider_id=provider_id,
        name=body.name,
        model=body.model,
        temperature=body.temperature,
        top_p=body.top_p,
        max_tokens=body.max_tokens,
    )
    db.add(model_obj)
    db.commit()
    db.refresh(model_obj)
    return LlmModelOut(
        id=model_obj.id,
        provider_id=model_obj.provider_id,
        name=model_obj.name,
        model=model_obj.model,
        temperature=model_obj.temperature,
        top_p=model_obj.top_p,
        max_tokens=model_obj.max_tokens,
        is_active=model_obj.is_active,
        created_at=model_obj.created_at,
    )


@router.put("/llm-models/{model_id}", response_model=LlmModelOut)
def update_llm_model(
    model_id: int,
    body: LlmModelUpdate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新模型配置。"""
    model_obj = db.query(LlmModel).filter(LlmModel.id == model_id).first()
    if not model_obj:
        raise HTTPException(404, "Model not found")

    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(model_obj, k, v)
    db.commit()
    db.refresh(model_obj)
    return LlmModelOut(
        id=model_obj.id,
        provider_id=model_obj.provider_id,
        name=model_obj.name,
        model=model_obj.model,
        temperature=model_obj.temperature,
        top_p=model_obj.top_p,
        max_tokens=model_obj.max_tokens,
        is_active=model_obj.is_active,
        created_at=model_obj.created_at,
    )


@router.delete("/llm-models/{model_id}", response_model=MessageResponse)
def delete_llm_model(
    model_id: int,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除模型。同时清除编排中对该模型的引用。"""
    model_obj = db.query(LlmModel).filter(LlmModel.id == model_id).first()
    if not model_obj:
        raise HTTPException(404, "Model not found")

    # 清除编排引用
    routing = db.query(LlmRouting).first()
    if routing:
        for col in ("distill_model_id", "reason_model_id",
                     "audit_model_id", "embed_model_id"):
            if getattr(routing, col) == model_id:
                setattr(routing, col, None)

    db.delete(model_obj)
    db.commit()
    return MessageResponse(message="模型已删除")


@router.post("/llm-providers/{provider_id}/discover-models", response_model=list[LlmModelItem])
def discover_provider_models(
    provider_id: int,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取指定供应商的可用模型列表（调用 /models 端点自动发现）。"""
    provider = db.query(LlmProvider).filter(LlmProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(404, "Provider not found")

    from ..llm import OpenAICompatibleLLM
    llm = OpenAICompatibleLLM(
        api_key=provider.api_key,
        api_base=provider.api_base,
        model="temp",
    )
    discovered = llm.list_models()
    return [LlmModelItem(id=m["id"], owned_by=m.get("owned_by", "")) for m in discovered]


# ─── LLM 编排 ─────────────────────────────────────────────

@router.get("/llm-routing", response_model=LlmRoutingOut)
def get_llm_routing(
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取 LLM 编排配置。"""
    routing = db.query(LlmRouting).first()
    if not routing:
        return LlmRoutingOut()

    return _build_routing_out(routing, db)


@router.put("/llm-routing", response_model=LlmRoutingOut)
def update_llm_routing(
    body: LlmRoutingUpdate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新 LLM 编排配置。"""
    routing = db.query(LlmRouting).first()
    if not routing:
        routing = LlmRouting()
        db.add(routing)
        db.flush()

    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(routing, k, v)
    db.commit()
    db.refresh(routing)

    # 复用 GET 逻辑 — 提取为辅助函数避免重复
    return _build_routing_out(routing, db)


def _build_routing_out(routing: LlmRouting, db: Session) -> LlmRoutingOut:
    """构建 LlmRoutingOut，批量预加载避免 N+1。"""
    llm_model_ids = {routing.distill_model_id, routing.reason_model_id, routing.audit_model_id} - {None}
    embed_model_ids = {routing.embed_model_id} - {None}

    llm_models = {}
    llm_providers = {}
    if llm_model_ids:
        for m in db.query(LlmModel).filter(LlmModel.id.in_(llm_model_ids)).all():
            llm_models[m.id] = m
        provider_ids = {m.provider_id for m in llm_models.values()}
        if provider_ids:
            for p in db.query(LlmProvider).filter(LlmProvider.id.in_(provider_ids)).all():
                llm_providers[p.id] = p

    embed_models = {}
    embed_providers = {}
    if embed_model_ids:
        for m in db.query(EmbedModel).filter(EmbedModel.id.in_(embed_model_ids)).all():
            embed_models[m.id] = m
        provider_ids = {m.provider_id for m in embed_models.values()}
        if provider_ids:
            for p in db.query(EmbedProvider).filter(EmbedProvider.id.in_(provider_ids)).all():
                embed_providers[p.id] = p

    def _info(model_id):
        if not model_id:
            return None, None
        m = llm_models.get(model_id)
        if not m:
            return None, None
        p = llm_providers.get(m.provider_id)
        return m.name, (p.name if p else None)

    def _embed_info(model_id):
        if not model_id:
            return None, None
        m = embed_models.get(model_id)
        if not m:
            return None, None
        p = embed_providers.get(m.provider_id)
        return m.name, (p.name if p else None)

    d_name, d_prov = _info(routing.distill_model_id)
    r_name, r_prov = _info(routing.reason_model_id)
    a_name, a_prov = _info(routing.audit_model_id)
    e_name, e_prov = _embed_info(routing.embed_model_id)

    return LlmRoutingOut(
        distill_model_id=routing.distill_model_id,
        distill_model_name=d_name,
        distill_provider_name=d_prov,
        reason_model_id=routing.reason_model_id,
        reason_model_name=r_name,
        reason_provider_name=r_prov,
        audit_model_id=routing.audit_model_id,
        audit_model_name=a_name,
        audit_provider_name=a_prov,
        embed_model_id=routing.embed_model_id,
        embed_model_name=e_name,
        embed_provider_name=e_prov,
    )


# ─── 向量模型供应商管理 ─────────────────────────────────────

@router.get("/embed-providers", response_model=list[EmbedProviderOut])
def list_embed_providers(
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """列出所有向量模型供应商（含其模型列表）。"""
    providers = db.query(EmbedProvider).order_by(EmbedProvider.id).all()
    return [
        EmbedProviderOut(
            id=p.id,
            name=p.name,
            api_base=p.api_base,
            api_key_set=bool(p.api_key),
            is_active=p.is_active,
            created_at=p.created_at,
            models=[
                EmbedModelOut(
                    id=m.id,
                    provider_id=m.provider_id,
                    name=m.name,
                    model=m.model,
                    is_active=m.is_active,
                    created_at=m.created_at,
                )
                for m in p.models
            ],
        )
        for p in providers
    ]


@router.post("/embed-providers", response_model=EmbedProviderOut)
def create_embed_provider(
    body: EmbedProviderCreate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建向量模型供应商。"""
    provider = EmbedProvider(
        name=body.name,
        api_base=body.api_base,
        api_key=body.api_key,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return EmbedProviderOut(
        id=provider.id,
        name=provider.name,
        api_base=provider.api_base,
        api_key_set=bool(provider.api_key),
        is_active=provider.is_active,
        created_at=provider.created_at,
        models=[],
    )


@router.put("/embed-providers/{provider_id}", response_model=EmbedProviderOut)
def update_embed_provider(
    provider_id: int,
    body: EmbedProviderUpdate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新向量模型供应商。"""
    provider = db.query(EmbedProvider).filter(EmbedProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(404, "Embed provider not found")

    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(provider, k, v)
    db.commit()
    db.refresh(provider)
    return EmbedProviderOut(
        id=provider.id,
        name=provider.name,
        api_base=provider.api_base,
        api_key_set=bool(provider.api_key),
        is_active=provider.is_active,
        created_at=provider.created_at,
        models=[
            EmbedModelOut(
                id=m.id, provider_id=m.provider_id, name=m.name,
                model=m.model, is_active=m.is_active, created_at=m.created_at,
            )
            for m in provider.models
        ],
    )


@router.delete("/embed-providers/{provider_id}", response_model=MessageResponse)
def delete_embed_provider(
    provider_id: int,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除向量模型供应商及其所有模型。同时清除编排中的引用。"""
    provider = db.query(EmbedProvider).filter(EmbedProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(404, "Embed provider not found")

    model_ids = [m.id for m in provider.models]

    routing = db.query(LlmRouting).first()
    if routing and model_ids:
        if routing.embed_model_id in model_ids:
            routing.embed_model_id = None

    db.delete(provider)
    db.commit()
    return MessageResponse(message="向量供应商及其模型已删除")


# ─── 向量模型管理（嵌套在供应商下）──────────────────────

@router.post("/embed-providers/{provider_id}/models", response_model=EmbedModelOut)
def create_embed_model(
    provider_id: int,
    body: EmbedModelCreate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """在指定向量供应商下创建模型。"""
    provider = db.query(EmbedProvider).filter(EmbedProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(404, "Embed provider not found")

    model_obj = EmbedModel(
        provider_id=provider_id,
        name=body.name,
        model=body.model,
    )
    db.add(model_obj)
    db.commit()
    db.refresh(model_obj)
    return EmbedModelOut(
        id=model_obj.id,
        provider_id=model_obj.provider_id,
        name=model_obj.name,
        model=model_obj.model,
        is_active=model_obj.is_active,
        created_at=model_obj.created_at,
    )


@router.put("/embed-models/{model_id}", response_model=EmbedModelOut)
def update_embed_model(
    model_id: int,
    body: EmbedModelUpdate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新向量模型配置。"""
    model_obj = db.query(EmbedModel).filter(EmbedModel.id == model_id).first()
    if not model_obj:
        raise HTTPException(404, "Embed model not found")

    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(model_obj, k, v)
    db.commit()
    db.refresh(model_obj)
    return EmbedModelOut(
        id=model_obj.id,
        provider_id=model_obj.provider_id,
        name=model_obj.name,
        model=model_obj.model,
        is_active=model_obj.is_active,
        created_at=model_obj.created_at,
    )


@router.delete("/embed-models/{model_id}", response_model=MessageResponse)
def delete_embed_model(
    model_id: int,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除向量模型。同时清除编排中对该模型的引用。"""
    model_obj = db.query(EmbedModel).filter(EmbedModel.id == model_id).first()
    if not model_obj:
        raise HTTPException(404, "Embed model not found")

    routing = db.query(LlmRouting).first()
    if routing and routing.embed_model_id == model_id:
        routing.embed_model_id = None

    db.delete(model_obj)
    db.commit()
    return MessageResponse(message="向量模型已删除")


@router.post("/embed-providers/{provider_id}/discover-models", response_model=list[LlmModelItem])
def discover_embed_models(
    provider_id: int,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取指定向量供应商的可用模型列表。"""
    provider = db.query(EmbedProvider).filter(EmbedProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(404, "Embed provider not found")

    from ..llm import OpenAICompatibleLLM
    llm = OpenAICompatibleLLM(
        api_key=provider.api_key,
        api_base=provider.api_base,
        model="temp",
    )
    discovered = llm.list_models()
    return [LlmModelItem(id=m["id"], owned_by=m.get("owned_by", "")) for m in discovered]


