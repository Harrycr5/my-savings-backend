from importlib import import_module
from io import StringIO
from uuid import uuid4

import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from app.db.base import Base
from app.db.models import load_models


def test_migration_chain_and_postgresql_sql():
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_current_head() == "e530f8ca2d17"
    assert [revision.revision for revision in scripts.walk_revisions()] == [
        "e530f8ca2d17",
        "c41a2098fd6e",
        "6d3ce54ce4a8",
        "c6e7d9b812f0",
        "a7d92c5e1048",
        "f4c839a2b671",
        "e3b426c8ad51",
        "d72a48f0e196",
        "b0d80c690963",
        "911b7d3f0603",
    ]
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    for table in ("users", "profiles", "permissions", "profile_permissions", "auth_sessions"):
        assert f"CREATE TABLE {table}" in sql
    assert sql.index("CREATE TABLE profiles") < sql.index("INSERT INTO profiles")
    assert "refresh_token_hash VARCHAR(64)" in sql
    assert "ADD COLUMN doc_number VARCHAR(8)" in sql
    assert "ADD COLUMN avatar_url VARCHAR(255)" in sql
    assert "CONSTRAINT uq_users_doc_number UNIQUE (doc_number)" in sql
    for table in (
        "tills",
        "till_concepts",
        "till_movements",
        "till_movement_requests",
        "debts",
        "debt_payments",
        "inheritance_assets",
        "employees",
        "monthly_budgets",
        "currencies",
    ):
        assert f"CREATE TABLE {table}" in sql
    assert "UNIQUE (debt_id, due_date)" in sql
    assert "CONSTRAINT pk_till_movement_requests PRIMARY KEY (user_id, key)" in sql
    assert "FOREIGN KEY(concept_id, till_id, direction)" in sql
    assert sql.count("FOREIGN KEY(currency) REFERENCES currencies (code)") == 6
    assert "INSERT INTO currencies (code, name, is_selectable)" in sql
    assert "INSERT INTO profile_permissions" in sql
    assert "profiles.code = 'user'" in sql


def test_basic_profile_grants_only_personal_permissions():
    migration = import_module("migrations.versions.c6e7d9b812f0_seed_basic_profile_permissions")
    load_models()
    profiles = Base.metadata.tables["profiles"]
    permissions = Base.metadata.tables["permissions"]
    grants = Base.metadata.tables["profile_permissions"]

    with sa.create_engine("sqlite://").begin() as connection:
        Base.metadata.create_all(connection, tables=[profiles, permissions, grants])
        connection.execute(
            profiles.insert(),
            [{"code": code, "name": code} for code in ("user", "superadmin", "custom")],
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()

        rows = connection.execute(
            sa.select(profiles.c.code, permissions.c.code).select_from(
                profiles.join(grants).join(permissions)
            )
        ).all()
        assert {profile for profile, _ in rows} == {"user"}
        codes = {code for _, code in rows}
        assert {code for code in codes if code.startswith("users.")} == {"users.me"}
        assert {code.split(".")[0] for code in codes} == {
            "tills",
            "till_concepts",
            "till_movements",
            "debts",
            "debt_payments",
            "inheritance_assets",
            "users",
        }


def test_finance_migration_matches_models_and_reverses():
    load_models()
    migration = import_module("migrations.versions.a7d92c5e1048_create_personal_finance_modules")
    idempotency = import_module("migrations.versions.6d3ce54ce4a8_add_till_movement_idempotency")
    planning = import_module(
        "migrations.versions.c41a2098fd6e_create_employees_and_monthly_budgets"
    )
    catalog = import_module("migrations.versions.e530f8ca2d17_create_currency_catalog")
    tables = {
        "tills",
        "till_concepts",
        "till_movements",
        "till_movement_requests",
        "debts",
        "debt_payments",
        "inheritance_assets",
        "employees",
        "monthly_budgets",
        "currencies",
    }
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            sa.Table("users", sa.MetaData(), sa.Column("id", sa.Uuid(), primary_key=True)).create(
                connection
            )
            context = MigrationContext.configure(
                connection,
                opts={
                    "include_object": lambda obj, name, kind, reflected, compare_to: (
                        kind != "table" or name in tables
                    ),
                },
            )
            with Operations.context(context):
                migration.upgrade()
                idempotency.upgrade()
                planning.upgrade()
                Till = Base.metadata.tables["tills"]
                till_id = uuid4()
                connection.execute(
                    Till.insert().values(
                        id=till_id,
                        user_id=uuid4(),
                        name="Caja anterior",
                        currency="JPY",
                        opening_balance=0,
                    )
                )
                catalog.upgrade()
                assert set(sa.inspect(connection).get_table_names()) == tables | {"users"}
                assert compare_metadata(context, Base.metadata) == []
                currencies = Base.metadata.tables["currencies"]
                assert (
                    connection.scalar(
                        sa.select(currencies.c.is_selectable).where(currencies.c.code == "JPY")
                    )
                    is False
                )
                assert (
                    connection.scalar(sa.select(Till.c.currency).where(Till.c.id == till_id))
                    == "JPY"
                )
                catalog.downgrade()
                planning.downgrade()
                idempotency.downgrade()
                migration.downgrade()
                assert sa.inspect(connection).get_table_names() == ["users"]
    finally:
        engine.dispose()
