"""ORM models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer,
    JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), default="user")  # user | admin
    avatar = Column(String(256), default="")
    created_at = Column(DateTime, default=_now)

    follows = relationship("UserFollow", back_populates="user", cascade="all, delete-orphan")


class RssSource(Base):
    __tablename__ = "rss_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    category = Column(String(50), default="tech")
    is_active = Column(Boolean, default=True)
    last_crawled = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    credibility_tier = Column(String(1), default="C")
    source_reputation = Column(Float, default=50.0)

    articles = relationship("Article", back_populates="rss_source")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, default="")
    summary = Column(Text, default="")
    source_url = Column(String(500), default="")
    rss_source_id = Column(Integer, ForeignKey("rss_sources.id"), nullable=True)
    keywords = Column(JSON, default=list)
    entities = Column(JSON, default=list)
    embedding = Column(JSON, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    credibility_score = Column(Float, default=0.0)
    credibility_factors = Column(JSON, nullable=True)
    duplicate_of = Column(Integer, ForeignKey("articles.id"), nullable=True)
    is_duplicate = Column(Boolean, default=False)

    rss_source = relationship("RssSource", back_populates="articles")
    event_links = relationship("EventArticle", back_populates="article", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text, default="")
    category = Column(String(50), default="")
    importance = Column(Integer, default=3)  # 1-5
    status = Column(String(20), default="active")  # active | resolved
    embedding = Column(JSON, nullable=True)  # centroid vector of articles
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    article_links = relationship("EventArticle", back_populates="event", cascade="all, delete-orphan")
    follows = relationship("UserFollow", back_populates="event", cascade="all, delete-orphan")


class EventArticle(Base):
    __tablename__ = "event_articles"

    event_id = Column(Integer, ForeignKey("events.id"), primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), primary_key=True)
    relevance_score = Column(Float, default=0.0)

    event = relationship("Event", back_populates="article_links")
    article = relationship("Article", back_populates="event_links")


class UserFollow(Base):
    __tablename__ = "user_follows"
    __table_args__ = (UniqueConstraint("user_id", "event_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="follows")
    event = relationship("Event", back_populates="follows")
