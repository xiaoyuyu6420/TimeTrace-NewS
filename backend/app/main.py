"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, SessionLocal, engine
from .models import User
from .auth import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def seed_database():
    """Create tables, run migrations, and seed default admin user only."""
    Base.metadata.create_all(bind=engine)

    # Migration: add columns if missing (SQLite compatible)
    import sqlite3
    db_path = engine.url.database
    if db_path:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Add embedding to articles
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN embedding JSON")
            logger.info("Added embedding column to articles")
        except Exception:
            pass
        # Add embedding to events
        try:
            cursor.execute("ALTER TABLE events ADD COLUMN embedding JSON")
            logger.info("Added embedding column to events")
        except Exception:
            pass
        # Add credibility fields to articles
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN credibility_score REAL DEFAULT 0.0")
            logger.info("Added credibility_score column to articles")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN credibility_factors JSON")
            logger.info("Added credibility_factors column to articles")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN duplicate_of INTEGER REFERENCES articles(id)")
            logger.info("Added duplicate_of column to articles")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN is_duplicate INTEGER DEFAULT 0")
            logger.info("Added is_duplicate column to articles")
        except Exception:
            pass
        # Add credibility fields to rss_sources
        try:
            cursor.execute("ALTER TABLE rss_sources ADD COLUMN credibility_tier TEXT DEFAULT 'C'")
            logger.info("Added credibility_tier column to rss_sources")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE rss_sources ADD COLUMN source_reputation REAL DEFAULT 50.0")
            logger.info("Added source_reputation column to rss_sources")
        except Exception:
            pass
        conn.commit()
        conn.close()

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == settings.ADMIN_USERNAME).first():
            admin = User(
                username=settings.ADMIN_USERNAME,
                email="admin@timetrace.local",
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            logger.info("Created default admin user")
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_database()
    logger.info(f"{settings.APP_NAME} started")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
from .api import users, articles, events, rss, admin  # noqa: E402

app.include_router(users.router)
app.include_router(articles.router)
app.include_router(events.router)
app.include_router(rss.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}
