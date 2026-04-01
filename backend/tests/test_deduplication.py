"""Unit tests for deduplication service."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from app.services.deduplication import (
    TitleSimilarityCalculator,
    ContentSimilarityCalculator,
    DeduplicationService,
    DuplicatePair,
    find_duplicate_articles,
    deduplicate_all,
    merge_duplicate_articles,
)


class TestTitleSimilarityCalculator:
    """Tests for title similarity calculation."""
    
    def setup_method(self):
        self.calculator = TitleSimilarityCalculator(threshold=0.85)
    
    def test_identical_titles(self):
        """Test identical titles have 1.0 similarity."""
        result = self.calculator.calculate(
            "人工智能发展迅速",
            "人工智能发展迅速"
        )
        assert result == 1.0
    
    def test_similar_titles(self):
        """Test similar titles have high similarity."""
        result = self.calculator.calculate(
            "人工智能发展迅速，科技行业迎来新机遇",
            "人工智能发展迅猛，科技行业迎来新机会"
        )
        assert result > 0.8
    
    def test_different_titles(self):
        """Test different titles have low similarity."""
        result = self.calculator.calculate(
            "人工智能发展迅速",
            "今日天气预报"
        )
        assert result < 0.5
    
    def test_empty_titles(self):
        """Test empty title handling."""
        result = self.calculator.calculate("", "标题")
        assert result == 0.0
        
        result = self.calculator.calculate("标题", "")
        assert result == 0.0
    
    def test_is_similar(self):
        """Test threshold check."""
        assert self.calculator.is_similar("标题一", "标题一")
        assert not self.calculator.is_similar("标题一", "完全不同的标题")


class TestContentSimilarityCalculator:
    """Tests for content similarity calculation."""
    
    def setup_method(self):
        self.calculator = ContentSimilarityCalculator(threshold=0.70)
    
    def test_identical_content(self):
        """Test identical content have 1.0 similarity."""
        content = "这是一段测试内容，用于验证相似度计算功能。需要确保内容长度达到最低要求，这样才能正确计算相似度。本文将详细介绍测试方法和预期结果。"
        result = self.calculator.calculate(content, content)
        assert result == 1.0
    
    def test_similar_content(self):
        """Test similar content have high similarity."""
        content1 = "人工智能技术在近年来取得了重大突破，深度学习、自然语言处理等领域发展迅速。专家预测，未来五年AI将在更多领域得到应用，这将带来巨大的社会变革和机遇。"
        content2 = "人工智能技术近年来取得重大突破，深度学习、自然语言处理等领域发展迅猛。专家预测未来五年AI将在更多领域应用，这将带来巨大的社会变革和机遇。"
        
        result = self.calculator.calculate(content1, content2)
        assert result > 0.6
    
    def test_different_content(self):
        """Test different content have low similarity."""
        content1 = "人工智能技术在近年来取得了重大突破，深度学习发展迅速，专家预测未来五年AI将在更多领域得到应用，这将带来巨大的社会变革和机遇。"
        content2 = "今天天气晴朗，适合外出游玩，阳光明媚，温度适宜，是个好天气，非常适合户外活动和运动。"
        
        result = self.calculator.calculate(content1, content2)
        assert result < 0.3
    
    def test_short_content(self):
        """Test short content handling."""
        short_content = "短内容"
        normal_content = "这是一段正常长度的内容，用于测试短内容处理功能，需要确保长度超过最低要求。"
        
        result = self.calculator.calculate(short_content, normal_content)
        assert result == 0.0
    
    def test_empty_content(self):
        """Test empty content handling."""
        result = self.calculator.calculate("", "内容")
        assert result == 0.0


class TestDeduplicationService:
    """Tests for DeduplicationService."""
    
    def setup_method(self):
        self.service = DeduplicationService()
    
    def test_init(self):
        """Test service initialization."""
        assert self.service.title_threshold == 0.85
        assert self.service.content_threshold == 0.70
        assert self.service.title_weight == 0.4
        assert self.service.content_weight == 0.6
    
    def test_calculate_similarity(self):
        """Test similarity calculation between articles."""
        article1 = Mock()
        article1.id = 1
        article1.title = "人工智能发展迅速"
        article1.content = "人工智能技术在近年来取得了重大突破，深度学习发展迅速，专家预测未来五年AI将在更多领域得到应用，这将带来巨大的社会变革和机遇。"
        article1.published_at = None
        
        article2 = Mock()
        article2.id = 2
        article2.title = "人工智能发展迅猛"
        article2.content = "人工智能技术近年来取得重大突破，深度学习发展迅猛，专家预测未来五年AI将在更多领域应用，这将带来巨大的社会变革和机遇。"
        article2.published_at = None
        
        pair = self.service._calculate_similarity(article1, article2)
        
        assert pair is not None
        assert pair.title_similarity > 0.8
        assert pair.content_similarity > 0.3
    
    def test_is_duplicate(self):
        """Test duplicate detection."""
        article1 = Mock()
        article1.id = 1
        article1.title = "标题"
        article1.content = "内容"
        
        article2 = Mock()
        article2.id = 2
        article2.title = "标题"
        article2.content = "内容"
        
        pair = DuplicatePair(
            article1=article1,
            article2=article2,
            title_similarity=0.95,
            content_similarity=0.90,
            combined_score=0.92,
        )
        
        assert self.service._is_duplicate(pair) is True
        
        pair2 = DuplicatePair(
            article1=article1,
            article2=article2,
            title_similarity=0.50,
            content_similarity=0.40,
            combined_score=0.44,
        )
        
        assert self.service._is_duplicate(pair2) is False
    
    def test_find_duplicates(self, sample_articles):
        """Test finding duplicates."""
        from datetime import datetime, timezone
        from app.models import Article
        
        article1 = Article(
            id=1,
            title=sample_articles[0]["title"],
            content=sample_articles[0]["content"],
            published_at=sample_articles[0]["published_at"],
        )
        
        article2 = Article(
            id=2,
            title=sample_articles[1]["title"],
            content=sample_articles[1]["content"],
            published_at=sample_articles[1]["published_at"],
        )
        
        article3 = Article(
            id=3,
            title=sample_articles[2]["title"],
            content=sample_articles[2]["content"],
            published_at=sample_articles[2]["published_at"],
        )
        
        mock_db = Mock()
        mock_query = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        
        mock_filter2.limit.return_value.all.return_value = [article2, article3]
        mock_filter1.filter.return_value = mock_filter2
        mock_query.filter.return_value = mock_filter1
        mock_db.query.return_value = mock_query
        
        duplicates = self.service.find_duplicates(article1, mock_db)
        
        assert isinstance(duplicates, list)
    
    def test_merge_articles(self):
        """Test merging duplicate articles."""
        keep_article = Mock()
        keep_article.id = 1
        keep_article.content = ""
        keep_article.summary = ""
        keep_article.is_duplicate = False
        keep_article.duplicate_of = None
        
        remove_article = Mock()
        remove_article.id = 2
        remove_article.content = "要保留的内容"
        remove_article.summary = "要保留的摘要"
        remove_article.is_duplicate = False
        remove_article.duplicate_of = None
        
        mock_db = Mock()
        
        result = self.service.merge_articles(keep_article, remove_article, mock_db)
        
        assert result is True
        mock_db.commit.assert_called_once()


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    @patch('app.services.deduplication.DeduplicationService')
    def test_find_duplicate_articles(self, mock_service_class):
        """Test find_duplicate_articles function."""
        mock_service = Mock()
        mock_service.find_duplicates.return_value = []
        mock_service_class.return_value = mock_service
        
        from app.services.deduplication import find_duplicate_articles
        result = find_duplicate_articles(Mock(), Mock())
        
        mock_service.find_duplicates.assert_called_once()
    
    @patch('app.services.deduplication.DeduplicationService')
    def test_deduplicate_all(self, mock_service_class):
        """Test deduplicate_all function."""
        mock_service = Mock()
        mock_service.deduplicate_all.return_value = {"total_checked": 0}
        mock_service_class.return_value = mock_service
        
        from app.services.deduplication import deduplicate_all
        result = deduplicate_all(Mock())
        
        mock_service.deduplicate_all.assert_called_once()


class TestDuplicatePair:
    """Tests for DuplicatePair dataclass."""
    
    def test_create_pair(self):
        """Test creating a duplicate pair."""
        article1 = Mock()
        article1.id = 1
        article2 = Mock()
        article2.id = 2
        
        pair = DuplicatePair(
            article1=article1,
            article2=article2,
            title_similarity=0.9,
            content_similarity=0.8,
            combined_score=0.84,
        )
        
        assert pair.article1.id == 1
        assert pair.article2.id == 2
        assert pair.title_similarity == 0.9
        assert pair.content_similarity == 0.8
        assert pair.combined_score == 0.84
