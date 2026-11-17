import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID

import aiosmtplib
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import get_settings
from app.infrastructure.mail import send_password_code
from app.modules.auth.models import PasswordResetCode

PASSWORD = "TestingPassword123!"
NEW_PASSWORD = "NewPassword456!"


async def login(client, password=PASSWORD):
    response = await client.post(
        "/api/v1/auth/login", data={"username": "normal", "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def mailbox(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from_email", "starter@example.com")
    outbox = []

    async def fake_send(recipient, code):
        outbox.append((recipient, code))

    monkeypatch.setattr("app.modules.auth.router.send_password_code", fake_send)
    return outbox


async def test_change_password_checks_old_password_and_revokes_sessions(client):
    tokens = await login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "incorrect", "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 200
    response = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200, response.text
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401
    assert (
        await client.post("/api/v1/auth/login", data={"username": "normal", "password": PASSWORD})
    ).status_code == 401
    await login(client, NEW_PASSWORD)


async def test_reset_by_email_hides_account_existence_and_is_one_use(client, db, seeded, mailbox):
    tokens = await login(client)
    response = await client.post("/api/v1/auth/forgot-password", json={"email": "USER@example.com"})
    assert response.status_code == 202, response.text
    absent = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "missing@example.com"}
    )
    assert absent.status_code == 202
    assert absent.json() == response.json()
    assert len(mailbox) == 1
    recipient, code = mailbox[0]
    assert recipient == "user@example.com"
    assert len(code) == 6 and code.isdigit()
    assert code not in response.text
    stored = await db.scalar(select(PasswordResetCode))
    assert len(stored.code_hash) == 64 and stored.code_hash != code
    assert stored.user_id == UUID(seeded["user_id"])
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": recipient, "code": code, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200, response.text
    assert (
        await client.post(
            "/api/v1/auth/reset-password",
            json={"email": recipient, "code": code, "new_password": "OtherPassword789!"},
        )
    ).status_code == 400
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401
    await login(client, NEW_PASSWORD)


async def test_code_cooldown_attempt_limit_and_new_code_invalidates_old(client, db, mailbox):
    request = {"email": "user@example.com"}
    await client.post("/api/v1/auth/forgot-password", json=request)
    old_code = mailbox[0][1]
    await client.post("/api/v1/auth/forgot-password", json=request)
    assert len(mailbox) == 1
    wrong = "000000" if old_code != "000000" else "111111"
    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={**request, "code": wrong, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 400
    assert (
        await client.post(
            "/api/v1/auth/reset-password",
            json={**request, "code": old_code, "new_password": NEW_PASSWORD},
        )
    ).status_code == 400
    stored = await db.scalar(select(PasswordResetCode))
    await db.refresh(stored)
    assert stored.attempts == 5
    stored.requested_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    await db.commit()
    await client.post("/api/v1/auth/forgot-password", json=request)
    assert len(mailbox) == 2
    new_code = mailbox[1][1]
    assert new_code != old_code
    assert (
        await client.post(
            "/api/v1/auth/reset-password",
            json={**request, "code": old_code, "new_password": NEW_PASSWORD},
        )
    ).status_code == 400
    assert (
        await client.post(
            "/api/v1/auth/reset-password",
            json={**request, "code": new_code, "new_password": NEW_PASSWORD},
        )
    ).status_code == 200


async def test_expired_code_rejected_and_unconfigured_mail_is_explicit(
    client, db, mailbox, monkeypatch
):
    await client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    stored = await db.scalar(select(PasswordResetCode))
    stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": "user@example.com", "code": mailbox[0][1], "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400
    monkeypatch.setattr(get_settings(), "smtp_host", None)
    for email in ("user@example.com", "missing@example.com"):
        assert (
            await client.post("/api/v1/auth/forgot-password", json={"email": email})
        ).status_code == 503


async def test_smtp_transport_and_no_code_in_failure_logs(mailbox, monkeypatch, caplog):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "smtp_password", SecretStr("smtp-secret"))
    transport = AsyncMock()
    monkeypatch.setattr("aiosmtplib.send", transport)
    await send_password_code("user@example.com", "123456")
    message = transport.call_args.args[0]
    assert message["To"] == "user@example.com"
    assert "123456" in message.get_content()
    assert transport.call_args.kwargs["start_tls"] is True
    assert transport.call_args.kwargs["password"] == "smtp-secret"
    transport.side_effect = aiosmtplib.SMTPException("123456")
    await send_password_code("user@example.com", "123456")
    assert "123456" not in caplog.text


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="El bloqueo de filas requiere PostgreSQL."
)
async def test_reset_code_can_only_be_consumed_once_concurrently(client, mailbox):
    await client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    payload = {"email": "user@example.com", "code": mailbox[0][1], "new_password": NEW_PASSWORD}
    responses = await asyncio.gather(
        *[client.post("/api/v1/auth/reset-password", json=payload) for _ in range(2)]
    )
    assert sorted(response.status_code for response in responses) == [200, 400]
