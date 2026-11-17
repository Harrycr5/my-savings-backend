from uuid import UUID

from app.modules.users.models import User


async def test_filters_visible_in_swagger_and_totals_match(client, admin_headers):
    schema = (await client.get("/openapi.json")).json()
    expected = {
        "/api/v1/users": {
            "page",
            "page_size",
            "search",
            "name",
            "last_name",
            "email",
            "username",
            "profile_id",
            "is_active",
            "is_admin",
        },
        "/api/v1/profiles": {
            "page",
            "page_size",
            "search",
            "code",
            "name",
            "description",
            "is_active",
        },
        "/api/v1/permissions": {"page", "page_size", "search", "code", "name", "description"},
    }
    for path, names in expected.items():
        assert names <= {p["name"] for p in schema["paths"][path]["get"]["parameters"]}
    for params in (
        {"search": "nOrMaL"},
        {"name": "normal", "email": "user@", "is_active": "true"},
        {"is_admin": "false"},
    ):
        response = await client.get("/api/v1/users", params=params, headers=admin_headers)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["total"] == 1
        assert response.json()["data"]["items"][0]["username"] == "NORMAL"
    response = await client.get("/api/v1/users", params={"name": "%"}, headers=admin_headers)
    assert response.json()["data"]["total"] == 0
    assert (
        await client.get("/api/v1/users?password_hash=x", headers=admin_headers)
    ).status_code == 422
    response = await client.get("/api/v1/permissions?search=users&code=read", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["items"][0]["code"] == "users.read"


async def test_uppercase_visible_fields_preserves_codes_and_credentials(client, admin_headers):
    response = await client.post(
        "/api/v1/profiles",
        headers=admin_headers,
        json={"code": "seller", "name": " vendedor ", "description": "permite vender"},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["name"] == "VENDEDOR"
    assert data["description"] == "PERMITE VENDER"
    assert data["code"] == "seller"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "username": "newuser",
            "name": "Harry",
            "last_name": "Cobos",
            "password": "MixedCasePassword123!",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["name"] == "HARRY" and data["last_name"] == "COBOS"
    assert data["email"] == "new@example.com" and data["username"] == "NEWUSER"
    assert data["is_admin"] is False
    assert (
        await client.post(
            "/api/v1/auth/login", data={"username": "newuser", "password": "MixedCasePassword123!"}
        )
    ).status_code == 200


async def test_admin_flag_controls_access_independently_of_profile_code(client, db, seeded):
    admin = await db.get(User, UUID(seeded["admin_id"]))
    normal = await db.get(User, UUID(seeded["user_id"]))
    admin.profile_id = UUID(seeded["profile_id"])
    normal.profile_id = UUID(seeded["admin_profile_id"])
    await db.commit()

    async def login(username):
        response = await client.post(
            "/api/v1/auth/login", data={"username": username, "password": "TestingPassword123!"}
        )
        assert response.status_code == 200, response.text
        return response.json()

    yes = await login("admin")
    no = await login("normal")
    assert yes["user"]["is_admin"] is True
    assert no["user"]["is_admin"] is False
    assert (
        await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {yes['access_token']}"}
        )
    ).status_code == 200
    assert (
        await client.get("/api/v1/users", headers={"Authorization": f"Bearer {no['access_token']}"})
    ).status_code == 403
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "attacker@example.com",
            "username": "attacker",
            "name": "x",
            "last_name": "x",
            "password": "TestingPassword123!",
            "is_admin": True,
        },
    )
    assert response.status_code == 422
