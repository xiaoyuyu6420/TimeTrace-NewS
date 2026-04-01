"""People's Daily (人民网) historical news crawler.

This module provides a dedicated crawler for People's Daily website,
with robust error handling, data cleaning, and support for historical
data fetching up to 2 years.

人民网新闻列表页面结构：
- 频道列表页：http://www.people.com.cn/GB/123150/index.html
- 分页：http://www.people.com.cn/GB/123150/index{page}.html

文章页面结构：
- 标题：<h1> 或 .title
- 内容：#rwb_zw 或 .article-content
- 日期：.box01_date 或 meta
- 来源：.editor 或 .source
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Generator
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class PeopleArticle:
    """人民网文章数据结构."""
    title: str
    content: str
    source_url: str
    published_at: datetime | None = None
    author: str = ""
    source_name: str = "人民网"
    category: str = ""
    keywords: list[str] = field(default_factory=list)
    
    def is_valid(self) -> bool:
        """检查文章是否有效."""
        return bool(self.title and len(self.title) >= 5)
    
    def clean_content(self) -> str:
        """清理内容."""
        if not self.content:
            return ""
        text = re.sub(r'\s+', ' ', self.content)
        text = re.sub(r'[\xa0\u3000]+', ' ', text)
        text = text.strip()
        return text


@dataclass
class CrawlStats:
    """爬取统计."""
    total_pages: int = 0
    total_articles: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class PeopleCnCrawler:
    """人民网历史新闻爬虫.
    
    专注于人民网数据获取，确保数据质量和稳定性。
    
    Usage:
        crawler = PeopleCnCrawler()
        
        # 获取最近30天的新闻
        articles = crawler.fetch_recent(days=30)
        
        # 获取指定日期范围的新闻
        articles = crawler.fetch_range(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31)
        )
        
        # 获取最近2年的新闻
        articles = crawler.fetch_years(years=2)
    """
    
    BASE_URL = "http://www.people.com.cn"
    
    CHANNELS = {
        "news": {
            "name": "新闻",
            "list_url": "http://www.people.com.cn/GB/123150/index{page}.html",
        },
        "politics": {
            "name": "时政",
            "list_url": "http://politics.people.com.cn/GB/1024/index{page}.html",
        },
        "society": {
            "name": "社会",
            "list_url": "http://society.people.com.cn/GB/1062/index{page}.html",
        },
        "tech": {
            "name": "科技",
            "list_url": "http://scitech.people.com.cn/GB/1057/index{page}.html",
        },
        "finance": {
            "name": "财经",
            "list_url": "http://finance.people.com.cn/GB/1040/index{page}.html",
        },
        "world": {
            "name": "国际",
            "list_url": "http://world.people.com.cn/GB/1029/index{page}.html",
        },
    }
    
    def __init__(
        self,
        max_articles: int = 10000,
        max_pages_per_channel: int = 100,
        request_delay: float = 1.0,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.max_articles = max_articles
        self.max_pages_per_channel = max_pages_per_channel
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        
        self.stats = CrawlStats()
    
    def fetch_recent(
        self,
        days: int = 30,
        channels: list[str] | None = None,
    ) -> list[PeopleArticle]:
        """获取最近N天的新闻.
        
        Args:
            days: 天数
            channels: 频道列表，None表示全部
            
        Returns:
            文章列表
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        return self.fetch_range(start_date, end_date, channels)
    
    def fetch_years(
        self,
        years: int = 2,
        channels: list[str] | None = None,
    ) -> list[PeopleArticle]:
        """获取最近N年的新闻.
        
        Args:
            years: 年数
            channels: 频道列表
            
        Returns:
            文章列表
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=years * 365)
        return self.fetch_range(start_date, end_date, channels)
    
    def fetch_range(
        self,
        start_date: datetime,
        end_date: datetime,
        channels: list[str] | None = None,
    ) -> list[PeopleArticle]:
        """获取指定日期范围的新闻.
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            channels: 频道列表
            
        Returns:
            文章列表
        """
        self.stats = CrawlStats()
        
        channel_keys = channels if channels else list(self.CHANNELS.keys())
        all_articles = []
        seen_urls = set()
        
        logger.info(f"开始爬取人民网: {start_date.date()} 至 {end_date.date()}")
        logger.info(f"频道: {channel_keys}")
        
        for channel_key in channel_keys:
            if len(all_articles) >= self.max_articles:
                break
                
            channel = self.CHANNELS.get(channel_key)
            if not channel:
                logger.warning(f"未知频道: {channel_key}")
                continue
            
            logger.info(f"爬取频道: {channel['name']}")
            
            articles = self._crawl_channel(
                channel=channel,
                start_date=start_date,
                end_date=end_date,
                seen_urls=seen_urls,
            )
            
            all_articles.extend(articles)
            logger.info(f"频道 {channel['name']} 获取 {len(articles)} 篇文章")
        
        self.stats.total_articles = len(all_articles)
        logger.info(f"爬取完成: 共 {len(all_articles)} 篇文章")
        logger.info(f"统计: 成功={self.stats.successful}, 失败={self.stats.failed}, 跳过={self.stats.skipped}")
        
        return all_articles
    
    def _crawl_channel(
        self,
        channel: dict,
        start_date: datetime,
        end_date: datetime,
        seen_urls: set,
    ) -> list[PeopleArticle]:
        """爬取单个频道."""
        articles = []
        page = 1
        
        while page <= self.max_pages_per_channel:
            if len(articles) >= self.max_articles:
                break
            
            self.stats.total_pages += 1
            
            list_url = channel["list_url"].format(
                page="" if page == 1 else f"_{page}"
            )
            
            try:
                article_urls = self._fetch_list_page(list_url)
                
                if not article_urls:
                    logger.info(f"频道 {channel['name']} 第 {page} 页无文章，停止")
                    break
                
                stop_crawling = False
                
                for article_url in article_urls:
                    if article_url in seen_urls:
                        self.stats.skipped += 1
                        continue
                    
                    seen_urls.add(article_url)
                    
                    self._delay()
                    
                    article = self._fetch_article(article_url, channel["name"])
                    
                    if article is None:
                        self.stats.failed += 1
                        continue
                    
                    if article.published_at:
                        if article.published_at < start_date:
                            logger.info(f"文章日期 {article.published_at.date()} 早于开始日期，停止爬取")
                            stop_crawling = True
                            break
                        if article.published_at > end_date:
                            self.stats.skipped += 1
                            continue
                    
                    if article.is_valid():
                        article.content = article.clean_content()
                        articles.append(article)
                        self.stats.successful += 1
                        
                        if len(articles) % 50 == 0:
                            logger.info(f"已获取 {len(articles)} 篇文章...")
                
                if stop_crawling:
                    break
                    
            except Exception as e:
                error_msg = f"爬取频道 {channel['name']} 第 {page} 页失败: {e}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)
            
            page += 1
            self._delay()
        
        return articles
    
    def _fetch_list_page(self, url: str) -> list[str]:
        """获取列表页的文章URL."""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.encoding = "gb2312"
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                article_urls = []
                
                for link in soup.select("a[href]"):
                    href = link.get("href", "")
                    
                    if self._is_article_url(href):
                        full_url = urljoin(self.BASE_URL, href)
                        article_urls.append(full_url)
                
                return list(set(article_urls))
                
            except Exception as e:
                logger.warning(f"获取列表页失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.request_delay * 2)
        
        return []
    
    def _is_article_url(self, url: str) -> bool:
        """判断是否为文章URL."""
        if not url:
            return False
        
        patterns = [
            r'/n1/\d{4}/\d{4}-\d{2}/\w+\.html',
            r'/GB/\d+/\d+-\d+/\d+\.html',
            r'/\d{4}/\d{4}/\w+\.html',
        ]
        
        for pattern in patterns:
            if re.search(pattern, url):
                return True
        
        return False
    
    def _fetch_article(
        self,
        url: str,
        channel_name: str,
    ) -> PeopleArticle | None:
        """获取文章详情."""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                
                encoding = response.apparent_encoding or "gb2312"
                response.encoding = encoding
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                title = self._extract_title(soup)
                if not title:
                    return None
                
                content = self._extract_content(soup)
                published_at = self._extract_date(soup, url)
                author = self._extract_author(soup)
                
                return PeopleArticle(
                    title=title,
                    content=content,
                    source_url=url,
                    published_at=published_at,
                    author=author,
                    category=channel_name,
                )
                
            except Exception as e:
                logger.warning(f"获取文章失败 (尝试 {attempt + 1}/{self.max_retries}): {url} - {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.request_delay)
        
        return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取标题."""
        selectors = [
            "h1",
            ".title",
            ".article-title",
            "#title",
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                if title and len(title) >= 5:
                    return title
        
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
            title = re.sub(r'_?人民网_?$', '', title)
            title = re.sub(r'_?人民网点?$', '', title)
            return title.strip()
        
        return ""
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """提取正文内容."""
        selectors = [
            "#rwb_zw",
            ".article-content",
            "#article-content",
            ".content",
            "#content",
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                for tag in elem.find_all(["script", "style", "iframe"]):
                    tag.decompose()
                
                paragraphs = []
                for p in elem.find_all("p"):
                    text = p.get_text(strip=True)
                    if text and len(text) > 10:
                        paragraphs.append(text)
                
                if paragraphs:
                    return "\n".join(paragraphs)
                
                text = elem.get_text(strip=True)
                if text and len(text) > 50:
                    return text
        
        return ""
    
    def _extract_date(self, soup: BeautifulSoup, url: str) -> datetime | None:
        """提取发布日期."""
        date_selectors = [
            ".box01_date",
            ".date",
            ".time",
            "#pubtime",
        ]
        
        for selector in date_selectors:
            elem = soup.select_one(selector)
            if elem:
                date_text = elem.get_text(strip=True)
                date = self._parse_date(date_text)
                if date:
                    return date
        
        meta_date = soup.find("meta", {"name": "publishdate"})
        if meta_date:
            date = self._parse_date(meta_date.get("content", ""))
            if date:
                return date
        
        url_pattern = r'/(\d{4})(\d{2})/(\w+)\.html'
        match = re.search(url_pattern, url)
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                return datetime(year, month, 1, tzinfo=timezone.utc)
            except ValueError:
                pass
        
        return None
    
    def _parse_date(self, date_text: str) -> datetime | None:
        """解析日期字符串."""
        if not date_text:
            return None
        
        patterns = [
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{1,2})', "%Y年%m月%d日 %H:%M"),
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', "%Y年%m月%d日"),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})\s*(\d{1,2}):(\d{1,2}):(\d{1,2})', "%Y-%m-%d %H:%M:%S"),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})\s*(\d{1,2}):(\d{1,2})', "%Y-%m-%d %H:%M"),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', "%Y-%m-%d"),
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', "%Y/%m/%d"),
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    clean_text = match.group(0)
                    clean_text = re.sub(r'[年月]', '-', clean_text)
                    clean_text = re.sub(r'日', '', clean_text)
                    
                    date = datetime.strptime(clean_text, fmt.replace('年', '-').replace('月', '-').replace('日', ''))
                    return date.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        
        return None
    
    def _extract_author(self, soup: BeautifulSoup) -> str:
        """提取作者."""
        selectors = [
            ".editor",
            ".author",
            "#author",
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                text = re.sub(r'(责任编辑|编辑|记者|作者)[：:]\s*', '', text)
                return text.strip()
        
        return ""
    
    def _delay(self):
        """请求延迟."""
        time.sleep(self.request_delay)
    
    def save_to_database(
        self,
        articles: list[PeopleArticle],
        db,
        rss_source_id: int | None = None,
    ) -> int:
        """保存文章到数据库.
        
        Args:
            articles: 文章列表
            db: 数据库会话
            rss_source_id: RSS源ID
            
        Returns:
            保存的文章数量
        """
        from ...models import Article
        
        saved_count = 0
        
        for article in articles:
            if not article.is_valid():
                continue
            
            existing = db.query(Article).filter(
                Article.source_url == article.source_url
            ).first()
            
            if existing:
                continue
            
            db_article = Article(
                title=article.title,
                content=article.content[:5000] if article.content else "",
                source_url=article.source_url,
                rss_source_id=rss_source_id,
                published_at=article.published_at,
            )
            
            db.add(db_article)
            saved_count += 1
            
            if saved_count % 100 == 0:
                db.commit()
                logger.info(f"已保存 {saved_count} 篇文章到数据库")
        
        db.commit()
        logger.info(f"共保存 {saved_count} 篇文章到数据库")
        
        return saved_count


def fetch_people_news(
    days: int = 30,
    max_articles: int = 5000,
    channels: list[str] | None = None,
) -> list[PeopleArticle]:
    """便捷函数：获取人民网新闻.
    
    Args:
        days: 天数
        max_articles: 最大文章数
        channels: 频道列表
        
    Returns:
        文章列表
    """
    crawler = PeopleCnCrawler(max_articles=max_articles)
    return crawler.fetch_recent(days=days, channels=channels)


def fetch_people_news_years(
    years: int = 2,
    max_articles: int = 20000,
    channels: list[str] | None = None,
) -> list[PeopleArticle]:
    """便捷函数：获取人民网多年历史新闻.
    
    Args:
        years: 年数
        max_articles: 最大文章数
        channels: 频道列表
        
    Returns:
        文章列表
    """
    crawler = PeopleCnCrawler(max_articles=max_articles)
    return crawler.fetch_years(years=years, channels=channels)
