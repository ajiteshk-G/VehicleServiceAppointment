"""Database session and connection management (PostgreSQL & SQLite compatible)."""

import logging
from typing import Any, AsyncGenerator
from backend.app.config import settings

logger = logging.getLogger(__name__)

try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm import declarative_base

    # Normalize DATABASE_URL for async drivers
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("sqlite://") and not database_url.startswith("sqlite+aiosqlite://"):
        database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    engine_kwargs = {}
    if "sqlite" in database_url:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20

    engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
        **engine_kwargs
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

    Base = declarative_base()

except ImportError:
    AsyncSession = None  # type: ignore
    async_sessionmaker = None  # type: ignore
    create_async_engine = None  # type: ignore
    declarative_base = None  # type: ignore
    engine = None
    AsyncSessionLocal = None
    Base = None


async def get_db() -> AsyncGenerator[Any, None]:
    """Dependency for providing database sessions to FastAPI routes."""
    if not AsyncSessionLocal:
        raise RuntimeError("SQLAlchemy is not available.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initializes tables in database."""
    if not engine or not Base:
        logger.warning("Database init skipped (SQLAlchemy not installed).")
        return
    async with engine.begin() as conn:
        from backend.app import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema synchronized successfully.")
