"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import SessionLocal, engine
from .models import Base, User
from .schemas import MessageResponse
from .deps import get_db, hash_password, require_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Reduce noise from third-party libraries
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


def run_migrations(db_path: str):
    """Run database migrations using raw SQLite."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    migrations = [
        ("ALTER TABLE articles ADD COLUMN embedding JSON", "embedding column to articles"),
        ("ALTER TABLE events ADD COLUMN embedding JSON", "embedding column to events"),
        ("ALTER TABLE articles ADD COLUMN credibility_score REAL DEFAULT 0.0", "credibility_score column to articles"),
        ("ALTER TABLE articles ADD COLUMN credibility_factors JSON", "credibility_factors column to articles"),
        ("ALTER TABLE articles ADD COLUMN duplicate_of INTEGER REFERENCES articles(id)", "duplicate_of column to articles"),
        ("ALTER TABLE articles ADD COLUMN is_duplicate INTEGER DEFAULT 0", "is_duplicate column to articles"),
        ("ALTER TABLE rss_sources ADD COLUMN credibility_tier TEXT DEFAULT 'C'", "credibility_tier column to rss_sources"),
        ("ALTER TABLE rss_sources ADD COLUMN source_reputation REAL DEFAULT 50.0", "source_reputation column to rss_sources"),
        ("ALTER TABLE event_articles ADD COLUMN phase TEXT DEFAULT 'development'", "phase column to event_articles"),
        ("ALTER TABLE events ADD COLUMN last_enhanced_at DATETIME", "last_enhanced_at column to events"),
        # ─── 三级管线：拆解 → 推演 → 审计 ───
        ("ALTER TABLE articles ADD COLUMN pipeline_state TEXT DEFAULT 'raw'", "pipeline_state to articles"),
        ("ALTER TABLE articles ADD COLUMN distilled_facts JSON", "distilled_facts to articles"),
        ("ALTER TABLE articles ADD COLUMN reasoning_result JSON", "reasoning_result to articles"),
    ]

    # 创建审计日志表（如果不存在）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL REFERENCES articles(id),
            event_id INTEGER REFERENCES events(id),
            stage VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL,
            confidence REAL DEFAULT 1.0,
            entity_check JSON,
            issues JSON,
            raw_snapshot JSON,
            result_snapshot JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建 LLM 供应商表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            api_base VARCHAR(500) NOT NULL,
            api_key VARCHAR(500) NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建 LLM 模型表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id INTEGER NOT NULL REFERENCES llm_providers(id),
            name VARCHAR(100) NOT NULL,
            model VARCHAR(200) NOT NULL,
            temperature REAL DEFAULT 0.3,
            top_p REAL DEFAULT 0.7,
            max_tokens INTEGER DEFAULT 300,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建 LLM 编排表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_routing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            distill_model_id INTEGER REFERENCES llm_models(id),
            reason_model_id INTEGER REFERENCES llm_models(id),
            audit_model_id INTEGER REFERENCES llm_models(id),
            embed_model_id INTEGER REFERENCES embed_models(id),
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建向量模型供应商表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embed_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            api_base VARCHAR(500) NOT NULL,
            api_key VARCHAR(500) NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建向量模型表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embed_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id INTEGER NOT NULL REFERENCES embed_providers(id),
            name VARCHAR(100) NOT NULL,
            model VARCHAR(200) NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建蒸馏产物表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS article_distillations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL UNIQUE REFERENCES articles(id),
            facts JSON,
            core_entities JSON,
            key_numbers JSON,
            primary_action TEXT DEFAULT '',
            summary_line TEXT DEFAULT '',
            confidence REAL DEFAULT 0.0,
            model_used TEXT DEFAULT '',
            is_llm_generated INTEGER DEFAULT 0,
            processing_time_ms INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建推演产物表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS article_reasonings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL UNIQUE REFERENCES articles(id),
            distillation_id INTEGER REFERENCES article_distillations(id),
            action VARCHAR(20) DEFAULT 'new',
            target_event_id INTEGER REFERENCES events(id),
            target_event_title TEXT DEFAULT '',
            phase VARCHAR(20) DEFAULT 'trigger',
            suggested_category VARCHAR(50) DEFAULT '',
            suggested_importance INTEGER DEFAULT 3,
            event_title TEXT DEFAULT '',
            event_summary TEXT DEFAULT '',
            has_conflict INTEGER DEFAULT 0,
            conflict_details TEXT DEFAULT '',
            confidence REAL DEFAULT 0.0,
            needs_review INTEGER DEFAULT 0,
            safe_mode INTEGER DEFAULT 0,
            model_used TEXT DEFAULT '',
            processing_time_ms INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for sql, desc in migrations:
        try:
            cursor.execute(sql)
            logger.info(f"Added {desc}")
        except Exception:
            pass

    conn.commit()
    conn.close()


def seed_database():
    """Create tables and seed initial data."""
    Base.metadata.create_all(bind=engine)

    db_path = engine.url.database
    if db_path:
        run_migrations(db_path)

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == settings.ADMIN_USERNAME).first():
            admin = User(
                username=settings.ADMIN_USERNAME,
                email="admin@timetrace.local",
                password_hash=hash_password(settings.get_admin_password()),
                role="admin",
            )
            db.add(admin)
            logger.info("Created default admin user")
        db.commit()

        # 回填已有事件的阶段：每个事件最早的文章 → trigger
        _backfill_phases(db)

        # 预置 RSS 源种子数据
        _seed_rss_sources(db)
    finally:
        db.close()


def _backfill_phases(db):
    """回填已有 event_articles 的 phase 字段。"""
    from sqlalchemy import text
    try:
        # 找出所有需要回填的事件（有 phase 为默认值或空的记录）
        result = db.execute(text(
            "SELECT DISTINCT event_id FROM event_articles "
            "WHERE phase = 'development' OR phase IS NULL"
        ))
        event_ids = [row[0] for row in result.fetchall()]
        if not event_ids:
            return

        updated = 0
        for eid in event_ids:
            # 找该事件最早的一篇文章（composite PK: event_id + article_id）
            earliest = db.execute(text(
                "SELECT ea.article_id FROM event_articles ea "
                "JOIN articles a ON ea.article_id = a.id "
                "WHERE ea.event_id = :eid "
                "ORDER BY COALESCE(a.published_at, a.created_at) ASC LIMIT 1"
            ), {"eid": eid}).fetchone()
            if earliest:
                db.execute(text(
                    "UPDATE event_articles SET phase = 'trigger' "
                    "WHERE event_id = :eid AND article_id = :aid"
                ), {"eid": eid, "aid": earliest[0]})
                updated += 1

        if updated:
            db.commit()
            logger.info(f"Backfilled {updated} events with trigger phase")
    except Exception as e:
        logger.warning(f"Phase backfill skipped: {e}")


def _seed_rss_sources(db):
    """预置精简 RSS 源。仅在数据库为空时添加。

    设计原则：
    - 精而不多：每个分类 1-2 个高质量源
    - 对照组：同一事件用不同视角交叉验证
    - 分类：官方(政策风向) / 国际(非西方视角) / 财经(市场信号) / 科技(行业前沿)
    """
    from .models import RssSource

    if db.query(RssSource).count() > 0:
        return

    # (名称, URL, 分类, 可信度层级, 信度分)
    # 可信度层级: A=权威, B=优质, C=聚合
    sources = [
        # ─── 官方权威 — 政策风向标 ───
        ("新华网", "http://www.xinhuanet.com/politics/news_politics.xml", "官方", "A", 88),
        ("求是网", "https://rsshub.app/qstheory/important", "官方", "A", 92),

        # ─── 国际视角 — 非西方主流 ───
        ("半岛电视台", "https://rsshub.app/aljazeera/news", "国际", "A", 85),
        ("Reuters", "https://feeds.reuters.com/reuters/worldNews", "国际", "A", 88),

        # ─── 财经权威 — 市场信号 ───
        ("FT中文网", "https://rsshub.app/ft/chinese/hotstoryby", "财经", "A", 90),
        ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews", "财经", "A", 88),

        # ─── 科技精选 — 行业前沿 ───
        ("36氪", "https://36kr.com/feed", "科技", "B", 75),
        ("Hacker News", "https://hnrss.org/frontpage", "科技", "B", 78),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "科技", "B", 80),
    ]

    for name, url, category, tier, reputation in sources:
        src = RssSource(
            name=name,
            url=url,
            category=category,
            is_active=True,
            credibility_tier=tier,
            source_reputation=float(reputation),
        )
        db.add(src)

    db.commit()
    logger.info(f"Seeded {len(sources)} RSS sources")


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_database()
    logger.info(f"{settings.APP_NAME} started")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="News event tracking system",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Import and include routers
from .routes import users, articles, events, rss, admin

app.include_router(users.router)
app.include_router(articles.router)
app.include_router(events.router)
app.include_router(rss.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/public-info")
def public_info():
    """公开信息 — 前端首页展示用，不含敏感数据。"""
    return {
        "name": settings.APP_NAME,
        "version": "2.0.0",
        "llm_available": bool(settings.LLM_API_KEY and settings.LLM_MODEL),
    }


@app.get("/api/info")
def info(_admin=Depends(require_admin)):
    return {
        "name": settings.APP_NAME,
        "version": "2.0.0",
        "llm_available": bool(settings.LLM_API_KEY and settings.LLM_MODEL),
    }
