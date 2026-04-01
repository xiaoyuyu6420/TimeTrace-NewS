"""Factory module for unified historical news fetching.

This module provides a unified interface to fetch historical news
from multiple sources including RSS, web crawlers, and news APIs.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Iterator

from sqlalchemy.orm import Session

from .base import (
    FetchResult,
    HistoricalFetcher,
    NewsArticle,
    SourceType,
)
from .web_crawler import get_crawler, WebCrawlerFetcher
from .news_api import get_api_fetcher, NewsApiFetcher

logger = logging.getLogger(__name__)


class HistoricalFetcherFactory:
    """Factory for creating and managing historical news fetchers."""
    
    def __init__(
        self,
        api_keys: dict[str, str] | None = None,
        max_articles_per_source: int = 100,
        rate_limit_delay: float = 1.0,
    ):
        self.api_keys = api_keys or {}
        self.max_articles_per_source = max_articles_per_source
        self.rate_limit_delay = rate_limit_delay
        self._fetchers: dict[str, HistoricalFetcher] = {}
    
    def get_fetcher(
        self,
        source: str,
        source_type: SourceType | None = None,
    ) -> HistoricalFetcher:
        """Get or create a fetcher for the specified source."""
        cache_key = f"{source_type.value if source_type else 'auto'}:{source}"
        
        if cache_key in self._fetchers:
            return self._fetchers[cache_key]
        
        if source_type == SourceType.WEB_CRAWLER:
            fetcher = get_crawler(
                source,
                max_articles=self.max_articles_per_source,
                rate_limit_delay=self.rate_limit_delay,
            )
        elif source_type == SourceType.NEWS_API:
            api_key = self.api_keys.get(source)
            fetcher = get_api_fetcher(
                source,
                api_key=api_key,
                max_articles=self.max_articles_per_source,
                rate_limit_delay=self.rate_limit_delay,
            )
        elif source_type == SourceType.SEARCH_ENGINE:
            fetcher = get_api_fetcher(
                source,
                max_articles=self.max_articles_per_source,
                rate_limit_delay=self.rate_limit_delay,
            )
        else:
            fetcher = self._auto_detect_fetcher(source)
        
        self._fetchers[cache_key] = fetcher
        return fetcher
    
    def _auto_detect_fetcher(self, source: str) -> HistoricalFetcher:
        """Auto-detect fetcher type based on source name."""
        web_crawlers = ["people", "sina", "36kr", "huxiu"]
        apis = ["newsapi", "gnews", "zhipu"]
        
        source_lower = source.lower()
        
        if source_lower in web_crawlers:
            return get_crawler(
                source_lower,
                max_articles=self.max_articles_per_source,
                rate_limit_delay=self.rate_limit_delay,
            )
        
        if source_lower in apis:
            api_key = self.api_keys.get(source_lower)
            return get_api_fetcher(
                source_lower,
                api_key=api_key,
                max_articles=self.max_articles_per_source,
                rate_limit_delay=self.rate_limit_delay,
            )
        
        raise ValueError(f"Unknown source: {source}")


class MultiSourceFetcher:
    """Fetch historical news from multiple sources simultaneously."""
    
    AVAILABLE_SOURCES = {
        "web_crawlers": {
            "people": "人民网",
            "sina": "新浪新闻",
            "36kr": "36氪",
            "huxiu": "虎嗅",
        },
        "news_apis": {
            "newsapi": "NewsAPI (需要 API Key)",
            "gnews": "GNews (需要 API Key)",
            "zhipu": "智谱新闻搜索",
        },
    }
    
    def __init__(
        self,
        api_keys: dict[str, str] | None = None,
        max_articles_per_source: int = 100,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ):
        self.factory = HistoricalFetcherFactory(
            api_keys=api_keys,
            max_articles_per_source=max_articles_per_source,
        )
        self.progress_callback = progress_callback
    
    def fetch_from_source(
        self,
        source: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        keywords: list[str] | None = None,
        category: str | None = None,
    ) -> FetchResult:
        """Fetch from a single source."""
        fetcher = self.factory.get_fetcher(source)
        return fetcher.fetch(
            start_date=start_date,
            end_date=end_date,
            keywords=keywords,
            category=category,
        )
    
    def fetch_from_multiple(
        self,
        sources: list[str],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        keywords: list[str] | None = None,
        category: str | None = None,
    ) -> dict[str, FetchResult]:
        """Fetch from multiple sources and return results per source."""
        results = {}
        
        for source in sources:
            try:
                logger.info(f"Fetching from {source}...")
                result = self.fetch_from_source(
                    source=source,
                    start_date=start_date,
                    end_date=end_date,
                    keywords=keywords,
                    category=category,
                )
                results[source] = result
                logger.info(f"  {source}: {result.total_fetched} articles")
            except Exception as e:
                logger.error(f"Failed to fetch from {source}: {e}")
                results[source] = FetchResult(
                    success=False,
                    errors=[str(e)],
                )
        
        return results
    
    def fetch_all(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        keywords: list[str] | None = None,
        category: str | None = None,
        include_apis: bool = True,
    ) -> list[NewsArticle]:
        """Fetch from all available sources."""
        all_articles = []
        seen_urls = set()
        
        sources = list(self.AVAILABLE_SOURCES["web_crawlers"].keys())
        
        if include_apis:
            for api_name in self.AVAILABLE_SOURCES["news_apis"].keys():
                if api_name == "zhipu" or self.factory.api_keys.get(api_name):
                    sources.append(api_name)
        
        results = self.fetch_from_multiple(
            sources=sources,
            start_date=start_date,
            end_date=end_date,
            keywords=keywords,
            category=category,
        )
        
        for source, result in results.items():
            if result.success:
                for article in result.articles:
                    if article.source_url and article.source_url not in seen_urls:
                        seen_urls.add(article.source_url)
                        all_articles.append(article)
                    elif not article.source_url:
                        all_articles.append(article)
        
        logger.info(f"Total articles fetched: {len(all_articles)}")
        return all_articles
    
    def save_to_database(
        self,
        articles: list[NewsArticle],
        db: Session,
        rss_source_id: int | None = None,
    ) -> int:
        """Save fetched articles to database."""
        from ...models import Article
        
        saved_count = 0
        
        for news_article in articles:
            if news_article.source_url:
                existing = db.query(Article).filter(
                    Article.source_url == news_article.source_url
                ).first()
                if existing:
                    continue
            
            article = Article(
                title=news_article.title,
                content=news_article.content[:5000] if news_article.content else "",
                source_url=news_article.source_url,
                rss_source_id=rss_source_id,
                published_at=news_article.published_at,
            )
            
            db.add(article)
            saved_count += 1
        
        db.commit()
        logger.info(f"Saved {saved_count} articles to database")
        return saved_count


def fetch_historical_news(
    sources: list[str] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    keywords: list[str] | None = None,
    api_keys: dict[str, str] | None = None,
    max_articles: int = 500,
) -> list[NewsArticle]:
    """Convenience function to fetch historical news.
    
    Args:
        sources: List of source names, None for all available
        start_date: Start date for historical range
        end_date: End date for historical range
        keywords: Keywords to search
        api_keys: API keys for news APIs
        max_articles: Maximum articles to fetch per source
        
    Returns:
        List of NewsArticle objects
    """
    fetcher = MultiSourceFetcher(
        api_keys=api_keys,
        max_articles_per_source=max_articles,
    )
    
    if sources:
        results = fetcher.fetch_from_multiple(
            sources=sources,
            start_date=start_date,
            end_date=end_date,
            keywords=keywords,
        )
        articles = []
        for result in results.values():
            if result.success:
                articles.extend(result.articles)
        return articles
    else:
        return fetcher.fetch_all(
            start_date=start_date,
            end_date=end_date,
            keywords=keywords,
        )


def get_available_sources() -> dict[str, dict[str, str]]:
    """Get list of available news sources.
    
    Returns:
        Dictionary with source categories and their sources
    """
    return MultiSourceFetcher.AVAILABLE_SOURCES
