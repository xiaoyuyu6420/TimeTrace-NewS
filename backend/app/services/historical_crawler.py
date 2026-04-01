"""Historical news crawler service.

This module provides functionality to fetch historical news from RSS sources.
It extends the basic crawler with date range filtering and batch processing.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

import feedparser
from sqlalchemy.orm import Session

from ..models import Article, RssSource

logger = logging.getLogger(__name__)

MAX_HISTORICAL_DAYS = 30
MAX_ARTICLES_PER_SOURCE = 500
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


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


def _is_within_date_range(published: datetime | None, cutoff_date: datetime) -> bool:
    """Check if article is within the specified date range."""
    if published is None:
        return False
    return published >= cutoff_date


def _article_exists(db: Session, source_url: str) -> bool:
    """Check if article already exists in database."""
    if not source_url:
        return False
    return db.query(Article).filter(Article.source_url == source_url).first() is not None


def _create_article_from_entry(entry, source: RssSource) -> Article | None:
    """Create an Article instance from a feed entry."""
    title = getattr(entry, "title", "").strip()
    link = getattr(entry, "link", "").strip()
    
    if not title:
        return None
    
    content = ""
    if hasattr(entry, "summary"):
        content = entry.summary
    if hasattr(entry, "content") and entry.content:
        content = entry.content[0].get("value", content) or content
    
    published = _parse_published(entry)
    
    return Article(
        title=title,
        content=content[:5000],
        source_url=link,
        rss_source_id=source.id,
        published_at=published,
    )


class HistoricalCrawler:
    """Historical news crawler with date range support."""
    
    def __init__(
        self,
        max_days: int = MAX_HISTORICAL_DAYS,
        max_articles: int = MAX_ARTICLES_PER_SOURCE,
        max_retries: int = MAX_RETRIES,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ):
        self.max_days = max_days
        self.max_articles = max_articles
        self.max_retries = max_retries
        self.progress_callback = progress_callback
    
    def _fetch_feed(self, url: str) -> feedparser.FeedParserDict | None:
        """Fetch RSS feed with retry logic."""
        import time
        
        for attempt in range(self.max_retries):
            try:
                feed = feedparser.parse(url)
                if feed.bozo and feed.bozo_exception:
                    logger.warning(f"Feed parse warning for {url}: {feed.bozo_exception}")
                return feed
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(RETRY_DELAY_SECONDS)
        
        logger.error(f"All {self.max_retries} attempts failed for {url}")
        return None
    
    def crawl_source(
        self,
        source: RssSource,
        db: Session,
        days_back: int | None = None,
        max_articles: int | None = None,
    ) -> int:
        """Crawl a single RSS source for historical articles.
        
        Args:
            source: RSS source to crawl
            db: Database session
            days_back: Number of days to look back (default: self.max_days)
            max_articles: Maximum articles to fetch (default: self.max_articles)
            
        Returns:
            Number of new articles added
        """
        days_back = days_back or self.max_days
        max_articles = max_articles or self.max_articles
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        logger.info(f"History crawling: {source.name} ({source.url}), days_back={days_back}")
        
        feed = self._fetch_feed(source.url)
        if feed is None:
            return 0
        
        new_count = 0
        processed = 0
        
        for entry in feed.entries:
            if new_count >= max_articles:
                logger.info(f"Reached max articles limit ({max_articles}) for {source.name}")
                break
            
            processed += 1
            
            link = getattr(entry, "link", "").strip()
            if _article_exists(db, link):
                continue
            
            published = _parse_published(entry)
            if not _is_within_date_range(published, cutoff_date):
                continue
            
            article = _create_article_from_entry(entry, source)
            if article is None:
                continue
            
            db.add(article)
            new_count += 1
            
            if self.progress_callback:
                self.progress_callback(source.name, processed, new_count)
        
        source.last_crawled = datetime.now(timezone.utc)
        db.commit()
        
        logger.info(f"  {source.name}: {new_count} new historical articles (from {processed} entries)")
        return new_count
    
    def crawl_all(
        self,
        db: Session,
        days_back: int | None = None,
        source_filter: Callable[[RssSource], bool] | None = None,
    ) -> dict:
        """Crawl all active RSS sources for historical articles.
        
        Args:
            db: Database session
            days_back: Number of days to look back
            source_filter: Optional filter function for sources
            
        Returns:
            Dictionary with crawl statistics
        """
        query = db.query(RssSource).filter(RssSource.is_active == True)
        sources = query.all()
        
        if source_filter:
            sources = [s for s in sources if source_filter(s)]
        
        stats = {
            "sources_processed": 0,
            "total_articles": 0,
            "errors": [],
        }
        
        for source in sources:
            try:
                count = self.crawl_source(source, db, days_back)
                stats["sources_processed"] += 1
                stats["total_articles"] += count
            except Exception as e:
                error_msg = f"Error crawling {source.name}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        logger.info(f"Historical crawl complete. Total: {stats['total_articles']} articles from {stats['sources_processed']} sources")
        return stats
    
    def crawl_source_by_id(
        self,
        source_id: int,
        db: Session,
        days_back: int | None = None,
    ) -> int:
        """Crawl a specific RSS source by ID.
        
        Args:
            source_id: ID of the RSS source
            db: Database session
            days_back: Number of days to look back
            
        Returns:
            Number of new articles added, or -1 if source not found
        """
        source = db.query(RssSource).filter(RssSource.id == source_id).first()
        if source is None:
            logger.warning(f"RSS source with ID {source_id} not found")
            return -1
        
        return self.crawl_source(source, db, days_back)


def crawl_source(
    source: RssSource,
    db: Session,
    max_articles: int = MAX_ARTICLES_PER_SOURCE,
    days_back: int = MAX_HISTORICAL_DAYS,
) -> int:
    """Convenience function for single source historical crawl."""
    crawler = HistoricalCrawler(max_days=days_back, max_articles=max_articles)
    return crawler.crawl_source(source, db, days_back)


def crawl_all(
    db: Session,
    days_back: int = MAX_HISTORICAL_DAYS,
) -> dict:
    """Convenience function for all sources historical crawl."""
    crawler = HistoricalCrawler(max_days=days_back)
    return crawler.crawl_all(db, days_back)


def crawl_source_by_id(
    source_id: int,
    db: Session,
    days_back: int = MAX_HISTORICAL_DAYS,
) -> int:
    """Convenience function for crawling by source ID."""
    crawler = HistoricalCrawler(max_days=days_back)
    return crawler.crawl_source_by_id(source_id, db, days_back)
