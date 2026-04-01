"""RSS source management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import RssSource
from ..schemas import MessageResponse, RssSourceCreate, RssSourceOut, RssSourceUpdate

router = APIRouter(prefix="/api/rss", tags=["rss"])


@router.get("", response_model=list[RssSourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.query(RssSource).order_by(RssSource.id).all()


@router.post("", response_model=RssSourceOut)
def create_source(body: RssSourceCreate, _admin=Depends(require_admin), db: Session = Depends(get_db)):
    src = RssSource(name=body.name, url=body.url, category=body.category)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


@router.put("/{source_id}", response_model=RssSourceOut)
def update_source(
    source_id: int, body: RssSourceUpdate, _admin=Depends(require_admin), db: Session = Depends(get_db)
):
    src = db.query(RssSource).get(source_id)
    if not src:
        raise HTTPException(404, "Source not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(src, k, v)
    db.commit()
    db.refresh(src)
    return src


@router.delete("/{source_id}", response_model=MessageResponse)
def delete_source(source_id: int, _admin=Depends(require_admin), db: Session = Depends(get_db)):
    src = db.query(RssSource).get(source_id)
    if not src:
        raise HTTPException(404, "Source not found")
    db.delete(src)
    db.commit()
    return MessageResponse(message="Deleted")


@router.post("/crawl", response_model=MessageResponse)
def trigger_crawl(_admin=Depends(require_admin)):
    """Manually trigger RSS crawl."""
    from ..services.crawler import crawl_all
    import threading
    threading.Thread(target=crawl_all, daemon=True).start()
    return MessageResponse(message="Crawl started")
