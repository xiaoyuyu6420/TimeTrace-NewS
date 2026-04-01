"""Credibility evaluation service.

This module provides automatic credibility scoring for news articles
based on multiple factors including source reputation, content completeness,
cross-reference validation, and timeliness.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Article, RssSource

logger = logging.getLogger(__name__)

SOURCE_WEIGHT = 0.30
CONTENT_WEIGHT = 0.20
CROSS_REF_WEIGHT = 0.30
TIMELINESS_WEIGHT = 0.20

CREDIBILITY_TIERS = {
    'A': {'min': 90, 'max': 100, 'default_reputation': 95.0},
    'B': {'min': 70, 'max': 89, 'default_reputation': 75.0},
    'C': {'min': 50, 'max': 69, 'default_reputation': 55.0},
    'D': {'min': 0, 'max': 49, 'default_reputation': 25.0},
}

FRESHNESS_HOURS_HIGH = 24
FRESHNESS_HOURS_MEDIUM = 72
FRESHNESS_HOURS_LOW = 168

MIN_TITLE_LENGTH = 5
MIN_CONTENT_LENGTH = 100
OPTIMAL_CONTENT_LENGTH = 500


@dataclass
class CredibilityFactors:
    """Data class for credibility scoring factors."""
    source_score: float = 0.0
    content_score: float = 0.0
    cross_ref_score: float = 0.0
    timeliness_score: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CredibilityResult:
    """Data class for credibility evaluation result."""
    score: float
    factors: CredibilityFactors
    tier: str
    confidence: float


class SourceCredibilityEvaluator:
    """Evaluates credibility based on RSS source reputation."""
    
    def __init__(self, tier_defaults: dict | None = None):
        self.tier_defaults = tier_defaults or CREDIBILITY_TIERS
    
    def evaluate(self, article: Article, db: Session) -> tuple[float, dict]:
        """Evaluate source credibility.
        
        Args:
            article: Article to evaluate
            db: Database session
            
        Returns:
            Tuple of (score, details_dict)
        """
        details = {
            'source_id': article.rss_source_id,
            'source_name': None,
            'tier': 'C',
            'reputation': 50.0,
        }
        
        if article.rss_source_id is None:
            details['reason'] = 'No RSS source associated'
            return 50.0, details
        
        source = db.query(RssSource).filter(
            RssSource.id == article.rss_source_id
        ).first()
        
        if source is None:
            details['reason'] = 'RSS source not found'
            return 50.0, details
        
        details['source_name'] = source.name
        
        tier = getattr(source, 'credibility_tier', 'C') or 'C'
        reputation = getattr(source, 'source_reputation', None)
        
        details['tier'] = tier
        
        if reputation is not None:
            score = float(reputation)
        else:
            tier_info = self.tier_defaults.get(tier, self.tier_defaults['C'])
            score = tier_info['default_reputation']
        
        details['reputation'] = score
        return score, details


class ContentCompletenessEvaluator:
    """Evaluates credibility based on content completeness."""
    
    def __init__(
        self,
        min_title_length: int = MIN_TITLE_LENGTH,
        min_content_length: int = MIN_CONTENT_LENGTH,
        optimal_content_length: int = OPTIMAL_CONTENT_LENGTH,
    ):
        self.min_title_length = min_title_length
        self.min_content_length = min_content_length
        self.optimal_content_length = optimal_content_length
    
    def evaluate(self, article: Article) -> tuple[float, dict]:
        """Evaluate content completeness.
        
        Args:
            article: Article to evaluate
            
        Returns:
            Tuple of (score, details_dict)
        """
        details = {
            'title_length': len(article.title) if article.title else 0,
            'content_length': len(article.content) if article.content else 0,
            'has_summary': bool(article.summary),
            'has_keywords': bool(article.keywords),
            'has_entities': bool(article.entities),
            'has_published_date': article.published_at is not None,
        }
        
        score = 0.0
        max_score = 100.0
        
        title_len = details['title_length']
        if title_len >= self.min_title_length:
            score += 20
        elif title_len > 0:
            score += 10 * (title_len / self.min_title_length)
        
        content_len = details['content_length']
        if content_len >= self.optimal_content_length:
            score += 30
        elif content_len >= self.min_content_length:
            ratio = (content_len - self.min_content_length) / (
                self.optimal_content_length - self.min_content_length
            )
            score += 15 + 15 * ratio
        elif content_len > 0:
            score += 10 * (content_len / self.min_content_length)
        
        if details['has_summary']:
            score += 15
        if details['has_keywords']:
            score += 10
        if details['has_entities']:
            score += 10
        if details['has_published_date']:
            score += 15
        
        return min(score, max_score), details


class CrossReferenceEvaluator:
    """Evaluates credibility based on cross-reference with other sources."""
    
    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
    
    def evaluate(self, article: Article, db: Session) -> tuple[float, dict]:
        """Evaluate cross-reference credibility.
        
        More sources reporting the same event increases credibility.
        
        Args:
            article: Article to evaluate
            db: Database session
            
        Returns:
            Tuple of (score, details_dict)
        """
        details = {
            'related_articles': 0,
            'unique_sources': 0,
            'event_id': None,
        }
        
        if article.embedding is None:
            details['reason'] = 'No embedding available'
            return 50.0, details
        
        from ..models import EventArticle
        
        event_links = db.query(EventArticle).filter(
            EventArticle.article_id == article.id
        ).all()
        
        if not event_links:
            details['reason'] = 'Not associated with any event'
            return 50.0, details
        
        event_id = event_links[0].event_id
        details['event_id'] = event_id
        
        related = db.query(EventArticle).filter(
            EventArticle.event_id == event_id,
            EventArticle.article_id != article.id,
        ).count()
        
        details['related_articles'] = related
        
        source_count = db.query(func.count(func.distinct(Article.rss_source_id))).join(
            EventArticle, Article.id == EventArticle.article_id
        ).filter(
            EventArticle.event_id == event_id,
            Article.id != article.id,
        ).scalar() or 0
        
        details['unique_sources'] = source_count
        
        if source_count >= 5:
            score = 100.0
        elif source_count >= 3:
            score = 85.0
        elif source_count >= 2:
            score = 70.0
        elif source_count >= 1:
            score = 60.0
        else:
            score = 50.0
        
        return score, details


class TimelinessEvaluator:
    """Evaluates credibility based on news timeliness."""
    
    def __init__(
        self,
        fresh_hours: int = FRESHNESS_HOURS_HIGH,
        medium_hours: int = FRESHNESS_HOURS_MEDIUM,
        low_hours: int = FRESHNESS_HOURS_LOW,
    ):
        self.fresh_hours = fresh_hours
        self.medium_hours = medium_hours
        self.low_hours = low_hours
    
    def evaluate(self, article: Article) -> tuple[float, dict]:
        """Evaluate timeliness score.
        
        Newer articles get higher scores for timeliness.
        
        Args:
            article: Article to evaluate
            
        Returns:
            Tuple of (score, details_dict)
        """
        now = datetime.now(timezone.utc)
        
        details = {
            'published_at': article.published_at.isoformat() if article.published_at else None,
            'hours_old': None,
        }
        
        if article.published_at is None:
            details['reason'] = 'No publication date'
            return 50.0, details
        
        age = now - article.published_at
        hours_old = age.total_seconds() / 3600
        details['hours_old'] = round(hours_old, 1)
        
        if hours_old <= self.fresh_hours:
            score = 100.0
        elif hours_old <= self.medium_hours:
            ratio = (hours_old - self.fresh_hours) / (self.medium_hours - self.fresh_hours)
            score = 100.0 - 20 * ratio
        elif hours_old <= self.low_hours:
            ratio = (hours_old - self.medium_hours) / (self.low_hours - self.medium_hours)
            score = 80.0 - 30 * ratio
        else:
            score = max(20.0, 50.0 - hours_old / 168)
        
        return score, details


class CredibilityService:
    """Main service for evaluating article credibility."""
    
    def __init__(
        self,
        source_weight: float = SOURCE_WEIGHT,
        content_weight: float = CONTENT_WEIGHT,
        cross_ref_weight: float = CROSS_REF_WEIGHT,
        timeliness_weight: float = TIMELINESS_WEIGHT,
    ):
        self.weights = {
            'source': source_weight,
            'content': content_weight,
            'cross_ref': cross_ref_weight,
            'timeliness': timeliness_weight,
        }
        
        self.source_evaluator = SourceCredibilityEvaluator()
        self.content_evaluator = ContentCompletenessEvaluator()
        self.cross_ref_evaluator = CrossReferenceEvaluator()
        self.timeliness_evaluator = TimelinessEvaluator()
    
    def evaluate(self, article: Article, db: Session) -> CredibilityResult:
        """Evaluate credibility for a single article.
        
        Args:
            article: Article to evaluate
            db: Database session
            
        Returns:
            CredibilityResult with score and factors
        """
        source_score, source_details = self.source_evaluator.evaluate(article, db)
        content_score, content_details = self.content_evaluator.evaluate(article)
        cross_ref_score, cross_ref_details = self.cross_ref_evaluator.evaluate(article, db)
        timeliness_score, timeliness_details = self.timeliness_evaluator.evaluate(article)
        
        factors = CredibilityFactors(
            source_score=source_score,
            content_score=content_score,
            cross_ref_score=cross_ref_score,
            timeliness_score=timeliness_score,
            details={
                'source': source_details,
                'content': content_details,
                'cross_ref': cross_ref_details,
                'timeliness': timeliness_details,
            },
        )
        
        weighted_score = (
            source_score * self.weights['source'] +
            content_score * self.weights['content'] +
            cross_ref_score * self.weights['cross_ref'] +
            timeliness_score * self.weights['timeliness']
        )
        
        final_score = max(0.0, min(100.0, weighted_score))
        
        tier = self._get_tier(final_score)
        confidence = self._calculate_confidence(factors)
        
        return CredibilityResult(
            score=round(final_score, 2),
            factors=factors,
            tier=tier,
            confidence=round(confidence, 2),
        )
    
    def _get_tier(self, score: float) -> str:
        """Get credibility tier from score."""
        if score >= 90:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 50:
            return 'C'
        else:
            return 'D'
    
    def _calculate_confidence(self, factors: CredibilityFactors) -> float:
        """Calculate confidence level of the credibility score.
        
        Higher confidence when more data is available.
        """
        confidence = 0.5
        
        details = factors.details
        
        if details.get('source', {}).get('source_id'):
            confidence += 0.15
        if details.get('content', {}).get('content_length', 0) >= MIN_CONTENT_LENGTH:
            confidence += 0.15
        if details.get('cross_ref', {}).get('related_articles', 0) > 0:
            confidence += 0.15
        if details.get('timeliness', {}).get('hours_old') is not None:
            confidence += 0.05
        
        return min(1.0, confidence)
    
    def batch_evaluate(
        self,
        db: Session,
        article_ids: list[int] | None = None,
        force_recalculate: bool = False,
        batch_size: int = 100,
    ) -> dict:
        """Evaluate credibility for multiple articles.
        
        Args:
            db: Database session
            article_ids: Optional list of article IDs to evaluate
            force_recalculate: If True, recalculate even if score exists
            batch_size: Number of articles to process per batch
            
        Returns:
            Dictionary with evaluation statistics
        """
        stats = {
            'total_evaluated': 0,
            'average_score': 0.0,
            'tier_distribution': {'A': 0, 'B': 0, 'C': 0, 'D': 0},
            'errors': [],
        }
        
        query = db.query(Article)
        
        if article_ids:
            query = query.filter(Article.id.in_(article_ids))
        
        if not force_recalculate and hasattr(Article, 'credibility_score'):
            query = query.filter(
                (Article.credibility_score == None) |
                (Article.credibility_score == 0)
            )
        
        total = query.count()
        logger.info(f"Starting credibility evaluation for {total} articles")
        
        scores = []
        offset = 0
        
        while offset < total:
            articles = query.offset(offset).limit(batch_size).all()
            
            for article in articles:
                try:
                    result = self.evaluate(article, db)
                    
                    if hasattr(article, 'credibility_score'):
                        article.credibility_score = result.score
                    if hasattr(article, 'credibility_factors'):
                        article.credibility_factors = {
                            'source_score': result.factors.source_score,
                            'content_score': result.factors.content_score,
                            'cross_ref_score': result.factors.cross_ref_score,
                            'timeliness_score': result.factors.timeliness_score,
                            'details': result.factors.details,
                            'tier': result.tier,
                            'confidence': result.confidence,
                        }
                    
                    scores.append(result.score)
                    stats['tier_distribution'][result.tier] += 1
                    stats['total_evaluated'] += 1
                    
                except Exception as e:
                    error_msg = f"Error evaluating article {article.id}: {e}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)
            
            db.commit()
            offset += batch_size
        
        if scores:
            stats['average_score'] = round(sum(scores) / len(scores), 2)
        
        logger.info(
            f"Credibility evaluation complete: {stats['total_evaluated']} articles, "
            f"average score: {stats['average_score']}"
        )
        return stats
    
    def get_stats(self, db: Session) -> dict:
        """Get credibility statistics for all articles.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with credibility statistics
        """
        if not hasattr(Article, 'credibility_score'):
            return {'error': 'Credibility scoring not enabled'}
        
        total = db.query(func.count(Article.id)).scalar() or 0
        scored = db.query(func.count(Article.id)).filter(
            Article.credibility_score != None
        ).scalar() or 0
        
        avg_score = db.query(func.avg(Article.credibility_score)).filter(
            Article.credibility_score != None
        ).scalar() or 0
        
        tier_distribution = {}
        for tier in ['A', 'B', 'C', 'D']:
            if hasattr(Article, 'credibility_factors'):
                count = db.query(func.count(Article.id)).filter(
                    Article.credibility_factors['tier'].as_string() == tier
                ).scalar() or 0
            else:
                if tier == 'A':
                    count = db.query(func.count(Article.id)).filter(
                        Article.credibility_score >= 90
                    ).scalar() or 0
                elif tier == 'B':
                    count = db.query(func.count(Article.id)).filter(
                        Article.credibility_score >= 70,
                        Article.credibility_score < 90
                    ).scalar() or 0
                elif tier == 'C':
                    count = db.query(func.count(Article.id)).filter(
                        Article.credibility_score >= 50,
                        Article.credibility_score < 70
                    ).scalar() or 0
                else:
                    count = db.query(func.count(Article.id)).filter(
                        Article.credibility_score < 50
                    ).scalar() or 0
            tier_distribution[tier] = count
        
        return {
            'total_articles': total,
            'scored_articles': scored,
            'average_score': round(float(avg_score), 2),
            'tier_distribution': tier_distribution,
        }


def calculate_credibility(article: Article, db: Session) -> CredibilityResult:
    """Convenience function to evaluate single article credibility."""
    service = CredibilityService()
    return service.evaluate(article, db)


def batch_evaluate(
    db: Session,
    article_ids: list[int] | None = None,
    force_recalculate: bool = False,
) -> dict:
    """Convenience function for batch credibility evaluation."""
    service = CredibilityService()
    return service.batch_evaluate(db, article_ids, force_recalculate)


def get_credibility_stats(db: Session) -> dict:
    """Convenience function to get credibility statistics."""
    service = CredibilityService()
    return service.get_stats(db)
