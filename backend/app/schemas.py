"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ─── Auth ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=6, max_length=100)

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


# ─── Users ──────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    avatar: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── RSS Sources ────────────────────────────────────────

class RssSourceCreate(BaseModel):
    name: str
    url: str
    category: str = "tech"

class RssSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class RssSourceOut(BaseModel):
    id: int
    name: str
    url: str
    category: str
    is_active: bool
    last_crawled: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── Articles ───────────────────────────────────────────

class ArticleOut(BaseModel):
    id: int
    title: str
    content: str = ""
    summary: str = ""
    source_url: str = ""
    keywords: list = []
    entities: list = []
    rss_source_id: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── Events ─────────────────────────────────────────────

class EventOut(BaseModel):
    id: int
    title: str
    summary: str = ""
    category: str = ""
    importance: int = 3
    status: str = "active"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    article_count: int = 0
    follow_count: int = 0
    is_followed: bool = False

    model_config = {"from_attributes": True}

class EventDetail(EventOut):
    articles: list[ArticleOut] = []


# ─── Follow ─────────────────────────────────────────────

class FollowOut(BaseModel):
    event_id: int
    event_title: str
    event_status: str
    followed_at: Optional[datetime] = None


# ─── Admin Stats ────────────────────────────────────────

class AdminStats(BaseModel):
    total_users: int
    total_articles: int
    total_events: int
    active_events: int
    total_sources: int
    articles_today: int


# ─── Common ─────────────────────────────────────────────

class PageResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int

class MessageResponse(BaseModel):
    message: str


# ─── Admin Event Management ─────────────────────────────

class MergeEventsRequest(BaseModel):
    source_id: int
    target_id: int

class AssignArticleRequest(BaseModel):
    event_id: int

class UpdateEventRequest(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    importance: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[str] = None
