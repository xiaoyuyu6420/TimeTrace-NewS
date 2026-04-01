"""Event CRUD and timeline routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Event, EventArticle, Article, UserFollow
from ..schemas import (
    ArticleOut, EventDetail, EventOut, MessageResponse, PageResponse,
)

router = APIRouter(prefix="/api/events", tags=["events"])


def _event_to_out(event: Event, db: Session, user_id: int | None = None) -> EventOut:
    article_count = db.query(func.count(EventArticle.article_id)).filter(
        EventArticle.event_id == event.id
    ).scalar() or 0

    follow_count = db.query(func.count(UserFollow.id)).filter(
        UserFollow.event_id == event.id
    ).scalar() or 0

    is_followed = False
    if user_id:
        is_followed = db.query(UserFollow).filter_by(
            user_id=user_id, event_id=event.id
        ).first() is not None

    return EventOut(
        id=event.id,
        title=event.title,
        summary=event.summary,
        category=event.category,
        importance=event.importance,
        status=event.status,
        start_date=event.start_date,
        end_date=event.end_date,
        created_at=event.created_at,
        updated_at=event.updated_at,
        article_count=article_count,
        follow_count=follow_count,
        is_followed=is_followed,
    )


@router.get("", response_model=PageResponse)
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    category: str = Query(None),
    keyword: str = Query(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = int(user["user_id"]) if user else None
    q = db.query(Event)
    if status:
        q = q.filter(Event.status == status)
    if category:
        q = q.filter(Event.category == category)
    if keyword:
        q = q.filter(Event.title.contains(keyword))

    total = q.count()
    events = (
        q.order_by(Event.importance.desc(), Event.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_event_to_out(e, db, uid) for e in events]
    return PageResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/public", response_model=PageResponse)
def public_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query("active"),
    category: str = Query(None),
    db: Session = Depends(get_db),
):
    """Public endpoint - no auth required."""
    q = db.query(Event)
    if status:
        q = q.filter(Event.status == status)
    if category:
        q = q.filter(Event.category == category)

    total = q.count()
    events = (
        q.order_by(Event.importance.desc(), Event.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_event_to_out(e, db) for e in events]
    return PageResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{event_id}", response_model=EventDetail)
def get_event(
    event_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = int(user["user_id"]) if user else None
    event = db.query(Event).get(event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    out = _event_to_out(event, db, uid)

    # Get linked articles sorted by published_at
    links = (
        db.query(EventArticle, Article)
        .join(Article, EventArticle.article_id == Article.id)
        .filter(EventArticle.event_id == event_id)
        .order_by(Article.published_at.desc())
        .all()
    )
    articles = [ArticleOut.model_validate(a) for _, a in links]
    return EventDetail(**out.model_dump(), articles=articles)


@router.get("/{event_id}/public", response_model=EventDetail)
def get_event_public(event_id: int, db: Session = Depends(get_db)):
    """Public event detail - no auth required."""
    event = db.query(Event).get(event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    out = _event_to_out(event, db)
    links = (
        db.query(EventArticle, Article)
        .join(Article, EventArticle.article_id == Article.id)
        .filter(EventArticle.event_id == event_id)
        .order_by(Article.published_at.desc())
        .all()
    )
    articles = [ArticleOut.model_validate(a) for _, a in links]
    return EventDetail(**out.model_dump(), articles=articles)


@router.put("/{event_id}/status", response_model=MessageResponse)
def update_event_status(
    event_id: int,
    status: str = Query(..., regex="^(active|resolved)$"),
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    event = db.query(Event).get(event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    event.status = status
    if status == "resolved":
        from datetime import datetime, timezone
        event.end_date = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message=f"Event status updated to {status}")


@router.delete("/{event_id}", response_model=MessageResponse)
def delete_event(event_id: int, _admin=Depends(require_admin), db: Session = Depends(get_db)):
    event = db.query(Event).get(event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    db.delete(event)
    db.commit()
    return MessageResponse(message="Deleted")


@router.get("/search/{query}", response_model=PageResponse)
def search_events(
    query: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Event).filter(
        Event.title.contains(query) | Event.summary.contains(query)
    )
    total = q.count()
    events = q.order_by(Event.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_event_to_out(e, db) for e in events]
    return PageResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
