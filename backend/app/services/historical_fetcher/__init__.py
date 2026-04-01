"""Historical news fetching module.

This module provides unified access to historical news from multiple sources:
- Web crawlers for news websites
- News APIs (NewsAPI, GNews, etc.)
- Search engine integrations

Usage:
    from app.services.historical_fetcher import (
        fetch_historical_news,
        get_available_sources,
        MultiSourceFetcher,
    )
    
    # Get available sources
    sources = get_available_sources()
    
    # Fetch from specific sources
    articles = fetch_historical_news(
        sources=["people", "sina"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
    )
    
    # Fetch from all sources
    articles = fetch_historical_news(
        keywords=["人工智能", "科技"],
        max_articles=200,
    )
"""

from .base import (
    FetchResult,
    HistoricalFetcher,
    NewsArticle,
    NewsApiConfig,
    SourceType,
    WebCrawlerConfig,
)
from .factory import (
    HistoricalFetcherFactory,
    MultiSourceFetcher,
    fetch_historical_news,
    get_available_sources,
)
from .news_api import (
    GNewsFetcher,
    NewsApiFetcher,
    ZhipuNewsFetcher,
    get_api_fetcher,
)
from .web_crawler import (
    PeopleCnCrawler,
    SinaNewsCrawler,
    TechNewsCrawler,
    WebCrawlerFetcher,
    get_crawler,
)

__all__ = [
    # Base classes
    "FetchResult",
    "HistoricalFetcher",
    "NewsArticle",
    "NewsApiConfig",
    "SourceType",
    "WebCrawlerConfig",
    # Factory
    "HistoricalFetcherFactory",
    "MultiSourceFetcher",
    "fetch_historical_news",
    "get_available_sources",
    # News API
    "GNewsFetcher",
    "NewsApiFetcher",
    "ZhipuNewsFetcher",
    "get_api_fetcher",
    # Web crawlers
    "PeopleCnCrawler",
    "SinaNewsCrawler",
    "TechNewsCrawler",
    "WebCrawlerFetcher",
    "get_crawler",
]
