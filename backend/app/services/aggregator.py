"""Event aggregation: match articles to events via semantic similarity.

Pipeline:
  1. Time-window filter — only compare with active events from last N days
  2. Embedding cosine similarity (primary) — fallback to keyword overlap
  3. LLM verification for borderline scores
  4. Auto-close stale events
"""

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..models import Article, Event, EventArticle
from .llm_service import (
    cosine_similarity, compute_centroid, get_embedding,
    verify_same_event, generate_event_title, generate_event_summary,
)

logger = logging.getLogger(__name__)


# ─── Fallback similarity (keyword / entity / title) ──────

def _keyword_similarity(kw1: list[str], kw2: list[str]) -> float:
    """Jaccard-like keyword overlap score."""
    if not kw1 or not kw2:
        return 0.0
    set1, set2 = set(kw1), set(kw2)
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union) if union else 0.0


def _entity_similarity(ent1: list[dict], ent2: list[dict]) -> float:
    """Entity overlap score with type weighting."""
    if not ent1 or not ent2:
        return 0.0
    type_weight = {"PERSON": 0.4, "ORG": 0.3, "LOCATION": 0.3}
    names1 = {e["name"]: e["type"] for e in ent1}
    names2 = {e["name"]: e["type"] for e in ent2}
    common = set(names1.keys()) & set(names2.keys())
    if not common:
        return 0.0
    score = sum(type_weight.get(names1[n], 0.2) for n in common)
    max_score = sum(
        max(type_weight.get(names1.get(n, ""), 0.2), type_weight.get(names2.get(n, ""), 0.2))
        for n in common
    )
    return score / max_score if max_score else 0.0


def _title_char_similarity(t1: str, t2: str) -> float:
    """Character-level title overlap."""
    if not t1 or not t2:
        return 0.0
    set1, set2 = set(t1), set(t2)
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union) if union else 0.0


def _fallback_score(article: Article, event: Event) -> float:
    """Compute similarity using keyword/entity/title overlap (no embeddings)."""
    ak = article.keywords or []
    ek_strs = []
    for link in event.article_links:
        if link.article.keywords:
            ek_strs.extend(link.article.keywords)
    ek = list(set(ek_strs))

    ent_a = article.entities or []
    ent_e = []
    for link in event.article_links:
        if link.article.entities:
            ent_e.extend(link.article.entities)

    kw_sim = _keyword_similarity(ak, ek)
    ent_sim = _entity_similarity(ent_a, ent_e)
    t_sim = _title_char_similarity(article.title, event.title)

    return kw_sim * 0.4 + ent_sim * 0.35 + t_sim * 0.25


# ─── Main similarity computation ─────────────────────────

def compute_similarity(article: Article, event: Event) -> float:
    """Compute article-event similarity. Uses embeddings when available, falls back to keywords."""
    art_emb = article.embedding

    # Collect embeddings from event's articles
    event_embs = []
    for link in event.article_links:
        if link.article and link.article.embedding:
            event_embs.append(link.article.embedding)

    # Also consider the event centroid if stored
    if event.embedding:
        event_embs.append(event.embedding)

    if art_emb and event_embs:
        # Embedding-based: take max similarity across event's article embeddings
        best_sim = 0.0
        for ev_emb in event_embs:
            sim = cosine_similarity(art_emb, ev_emb)
            if sim > best_sim:
                best_sim = sim
        return best_sim

    # Fallback to keyword/entity/title overlap
    return _fallback_score(article, event)


# ─── Auto-close stale events ─────────────────────────────

def auto_close_stale_events(db: Session):
    """Close events with no new articles for EVENT_AUTO_CLOSE_DAYS."""
    threshold = datetime.now(timezone.utc) - timedelta(days=settings.EVENT_AUTO_CLOSE_DAYS)
    stale = (
        db.query(Event)
        .filter(Event.status == "active", Event.updated_at < threshold)
        .all()
    )
    for event in stale:
        event.status = "resolved"
        logger.info(f"Auto-closed stale event: {event.title} (id={event.id})")
    if stale:
        db.commit()


# ─── Main aggregation logic ──────────────────────────────

def aggregate_all(db: Session):
    """Match unlinked articles to events using semantic similarity."""
    # Step 0: Auto-close stale events
    auto_close_stale_events(db)

    # Step 1: Get unlinked articles
    linked_ids = select(EventArticle.article_id).distinct()
    unlinked = (
        db.query(Article)
        .filter(~Article.id.in_(linked_ids))
        .order_by(Article.published_at.desc())
        .limit(200)
        .all()
    )

    if not unlinked:
        logger.info("No unlinked articles to aggregate")
        return

    # Step 2: Get active events within time window
    time_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.EVENT_TIME_WINDOW_DAYS)
    active_events = (
        db.query(Event)
        .filter(Event.status == "active")
        .options(joinedload(Event.article_links).joinedload(EventArticle.article))
        .all()
    )

    # Also include events outside window that have been recently updated
    # (allows long-running events to still get matches)
    recent_events = [e for e in active_events if (e.updated_at or e.created_at) and (e.updated_at or e.created_at) >= time_cutoff]
    older_events = [e for e in active_events if e not in recent_events]

    threshold = settings.EMBEDDING_THRESHOLD
    verify_lo, verify_hi = settings.EMBEDDING_VERIFY_RANGE
    fallback_threshold = settings.SIMILARITY_THRESHOLD

    new_event_count = 0
    linked_count = 0
    llm_verified = 0

    for article in unlinked:
        # Ensure article has keywords and embedding
        if not article.keywords:
            from .processor import extract_keywords, extract_entities
            text = f"{article.title} {article.content[:1000]}"
            article.keywords = extract_keywords(text)
            article.entities = extract_entities(text)

        if not article.embedding:
            from .processor import extract_embedding_for_article
            article.embedding = extract_embedding_for_article(article)

        # Phase 1: Compare with recent events (higher priority)
        best_event, best_score = _find_best_match(article, recent_events, threshold)

        # Phase 2: If no good match in recent, check older events with higher threshold
        if not best_event:
            best_event, best_score = _find_best_match(article, older_events, threshold + 0.1)

        if best_event and best_score >= threshold:
            # Phase 3: LLM verification for borderline scores
            use_embedding = bool(article.embedding)
            effective_verify_lo = verify_lo if use_embedding else fallback_threshold * 0.8
            effective_verify_hi = verify_hi if use_embedding else fallback_threshold * 1.2

            if effective_verify_lo <= best_score < effective_verify_hi and settings.LLM_API_KEY:
                # Borderline — ask LLM
                is_same = verify_same_event(
                    article.title, best_event.title,
                    article.summary or "", best_event.summary or "",
                )
                if is_same is False:
                    best_event = None  # LLM says no match
                    llm_verified += 1
                elif is_same is True:
                    llm_verified += 1
                    # LLM confirmed, proceed to link

            if best_event:
                # Link article to event
                link = EventArticle(
                    event_id=best_event.id,
                    article_id=article.id,
                    relevance_score=best_score,
                )
                db.add(link)
                linked_count += 1

                # Update event dates
                if article.published_at:
                    if not best_event.start_date or article.published_at < best_event.start_date:
                        best_event.start_date = article.published_at
                    if not best_event.end_date or article.published_at > best_event.end_date:
                        best_event.end_date = article.published_at
                best_event.updated_at = datetime.now(timezone.utc)

                # Update event centroid embedding
                _update_event_embedding(best_event)
        else:
            # No match — create new event
            title = article.title
            summary = article.summary or article.content[:200] if article.content else ""

            event = Event(
                title=title,
                summary=summary,
                category="",
                importance=3,
                embedding=article.embedding,  # Seed with first article's embedding
                start_date=article.published_at,
                end_date=article.published_at,
            )
            db.add(event)
            db.flush()  # Get event.id

            link = EventArticle(
                event_id=event.id,
                article_id=article.id,
                relevance_score=1.0,
            )
            db.add(link)
            active_events.append(event)
            recent_events.append(event)
            new_event_count += 1

    db.commit()

    # LLM enhancement for new events
    if new_event_count > 0:
        _enhance_new_events(db)

    logger.info(
        f"Aggregation: {linked_count} linked, {new_event_count} new events, "
        f"{llm_verified} LLM verified"
    )


def _find_best_match(
    article: Article, events: list[Event], threshold: float
) -> tuple[Event | None, float]:
    """Find the best matching event for an article."""
    best_event = None
    best_score = 0.0

    for event in events:
        score = compute_similarity(article, event)
        if score > best_score:
            best_score = score
            best_event = event

    if best_score < threshold:
        return None, best_score

    return best_event, best_score


def _update_event_embedding(event: Event):
    """Recalculate the event's centroid embedding from its articles."""
    embs = []
    for link in event.article_links:
        if link.article and link.article.embedding:
            embs.append(link.article.embedding)
    if embs:
        event.embedding = compute_centroid(embs)


# ─── LLM Enhancement ────────────────────────────────────

def _enhance_new_events(db: Session):
    """Use LLM to improve event titles and summaries."""
    if not settings.LLM_API_KEY:
        return
    try:
        events = (
            db.query(Event)
            .filter(Event.category == "")
            .limit(10)
            .all()
        )
        for event in events:
            articles = (
                db.query(Article)
                .join(EventArticle, EventArticle.article_id == Article.id)
                .filter(EventArticle.event_id == event.id)
                .all()
            )
            if not articles:
                continue

            texts = [f"- {a.title}" for a in articles[:5]]
            prompt_text = "\n".join(texts)

            new_title = generate_event_title(prompt_text)
            if new_title:
                event.title = new_title

            new_summary = generate_event_summary(prompt_text)
            if new_summary:
                event.summary = new_summary

        db.commit()
    except Exception as e:
        logger.warning(f"LLM enhancement failed: {e}")
