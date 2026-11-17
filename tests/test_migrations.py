from importlib import import_module
from io import StringIO

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
    assert scripts.get_current_head() == "a7d92c5e1048"
    assert [revision.revision for revision in scripts.walk_revisions()] == [
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
        "debts",
        "debt_payments",
        "inheritance_assets",
    ):
        assert f"CREATE TABLE {table}" in sql
    assert "UNIQUE (debt_id, due_date)" in sql
    assert "FOREIGN KEY(concept_id, till_id, direction)" in sql


def test_finance_migration_matches_models_and_reverses():
    load_models()
    migration = import_module("migrations.versions.a7d92c5e1048_create_personal_finance_modules")
    tables = {
        "tills",
        "till_concepts",
        "till_movements",
        "debts",
        "debt_payments",
        "inheritance_assets",
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
                assert set(sa.inspect(connection).get_table_names()) == tables | {"users"}
                assert compare_metadata(context, Base.metadata) == []
                migration.downgrade()
                assert sa.inspect(connection).get_table_names() == ["users"]
    finally:
        engine.dispose()
