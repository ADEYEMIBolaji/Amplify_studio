from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

connect_args: dict[str, Any]
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Supabase's pooler runs PgBouncer in transaction mode, which doesn't
    # support asyncpg's server-side prepared statements — disabling the
    # statement cache is required for the pooled connection string to work
    # at all, and is a harmless no-op against a direct (non-pooled) one.
    connect_args = {"statement_cache_size": 0}

engine = create_async_engine(settings.database_url, echo=False, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
