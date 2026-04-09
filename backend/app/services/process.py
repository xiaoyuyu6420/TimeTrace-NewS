"""Process service - text processing for articles."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Article, EventArticle

logger = logging.getLogger(__name__)


class ProcessService:
    """Service for processing articles - keyword extraction, embedding, etc."""

    def __init__(self, db: Session, llm, nlp):
        self._db = db
        self._llm = llm
        self._nlp = nlp

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

    def process_unprocessed(self, limit: int = 100) -> dict:
        articles = (
            self._db.query(Article)
            .filter((Article.keywords == None) | (Article.keywords == "[]"))
            .limit(limit)
            .all()
        )

        processed = 0
        for article in articles:
            self._process_article(article)
            processed += 1

        return {
            "success": True,
            "processed": processed,
        }

    def process_article(self, article_id: int) -> dict:
        article = self._db.query(Article).filter(Article.id == article_id).first()
        if not article:
            return {"success": False, "error": "Article not found"}

        self._process_article(article)
        return {"success": True, "article_id": article_id}

    def _process_article(self, article) -> None:
        text = f"{article.title} {article.content[:1000] if article.content else ''}"

        if not article.keywords:
            article.keywords = self._nlp.extract_keywords(text)

        if not article.entities:
            article.entities = self._nlp.extract_entities(text)

        if not article.embedding:
            embed_llm = self._get_embed_llm()
            if embed_llm.is_available():
                article.embedding = self._get_article_embedding(article)

        if not article.summary and self._llm.is_available():
            article.summary = self._llm.generate_summary(
                f"{article.title}。{article.content[:500] if article.content else ''}"
            ) or ""

        self._db.commit()

    def _get_article_embedding(self, article) -> list[float] | None:
        text = f"{article.title}。{(article.content or '')[:500]}"
        embed_llm = self._get_embed_llm()
        return embed_llm.get_embedding(text)

    def generate_embeddings(self, limit: int = 50) -> dict:
        articles = (
            self._db.query(Article)
            .filter(Article.embedding == None)
            .limit(limit)
            .all()
        )

        generated = 0
        embed_llm = self._get_embed_llm()
        for article in articles:
            if embed_llm.is_available():
                article.embedding = self._get_article_embedding(article)
                self._db.commit()
                generated += 1

        return {
            "success": True,
            "generated": generated,
        }
