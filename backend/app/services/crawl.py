"""Crawl service - RSS feed crawling."""

import logging
from datetime import datetime, timezone

import feedparser
from sqlalchemy.orm import Session

from ..models import Article, RssSource

logger = logging.getLogger(__name__)


class CrawlService:
    """Service for crawling RSS feeds and creating articles."""

    def __init__(self, db: Session, llm, nlp):
        self._db = db
        self._llm = llm
        self._nlp = nlp

    def crawl_source(self, source_id: int) -> dict:
        source = self._db.query(RssSource).filter(RssSource.id == source_id).first()
        if not source:
            return {"success": False, "error": "Source not found"}

        return self._crawl_source(source)

    def crawl_all_active(self) -> dict:
        sources = self._db.query(RssSource).filter(RssSource.is_active == True).all()
        total_new = 0
        errors = []

        for source in sources:
            try:
                result = self._crawl_source(source)
                total_new += result.get("new_count", 0)
            except Exception as e:
                errors.append(f"{source.name}: {str(e)}")
                logger.error(f"Error crawling {source.name}: {e}")

        return {
            "success": True,
            "total_new": total_new,
            "sources_crawled": len(sources),
            "errors": errors,
        }

    def crawl_all(self) -> dict:
        return self.crawl_all_active()

    def _crawl_source(self, source) -> dict:
        logger.info(f"Crawling: {source.name} ({source.url})")

        try:
            feed = feedparser.parse(source.url)
        except Exception as e:
            logger.error(f"Failed to fetch {source.url}: {e}")
            return {"success": False, "error": str(e)}

        new_count = 0
        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            if not title:
                continue

            if link and self._db.query(Article).filter(Article.source_url == link).first():
                continue

            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            if hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", content) or content

            published = self._parse_published(entry)

            article = self._create_article(
                title=title,
                content=content,
                link=link,
                source_id=source.id,
                published=published,
            )
            self._db.add(article)
            self._db.commit()
            new_count += 1

        source.last_crawled = datetime.now(timezone.utc)
        self._db.commit()

        logger.info(f"  {source.name}: {new_count} new articles")
        return {"success": True, "new_count": new_count}

    def _parse_published(self, entry) -> datetime | None:
        for attr in ("published_parsed", "updated_parsed"):
            val = getattr(entry, attr, None)
            if val:
                try:
                    from time import mktime
                    return datetime.fromtimestamp(mktime(val), tz=timezone.utc)
                except Exception:
                    pass
        return None

    def _create_article(self, title, content, link, source_id, published):
        text = f"{title} {content[:1000]}"
        keywords = self._nlp.extract_keywords(text)
        entities = self._nlp.extract_entities(text)

        return Article(
            title=title,
            content=content[:5000],
            source_url=link,
            rss_source_id=source_id,
            keywords=keywords,
            entities=entities,
            published_at=published,
        )
