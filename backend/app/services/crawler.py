"""RSS crawler service."""

import logging
from datetime import datetime, timezone

import feedparser
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Article, RssSource

logger = logging.getLogger(__name__)


def _parse_published(entry) -> datetime | None:
    """Try to parse publication date from feed entry."""
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(val), tz=timezone.utc)
            except Exception:
                pass
    return None


def crawl_source(source: RssSource, db: Session) -> int:
    """Crawl a single RSS source, return count of new articles."""
    logger.info(f"Crawling: {source.name} ({source.url})")
    try:
        feed = feedparser.parse(source.url)
    except Exception as e:
        logger.error(f"Failed to fetch {source.url}: {e}")
        return 0

    new_count = 0
    for entry in feed.entries:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title:
            continue

        # Dedup by URL
        if link and db.query(Article).filter(Article.source_url == link).first():
            continue

        content = ""
        if hasattr(entry, "summary"):
            content = entry.summary
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", content) or content

        published = _parse_published(entry)

        article = Article(
            title=title,
            content=content[:5000],  # Truncate very long content
            source_url=link,
            rss_source_id=source.id,
            published_at=published,
        )
        db.add(article)
        new_count += 1

    source.last_crawled = datetime.now(timezone.utc)
    db.commit()
    logger.info(f"  {source.name}: {new_count} new articles")
    return new_count


def crawl_all():
    """Crawl all active RSS sources."""
    db = SessionLocal()
    try:
        sources = db.query(RssSource).filter(RssSource.is_active == True).all()
        total_new = 0
        for source in sources:
            try:
                total_new += crawl_source(source, db)
            except Exception as e:
                logger.error(f"Error crawling {source.name}: {e}")

        logger.info(f"Crawl complete. Total new articles: {total_new}")

        if total_new > 0:
            # Trigger processing pipeline
            from .processor import process_unprocessed
            from .aggregator import aggregate_all
            process_unprocessed(db)
            aggregate_all(db)
    finally:
        db.close()
