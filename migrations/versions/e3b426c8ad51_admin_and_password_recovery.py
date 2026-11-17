"""Add administrator flag, password recovery codes and uppercase display data.

Revision ID: e3b426c8ad51
Revises: d72a48f0e196
"""

import sqlalchemy as sa
from alembic import op

revision = "e3b426c8ad51"
down_revision = "d72a48f0e196"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Mantener administradoras las cuentas que ya tenían el perfil reservado.
    op.execute(
        sa.text(
            "UPDATE users SET is_admin = true WHERE profile_id IN (SELECT id FROM profiles WHERE code = 'superadmin')"
        )
    )
    op.create_table(
        "password_reset_codes",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_codes")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_password_reset_codes_user_id_users"),
        ),
        sa.UniqueConstraint("user_id", name=op.f("uq_password_reset_codes_user_id")),
    )
    # La conversión de mayúsculas de los datos existentes es intencional y no reversible.
    for table_name, columns in (
        ("users", ("name", "last_name")),
        ("profiles", ("name", "description")),
        ("permissions", ("name", "description")),
    ):
        table = sa.table(table_name, *(sa.column(column, sa.String) for column in columns))
        op.execute(
            table.update().values(
                **{column: sa.func.upper(sa.func.trim(table.c[column])) for column in columns}
            )
        )


def downgrade() -> None:
    op.drop_table("password_reset_codes")
    op.drop_column("users", "is_admin")
