"""Event CRUD and timeline routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db, get_timeline_service, require_admin
from ..models import Article, Event, EventArticle, UserFollow
from ..schemas import (
    ArticleOut, CategoryItem, EventDetail, EventOut,
    MessageResponse, PageResponse, TimelinePhase,
)

router = APIRouter(prefix="/api/events", tags=["events"])

# 时间范围过滤映射
_TIME_RANGE_FILTERS = {
    "today": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
}


def _events_to_out_batch(events: list[Event], db: Session, user_id: int | None = None) -> list[EventOut]:
    """批量构建 EventOut，避免 N+1 查询。"""
    if not events:
        return []

    event_ids = [e.id for e in events]

    # 批量查询文章数
    article_counts = dict(
        db.query(EventArticle.event_id, func.count(EventArticle.article_id))
        .filter(EventArticle.event_id.in_(event_ids))
        .group_by(EventArticle.event_id)
        .all()
    )

    # 批量查询关注数
    follow_counts = dict(
        db.query(UserFollow.event_id, func.count(UserFollow.id))
        .filter(UserFollow.event_id.in_(event_ids))
        .group_by(UserFollow.event_id)
        .all()
    )

    # 批量查询当前用户是否关注
    followed_ids: set[int] = set()
    if user_id:
        followed_ids = {
            row[0] for row in
            db.query(UserFollow.event_id)
            .filter(UserFollow.user_id == user_id, UserFollow.event_id.in_(event_ids))
            .all()
        }

    return [
        EventOut(
            id=e.id,
            title=e.title,
            summary=e.summary,
            category=e.category,
            importance=e.importance,
            status=e.status,
            start_date=e.start_date,
            end_date=e.end_date,
            created_at=e.created_at,
            updated_at=e.updated_at,
            article_count=article_counts.get(e.id, 0),
            follow_count=follow_counts.get(e.id, 0),
            is_followed=e.id in followed_ids,
        )
        for e in events
    ]


def _apply_time_range(query, time_range: str | None):
    """根据时间范围过滤事件。"""
    if not time_range or time_range == "all":
        return query
    delta = _TIME_RANGE_FILTERS.get(time_range)
    if delta:
        cutoff = datetime.now(timezone.utc) - delta
        return query.filter(Event.updated_at >= cutoff)
    return query


def _build_event_detail(event: Event, db: Session, timeline_svc, user_id: int | None = None) -> EventDetail:
    """构建事件详情，含时间线。"""
    out_list = _events_to_out_batch([event], db, user_id)
    out = out_list[0]

    # 获取关联文章
    links = (
        db.query(EventArticle, Article)
        .join(Article, EventArticle.article_id == Article.id)
        .filter(EventArticle.event_id == event.id)
        .order_by(Article.published_at.desc())
        .all()
    )
    articles = [ArticleOut.model_validate(a) for _, a in links]

    # 构建阶段时间线
    timeline = timeline_svc.build_timeline(event.id)

    # 尝试 LLM 精炼（满足条件时触发）
    if timeline_svc.should_enhance(event):
        try:
            timeline_svc.enhance_event(event)
        except Exception:
            pass  # LLM 精炼失败不影响返回

    return EventDetail(**out.model_dump(), articles=articles, timeline=timeline)


# ─── 公开端点 ──────────────────────────────────────────


@router.get("/public", response_model=PageResponse)
def public_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query("active"),
    category: str = Query(None),
    time_range: str = Query(None, pattern="^(today|week|month|all)$"),
    db: Session = Depends(get_db),
):
    """公开事件列表，支持时间范围过滤。"""
    q = db.query(Event)
    if status:
        q = q.filter(Event.status == status)
    if category:
        q = q.filter(Event.category == category)
    q = _apply_time_range(q, time_range)

    total = q.count()
    events = (
        q.order_by(Event.importance.desc(), Event.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = _events_to_out_batch(events, db)
    return PageResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/categories", response_model=list[CategoryItem])
def list_categories(db: Session = Depends(get_db)):
    """获取事件分类及数量。"""
    rows = (
        db.query(Event.category, func.count(Event.id))
        .filter(Event.category != "", Event.category.isnot(None))
        .group_by(Event.category)
        .order_by(func.count(Event.id).desc())
        .all()
    )
    return [CategoryItem(name=name, count=count) for name, count in rows]


@router.get("/search/{query}", response_model=PageResponse)
def search_events(
    query: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """公开搜索事件。"""
    q = db.query(Event).filter(
        Event.title.contains(query) | Event.summary.contains(query)
    )
    total = q.count()
    events = (
        q.order_by(Event.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = _events_to_out_batch(events, db)
    return PageResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{event_id}/public", response_model=EventDetail)
def get_event_public(event_id: int, db: Session = Depends(get_db)):
    """公开事件详情（含时间线）。"""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    timeline_svc = get_timeline_service(db)
    return _build_event_detail(event, db, timeline_svc)


# ─── 需要认证 ──────────────────────────────────────────


@router.get("", response_model=PageResponse)
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    category: str = Query(None),
    keyword: str = Query(None),
    time_range: str = Query(None, pattern="^(today|week|month|all)$"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """认证用户的事件列表。"""
    uid = int(user["user_id"]) if user else None
    q = db.query(Event)
    if status:
        q = q.filter(Event.status == status)
    if category:
        q = q.filter(Event.category == category)
    if keyword:
        q = q.filter(Event.title.contains(keyword))
    q = _apply_time_range(q, time_range)

    total = q.count()
    events = (
        q.order_by(Event.importance.desc(), Event.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = _events_to_out_batch(events, db, uid)
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
    """认证用户的事件详情（含时间线）。"""
    uid = int(user["user_id"]) if user else None
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    timeline_svc = get_timeline_service(db)
    return _build_event_detail(event, db, timeline_svc, uid)


# ─── 管理端点 ──────────────────────────────────────────


@router.put("/{event_id}/status", response_model=MessageResponse)
def update_event_status(
    event_id: int,
    status: str = Query(..., pattern="^(active|resolved)$"),
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    event.status = status
    if status == "resolved":
        event.end_date = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message=f"Event status updated to {status}")


@router.delete("/{event_id}", response_model=MessageResponse)
def delete_event(event_id: int, _admin=Depends(require_admin), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    db.delete(event)
    db.commit()
    return MessageResponse(message="Deleted")
