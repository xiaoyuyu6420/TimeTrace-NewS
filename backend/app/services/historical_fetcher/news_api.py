"""News API adapter for historical news fetching.

This module provides adapters for various news APIs to fetch
historical news articles.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import requests

from .base import (
    FetchResult,
    HistoricalFetcher,
    NewsApiConfig,
    NewsArticle,
    SourceType,
)

logger = logging.getLogger(__name__)


class NewsApiFetcher(HistoricalFetcher):
    """Fetcher for NewsAPI (newsapi.org)."""
    
    source_type = SourceType.NEWS_API
    source_name = "NewsAPI"
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://newsapi.org/v2",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.config = NewsApiConfig(
            api_key=api_key,
            base_url=base_url,
            endpoints={
                "everything": "/everything",
                "top_headlines": "/top-headlines",
                "sources": "/sources",
            },
        )
        self.session = requests.Session()
    
    def fetch(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        keywords: list[str] | None = None,
        category: str | None = None,
    ) -> FetchResult:
        """Fetch historical news from NewsAPI."""
        articles = []
        errors = []
        
        try:
            params = {
                "apiKey": self.config.api_key,
                "pageSize": min(100, self.max_articles),
                "language": "zh" if not keywords or any(
                    any('\u4e00' <= c <= '\u9fff' for c in kw) for kw in keywords
                ) else "en",
            }
            
            if start_date:
                params["from"] = start_date.strftime("%Y-%m-%dT%H:%M:%S")
            if end_date:
                params["to"] = end_date.strftime("%Y-%m-%dT%H:%M:%S")
            if keywords:
                params["q"] = " OR ".join(keywords)
            if category:
                params["category"] = category
            
            url = f"{self.config.base_url}{self.config.endpoints['everything']}"
            
            response = self._retry_request(
                self.session.get,
                url,
                params=params,
                timeout=30,
            )
            
            data = response.json()
            
            if data.get("status") != "ok":
                errors.append(f"API error: {data.get('message', 'Unknown error')}")
                return FetchResult(success=False, errors=errors)
            
            for item in data.get("articles", []):
                article = self._parse_article(item)
                if article:
                    articles.append(article)
                    
        except Exception as e:
            errors.append(f"API request failed: {e}")
            logger.error(f"NewsAPI fetch error: {e}")
        
        return FetchResult(
            success=len(articles) > 0,
            articles=articles,
            total_fetched=len(articles),
            errors=errors,
        )
    
    def fetch_by_page(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> FetchResult:
        """Fetch news by page from NewsAPI."""
        articles = []
        errors = []
        has_more = False
        
        try:
            params = {
                "apiKey": self.config.api_key,
                "page": page,
                "pageSize": page_size,
                "language": "zh",
            }
            
            if start_date:
                params["from"] = start_date.strftime("%Y-%m-%dT%H:%M:%S")
            if end_date:
                params["to"] = end_date.strftime("%Y-%m-%dT%H:%M:%S")
            
            url = f"{self.config.base_url}{self.config.endpoints['everything']}"
            
            response = self._retry_request(
                self.session.get,
                url,
                params=params,
                timeout=30,
            )
            
            data = response.json()
            
            if data.get("status") != "ok":
                errors.append(f"API error: {data.get('message', 'Unknown error')}")
                return FetchResult(success=False, errors=errors)
            
            total_results = data.get("totalResults", 0)
            has_more = (page * page_size) < total_results
            
            for item in data.get("articles", []):
                article = self._parse_article(item)
                if article:
                    articles.append(article)
                    
        except Exception as e:
            errors.append(f"API request failed: {e}")
        
        return FetchResult(
            success=len(articles) > 0,
            articles=articles,
            total_fetched=len(articles),
            errors=errors,
            has_more=has_more,
        )
    
    def _parse_article(self, item: dict) -> NewsArticle | None:
        """Parse article from API response."""
        if not item.get("title"):
            return None
        
        published_at = None
        if item.get("publishedAt"):
            try:
                published_at = datetime.fromisoformat(
                    item["publishedAt"].replace("Z", "+00:00")
                )
            except ValueError:
                pass
        
        return NewsArticle(
            title=item["title"],
            content=item.get("content", "") or item.get("description", ""),
            source_url=item.get("url", ""),
            published_at=published_at,
            author=item.get("author", ""),
            source_name=item.get("source", {}).get("name", ""),
        )


class GNewsFetcher(HistoricalFetcher):
    """Fetcher for GNews API (gnews.io)."""
    
    source_type = SourceType.NEWS_API
    source_name = "GNews"
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://gnews.io/api/v4",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.config = NewsApiConfig(
            api_key=api_key,
            base_url=base_url,
            endpoints={
                "search": "/search",
                "top_headlines": "/top-headlines",
            },
        )
        self.session = requests.Session()
    
    def fetch(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        keywords: list[str] | None = None,
        category: str | None = None,
    ) -> FetchResult:
        """Fetch historical news from GNews."""
        articles = []
        errors = []
        
        try:
            params = {
                "token": self.config.api_key,
                "max": min(100, self.max_articles),
                "lang": "zh",
            }
            
            if keywords:
                params["q"] = " OR ".join(keywords)
            if category:
                params["topic"] = category
            if start_date:
                params["from"] = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            if end_date:
                params["to"] = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            url = f"{self.config.base_url}{self.config.endpoints['search']}"
            
            response = self._retry_request(
                self.session.get,
                url,
                params=params,
                timeout=30,
            )
            
            data = response.json()
            
            for item in data.get("articles", []):
                article = self._parse_article(item)
                if article:
                    articles.append(article)
                    
        except Exception as e:
            errors.append(f"API request failed: {e}")
            logger.error(f"GNews fetch error: {e}")
        
        return FetchResult(
            success=len(articles) > 0,
            articles=articles,
            total_fetched=len(articles),
            errors=errors,
        )
    
    def fetch_by_page(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> FetchResult:
        """GNews doesn't support pagination, use fetch instead."""
        result = self.fetch(start_date=start_date, end_date=end_date)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        result.articles = result.articles[start_idx:end_idx]
        result.has_more = end_idx < result.total_fetched
        return result
    
    def _parse_article(self, item: dict) -> NewsArticle | None:
        """Parse article from API response."""
        if not item.get("title"):
            return None
        
        published_at = None
        if item.get("publishedAt"):
            try:
                published_at = datetime.fromisoformat(
                    item["publishedAt"].replace("Z", "+00:00")
                )
            except ValueError:
                pass
        
        return NewsArticle(
            title=item["title"],
            content=item.get("description", ""),
            source_url=item.get("url", ""),
            published_at=published_at,
            source_name=item.get("source", {}).get("name", ""),
        )


class ZhipuNewsFetcher(HistoricalFetcher):
    """Fetcher using Zhipu BigModel for news search.
    
    Uses the existing LLM service to search for news.
    """
    
    source_type = SourceType.SEARCH_ENGINE
    source_name = "智谱新闻搜索"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def fetch(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        keywords: list[str] | None = None,
        category: str | None = None,
    ) -> FetchResult:
        """Fetch news using Zhipu BigModel search."""
        from ..llm_service import get_client
        
        articles = []
        errors = []
        
        try:
            client = get_client()
            if not client:
                errors.append("Zhipu API client not available")
                return FetchResult(success=False, errors=errors)
            
            date_range = ""
            if start_date and end_date:
                date_range = f"（{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}）"
            
            query = f"搜索近期新闻{date_range}"
            if keywords:
                query = f"搜索关于 {' '.join(keywords)} 的新闻{date_range}"
            if category:
                query += f"，分类：{category}"
            
            response = client.chat.completions.create(
                model="glm-4",
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个新闻搜索助手。请根据用户请求，列出相关新闻的标题、摘要和来源。格式如下：\n1. 标题：xxx\n   摘要：xxx\n   来源：xxx\n   日期：xxx"
                    },
                    {"role": "user", "content": query}
                ],
            )
            
            content = response.choices[0].message.content
            parsed_articles = self._parse_llm_response(content)
            articles.extend(parsed_articles)
            
        except Exception as e:
            errors.append(f"Zhipu search failed: {e}")
            logger.error(f"Zhipu news search error: {e}")
        
        return FetchResult(
            success=len(articles) > 0,
            articles=articles,
            total_fetched=len(articles),
            errors=errors,
        )
    
    def fetch_by_page(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> FetchResult:
        """LLM search doesn't support pagination."""
        return self.fetch(start_date=start_date, end_date=end_date)
    
    def _parse_llm_response(self, content: str) -> list[NewsArticle]:
        """Parse LLM response into articles."""
        import re
        
        articles = []
        
        pattern = r'\d+\.\s*标题[：:]\s*(.+?)\n\s*摘要[：:]\s*(.+?)\n\s*来源[：:]\s*(.+?)\n\s*日期[：:]\s*(.+?)(?=\n\d+\.|$)'
        
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            title, summary, source, date_str = [m.strip() for m in match]
            
            published_at = None
            try:
                date_patterns = [
                    "%Y-%m-%d",
                    "%Y年%m月%d日",
                    "%Y/%m/%d",
                ]
                for pattern in date_patterns:
                    try:
                        published_at = datetime.strptime(date_str, pattern)
                        break
                    except ValueError:
                        continue
            except Exception:
                pass
            
            articles.append(NewsArticle(
                title=title,
                content=summary,
                source_url="",
                published_at=published_at,
                source_name=source,
            ))
        
        return articles


def get_api_fetcher(
    api_name: str,
    api_key: str | None = None,
    **kwargs,
) -> NewsApiFetcher:
    """Factory function to get an API fetcher by name."""
    fetchers = {
        "newsapi": NewsApiFetcher,
        "gnews": GNewsFetcher,
        "zhipu": ZhipuNewsFetcher,
    }
    
    if api_name not in fetchers:
        raise ValueError(f"Unknown API: {api_name}. Available: {list(fetchers.keys())}")
    
    fetcher_class = fetchers[api_name]
    
    if api_name == "zhipu":
        return fetcher_class(**kwargs)
    
    if not api_key:
        raise ValueError(f"API key required for {api_name}")
    
    return fetcher_class(api_key=api_key, **kwargs)
