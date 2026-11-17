from uuid import uuid4

from sqlalchemy import func, select

from app.core.permissions import sync_model_permissions
from app.modules.profiles.models import Permission


async def permission_ids(client, admin_headers):
    response = await client.get("/api/v1/permissions?page_size=100", headers=admin_headers)
    assert response.status_code == 200, response.text
    return {permission["code"]: permission["id"] for permission in response.json()["data"]["items"]}


async def test_permission_catalog_is_idempotent_and_excludes_sessions(db):
    before = await db.scalar(select(func.count()).select_from(Permission))
    connection = await db.connection()
    await connection.run_sync(sync_model_permissions)
    await db.commit()
    after = await db.scalar(select(func.count()).select_from(Permission))
    assert before == after == 9
    codes = list((await db.scalars(select(Permission.code))).all())
    assert not any(code.startswith("auth_sessions.") for code in codes)


async def test_add_preserves_existing_and_ignores_duplicates(client, admin_headers, seeded):
    ids = await permission_ids(client, admin_headers)
    path = f"/api/v1/profiles/{seeded['profile_id']}/permissions"
    first, second = ids["users.read"], ids["profiles.read"]
    response = await client.post(path, headers=admin_headers, json={"permission_ids": [first]})
    assert response.status_code == 200, response.text
    response = await client.post(
        path, headers=admin_headers, json={"permission_ids": [first, second, second]}
    )
    assert response.status_code == 200, response.text
    assert {p["id"] for p in response.json()["data"]["permissions"]} == {first, second}
    assert len(response.json()["data"]["permissions"]) == 2
    invalid = await client.post(
        path, headers=admin_headers, json={"permission_ids": [ids["users.update"], str(uuid4())]}
    )
    assert invalid.status_code == 404
    unchanged = await client.get(f"/api/v1/profiles/{seeded['profile_id']}", headers=admin_headers)
    assert {p["id"] for p in unchanged.json()["data"]["permissions"]} == {first, second}


async def test_removal_is_idempotent_preserves_catalog_and_changes_access(
    client, admin_headers, seeded
):
    ids = await permission_ids(client, admin_headers)
    permission_id = ids["users.read"]
    path = f"/api/v1/profiles/{seeded['profile_id']}/permissions"
    assert (
        await client.post(path, headers=admin_headers, json={"permission_ids": [permission_id]})
    ).status_code == 200
    tokens = (
        await client.post(
            "/api/v1/auth/login", data={"username": "normal", "password": "TestingPassword123!"}
        )
    ).json()
    user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.get("/api/v1/users", headers=user_headers)).status_code == 200
    for _ in range(2):
        response = await client.request(
            "DELETE", path, headers=admin_headers, json={"permission_ids": [permission_id]}
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["permissions"] == []
    assert (await client.get("/api/v1/users", headers=user_headers)).status_code == 403
    assert (await permission_ids(client, admin_headers))["users.read"] == permission_id


async def test_reserved_profile_cannot_be_changed(client, admin_headers, seeded):
    path = f"/api/v1/profiles/{seeded['admin_profile_id']}/permissions"
    response = await client.request(
        "DELETE", path, headers=admin_headers, json={"permission_ids": []}
    )
    assert response.status_code == 403
    response = await client.post(
        "/api/v1/profiles",
        headers=admin_headers,
        json={"code": "superadmin", "name": "Hidden admin"},
    )
    assert response.status_code == 403
