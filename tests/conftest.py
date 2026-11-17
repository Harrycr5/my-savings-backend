import os
from datetime import timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

# Ninguna prueba usa DATABASE_URL para guardar datos.
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://unused:unused@localhost/unused"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-not-for-production-1234567890"
os.environ["CORS_ORIGINS"] = '["http://localhost:5173"]'

from app.api.dependencies import get_db  # noqa: E402
from app.core.permissions import sync_model_permissions  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import load_models  # noqa: E402
from app.main import app, fastapi_app  # noqa: E402
from app.modules.auth.models import AuthSession, PasswordResetCode  # noqa: E402
from app.modules.profiles.models import Profile  # noqa: E402
from app.modules.users.models import User  # noqa: E402

PASSWORD = "TestingPassword123!"


def restore_sqlite_timezone(target, context, attrs=None):
    """SQLite omite el timezone; PostgreSQL devuelve TIMESTAMPTZ consciente de UTC."""
    for field in ("expires_at", "requested_at", "consumed_at"):
        value = getattr(target, field, None)
        if value is not None and value.tzinfo is None:
            setattr(target, field, value.replace(tzinfo=timezone.utc))


@pytest_asyncio.fixture
async def session_factory():
    load_models()
    test_url = os.environ.get("TEST_DATABASE_URL")
    schema = f"test_{uuid4().hex}"
    if test_url:
        url = make_url(test_url)
        if url.drivername != "postgresql+asyncpg" or not (url.database or "").endswith("_test"):
            pytest.fail(
                "TEST_DATABASE_URL debe usar asyncpg y una base exclusiva terminada en _test."
            )
        base_engine = create_async_engine(test_url)
        async with base_engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = base_engine.execution_options(schema_translate_map={None: schema})
    else:
        base_engine = engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        for model in (AuthSession, PasswordResetCode):
            event.listen(model, "load", restore_sqlite_timezone)
            event.listen(model, "refresh", restore_sqlite_timezone)

        @event.listens_for(engine.sync_engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(sync_model_permissions)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        if test_url:
            async with base_engine.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
        else:
            for model in (AuthSession, PasswordResetCode):
                event.remove(model, "load", restore_sqlite_timezone)
                event.remove(model, "refresh", restore_sqlite_timezone)
        await base_engine.dispose()


@pytest_asyncio.fixture
async def db(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded(db):
    normal = Profile(code="user", name="Usuario", permissions=[])
    admin = Profile(code="superadmin", name="Superadmin", permissions=[])
    password_hash = await hash_password(PASSWORD)
    normal_user = User(
        email="user@example.com",
        username="normal",
        name="Normal",
        last_name="User",
        password_hash=password_hash,
        profile=normal,
    )
    admin_user = User(
        email="admin@example.com",
        username="admin",
        is_admin=True,
        name="Admin",
        last_name="User",
        password_hash=password_hash,
        profile=admin,
    )
    db.add_all([normal_user, admin_user])
    await db.commit()
    return {
        "user_id": str(normal_user.id),
        "admin_id": str(admin_user.id),
        "profile_id": str(normal.id),
        "admin_profile_id": str(admin.id),
    }


@pytest_asyncio.fixture
async def client(session_factory, seeded):
    async def override_db():
        async with session_factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            yield client
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_headers(client):
    response = await client.post(
        "/api/v1/auth/login", data={"username": "admin", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
