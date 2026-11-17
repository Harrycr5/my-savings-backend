from app.modules.profiles.models import Profile

PASSWORD = "TestingPassword123!"


async def user_tokens(client):
    response = await client.post(
        "/api/v1/auth/login", data={"username": "normal", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_users_list_requires_auth_and_permission(client):
    assert (await client.get("/api/v1/users")).status_code == 401
    tokens = await user_tokens(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 403


async def test_admin_pagination_and_reserved_accounts(client, admin_headers, seeded):
    response = await client.get("/api/v1/users?page=1&page_size=1", headers=admin_headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == 2
    assert data["pages"] == 2
    assert len(data["items"]) == 1
    assert (await client.get("/api/v1/users?page=0", headers=admin_headers)).status_code == 422
    response = await client.patch(
        f"/api/v1/users/{seeded['admin_id']}", headers=admin_headers, json={"is_active": False}
    )
    assert response.status_code == 403
    response = await client.patch(
        f"/api/v1/users/{seeded['user_id']}",
        headers=admin_headers,
        json={"profile_id": seeded["admin_profile_id"]},
    )
    assert response.status_code == 403


async def test_update_own_names_cannot_change_profile(client, seeded):
    tokens = await user_tokens(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = await client.patch("/api/v1/users/me", headers=headers, json={"name": "Changed"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["name"] == "CHANGED"
    assert (
        await client.patch(
            "/api/v1/users/me", headers=headers, json={"profile_id": seeded["admin_profile_id"]}
        )
    ).status_code == 422
    assert (
        await client.patch("/api/v1/users/me", headers=headers, json={"name": None})
    ).status_code == 422


async def test_disable_and_reenable_does_not_restore_revoked_sessions(
    client, admin_headers, seeded
):
    tokens = await user_tokens(client)
    path = f"/api/v1/users/{seeded['user_id']}"
    response = await client.patch(path, headers=admin_headers, json={"is_active": False})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_active"] is False
    assert (
        await client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
    ).status_code == 401
    assert (
        await client.post("/api/v1/auth/login", data={"username": "normal", "password": PASSWORD})
    ).status_code == 401
    assert (
        await client.patch(path, headers=admin_headers, json={"is_active": True})
    ).status_code == 200
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401


async def test_profile_assignment_requires_admin_and_closes_sessions(
    client, admin_headers, seeded, db
):
    profile = Profile(code="seller", name="Vendedor", permissions=[])
    db.add(profile)
    await db.commit()
    tokens = await user_tokens(client)
    path = f"/api/v1/users/{seeded['user_id']}"
    payload = {"profile_id": str(profile.id)}
    assert (
        await client.patch(
            path, headers={"Authorization": f"Bearer {tokens['access_token']}"}, json=payload
        )
    ).status_code == 403
    response = await client.patch(path, headers=admin_headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["profile_id"] == str(profile.id)
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401
    updated = await user_tokens(client)
    assert updated["user"]["profile"]["code"] == "seller"
