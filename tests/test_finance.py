import asyncio
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from app.modules.debts.models import Debt, DebtPayment
from app.modules.debts.service import next_due_date
from app.modules.tills.models import TillMovement
from app.modules.tills.repository import TillRepository

PREFIX = "/api/v1"


async def normal_headers(client):
    response = await client.post(
        f"{PREFIX}/auth/login", data={"username": "normal", "password": "TestingPassword123!"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create(client, headers, path, payload):
    response = await client.post(f"{PREFIX}{path}", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def read(client, headers, path):
    response = await client.get(f"{PREFIX}{path}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_currency_catalog_is_used_by_financial_endpoints(client):
    headers = await normal_headers(client)
    catalog = await read(client, headers, "/currencies")
    codes = {currency["code"] for currency in catalog}
    assert {"PEN", "USD", "EUR", "MXN", "BRL", "XCG"} <= codes
    assert "JPY" not in codes
    endpoints = {
        "/tills": {"name": "Caja"},
        "/debts": {"name": "Alquiler", "amount": "100", "first_due_date": "2026-11-30"},
        "/inheritance": {
            "name": "Casa",
            "asset_type": "property",
            "current_value": "100",
            "market_value": "200",
        },
        "/employees": {"full_name": "María Pérez", "salary": "100", "first_pay_date": "2026-11-30"},
        "/budgets": {
            "year": 2026,
            "month": 11,
            "leisure": "0",
            "fixed_expenses": "0",
            "food": "0",
            "subscriptions": "0",
        },
    }
    for path, payload in endpoints.items():
        response = await client.post(
            f"{PREFIX}{path}", headers=headers, json={**payload, "currency": "JPY"}
        )
        assert response.status_code == 422, response.text
        assert "JPY" in response.json()["message"]
        record = await create(client, headers, path, {**payload, "currency": "EUR"})
        assert record["currency"] == "EUR"
        if path == "/employees":
            employee_path = f"{PREFIX}{path}/{record['id']}"
            response = await client.patch(employee_path, headers=headers, json={"currency": "JPY"})
            assert response.status_code == 422
            response = await client.patch(employee_path, headers=headers, json={"currency": "MXN"})
            assert response.status_code == 200, response.text
            assert response.json()["data"]["currency"] == "MXN"


async def test_employees_are_private_and_editable(client, admin_headers):
    headers = await normal_headers(client)
    payload = {"full_name": "María Pérez", "salary": "1500.00", "first_pay_date": "2026-11-30"}
    assert (await client.post(f"{PREFIX}/employees", json=payload)).status_code == 401
    response = await client.post(
        f"{PREFIX}/employees", headers=headers, json={**payload, "salary": "0"}
    )
    assert response.status_code == 422

    employee = await create(client, headers, "/employees", payload)
    path = f"{PREFIX}/employees/{employee['id']}"
    assert (await client.get(path, headers=admin_headers)).status_code == 404
    assert (await client.delete(path, headers=admin_headers)).status_code == 404
    listing = await read(client, headers, "/employees")
    assert listing["items"] == [employee]
    response = await client.patch(path, headers=headers, json={"salary": "1600.00"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["salary"] == "1600.00"
    assert (await client.delete(path, headers=headers)).status_code == 204
    assert (await client.get(path, headers=headers)).status_code == 404


async def test_monthly_budget_is_unique_per_user_and_period(client, admin_headers):
    headers = await normal_headers(client)
    payload = {
        "year": 2026,
        "month": 11,
        "leisure": "250.00",
        "fixed_expenses": "1800.00",
        "food": "600.00",
        "subscriptions": "0.00",
    }
    for changes in ({"month": 13}, {"food": "-1.00"}):
        response = await client.post(
            f"{PREFIX}/budgets", headers=headers, json={**payload, **changes}
        )
        assert response.status_code == 422

    budget = await create(client, headers, "/budgets", payload)
    assert budget["subscriptions"] == "0.00"
    assert budget["currency"] == "PEN"
    response = await client.post(f"{PREFIX}/budgets", headers=headers, json=payload)
    assert response.status_code == 409
    await create(client, admin_headers, "/budgets", payload)
    await create(client, headers, "/budgets", {**payload, "month": 12})


async def till_setup(client, headers, currency="PEN"):
    till = await create(
        client,
        headers,
        "/tills",
        {
            "name": "Yape",
            "currency": currency,
            "opening_balance": "100.00",
        },
    )
    path = f"/tills/{till['id']}"
    income = await create(
        client, headers, f"{path}/concepts", {"name": "Sueldo", "direction": "income"}
    )
    expense = await create(
        client, headers, f"{path}/concepts", {"name": "Alquiler", "direction": "expense"}
    )
    return till, income, expense


async def test_all_till_movements_are_paginated_and_scoped_to_user(client, admin_headers):
    headers = await normal_headers(client)
    till, income, _ = await till_setup(client, headers)
    other, _, expense = await till_setup(client, headers, "USD")
    foreign, foreign_income, _ = await till_setup(client, admin_headers)

    for owner, box, concept, day in (
        (headers, till, income, "2026-01-10"),
        (headers, other, expense, "2026-01-11"),
        (admin_headers, foreign, foreign_income, "2026-01-12"),
    ):
        await create(
            client,
            owner,
            f"/tills/{box['id']}/movements",
            {"concept_id": concept["id"], "amount": "10", "occurred_on": day},
        )

    page = await read(client, headers, "/tills/movements?page_size=1")
    assert page["total"] == 2
    assert page["pages"] == 2
    assert [item["till_id"] for item in page["items"]] == [other["id"]]
    second = await read(client, headers, "/tills/movements?page_size=1&page=2")
    assert [item["till_id"] for item in second["items"]] == [till["id"]]
    filtered = await read(client, headers, "/tills/movements?direction=income")
    assert filtered["total"] == 1
    assert [item["till_id"] for item in filtered["items"]] == [till["id"]]


async def test_till_movement_idempotency(client):
    headers = await normal_headers(client)
    till, income, _ = await till_setup(client, headers)
    path = f"/tills/{till['id']}/movements"
    payload = {"concept_id": income["id"], "amount": "10.00"}
    key_headers = {**headers, "Idempotency-Key": str(uuid4())}

    first = await create(client, key_headers, path, payload)
    replay = await create(client, key_headers, path, {**payload, "amount": "10"})
    assert replay == first
    conflict = await client.post(
        f"{PREFIX}{path}", headers=key_headers, json={**payload, "amount": "11"}
    )
    assert conflict.status_code == 409
    assert (await read(client, headers, path))["total"] == 1

    second = await create(client, {**headers, "Idempotency-Key": str(uuid4())}, path, payload)
    assert second["id"] != first["id"]
    assert (await read(client, headers, path))["total"] == 2

    other, _, _ = await till_setup(client, headers)
    conflict = await client.post(
        f"{PREFIX}/tills/{other['id']}/movements", headers=key_headers, json=payload
    )
    assert conflict.status_code == 409

    retry_headers = {**headers, "Idempotency-Key": str(uuid4())}
    failed = await client.post(
        f"{PREFIX}{path}", headers=retry_headers, json={**payload, "concept_id": str(uuid4())}
    )
    assert failed.status_code == 404
    await create(client, retry_headers, path, payload)
    assert (await read(client, headers, path))["total"] == 3


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="Requiere PostgreSQL.")
async def test_concurrent_till_movement_requests_create_one_movement(client, monkeypatch):
    headers = await normal_headers(client)
    till, income, _ = await till_setup(client, headers)
    path = f"/tills/{till['id']}/movements"
    headers["Idempotency-Key"] = str(uuid4())
    payload = {"concept_id": income["id"], "amount": "10.00"}
    barrier = asyncio.Barrier(2)
    reserve = TillRepository.reserve_movement_request

    async def reserve_together(repository, user_id, key, fingerprint):
        await barrier.wait()
        return await reserve(repository, user_id, key, fingerprint)

    monkeypatch.setattr(TillRepository, "reserve_movement_request", reserve_together)
    first, second = await asyncio.wait_for(
        asyncio.gather(*(create(client, headers, path, payload) for _ in range(2))), timeout=10
    )
    assert first == second
    assert (await read(client, headers, path))["total"] == 1
    balance = await read(client, headers, f"/tills/{till['id']}/balance")
    assert Decimal(balance["balance"]) == Decimal("110")


async def test_till_movements_balances_filters_and_permanence(client):
    headers = await normal_headers(client)
    till, income, expense = await till_setup(client, headers)
    path = f"/tills/{till['id']}"
    await create(
        client,
        headers,
        f"{path}/movements",
        {
            "concept_id": income["id"],
            "amount": "200.25",
            "occurred_on": "2026-01-10",
        },
    )
    await create(
        client,
        headers,
        f"{path}/movements",
        {
            "concept_id": expense["id"],
            "amount": "50.10",
            "occurred_on": "2026-01-11",
        },
    )
    balance = await read(client, headers, f"{path}/balance")
    assert Decimal(balance["balance"]) == Decimal("250.15")
    assert Decimal(balance["total_income"]) == Decimal("200.25")
    assert Decimal(balance["total_expense"]) == Decimal("50.10")
    filtered = await read(
        client, headers, f"{path}/movements?direction=expense&date_from=2026-01-11"
    )
    assert filtered["total"] == 1
    assert filtered["items"][0]["concept_id"] == expense["id"]
    assert (await read(client, headers, f"{path}/concepts"))["total"] == 2
    assert (await read(client, headers, f"{path}/movements?date_to=2026-01-01"))["total"] == 0
    other = await create(client, headers, "/tills", {"name": "Banco", "opening_balance": "30"})
    await create(
        client, headers, "/tills", {"name": "Paypal", "currency": "USD", "opening_balance": "10"}
    )
    totals = {row["currency"]: row for row in await read(client, headers, "/tills/summary")}
    assert totals["PEN"]["total_tills"] == 2
    assert Decimal(totals["PEN"]["balance"]) == Decimal("280.15")
    assert Decimal(totals["PEN"]["net_savings"]) == Decimal("150.15")
    assert Decimal(totals["USD"]["balance"]) == Decimal("10")
    assert (await read(client, headers, "/tills?page_size=1"))["pages"] == 3
    assert (await client.delete(f"{PREFIX}{path}", headers=headers)).status_code == 405
    for payload in ({"is_active": False}, {"currency": "USD"}, {"opening_balance": "0"}, {}):
        assert (
            await client.patch(f"{PREFIX}{path}", headers=headers, json=payload)
        ).status_code == 422
    response = await client.patch(f"{PREFIX}{path}", headers=headers, json={"name": "Mi Yape"})
    assert response.status_code == 200, response.text
    # A concept belongs to exactly one till.
    response = await client.post(
        f"{PREFIX}/tills/{other['id']}/movements",
        headers=headers,
        json={
            "concept_id": income["id"],
            "amount": "10",
        },
    )
    assert response.status_code == 404
    duplicate = await client.post(
        f"{PREFIX}{path}/concepts",
        headers=headers,
        json={
            "name": " sueldo ",
            "direction": "income",
        },
    )
    assert duplicate.status_code == 409


async def test_recurring_debt_payment_is_atomic_and_renews_without_day_drift(client, db):
    headers = await normal_headers(client)
    till, income, expense = await till_setup(client, headers)
    debt = await create(
        client,
        headers,
        "/debts",
        {
            "name": "Alquiler",
            "amount": "25.50",
            "frequency": "monthly",
            "first_due_date": "2026-01-31",
        },
    )
    path = f"/debts/{debt['id']}"
    payload = {
        "till_id": till["id"],
        "concept_id": expense["id"],
        "due_date": "2026-01-31",
        "paid_on": "2026-01-31",
    }
    invalid = await client.post(
        f"{PREFIX}{path}/payments", headers=headers, json={**payload, "concept_id": income["id"]}
    )
    assert invalid.status_code == 400
    assert (await read(client, headers, path))["next_due_date"] == "2026-01-31"
    assert await db.scalar(select(func.count()).select_from(TillMovement)) == 0
    payment = await create(client, headers, f"{path}/payments", payload)
    assert payment["due_date"] == "2026-01-31"
    assert (await read(client, headers, path))["next_due_date"] == "2026-02-28"
    duplicate = await client.post(f"{PREFIX}{path}/payments", headers=headers, json=payload)
    assert duplicate.status_code == 409
    await create(
        client,
        headers,
        f"{path}/payments",
        {**payload, "due_date": "2026-02-28", "paid_on": "2026-02-28"},
    )
    assert (await read(client, headers, path))["next_due_date"] == "2026-03-31"
    assert (await read(client, headers, f"{path}/payments"))["total"] == 2
    balance = await read(client, headers, f"/tills/{till['id']}/balance")
    assert Decimal(balance["total_expense"]) == Decimal("51.00")
    assert Decimal(balance["balance"]) == Decimal("49.00")
    response = await client.patch(f"{PREFIX}{path}", headers=headers, json={"is_active": False})
    assert response.status_code == 200
    response = await client.post(
        f"{PREFIX}{path}/payments", headers=headers, json={**payload, "due_date": "2026-03-31"}
    )
    assert response.status_code == 409
    assert (await read(client, headers, "/debts?is_active=true"))["total"] == 0


async def test_debt_currency_and_one_time_completion(client):
    headers = await normal_headers(client)
    till, _, expense = await till_setup(client, headers, "USD")
    debt = await create(
        client,
        headers,
        "/debts",
        {
            "name": "Jardinería",
            "amount": "12",
            "frequency": "once",
            "first_due_date": "2026-11-01",
        },
    )
    path = f"/debts/{debt['id']}"
    payload = {"till_id": till["id"], "concept_id": expense["id"], "due_date": "2026-11-01"}
    response = await client.post(f"{PREFIX}{path}/payments", headers=headers, json=payload)
    assert response.status_code == 400
    assert (await read(client, headers, f"{path}/payments"))["total"] == 0
    pen_till, _, pen_expense = await till_setup(client, headers)
    await create(
        client,
        headers,
        f"{path}/payments",
        {**payload, "till_id": pen_till["id"], "concept_id": pen_expense["id"]},
    )
    completed = await read(client, headers, path)
    assert completed["next_due_date"] is None
    assert completed["is_active"] is False
    response = await client.patch(f"{PREFIX}{path}", headers=headers, json={"is_active": True})
    assert response.status_code == 409


async def test_payment_failure_rolls_back_movement_payment_and_schedule(client, session_factory):
    headers = await normal_headers(client)
    till, _, expense = await till_setup(client, headers)
    debt = await create(
        client,
        headers,
        "/debts",
        {
            "name": "Alquiler",
            "amount": "25",
            "frequency": "once",
            "first_due_date": "2026-01-31",
        },
    )

    inserted_rows = []

    def fail_after_payment_insert(mapper, connection, payment):
        movement_id = connection.scalar(
            select(TillMovement.id).where(TillMovement.id == payment.movement_id)
        )
        payment_id = connection.scalar(select(DebtPayment.id).where(DebtPayment.id == payment.id))
        inserted_rows.append((movement_id is not None, payment_id is not None))
        raise RuntimeError("Simulated failure after payment insert")

    event.listen(DebtPayment, "after_insert", fail_after_payment_insert)
    try:
        response = await client.post(
            f"{PREFIX}/debts/{debt['id']}/payments",
            headers=headers,
            json={
                "till_id": till["id"],
                "concept_id": expense["id"],
                "due_date": "2026-01-31",
            },
        )
        assert response.status_code == 500
    finally:
        event.remove(DebtPayment, "after_insert", fail_after_payment_insert)

    assert inserted_rows == [(True, True)]
    async with session_factory() as verification_session:
        assert (
            await verification_session.scalar(select(func.count()).select_from(TillMovement)) == 0
        )
        assert await verification_session.scalar(select(func.count()).select_from(DebtPayment)) == 0
    pending = await read(client, headers, f"/debts/{debt['id']}")
    assert pending["next_due_date"] == "2026-01-31"
    assert pending["is_active"] is True


async def test_assets_crud_types_and_summary(client):
    headers = await normal_headers(client)
    house = await create(
        client,
        headers,
        "/inheritance",
        {
            "name": "Mi casa",
            "asset_type": "property",
            "current_value": "100000",
            "market_value": "120000",
        },
    )
    car = await create(
        client,
        headers,
        "/inheritance",
        {
            "name": "Auto",
            "asset_type": "vehicle",
            "current_value": "20000",
            "market_value": "18000",
        },
    )
    await create(
        client,
        headers,
        "/inheritance",
        {
            "name": "Acciones",
            "asset_type": "other",
            "other_type": "Inversiones",
            "currency": "USD",
            "current_value": "1500",
            "market_value": "1600",
        },
    )
    summary = {row["currency"]: row for row in await read(client, headers, "/inheritance/summary")}
    assert Decimal(summary["PEN"]["current_value"]) == Decimal("120000")
    assert Decimal(summary["PEN"]["market_value"]) == Decimal("138000")
    assert summary["USD"]["total_assets"] == 1
    path = f"{PREFIX}/inheritance/{house['id']}"
    response = await client.patch(path, headers=headers, json={"market_value": "130000"})
    assert response.status_code == 200
    assert Decimal(response.json()["data"]["market_value"]) == Decimal("130000")
    response = await client.patch(path, headers=headers, json={"asset_type": "other"})
    assert response.status_code == 400
    response = await client.patch(
        path, headers=headers, json={"asset_type": "other", "other_type": "Terreno"}
    )
    assert response.status_code == 200
    assert (await read(client, headers, "/inheritance?asset_type=vehicle"))["total"] == 1
    response = await client.delete(f"{PREFIX}/inheritance/{car['id']}", headers=headers)
    assert response.status_code == 204
    assert (await read(client, headers, "/inheritance"))["total"] == 2


async def test_financial_records_are_private_even_from_admin(client, admin_headers):
    headers = await normal_headers(client)
    till, _, expense = await till_setup(client, headers)
    debt = await create(
        client,
        headers,
        "/debts",
        {
            "name": "Nana",
            "amount": "50",
            "first_due_date": "2026-11-01",
        },
    )
    asset = await create(
        client,
        headers,
        "/inheritance",
        {
            "name": "Casa",
            "asset_type": "property",
            "current_value": "100",
            "market_value": "120",
        },
    )
    paths = [
        f"/tills/{till['id']}",
        f"/tills/{till['id']}/balance",
        f"/tills/{till['id']}/concepts",
        f"/tills/{till['id']}/movements",
        f"/debts/{debt['id']}",
        f"/debts/{debt['id']}/payments",
        f"/inheritance/{asset['id']}",
    ]
    for path in paths:
        assert (await client.get(f"{PREFIX}{path}", headers=admin_headers)).status_code == 404
    for path in ("/tills", "/debts", "/inheritance"):
        assert (await read(client, admin_headers, path))["total"] == 0
        assert (await client.get(f"{PREFIX}{path}")).status_code == 401
    for path in ("/tills/summary", "/inheritance/summary"):
        assert await read(client, admin_headers, path) == []
    response = await client.patch(
        f"{PREFIX}/tills/{till['id']}", headers=admin_headers, json={"name": "Intruso"}
    )
    assert response.status_code == 404
    response = await client.post(
        f"{PREFIX}/tills/{till['id']}/movements",
        headers=admin_headers,
        json={"concept_id": expense["id"], "amount": "1"},
    )
    assert response.status_code == 404
    response = await client.post(
        f"{PREFIX}/debts/{debt['id']}/payments",
        headers=admin_headers,
        json={"till_id": till["id"], "concept_id": expense["id"], "due_date": "2026-11-01"},
    )
    assert response.status_code == 404
    response = await client.delete(f"{PREFIX}/inheritance/{asset['id']}", headers=admin_headers)
    assert response.status_code == 404


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/tills", {"name": " ", "opening_balance": "0"}),
        ("/tills", {"name": "Caja", "opening_balance": "-1"}),
        ("/tills", {"name": "Caja", "opening_balance": "0.001"}),
        ("/tills", {"name": "Caja", "currency": "soles"}),
        ("/tills", {"name": "Caja", "user_id": str(uuid4())}),
        ("/debts", {"name": "Renta", "amount": "0", "first_due_date": "2026-01-01"}),
        ("/debts", {"name": "Renta", "amount": "1", "first_due_date": "2026-01-01", "interval": 0}),
        (
            "/inheritance",
            {"name": "Bien", "asset_type": "other", "current_value": "1", "market_value": "1"},
        ),
        (
            "/inheritance",
            {
                "name": "Bien",
                "asset_type": "other",
                "other_type": " ",
                "current_value": "1",
                "market_value": "1",
            },
        ),
        (
            "/inheritance",
            {"name": "Bien", "asset_type": "vehicle", "current_value": "-1", "market_value": "1"},
        ),
    ],
)
async def test_financial_validation(client, path, payload):
    headers = await normal_headers(client)
    response = await client.post(f"{PREFIX}{path}", headers=headers, json=payload)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "frequency,interval,first,current,expected",
    [
        ("daily", 2, "2026-01-01", "2026-01-01", "2026-01-03"),
        ("weekly", 2, "2026-01-01", "2026-01-01", "2026-01-15"),
        ("monthly", 1, "2026-01-31", "2026-02-28", "2026-03-31"),
        ("monthly", 3, "2026-01-31", "2026-01-31", "2026-04-30"),
        ("yearly", 1, "2024-02-29", "2027-02-28", "2028-02-29"),
        ("once", 1, "2026-01-01", "2026-01-01", None),
    ],
)
def test_schedule_dates(frequency, interval, first, current, expected):
    debt = Debt(
        frequency=frequency,
        interval=interval,
        first_due_date=date.fromisoformat(first),
        next_due_date=date.fromisoformat(current),
    )
    result = next_due_date(debt)
    assert result == (date.fromisoformat(expected) if expected else None)
