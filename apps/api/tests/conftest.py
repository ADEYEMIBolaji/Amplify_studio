import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import AuthUser, get_current_auth_user
from app.db.base import Base, get_db
from app.main import app

test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

_current_user: dict[str, AuthUser | None] = {"value": None}


def set_current_user(auth_user: AuthUser) -> None:
    _current_user["value"] = auth_user


async def _override_get_db() -> AsyncIterator[AsyncSession]:
    async with TestSessionLocal() as session:
        yield session


async def _override_get_current_auth_user() -> AuthUser:
    user = _current_user["value"]
    assert user is not None, "call set_current_user() before making a request in this test"
    return user


app.dependency_overrides[get_db] = _override_get_db
app.dependency_overrides[get_current_auth_user] = _override_get_current_auth_user


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def make_user(email: str = "owner@example.com") -> AuthUser:
    return AuthUser(id=uuid.uuid4(), email=email)


@pytest.fixture
def as_user():
    def _as_user(auth_user: AuthUser) -> None:
        set_current_user(auth_user)

    return _as_user
