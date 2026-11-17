async def test_cors_preflight_and_errors(client):
    origin = {"Origin": "http://localhost:5173"}
    response = await client.options(
        "/api/v1/users",
        headers={
            **origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin["Origin"]
    response = await client.get("/api/v1/users", headers=origin)
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == origin["Origin"]
    assert response.json()["success"] is False
    denied = await client.options(
        "/api/v1/users",
        headers={"Origin": "http://untrusted.invalid", "Access-Control-Request-Method": "GET"},
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


async def test_health_and_all_routers_are_present(client):
    assert (await client.get("/api/v1/health")).json() == {"status": "ok"}
    schema = (await client.get("/openapi.json")).json()
    expected = {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/users/me",
        "/api/v1/users/{user_id}",
        "/api/v1/profiles/{profile_id}/permissions",
        "/api/v1/permissions",
    }
    assert expected <= set(schema["paths"])
    assert "delete" in schema["paths"]["/api/v1/profiles/{profile_id}/permissions"]


async def test_unexpected_errors_are_json_with_cors():
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from starlette.middleware.cors import CORSMiddleware

    from app.core.exception_handlers import register_exception_handlers

    application = FastAPI(debug=False)
    register_exception_handlers(application)

    @application.get("/fail")
    async def fail():
        raise RuntimeError("internal-detail-must-not-be-exposed")

    wrapped = CORSMiddleware(application, allow_origins=["http://localhost:5173"])
    async with AsyncClient(
        transport=ASGITransport(app=wrapped, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.get("/fail", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.json()["success"] is False
    assert "internal-detail" not in response.text
