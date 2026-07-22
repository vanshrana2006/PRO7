"""
Async SQLAlchemy engine + session management.

Works out of the box with SQLite (zero config) and transparently upgrades
to Postgres by changing DATABASE_URL -- no code changes required, since we
only use dialect-agnostic SQLAlchemy Core/ORM features.
"""
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# Ensure local data directory exists for the default SQLite backend.
if settings.DATABASE_URL.startswith("sqlite"):
    os.makedirs("./data", exist_ok=True)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables. Used for local dev; production should use Alembic
    migrations (see backend/alembic/)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
