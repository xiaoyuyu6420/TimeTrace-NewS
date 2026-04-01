"""Unit tests for credibility service."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

from app.services.credibility_service import (
    SourceCredibilityEvaluator,
    ContentCompletenessEvaluator,
    CrossReferenceEvaluator,
    TimelinessEvaluator,
    CredibilityService,
    CredibilityFactors,
    CredibilityResult,
    calculate_credibility,
    batch_evaluate,
    get_credibility_stats,
)


class TestSourceCredibilityEvaluator:
    """Tests for source credibility evaluation."""
    
    def setup_method(self):
        self.evaluator = SourceCredibilityEvaluator()
    
    def test_evaluate_with_source(self):
        """Test evaluation with RSS source."""
        article = Mock()
        article.rss_source_id = 1
        
        mock_db = Mock()
        mock_source = Mock()
        mock_source.name = "人民网"
        mock_source.credibility_tier = "A"
        mock_source.source_reputation = 95.0
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_source
        
        score, details = self.evaluator.evaluate(article, mock_db)
        
        assert score == 95.0
        assert details["source_name"] == "人民网"
        assert details["tier"] == "A"
    
    def test_evaluate_without_source(self):
        """Test evaluation without RSS source."""
        article = Mock()
        article.rss_source_id = None
        
        mock_db = Mock()
        
        score, details = self.evaluator.evaluate(article, mock_db)
        
        assert score == 50.0
        assert "No RSS source" in details.get("reason", "")
    
    def test_evaluate_with_default_tier(self):
        """Test evaluation with default tier reputation."""
        article = Mock()
        article.rss_source_id = 1
        
        mock_db = Mock()
        mock_source = Mock()
        mock_source.name = "测试来源"
        mock_source.credibility_tier = "B"
        mock_source.source_reputation = None
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_source
        
        score, details = self.evaluator.evaluate(article, mock_db)
        
        assert score == 75.0


class TestContentCompletenessEvaluator:
    """Tests for content completeness evaluation."""
    
    def setup_method(self):
        self.evaluator = ContentCompletenessEvaluator()
    
    def test_evaluate_complete_article(self):
        """Test evaluation of complete article."""
        article = Mock()
        article.title = "这是一个完整的标题用于测试内容完整度评估功能"
        article.content = "这是一段足够长的内容，用于测试内容完整度评估功能。需要确保内容长度达到最低要求，这样才能正确评估文章的完整程度。本文将详细介绍评估方法和标准。"
        article.summary = "这是文章的摘要内容，用于快速了解文章主题"
        article.keywords = ["关键词1", "关键词2", "关键词3"]
        article.entities = [{"name": "实体1", "type": "PERSON"}, {"name": "实体2", "type": "ORG"}]
        article.published_at = datetime.now(timezone.utc)
        
        score, details = self.evaluator.evaluate(article)
        
        assert score >= 70
        assert details["has_summary"] is True
        assert details["has_keywords"] is True
        assert details["has_entities"] is True
        assert details["has_published_date"] is True
    
    def test_evaluate_incomplete_article(self):
        """Test evaluation of incomplete article."""
        article = Mock()
        article.title = "短标题"
        article.content = "短内容"
        article.summary = ""
        article.keywords = []
        article.entities = []
        article.published_at = None
        
        score, details = self.evaluator.evaluate(article)
        
        assert score < 50
        assert details["has_summary"] is False
        assert details["has_published_date"] is False
    
    def test_evaluate_empty_article(self):
        """Test evaluation of empty article."""
        article = Mock()
        article.title = ""
        article.content = ""
        article.summary = ""
        article.keywords = []
        article.entities = []
        article.published_at = None
        
        score, details = self.evaluator.evaluate(article)
        
        assert score < 30


class TestCrossReferenceEvaluator:
    """Tests for cross-reference evaluation."""
    
    def setup_method(self):
        self.evaluator = CrossReferenceEvaluator()
    
    def test_evaluate_with_multiple_sources(self):
        """Test evaluation with multiple sources."""
        article = Mock()
        article.id = 1
        article.embedding = [0.1, 0.2, 0.3]
        
        mock_db = Mock()
        
        mock_event_link = Mock()
        mock_event_link.event_id = 1
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_event_link]
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.return_value = 3
        
        score, details = self.evaluator.evaluate(article, mock_db)
        
        assert score >= 70
        assert details["related_articles"] == 5
        assert details["unique_sources"] == 3
    
    def test_evaluate_without_embedding(self):
        """Test evaluation without embedding."""
        article = Mock()
        article.id = 1
        article.embedding = None
        
        mock_db = Mock()
        
        score, details = self.evaluator.evaluate(article, mock_db)
        
        assert score == 50.0
        assert "No embedding" in details.get("reason", "")
    
    def test_evaluate_without_event(self):
        """Test evaluation without event association."""
        article = Mock()
        article.id = 1
        article.embedding = [0.1, 0.2, 0.3]
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        score, details = self.evaluator.evaluate(article, mock_db)
        
        assert score == 50.0


class TestTimelinessEvaluator:
    """Tests for timeliness evaluation."""
    
    def setup_method(self):
        self.evaluator = TimelinessEvaluator()
    
    def test_evaluate_fresh_article(self):
        """Test evaluation of fresh article."""
        article = Mock()
        article.published_at = datetime.now(timezone.utc) - timedelta(hours=12)
        
        score, details = self.evaluator.evaluate(article)
        
        assert score >= 90
        assert details["hours_old"] <= 24
    
    def test_evaluate_week_old_article(self):
        """Test evaluation of week-old article."""
        article = Mock()
        article.published_at = datetime.now(timezone.utc) - timedelta(days=5)
        
        score, details = self.evaluator.evaluate(article)
        
        assert 40 <= score <= 90
        assert details["hours_old"] > 72
    
    def test_evaluate_old_article(self):
        """Test evaluation of old article."""
        article = Mock()
        article.published_at = datetime.now(timezone.utc) - timedelta(days=30)
        
        score, details = self.evaluator.evaluate(article)
        
        assert score < 50
    
    def test_evaluate_without_date(self):
        """Test evaluation without publication date."""
        article = Mock()
        article.published_at = None
        
        score, details = self.evaluator.evaluate(article)
        
        assert score == 50.0
        assert "No publication date" in details.get("reason", "")


class TestCredibilityService:
    """Tests for CredibilityService."""
    
    def setup_method(self):
        self.service = CredibilityService()
    
    def test_init(self):
        """Test service initialization."""
        assert self.service.weights["source"] == 0.30
        assert self.service.weights["content"] == 0.20
        assert self.service.weights["cross_ref"] == 0.30
        assert self.service.weights["timeliness"] == 0.20
    
    def test_evaluate(self):
        """Test full credibility evaluation."""
        article = Mock()
        article.id = 1
        article.title = "测试标题"
        article.content = "测试内容"
        article.source_url = "http://example.com"
        article.rss_source_id = 1
        article.embedding = [0.1, 0.2]
        article.summary = ""
        article.keywords = []
        article.entities = []
        article.published_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        mock_db = Mock()
        mock_source = Mock()
        mock_source.name = "测试来源"
        mock_source.credibility_tier = "B"
        mock_source.source_reputation = 75.0
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_source
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = self.service.evaluate(article, mock_db)
        
        assert isinstance(result, CredibilityResult)
        assert 0 <= result.score <= 100
        assert result.tier in ["A", "B", "C", "D"]
        assert 0 <= result.confidence <= 1
    
    def test_get_tier(self):
        """Test tier determination."""
        assert self.service._get_tier(95) == "A"
        assert self.service._get_tier(85) == "B"
        assert self.service._get_tier(60) == "C"
        assert self.service._get_tier(30) == "D"
    
    def test_calculate_confidence(self):
        """Test confidence calculation."""
        factors = CredibilityFactors(
            source_score=80,
            content_score=70,
            cross_ref_score=60,
            timeliness_score=90,
            details={
                "source": {"source_id": 1},
                "content": {"content_length": 200},
                "cross_ref": {"related_articles": 3},
                "timeliness": {"hours_old": 12},
            }
        )
        
        confidence = self.service._calculate_confidence(factors)
        
        assert 0.5 <= confidence <= 1.0


class TestCredibilityFactors:
    """Tests for CredibilityFactors dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        factors = CredibilityFactors()
        
        assert factors.source_score == 0.0
        assert factors.content_score == 0.0
        assert factors.cross_ref_score == 0.0
        assert factors.timeliness_score == 0.0
        assert factors.details == {}


class TestCredibilityResult:
    """Tests for CredibilityResult dataclass."""
    
    def test_create_result(self):
        """Test creating a result."""
        factors = CredibilityFactors(
            source_score=80,
            content_score=70,
        )
        
        result = CredibilityResult(
            score=75.5,
            factors=factors,
            tier="B",
            confidence=0.85,
        )
        
        assert result.score == 75.5
        assert result.tier == "B"
        assert result.confidence == 0.85


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    @patch('app.services.credibility_service.CredibilityService')
    def test_calculate_credibility(self, mock_service_class):
        """Test calculate_credibility function."""
        mock_service = Mock()
        mock_result = Mock()
        mock_service.evaluate.return_value = mock_result
        mock_service_class.return_value = mock_service
        
        result = calculate_credibility(Mock(), Mock())
        
        mock_service.evaluate.assert_called_once()
    
    @patch('app.services.credibility_service.CredibilityService')
    def test_batch_evaluate(self, mock_service_class):
        """Test batch_evaluate function."""
        mock_service = Mock()
        mock_service.batch_evaluate.return_value = {"total": 0}
        mock_service_class.return_value = mock_service
        
        result = batch_evaluate(Mock())
        
        mock_service.batch_evaluate.assert_called_once()
    
    @patch('app.services.credibility_service.CredibilityService')
    def test_get_credibility_stats(self, mock_service_class):
        """Test get_credibility_stats function."""
        mock_service = Mock()
        mock_service.get_stats.return_value = {"total_articles": 0}
        mock_service_class.return_value = mock_service
        
        result = get_credibility_stats(Mock())
        
        mock_service.get_stats.assert_called_once()
