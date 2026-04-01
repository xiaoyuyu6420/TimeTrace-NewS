"""Admin stats and management routes."""

import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Article, Event, EventArticle, RssSource, User, UserFollow
from ..schemas import (
    AdminStats, ArticleOut, EventOut, MessageResponse,
    MergeEventsRequest, AssignArticleRequest, UpdateEventRequest,
    PageResponse,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


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


class HistoricalFetchRequest(BaseModel):
    """Request for historical news fetch from multiple sources."""
    sources: Optional[list[str]] = Field(None, description="Sources to fetch from, None for all")
    days_back: int = Field(30, ge=1, le=365, description="Days to look back")
    keywords: Optional[list[str]] = Field(None, description="Keywords to search")
    max_articles: int = Field(100, ge=1, le=1000, description="Max articles per source")


class HistoricalFetchResponse(BaseModel):
    """Response for historical news fetch."""
    success: bool
    total_articles: int
    sources_fetched: list[str]
    errors: list[str] = []


class AvailableSourcesResponse(BaseModel):
    """Response for available sources list."""
    web_crawlers: dict[str, str]
    news_apis: dict[str, str]


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
    source = db.query(Event).get(body.source_id)
    target = db.query(Event).get(body.target_id)
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
    article = db.query(Article).get(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    event = db.query(Event).get(body.event_id)
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
    event = db.query(Event).get(event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(event, k, v)
    event.updated_at = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="Event updated")


# ─── Trigger aggregation ─────────────────────────────────

@router.post("/aggregate", response_model=MessageResponse)
def trigger_aggregate(_admin=Depends(require_admin)):
    """Manually trigger the full aggregation pipeline."""
    from ..services.processor import process_unprocessed
    from ..services.aggregator import aggregate_all
    from ..database import SessionLocal

    def _run():
        db = SessionLocal()
        try:
            process_unprocessed(db)
            aggregate_all(db)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()
    return MessageResponse(message="Aggregation started")


# ─── Trigger re-embed ────────────────────────────────────

@router.post("/reembed", response_model=MessageResponse)
def trigger_reembed(_admin=Depends(require_admin)):
    """Re-generate embeddings for all articles missing them."""
    from ..services.processor import process_unprocessed
    from ..database import SessionLocal

    def _run():
        db = SessionLocal()
        try:
            process_unprocessed(db)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()
    return MessageResponse(message="Re-embedding started")


# ─── Historical Crawl ─────────────────────────────────────

@router.post("/crawl/historical", response_model=HistoricalCrawlResponse)
def trigger_historical_crawl(
    body: HistoricalCrawlRequest,
    _admin=Depends(require_admin),
):
    """Crawl historical news from RSS sources."""
    from ..services.historical_crawler import HistoricalCrawler
    from ..database import SessionLocal

    def _run():
        db = SessionLocal()
        try:
            crawler = HistoricalCrawler(max_days=body.days_back)
            if body.source_id:
                crawler.crawl_source_by_id(body.source_id, db, body.days_back)
            else:
                crawler.crawl_all(db, body.days_back)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()
    return HistoricalCrawlResponse(
        success=True,
        sources_processed=0,
        articles_added=0,
        errors=[],
    )


# ─── Deduplication ────────────────────────────────────────

@router.post("/deduplicate", response_model=DeduplicateResponse)
def trigger_deduplicate(
    body: DeduplicateRequest,
    _admin=Depends(require_admin),
):
    """Run article deduplication."""
    from ..services.deduplication import DeduplicationService
    from ..database import SessionLocal

    results = {"stats": None}

    def _run():
        db = SessionLocal()
        try:
            service = DeduplicationService(
                title_threshold=body.title_threshold,
                content_threshold=body.content_threshold,
            )
            results["stats"] = service.deduplicate_all(db, dry_run=body.dry_run)
        finally:
            db.close()

    if body.dry_run:
        _run()
        stats = results["stats"]
        return DeduplicateResponse(
            success=True,
            total_checked=stats.get("total_checked", 0),
            duplicates_found=stats.get("duplicates_found", 0),
            articles_merged=0,
            errors=stats.get("errors", []),
        )
    else:
        threading.Thread(target=_run, daemon=True).start()
        return DeduplicateResponse(
            success=True,
            total_checked=0,
            duplicates_found=0,
            articles_merged=0,
            errors=[],
        )


# ─── Credibility Evaluation ───────────────────────────────

@router.post("/credibility/evaluate", response_model=CredibilityEvaluateResponse)
def trigger_credibility_evaluate(
    body: CredibilityEvaluateRequest,
    _admin=Depends(require_admin),
):
    """Run credibility evaluation for articles."""
    from ..services.credibility_service import CredibilityService
    from ..database import SessionLocal

    results = {"stats": None}

    def _run():
        db = SessionLocal()
        try:
            service = CredibilityService()
            results["stats"] = service.batch_evaluate(
                db,
                article_ids=body.article_ids,
                force_recalculate=body.force_recalculate,
            )
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()
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
    from ..services.credibility_service import get_credibility_stats as _get_stats
    stats = _get_stats(db)
    return CredibilityStatsResponse(
        total_articles=stats.get("total_articles", 0),
        scored_articles=stats.get("scored_articles", 0),
        average_score=stats.get("average_score", 0.0),
        tier_distribution=stats.get("tier_distribution", {"A": 0, "B": 0, "C": 0, "D": 0}),
    )


# ─── Historical News Fetch ─────────────────────────────────

@router.get("/historical/sources", response_model=AvailableSourcesResponse)
def list_historical_sources(_admin=Depends(require_admin)):
    """List available sources for historical news fetching."""
    from ..services.historical_fetcher import get_available_sources
    sources = get_available_sources()
    return AvailableSourcesResponse(
        web_crawlers=sources.get("web_crawlers", {}),
        news_apis=sources.get("news_apis", {}),
    )


@router.post("/historical/fetch", response_model=HistoricalFetchResponse)
def trigger_historical_fetch(
    body: HistoricalFetchRequest,
    _admin=Depends(require_admin),
):
    """Fetch historical news from multiple sources (web crawlers, APIs)."""
    from ..services.historical_fetcher import MultiSourceFetcher
    from ..database import SessionLocal
    
    results = {"articles": [], "errors": [], "sources": []}
    
    def _run():
        db = SessionLocal()
        try:
            from datetime import datetime, timedelta, timezone
            
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=body.days_back)
            
            fetcher = MultiSourceFetcher(
                max_articles_per_source=body.max_articles,
            )
            
            if body.sources:
                fetch_results = fetcher.fetch_from_multiple(
                    sources=body.sources,
                    start_date=start_date,
                    end_date=end_date,
                    keywords=body.keywords,
                )
                for source, result in fetch_results.items():
                    results["sources"].append(source)
                    if result.success:
                        results["articles"].extend(result.articles)
                    else:
                        results["errors"].extend(result.errors)
            else:
                articles = fetcher.fetch_all(
                    start_date=start_date,
                    end_date=end_date,
                    keywords=body.keywords,
                )
                results["articles"] = articles
            
            saved = fetcher.save_to_database(results["articles"], db)
            
        except Exception as e:
            results["errors"].append(str(e))
        finally:
            db.close()
    
    threading.Thread(target=_run, daemon=True).start()
    
    return HistoricalFetchResponse(
        success=True,
        total_articles=0,
        sources_fetched=body.sources or [],
        errors=[],
    )
