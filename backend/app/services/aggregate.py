"""Aggregate service - event aggregation from articles."""

import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from ..models import Article, Event, EventArticle, UserFollow
from .timeline import determine_phase

logger = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    linked_count: int
    new_event_count: int
    llm_verified: int


class AggregateService:
    """Service for aggregating articles into events."""

    def __init__(
        self,
        db: Session,
        llm,
        nlp,
        embedding_threshold: float = 0.55,
        fallback_threshold: float = 0.25,
        time_window_days: int = 30,
        auto_close_days: int = 14,
    ):
        self._db = db
        self._llm = llm
        self._nlp = nlp
        self._embedding_threshold = embedding_threshold
        self._fallback_threshold = fallback_threshold
        self._time_window_days = time_window_days
        self._auto_close_days = auto_close_days

    def _get_embed_llm(self):
        """获取向量模型（优先使用独立配置的 embed 模型）。"""
        try:
            from ..deps import get_role_llm
            embed_llm = get_role_llm(self._db, "embed")
            if embed_llm and embed_llm.is_available():
                return embed_llm
        except Exception:
            pass
        return self._llm

    def aggregate_all(self) -> AggregationResult:
        closed_count = self._auto_close_stale()
        if closed_count > 0:
            logger.info(f"Auto-closed {closed_count} stale events")

        unlinked = self._find_unlinked(limit=200)
        if not unlinked:
            logger.info("No unlinked articles to aggregate")
            return AggregationResult(0, 0, 0)

        active_events = self._find_active_events()

        result = AggregationResult(0, 0, 0)

        for article in unlinked:
            self._process_article(article, active_events, result)

        logger.info(
            f"Aggregation: {result.linked_count} linked, "
            f"{result.new_event_count} new events, "
            f"{result.llm_verified} LLM verified"
        )

        return result

    def _auto_close_stale(self) -> int:
        threshold = datetime.now(timezone.utc) - timedelta(days=self._auto_close_days)
        stale = (
            self._db.query(Event)
            .filter(Event.status == "active", Event.updated_at < threshold)
            .all()
        )
        for event in stale:
            event.status = "resolved"
        if stale:
            self._db.commit()
        return len(stale)

    def _find_unlinked(self, limit: int = 200) -> list[Article]:
        linked_ids = select(EventArticle.article_id).distinct()
        return (
            self._db.query(Article)
            .filter(~Article.id.in_(linked_ids))
            .order_by(Article.published_at.desc())
            .limit(limit)
            .all()
        )

    def _find_active_events(self) -> list[Event]:
        return (
            self._db.query(Event)
            .filter(Event.status == "active")
            .options(joinedload(Event.article_links).joinedload(EventArticle.article))
            .all()
        )

    def _process_article(self, article, events: list, result: AggregationResult) -> None:
        if not article.keywords:
            text = f"{article.title} {article.content[:1000] if article.content else ''}"
            article.keywords = self._nlp.extract_keywords(text)
            article.entities = self._nlp.extract_entities(text)

        if not article.embedding:
            embed_llm = self._get_embed_llm()
            if embed_llm.is_available():
                article.embedding = embed_llm.get_embedding(
                    f"{article.title}。{(article.content or '')[:500]}"
                )

        best_event, best_score = self._find_best_match(article, events)

        threshold = self._embedding_threshold if article.embedding else self._fallback_threshold

        if best_event and best_score >= threshold:
            self._link_article_to_event(article, best_event, best_score, result)
        else:
            self._create_new_event(article, events, result)

    def _find_best_match(self, article, events: list) -> tuple:
        best_event = None
        best_score = 0.0

        for event in events:
            score = self._compute_similarity(article, event)
            if score > best_score:
                best_score = score
                best_event = event

        return best_event, best_score

    def _compute_similarity(self, article, event) -> float:
        if article.embedding and event.embedding:
            return self._cosine_similarity(article.embedding, event.embedding)

        if article.embedding:
            event_embs = []
            for link in getattr(event, 'article_links', []):
                if hasattr(link, 'article') and link.article and link.article.embedding:
                    event_embs.append(link.article.embedding)
            if event_embs:
                max_sim = max(
                    self._cosine_similarity(article.embedding, emb)
                    for emb in event_embs
                )
                return max_sim

        return self._fallback_similarity(article, event)

    def _cosine_similarity(self, v1: list[float], v2: list[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0

        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = sum(a * a for a in v1) ** 0.5
        n2 = sum(b * b for b in v2) ** 0.5

        if not n1 or not n2:
            return 0.0
        return dot / (n1 * n2)

    def _fallback_similarity(self, article, event) -> float:
        kw_sim = self._nlp.keyword_similarity(
            article.keywords or [],
            self._collect_event_keywords(event)
        )

        ent_sim = self._nlp.entity_similarity(
            article.entities or [],
            self._collect_event_entities(event)
        )

        title_sim = self._title_similarity(article.title, event.title)

        return kw_sim * 0.4 + ent_sim * 0.35 + title_sim * 0.25

    def _collect_event_keywords(self, event) -> list[str]:
        keywords = []
        for link in getattr(event, 'article_links', []):
            if hasattr(link, 'article') and link.article and link.article.keywords:
                keywords.extend(link.article.keywords)
        return list(set(keywords))

    def _collect_event_entities(self, event) -> list[dict]:
        entities = []
        for link in getattr(event, 'article_links', []):
            if hasattr(link, 'article') and link.article and link.article.entities:
                entities.extend(link.article.entities)
        return entities

    def _title_similarity(self, t1: str, t2: str) -> float:
        if not t1 or not t2:
            return 0.0
        set1, set2 = set(t1), set(t2)
        intersection = set1 & set2
        union = set1 | set2
        return len(intersection) / len(union) if union else 0.0

    def _link_article_to_event(self, article, event, score: float, result: AggregationResult) -> None:
        # 计算当前事件已有文章数，用于阶段判断
        existing_count = (
            self._db.query(func.count(EventArticle.article_id))
            .filter(EventArticle.event_id == event.id)
            .scalar() or 0
        )
        phase = determine_phase(event, article, existing_count)

        link = EventArticle(
            event_id=event.id,
            article_id=article.id,
            relevance_score=score,
            phase=phase,
        )
        self._db.add(link)

        if article.published_at:
            if not event.start_date or article.published_at < event.start_date:
                event.start_date = article.published_at
            if not event.end_date or article.published_at > event.end_date:
                event.end_date = article.published_at
        event.updated_at = datetime.now(timezone.utc)

        self._db.commit()
        result.linked_count += 1

    def _create_new_event(self, article, events: list, result: AggregationResult) -> None:
        event = Event(
            title=article.title,
            summary=article.summary or (article.content[:200] if article.content else ""),
            category="",
            importance=3,
            embedding=article.embedding,
            start_date=article.published_at,
            end_date=article.published_at,
        )

        self._db.add(event)
        self._db.commit()
        self._db.refresh(event)

        link = EventArticle(
            event_id=event.id,
            article_id=article.id,
            relevance_score=1.0,
            phase="trigger",
        )
        self._db.add(link)
        self._db.commit()

        events.append(event)
        result.new_event_count += 1
