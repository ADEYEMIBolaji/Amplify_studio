from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

connect_args: dict[str, Any]
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Belt-and-suspenders: disables asyncpg's client-side prepared-statement
    # cache. Harmless against Supabase's Session pooler (what DATABASE_URL
    # should point at — see .env.example) or a direct connection; required
    # if anything ever points this at the Transaction pooler instead, whose
    # PgBouncer mode doesn't support prepared statements at all and raises
    # DuplicatePreparedStatementError under concurrent load even with this
    # set — found that the hard way, don't repoint at port 6543.
    connect_args = {"statement_cache_size": 0}

engine = create_async_engine(settings.database_url, echo=False, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
