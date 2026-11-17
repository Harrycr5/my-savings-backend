from io import StringIO

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_chain_and_postgresql_sql():
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_current_head() == "e3b426c8ad51"
    assert [revision.revision for revision in scripts.walk_revisions()] == [
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
