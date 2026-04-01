"""Text processing: keyword extraction + entity recognition + embedding."""

import json
import logging
from collections import Counter

import jieba
import jieba.analyse
from sqlalchemy.orm import Session

from ..models import Article
from .llm_service import get_embedding

logger = logging.getLogger(__name__)

# Stop words
STOP_WORDS = set(
    "的了是在我有和就不人都一上也很到说要去你会着看好自己这那他她它们让被把"
    "从得对给与而已之以能将而但如因为所如果虽然只是不过然而此外而且并且或者"
)


def extract_keywords(text: str, topk: int = 10) -> list[str]:
    """TF-IDF keyword extraction via jieba."""
    if not text:
        return []
    keywords = jieba.analyse.extract_tags(text, topK=topk, withWeight=False)
    return [w for w in keywords if w not in STOP_WORDS and len(w) > 1]


def extract_entities(text: str) -> list[dict]:
    """Simple NER: extract named entities using jieba's posseg."""
    if not text:
        return []
    import jieba.posseg as pseg

    entities = []
    seen = set()
    for word, flag in pseg.cut(text):
        if flag in ("nr", "ns", "nt", "nz", "eng") and word not in seen and len(word) > 1:
            type_map = {"nr": "PERSON", "ns": "LOCATION", "nt": "ORG", "nz": "MISC", "eng": "ENG"}
            entities.append({"name": word, "type": type_map.get(flag, "MISC")})
            seen.add(word)
    return entities[:15]


def extract_embedding_for_article(article: Article) -> list[float] | None:
    """Get semantic embedding for an article (title + content excerpt)."""
    text = f"{article.title}。{(article.content or '')[:500]}"
    vec = get_embedding(text)
    if vec:
        logger.debug(f"Got embedding for article {article.id} (dim={len(vec)})")
    return vec


def process_unprocessed(db: Session):
    """Process articles that have no keywords yet. Also extract embeddings."""
    articles = db.query(Article).filter(Article.keywords == None).limit(100).all()
    if not articles:
        articles = db.query(Article).filter(Article.keywords == "[]").limit(100).all()

    logger.info(f"Processing {len(articles)} articles...")
    for article in articles:
        text = f"{article.title} {article.content[:1000]}"
        article.keywords = extract_keywords(text)
        article.entities = extract_entities(text)

        # Extract embedding (best-effort, non-blocking)
        if not article.embedding:
            article.embedding = extract_embedding_for_article(article)

    db.commit()

    # Also generate embeddings for articles that have keywords but no embedding
    no_embedding = (
        db.query(Article)
        .filter(Article.embedding == None)
        .limit(50)
        .all()
    )
    if no_embedding:
        logger.info(f"Extracting embeddings for {len(no_embedding)} articles...")
        for article in no_embedding:
            article.embedding = extract_embedding_for_article(article)
        db.commit()

    logger.info(f"Processed {len(articles)} articles")
