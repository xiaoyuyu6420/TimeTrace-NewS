"""Article deduplication service.

This module provides multi-strategy deduplication for news articles,
including title similarity and content similarity detection.
"""

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Protocol

import jieba
from sqlalchemy.orm import Session

from ..models import Article

logger = logging.getLogger(__name__)

TITLE_SIMILARITY_THRESHOLD = 0.85
CONTENT_SIMILARITY_THRESHOLD = 0.70
MIN_CONTENT_LENGTH = 50


class SimilarityCalculator(Protocol):
    """Protocol for similarity calculation strategies."""
    
    def calculate(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts, returns 0.0 to 1.0."""
        ...


class TitleSimilarityCalculator:
    """Calculate similarity between article titles using SequenceMatcher."""
    
    def __init__(self, threshold: float = TITLE_SIMILARITY_THRESHOLD):
        self.threshold = threshold
    
    def calculate(self, title1: str, title2: str) -> float:
        """Calculate title similarity using SequenceMatcher.
        
        Normalizes titles by removing extra whitespace and converting to lowercase.
        """
        if not title1 or not title2:
            return 0.0
        
        normalized1 = self._normalize(title1)
        normalized2 = self._normalize(title2)
        
        return SequenceMatcher(None, normalized1, normalized2).ratio()
    
    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        text = re.sub(r'\s+', ' ', text.strip())
        return text.lower()
    
    def is_similar(self, title1: str, title2: str) -> bool:
        """Check if two titles are similar above threshold."""
        return self.calculate(title1, title2) >= self.threshold


class ContentSimilarityCalculator:
    """Calculate similarity between article content using Jaccard similarity."""
    
    def __init__(self, threshold: float = CONTENT_SIMILARITY_THRESHOLD):
        self.threshold = threshold
    
    def calculate(self, content1: str, content2: str) -> float:
        """Calculate content similarity using Jaccard similarity with word segmentation.
        
        Uses jieba for Chinese word segmentation.
        """
        if not content1 or not content2:
            return 0.0
        
        if len(content1) < MIN_CONTENT_LENGTH or len(content2) < MIN_CONTENT_LENGTH:
            return 0.0
        
        words1 = self._tokenize(content1)
        words2 = self._tokenize(content2)
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into set of words."""
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        words = jieba.cut(text)
        return set(w.lower() for w in words if len(w.strip()) > 1)
    
    def is_similar(self, content1: str, content2: str) -> bool:
        """Check if two content pieces are similar above threshold."""
        return self.calculate(content1, content2) >= self.threshold


@dataclass
class DuplicatePair:
    """Represents a pair of duplicate articles."""
    article1: Article
    article2: Article
    title_similarity: float
    content_similarity: float
    combined_score: float


class DeduplicationService:
    """Service for finding and handling duplicate articles."""
    
    def __init__(
        self,
        title_threshold: float = TITLE_SIMILARITY_THRESHOLD,
        content_threshold: float = CONTENT_SIMILARITY_THRESHOLD,
        title_weight: float = 0.4,
        content_weight: float = 0.6,
    ):
        self.title_threshold = title_threshold
        self.content_threshold = content_threshold
        self.title_weight = title_weight
        self.content_weight = content_weight
        
        self.title_calculator = TitleSimilarityCalculator(title_threshold)
        self.content_calculator = ContentSimilarityCalculator(content_threshold)
    
    def find_duplicates(
        self,
        article: Article,
        db: Session,
        limit: int = 10,
    ) -> list[DuplicatePair]:
        """Find potential duplicates for a given article.
        
        Args:
            article: Article to check for duplicates
            db: Database session
            limit: Maximum number of duplicates to return
            
        Returns:
            List of DuplicatePair objects sorted by combined score
        """
        candidates = self._get_candidates(article, db)
        
        duplicates = []
        for candidate in candidates:
            if candidate.id == article.id:
                continue
            
            pair = self._calculate_similarity(article, candidate)
            if pair and self._is_duplicate(pair):
                duplicates.append(pair)
        
        duplicates.sort(key=lambda x: x.combined_score, reverse=True)
        return duplicates[:limit]
    
    def _get_candidates(self, article: Article, db: Session) -> list[Article]:
        """Get candidate articles for comparison.
        
        Uses time-based filtering to reduce comparison scope.
        """
        from datetime import timedelta
        from sqlalchemy import and_, or_
        
        query = db.query(Article).filter(Article.id != article.id)
        
        if article.published_at:
            time_window = timedelta(days=7)
            query = query.filter(
                or_(
                    Article.published_at == None,
                    and_(
                        Article.published_at >= article.published_at - time_window,
                        Article.published_at <= article.published_at + time_window,
                    )
                )
            )
        
        return query.limit(100).all()
    
    def _calculate_similarity(
        self,
        article1: Article,
        article2: Article,
    ) -> DuplicatePair | None:
        """Calculate similarity between two articles."""
        title_sim = self.title_calculator.calculate(
            article1.title, article2.title
        )
        content_sim = self.content_calculator.calculate(
            article1.content or "", article2.content or ""
        )
        
        combined = (
            title_sim * self.title_weight + 
            content_sim * self.content_weight
        )
        
        return DuplicatePair(
            article1=article1,
            article2=article2,
            title_similarity=title_sim,
            content_similarity=content_sim,
            combined_score=combined,
        )
    
    def _is_duplicate(self, pair: DuplicatePair) -> bool:
        """Determine if a pair represents a duplicate."""
        if pair.title_similarity >= self.title_threshold:
            return True
        if pair.content_similarity >= self.content_threshold:
            return True
        if pair.combined_score >= (self.title_threshold + self.content_threshold) / 2:
            return True
        return False
    
    def merge_articles(
        self,
        keep_article: Article,
        remove_article: Article,
        db: Session,
    ) -> bool:
        """Merge two articles, keeping one and marking the other as duplicate.
        
        Args:
            keep_article: Article to keep
            remove_article: Article to mark as duplicate
            db: Database session
            
        Returns:
            True if merge was successful
        """
        try:
            if hasattr(remove_article, 'is_duplicate'):
                remove_article.is_duplicate = True
            if hasattr(remove_article, 'duplicate_of'):
                remove_article.duplicate_of = keep_article.id
            
            if not keep_article.content and remove_article.content:
                keep_article.content = remove_article.content
            if not keep_article.summary and remove_article.summary:
                keep_article.summary = remove_article.summary
            
            db.commit()
            logger.info(f"Merged article {remove_article.id} into {keep_article.id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to merge articles: {e}")
            return False
    
    def deduplicate_all(
        self,
        db: Session,
        dry_run: bool = False,
        batch_size: int = 100,
    ) -> dict:
        """Deduplicate all articles in the database.
        
        Args:
            db: Database session
            dry_run: If True, only report duplicates without merging
            batch_size: Number of articles to process per batch
            
        Returns:
            Dictionary with deduplication statistics
        """
        stats = {
            "total_checked": 0,
            "duplicates_found": 0,
            "articles_merged": 0,
            "errors": [],
            "duplicate_pairs": [],
        }
        
        query = db.query(Article)
        if hasattr(Article, 'is_duplicate'):
            query = query.filter(Article.is_duplicate == False)
        
        total = query.count()
        logger.info(f"Starting deduplication for {total} articles")
        
        offset = 0
        processed_ids = set()
        
        while offset < total:
            articles = query.offset(offset).limit(batch_size).all()
            
            for article in articles:
                if article.id in processed_ids:
                    continue
                
                stats["total_checked"] += 1
                duplicates = self.find_duplicates(article, db)
                
                for pair in duplicates:
                    other_id = pair.article2.id
                    if other_id in processed_ids:
                        continue
                    
                    stats["duplicates_found"] += 1
                    
                    duplicate_info = {
                        "article1_id": pair.article1.id,
                        "article2_id": pair.article2.id,
                        "title_similarity": round(pair.title_similarity, 3),
                        "content_similarity": round(pair.content_similarity, 3),
                        "combined_score": round(pair.combined_score, 3),
                    }
                    stats["duplicate_pairs"].append(duplicate_info)
                    
                    if not dry_run:
                        if self.merge_articles(pair.article1, pair.article2, db):
                            stats["articles_merged"] += 1
                            processed_ids.add(other_id)
                        else:
                            stats["errors"].append(f"Failed to merge {pair.article1.id} and {pair.article2.id}")
                    
                    logger.info(
                        f"Duplicate found: {pair.article1.id} <-> {pair.article2.id} "
                        f"(title={pair.title_similarity:.2f}, content={pair.content_similarity:.2f})"
                    )
                
                processed_ids.add(article.id)
            
            offset += batch_size
        
        logger.info(
            f"Deduplication complete: {stats['duplicates_found']} duplicates found, "
            f"{stats['articles_merged']} merged"
        )
        return stats


def find_duplicate_articles(
    db: Session,
    article: Article,
    threshold: float | None = None,
) -> list[DuplicatePair]:
    """Convenience function to find duplicates for a single article."""
    service = DeduplicationService(
        title_threshold=threshold or TITLE_SIMILARITY_THRESHOLD,
        content_threshold=threshold or CONTENT_SIMILARITY_THRESHOLD,
    )
    return service.find_duplicates(article, db)


def deduplicate_all(
    db: Session,
    dry_run: bool = False,
    title_threshold: float = TITLE_SIMILARITY_THRESHOLD,
    content_threshold: float = CONTENT_SIMILARITY_THRESHOLD,
) -> dict:
    """Convenience function for full database deduplication."""
    service = DeduplicationService(
        title_threshold=title_threshold,
        content_threshold=content_threshold,
    )
    return service.deduplicate_all(db, dry_run)


def merge_duplicate_articles(
    db: Session,
    keep_article: Article,
    remove_article: Article,
) -> bool:
    """Convenience function to merge two duplicate articles."""
    service = DeduplicationService()
    return service.merge_articles(keep_article, remove_article, db)
