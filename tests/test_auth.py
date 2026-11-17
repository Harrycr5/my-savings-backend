import asyncio
import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.modules.auth.models import AuthSession

PASSWORD = "TestingPassword123!"


async def login(client, username="normal"):
    response = await client.post(
        "/api/v1/auth/login", data={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_login_me_and_secrets(client, db):
    tokens = await login(client)
    assert tokens["user"]["profile"]["code"] == "user"
    assert tokens["expires_in"] == 900
    assert "password" not in tokens["user"]
    assert "password_hash" not in tokens["user"]
    stored = await db.scalar(select(AuthSession))
    assert stored.refresh_token_hash != tokens["refresh_token"]
    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["username"] == "NORMAL"


async def test_refresh_rotation_and_logout_revoke_both_tokens(client):
    original = await login(client)
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )
    assert response.status_code == 200, response.text
    rotated = response.json()
    assert rotated["refresh_token"] != original["refresh_token"]
    assert rotated["access_token"] != original["access_token"]
    reused = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )
    assert reused.status_code == 401
    headers = {"Authorization": f"Bearer {rotated['access_token']}"}
    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 200
    for token in (original["access_token"], rotated["access_token"]):
        assert (
            await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        ).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    ).status_code == 401


async def test_expired_and_invalid_tokens(client, db):
    tokens = await login(client)
    user_id, session_id = decode_access_token(tokens["access_token"])
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=2),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "type": "access",
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    assert (
        await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"})
    ).status_code == 401
    auth_session = await db.get(AuthSession, session_id)
    auth_session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": "malformed"})
    ).status_code == 401


async def test_rejected_credentials_and_validation_do_not_echo_password(client):
    response = await client.post(
        "/api/v1/auth/login", data={"username": "missing", "password": PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.headers["www-authenticate"] == "Bearer"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "x@example.com",
            "username": "newuser",
            "name": "New",
            "last_name": "User",
            "password": "secret",
            "profile_id": "no",
        },
    )
    assert response.status_code == 422
    assert "secret" not in response.text
    assert all("input" not in error for error in response.json()["errors"])


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="El bloqueo de filas requiere PostgreSQL."
)
async def test_concurrent_refresh_accepts_token_once(client):
    tokens = await login(client)
    responses = await asyncio.gather(
        *[
            client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
            for _ in range(2)
        ]
    )
    assert sorted(response.status_code for response in responses) == [200, 401]


async def test_public_registration_assigns_default_profile_and_rejects_duplicate(client, seeded):
    payload = {
        "email": "new@example.com",
        "username": "NewUser",
        "name": "New",
        "last_name": "User",
        "password": PASSWORD,
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    user = response.json()["data"]
    assert user["profile_id"] == seeded["profile_id"]
    assert user["username"] == "NEWUSER"
    assert "password_hash" not in user
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 409
