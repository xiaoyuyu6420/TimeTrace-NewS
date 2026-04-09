"""Article CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..deps import get_db, require_admin
from ..models import Article
from ..schemas import ArticleOut, MessageResponse, PageResponse

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=PageResponse)
def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    rss_source_id: int = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Article)
    if keyword:
        q = q.filter(Article.title.contains(keyword))
    if rss_source_id:
        q = q.filter(Article.rss_source_id == rss_source_id)

    total = q.count()
    items = (
        q.order_by(Article.published_at.desc(), Article.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        items=[ArticleOut.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db)):
    a = db.get(Article, article_id)
    if not a:
        raise HTTPException(404, "Article not found")
    return a


@router.delete("/{article_id}", response_model=MessageResponse)
def delete_article(article_id: int, _admin=Depends(require_admin), db: Session = Depends(get_db)):
    a = db.get(Article, article_id)
    if not a:
        raise HTTPException(404, "Article not found")
    db.delete(a)
    db.commit()
    return MessageResponse(message="Deleted")
