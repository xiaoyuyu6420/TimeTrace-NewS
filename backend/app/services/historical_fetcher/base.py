"""Base classes and interfaces for historical news fetching.

This module defines the abstract interfaces for different news sources,
enabling a unified approach to fetching historical news from multiple sources.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Iterator

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Type of news source."""
    RSS = "rss"
    WEB_CRAWLER = "web_crawler"
    NEWS_API = "news_api"
    SEARCH_ENGINE = "search_engine"


@dataclass
class NewsArticle:
    """Represents a news article from any source."""
    title: str
    content: str
    source_url: str
    published_at: datetime | None = None
    author: str = ""
    source_name: str = ""
    category: str = ""
    keywords: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "content": self.content,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "author": self.author,
            "source_name": self.source_name,
            "category": self.category,
            "keywords": self.keywords,
            "extra": self.extra,
        }


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    success: bool
    articles: list[NewsArticle] = field(default_factory=list)
    total_fetched: int = 0
    errors: list[str] = field(default_factory=list)
    has_more: bool = False
    next_page_token: str | None = None


class HistoricalFetcher(ABC):
    """Abstract base class for historical news fetchers."""
    
    source_type: SourceType
    source_name: str
    
    def __init__(
        self,
        max_articles: int = 500,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ):
        self.max_articles = max_articles
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.progress_callback = progress_callback
    
    @abstractmethod
    def fetch(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        keywords: list[str] | None = None,
        category: str | None = None,
    ) -> FetchResult:
        """Fetch historical news articles.
        
        Args:
            start_date: Start date for historical range
            end_date: End date for historical range
            keywords: Optional keywords to filter
            category: Optional category filter
            
        Returns:
            FetchResult with articles and metadata
        """
        pass
    
    @abstractmethod
    def fetch_by_page(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> FetchResult:
        """Fetch news by pagination.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of articles per page
            start_date: Start date for historical range
            end_date: End date for historical range
            
        Returns:
            FetchResult with articles for the page
        """
        pass
    
    def fetch_all(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        keywords: list[str] | None = None,
        category: str | None = None,
    ) -> Iterator[NewsArticle]:
        """Fetch all articles as an iterator.
        
        Yields articles one by one, handling pagination automatically.
        
        Args:
            start_date: Start date for historical range
            end_date: End date for historical range
            keywords: Optional keywords to filter
            category: Optional category filter
            
        Yields:
            NewsArticle instances
        """
        page = 1
        total_yielded = 0
        
        while total_yielded < self.max_articles:
            result = self.fetch_by_page(
                page=page,
                start_date=start_date,
                end_date=end_date,
            )
            
            if not result.success or not result.articles:
                break
            
            for article in result.articles:
                if total_yielded >= self.max_articles:
                    return
                yield article
                total_yielded += 1
                
                if self.progress_callback:
                    self.progress_callback(self.source_name, total_yielded, self.max_articles)
            
            if not result.has_more:
                break
            
            page += 1
    
    def _delay(self):
        """Apply rate limiting delay."""
        import time
        time.sleep(self.rate_limit_delay)
    
    def _retry_request(
        self,
        request_func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Execute request with retry logic."""
        import time
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return request_func(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.rate_limit_delay * (attempt + 1))
        
        raise last_error


class WebCrawlerConfig:
    """Configuration for web crawler."""
    
    def __init__(
        self,
        base_url: str,
        list_url_template: str,
        article_url_template: str,
        list_selectors: dict[str, str],
        article_selectors: dict[str, str],
        date_format: str = "%Y-%m-%d",
        encoding: str = "utf-8",
        headers: dict[str, str] | None = None,
    ):
        self.base_url = base_url
        self.list_url_template = list_url_template
        self.article_url_template = article_url_template
        self.list_selectors = list_selectors
        self.article_selectors = article_selectors
        self.date_format = date_format
        self.encoding = encoding
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }


class NewsApiConfig:
    """Configuration for news API."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        endpoints: dict[str, str],
        default_params: dict[str, Any] | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.endpoints = endpoints
        self.default_params = default_params or {}
