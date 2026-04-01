"""Web crawler adapter for historical news fetching.

This module provides crawlers for various news websites to fetch
historical news articles directly from their archives.
"""

import logging
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import (
    FetchResult,
    HistoricalFetcher,
    NewsArticle,
    SourceType,
    WebCrawlerConfig,
)

logger = logging.getLogger(__name__)


class WebCrawlerFetcher(HistoricalFetcher):
    """Base web crawler for news websites."""
    
    source_type = SourceType.WEB_CRAWLER
    
    def __init__(
        self,
        config: WebCrawlerConfig,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(config.headers)
    
    def fetch(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        keywords: list[str] | None = None,
        category: str | None = None,
    ) -> FetchResult:
        """Fetch historical news from the website."""
        articles = []
        errors = []
        
        try:
            page = 1
            while len(articles) < self.max_articles:
                result = self._fetch_list_page(
                    page=page,
                    start_date=start_date,
                    end_date=end_date,
                )
                
                if not result.articles:
                    break
                
                for article_url in result.articles:
                    if len(articles) >= self.max_articles:
                        break
                    
                    try:
                        self._delay()
                        article = self._fetch_article(article_url)
                        if article:
                            if self._matches_filters(article, keywords, category):
                                articles.append(article)
                    except Exception as e:
                        errors.append(f"Failed to fetch {article_url}: {e}")
                        logger.error(f"Error fetching article: {e}")
                
                if not result.has_more:
                    break
                page += 1
                
        except Exception as e:
            errors.append(f"Crawl failed: {e}")
            logger.error(f"Crawl error: {e}")
        
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
        """Fetch a single page of articles."""
        articles = []
        errors = []
        
        try:
            list_result = self._fetch_list_page(
                page=page,
                start_date=start_date,
                end_date=end_date,
            )
            
            for article_url in list_result.articles[:page_size]:
                try:
                    self._delay()
                    article = self._fetch_article(article_url)
                    if article:
                        articles.append(article)
                except Exception as e:
                    errors.append(f"Failed to fetch {article_url}: {e}")
                    
        except Exception as e:
            errors.append(f"Page fetch failed: {e}")
        
        return FetchResult(
            success=len(articles) > 0,
            articles=articles,
            total_fetched=len(articles),
            errors=errors,
            has_more=list_result.has_more if 'list_result' in dir() else False,
        )
    
    def _fetch_list_page(
        self,
        page: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> FetchResult:
        """Fetch list of article URLs from a page."""
        raise NotImplementedError("Subclasses must implement _fetch_list_page")
    
    def _fetch_article(self, url: str) -> NewsArticle | None:
        """Fetch and parse a single article."""
        raise NotImplementedError("Subclasses must implement _fetch_article")
    
    def _matches_filters(
        self,
        article: NewsArticle,
        keywords: list[str] | None,
        category: str | None,
    ) -> bool:
        """Check if article matches filters."""
        if category and article.category != category:
            return False
        
        if keywords:
            text = f"{article.title} {article.content}".lower()
            if not any(kw.lower() in text for kw in keywords):
                return False
        
        return True


class PeopleCnCrawler(WebCrawlerFetcher):
    """Crawler for People's Daily (人民网)."""
    
    source_name = "人民网"
    
    def __init__(self, **kwargs):
        config = WebCrawlerConfig(
            base_url="http://www.people.com.cn",
            list_url_template="http://www.people.com.cn/GB/123150/index{page}.html",
            article_url_template="",
            list_selectors={
                "article_links": "ul.list_14 li a",
            },
            article_selectors={
                "title": "h1",
                "content": "#rwb_zw",
                "date": ".box01_date",
            },
            date_format="%Y年%m月%d日%H:%M",
        )
        super().__init__(config=config, **kwargs)
    
    def _fetch_list_page(
        self,
        page: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> FetchResult:
        """Fetch article list from people.com.cn."""
        articles = []
        has_more = False
        
        try:
            url = self.config.list_url_template.format(page=page if page > 1 else "")
            response = self._retry_request(self.session.get, url, timeout=30)
            response.encoding = self.config.encoding
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            for link in soup.select(self.config.list_selectors["article_links"]):
                href = link.get("href", "")
                if href:
                    full_url = urljoin(self.config.base_url, href)
                    articles.append(full_url)
            
            has_more = len(articles) > 0 and page < 100
            
        except Exception as e:
            logger.error(f"Failed to fetch list page: {e}")
        
        return FetchResult(
            success=len(articles) > 0,
            articles=articles,
            has_more=has_more,
        )
    
    def _fetch_article(self, url: str) -> NewsArticle | None:
        """Fetch article from people.com.cn."""
        try:
            response = self._retry_request(self.session.get, url, timeout=30)
            response.encoding = self.config.encoding
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            title_elem = soup.select_one(self.config.article_selectors["title"])
            content_elem = soup.select_one(self.config.article_selectors["content"])
            date_elem = soup.select_one(self.config.article_selectors["date"])
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            content = content_elem.get_text(strip=True) if content_elem else ""
            
            published_at = None
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                try:
                    published_at = datetime.strptime(date_text, self.config.date_format)
                except ValueError:
                    pass
            
            return NewsArticle(
                title=title,
                content=content,
                source_url=url,
                published_at=published_at,
                source_name=self.source_name,
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch article {url}: {e}")
            return None


class SinaNewsCrawler(WebCrawlerFetcher):
    """Crawler for Sina News (新浪新闻)."""
    
    source_name = "新浪新闻"
    
    def __init__(self, **kwargs):
        config = WebCrawlerConfig(
            base_url="https://news.sina.com.cn",
            list_url_template="https://news.sina.com.cn/roll/index.d.html?curpage={page}",
            article_url_template="",
            list_selectors={
                "article_links": ".news-item h2 a",
            },
            article_selectors={
                "title": "h1.main-title",
                "content": ".article-content",
                "date": ".date",
            },
            date_format="%Y年%m月%d日 %H:%M",
        )
        super().__init__(config=config, **kwargs)
    
    def _fetch_list_page(
        self,
        page: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> FetchResult:
        """Fetch article list from sina.com.cn."""
        articles = []
        has_more = False
        
        try:
            url = self.config.list_url_template.format(page=page)
            response = self._retry_request(self.session.get, url, timeout=30)
            response.encoding = self.config.encoding
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            for link in soup.select(self.config.list_selectors["article_links"]):
                href = link.get("href", "")
                if href and href.startswith("http"):
                    articles.append(href)
            
            has_more = len(articles) > 0 and page < 50
            
        except Exception as e:
            logger.error(f"Failed to fetch list page: {e}")
        
        return FetchResult(
            success=len(articles) > 0,
            articles=articles,
            has_more=has_more,
        )
    
    def _fetch_article(self, url: str) -> NewsArticle | None:
        """Fetch article from sina.com.cn."""
        try:
            response = self._retry_request(self.session.get, url, timeout=30)
            response.encoding = "utf-8"
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            title_elem = soup.select_one(self.config.article_selectors["title"])
            content_elem = soup.select_one(self.config.article_selectors["content"])
            date_elem = soup.select_one(self.config.article_selectors["date"])
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            content = ""
            if content_elem:
                for p in content_elem.find_all("p"):
                    content += p.get_text(strip=True) + "\n"
            
            published_at = None
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                try:
                    published_at = datetime.strptime(date_text, self.config.date_format)
                except ValueError:
                    pass
            
            return NewsArticle(
                title=title,
                content=content.strip(),
                source_url=url,
                published_at=published_at,
                source_name=self.source_name,
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch article {url}: {e}")
            return None


class TechNewsCrawler(WebCrawlerFetcher):
    """Crawler for tech news sites (36Kr, Huxiu, etc.)."""
    
    source_name = "科技新闻"
    
    SITES = {
        "36kr": {
            "base_url": "https://36kr.com",
            "list_url": "https://36kr.com/newsflashes",
            "list_selector": ".newsflash-item a",
            "title_selector": "h1",
            "content_selector": ".article-content",
        },
        "huxiu": {
            "base_url": "https://www.huxiu.com",
            "list_url": "https://www.huxiu.com/channel/106.html",
            "list_selector": ".article-item a",
            "title_selector": "h1",
            "content_selector": ".article-content",
        },
    }
    
    def __init__(self, site: str = "36kr", **kwargs):
        if site not in self.SITES:
            raise ValueError(f"Unknown site: {site}")
        
        self.site_config = self.SITES[site]
        self.source_name = site.upper()
        
        config = WebCrawlerConfig(
            base_url=self.site_config["base_url"],
            list_url_template=self.site_config["list_url"],
            article_url_template="",
            list_selectors={"article_links": self.site_config["list_selector"]},
            article_selectors={
                "title": self.site_config["title_selector"],
                "content": self.site_config["content_selector"],
            },
        )
        super().__init__(config=config, **kwargs)
    
    def _fetch_list_page(
        self,
        page: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> FetchResult:
        """Fetch article list from tech news site."""
        articles = []
        has_more = False
        
        try:
            url = self.config.list_url_template
            response = self._retry_request(self.session.get, url, timeout=30)
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            for link in soup.select(self.config.list_selectors["article_links"]):
                href = link.get("href", "")
                if href:
                    full_url = urljoin(self.config.base_url, href)
                    articles.append(full_url)
            
            has_more = len(articles) > 0 and page < 10
            
        except Exception as e:
            logger.error(f"Failed to fetch list page: {e}")
        
        return FetchResult(
            success=len(articles) > 0,
            articles=articles,
            has_more=has_more,
        )
    
    def _fetch_article(self, url: str) -> NewsArticle | None:
        """Fetch article from tech news site."""
        try:
            response = self._retry_request(self.session.get, url, timeout=30)
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            title_elem = soup.select_one(self.config.article_selectors["title"])
            content_elem = soup.select_one(self.config.article_selectors["content"])
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            content = content_elem.get_text(strip=True) if content_elem else ""
            
            return NewsArticle(
                title=title,
                content=content,
                source_url=url,
                source_name=self.source_name,
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch article {url}: {e}")
            return None


def get_crawler(source: str, **kwargs) -> WebCrawlerFetcher:
    """Factory function to get a crawler by source name."""
    crawlers = {
        "people": PeopleCnCrawler,
        "sina": SinaNewsCrawler,
        "36kr": lambda **kw: TechNewsCrawler(site="36kr", **kw),
        "huxiu": lambda **kw: TechNewsCrawler(site="huxiu", **kw),
    }
    
    if source not in crawlers:
        raise ValueError(f"Unknown crawler source: {source}. Available: {list(crawlers.keys())}")
    
    crawler_class = crawlers[source]
    if callable(crawler_class) and not isinstance(crawler_class, type):
        return crawler_class(**kwargs)
    return crawler_class(**kwargs)
