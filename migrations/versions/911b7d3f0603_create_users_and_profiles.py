"""Create users, profiles and permissions."""

import sqlalchemy as sa
from alembic import op

revision = "911b7d3f0603"
down_revision = None
branch_labels = None
depends_on = None


def base_columns():
    return [
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "profiles",
        *base_columns(),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profiles")),
        sa.UniqueConstraint("code", name=op.f("uq_profiles_code")),
    )

    op.create_table(
        "permissions",
        *base_columns(),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )

    op.create_table(
        "users",
        *base_columns(),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name=op.f("fk_users_profile_id_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )

    op.create_index(
        op.f("ix_users_profile_id"),
        "users",
        ["profile_id"],
        unique=False,
    )

    op.create_table(
        "profile_permissions",
        sa.Column(
            "profile_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name=op.f("fk_profile_permissions_profile_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_profile_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "profile_id",
            "permission_id",
            name=op.f("pk_profile_permissions"),
        ),
    )


def downgrade() -> None:
    op.drop_table("profile_permissions")
    op.drop_index(op.f("ix_users_profile_id"), table_name="users")
    op.drop_table("users")
    op.drop_table("permissions")
    op.drop_table("profiles")
