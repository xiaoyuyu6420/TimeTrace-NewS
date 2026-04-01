"""Unit tests for People's Daily crawler."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from bs4 import BeautifulSoup

from app.services.people_crawler import (
    PeopleCnCrawler,
    PeopleArticle,
    CrawlStats,
    fetch_people_news,
    fetch_people_news_years,
)


class TestPeopleArticle:
    """Tests for PeopleArticle dataclass."""
    
    def test_create_article(self):
        """Test creating an article."""
        article = PeopleArticle(
            title="测试标题",
            content="测试内容",
            source_url="http://example.com/test",
        )
        
        assert article.title == "测试标题"
        assert article.content == "测试内容"
        assert article.source_url == "http://example.com/test"
        assert article.source_name == "人民网"
    
    def test_is_valid(self):
        """Test article validation."""
        valid_article = PeopleArticle(
            title="这是一个有效的标题",
            content="内容",
            source_url="http://example.com/1",
        )
        assert valid_article.is_valid() is True
        
        invalid_article = PeopleArticle(
            title="短",
            content="内容",
            source_url="http://example.com/2",
        )
        assert invalid_article.is_valid() is False
        
        empty_article = PeopleArticle(
            title="",
            content="内容",
            source_url="http://example.com/3",
        )
        assert empty_article.is_valid() is False
    
    def test_clean_content(self):
        """Test content cleaning."""
        article = PeopleArticle(
            title="标题",
            content="  多余  空格  \n\n换行  ",
            source_url="http://example.com",
        )
        
        cleaned = article.clean_content()
        assert "  " not in cleaned
        assert "\n\n" not in cleaned


class TestPeopleCnCrawler:
    """Tests for PeopleCnCrawler class."""
    
    def test_init(self):
        """Test crawler initialization."""
        crawler = PeopleCnCrawler(
            max_articles=1000,
            request_delay=0.5,
        )
        
        assert crawler.max_articles == 1000
        assert crawler.request_delay == 0.5
        assert crawler.timeout == 30
        assert crawler.max_retries == 3
    
    def test_channels_defined(self):
        """Test that channels are properly defined."""
        crawler = PeopleCnCrawler()
        
        assert "news" in crawler.CHANNELS
        assert "politics" in crawler.CHANNELS
        assert "tech" in crawler.CHANNELS
        assert len(crawler.CHANNELS) == 6
    
    def test_extract_title(self, sample_article_html):
        """Test title extraction."""
        crawler = PeopleCnCrawler()
        soup = BeautifulSoup(sample_article_html, "html.parser")
        
        title = crawler._extract_title(soup)
        
        assert title == "测试文章标题"
    
    def test_extract_content(self, sample_article_html):
        """Test content extraction."""
        crawler = PeopleCnCrawler()
        soup = BeautifulSoup(sample_article_html, "html.parser")
        
        content = crawler._extract_content(soup)
        
        assert "第一段测试内容" in content
        assert "第二段测试内容" in content
        assert "第三段测试内容" in content
    
    def test_extract_date(self, sample_article_html):
        """Test date extraction."""
        crawler = PeopleCnCrawler()
        soup = BeautifulSoup(sample_article_html, "html.parser")
        
        date = crawler._extract_date(soup, "http://example.com")
        
        assert date is not None
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 15
    
    def test_extract_author(self, sample_article_html):
        """Test author extraction."""
        crawler = PeopleCnCrawler()
        soup = BeautifulSoup(sample_article_html, "html.parser")
        
        author = crawler._extract_author(soup)
        
        assert "张三" in author
    
    def test_parse_date_formats(self):
        """Test various date format parsing."""
        crawler = PeopleCnCrawler()
        
        test_cases = [
            ("2024年01月15日10:30", 2024, 1, 15),
            ("2024-01-15 10:30:00", 2024, 1, 15),
            ("2024-01-15", 2024, 1, 15),
            ("2024/01/15", 2024, 1, 15),
        ]
        
        for date_str, year, month, day in test_cases:
            result = crawler._parse_date(date_str)
            assert result is not None, f"Failed to parse: {date_str}"
            assert result.year == year
            assert result.month == month
            assert result.day == day
    
    def test_is_article_url(self):
        """Test article URL detection."""
        crawler = PeopleCnCrawler()
        
        valid_urls = [
            "http://www.people.com.cn/n1/2024/01-15/c123456-78901234.html",
            "/n1/2024/01-15/c123456-78901234.html",
            "http://www.people.com.cn/GB/123456/789-123/12345.html",
        ]
        
        invalid_urls = [
            "http://www.people.com.cn/",
            "http://www.people.com.cn/GB/123150/",
            "javascript:void(0)",
            "",
        ]
        
        for url in valid_urls:
            assert crawler._is_article_url(url), f"Should be valid: {url}"
        
        for url in invalid_urls:
            assert not crawler._is_article_url(url), f"Should be invalid: {url}"
    
    @patch('app.services.people_crawler.requests.Session')
    def test_fetch_list_page(self, mock_session, sample_list_html):
        """Test fetching list page."""
        mock_response = Mock()
        mock_response.text = sample_list_html
        mock_response.encoding = "gb2312"
        
        mock_session_instance = Mock()
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        crawler = PeopleCnCrawler()
        crawler.session = mock_session_instance
        
        urls = crawler._fetch_list_page("http://example.com/list")
        
        assert len(urls) == 3
        assert all("people.com.cn" in url for url in urls)
    
    def test_fetch_article(self, sample_article_html):
        """Test fetching single article."""
        crawler = PeopleCnCrawler()
        
        mock_response = Mock()
        mock_response.text = sample_article_html
        mock_response.apparent_encoding = "utf-8"
        
        crawler.session = Mock()
        crawler.session.get.return_value = mock_response
        
        article = crawler._fetch_article(
            "http://www.people.com.cn/n1/2024/01-15/c123456-78901234.html",
            "新闻"
        )
        
        assert article is not None
        assert article.title == "测试文章标题"
        assert article.category == "新闻"


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    @patch('app.services.people_crawler.PeopleCnCrawler')
    def test_fetch_people_news(self, mock_crawler_class):
        """Test fetch_people_news function."""
        mock_crawler = Mock()
        mock_crawler.fetch_recent.return_value = []
        mock_crawler_class.return_value = mock_crawler
        
        result = fetch_people_news(days=30, max_articles=100)
        
        mock_crawler_class.assert_called_once_with(max_articles=100)
        mock_crawler.fetch_recent.assert_called_once_with(days=30, channels=None)
    
    @patch('app.services.people_crawler.PeopleCnCrawler')
    def test_fetch_people_news_years(self, mock_crawler_class):
        """Test fetch_people_news_years function."""
        mock_crawler = Mock()
        mock_crawler.fetch_years.return_value = []
        mock_crawler_class.return_value = mock_crawler
        
        result = fetch_people_news_years(years=2, max_articles=1000)
        
        mock_crawler_class.assert_called_once_with(max_articles=1000)
        mock_crawler.fetch_years.assert_called_once_with(years=2, channels=None)


class TestCrawlStats:
    """Tests for CrawlStats dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        stats = CrawlStats()
        
        assert stats.total_pages == 0
        assert stats.total_articles == 0
        assert stats.successful == 0
        assert stats.failed == 0
        assert stats.skipped == 0
        assert stats.errors == []
    
    def test_with_values(self):
        """Test with custom values."""
        stats = CrawlStats(
            total_pages=10,
            total_articles=100,
            successful=95,
            failed=5,
        )
        
        assert stats.total_pages == 10
        assert stats.total_articles == 100
        assert stats.successful == 95
        assert stats.failed == 5
