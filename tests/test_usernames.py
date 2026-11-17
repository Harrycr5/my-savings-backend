from uuid import UUID

import pytest
from sqlalchemy import func, select, update

from app.modules.users.models import User
from app.modules.users.schemas import UserCreate

PASSWORD = "TestingPassword123!"


@pytest.mark.parametrize("username", ["normal", "NORMAL", "NoRmAl"])
async def test_login_accepts_any_username_case(client, username):
    response = await client.post(
        "/api/v1/auth/login", data={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["username"] == "NORMAL"
    wrong_password = await client.post(
        "/api/v1/auth/login", data={"username": username, "password": PASSWORD.upper()}
    )
    assert wrong_password.status_code == 401


async def test_legacy_lowercase_username_can_login_and_cannot_be_duplicated(client, db, seeded):
    await db.execute(
        update(User).where(User.id == UUID(seeded["user_id"])).values(username="legacyuser")
    )
    await db.commit()
    for username in ("legacyuser", "LEGACYUSER", "LeGaCyUsEr"):
        response = await client.post(
            "/api/v1/auth/login", data={"username": username, "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        assert response.json()["user"]["id"] == seeded["user_id"]

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "different@example.com",
            "username": "LeGaCyUsEr",
            "name": "Other",
            "last_name": "User",
            "password": PASSWORD,
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert await db.scalar(select(func.count()).select_from(User)) == 2


async def test_superadmin_script_detects_username_duplicate_case_insensitively(
    client, db, session_factory, monkeypatch, capsys
):
    from scripts import create_superadmin as script

    monkeypatch.setattr(script, "AsyncSessionLocal", session_factory)
    data = UserCreate(
        email="different-admin@example.com",
        username="NoRmAl",
        name="Other",
        last_name="Admin",
        password=PASSWORD,
    )
    await script.create_superadmin(data)
    assert "ya existe" in capsys.readouterr().out
    assert await db.scalar(select(func.count()).select_from(User)) == 2
