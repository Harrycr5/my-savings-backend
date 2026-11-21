"""Create the currency catalog and link financial records to it."""

import sqlalchemy as sa
from alembic import op

revision = "e530f8ca2d17"
down_revision = "c41a2098fd6e"
branch_labels = None
depends_on = None

CURRENCY_NAMES = {
    "ARS": "Peso argentino",
    "AWG": "Florín arubeño",
    "BBD": "Dólar de Barbados",
    "BMD": "Dólar de Bermudas",
    "BOB": "Boliviano",
    "BRL": "Real brasileño",
    "BSD": "Dólar bahameño",
    "BZD": "Dólar beliceño",
    "CLP": "Peso chileno",
    "COP": "Peso colombiano",
    "CRC": "Colón costarricense",
    "CUP": "Peso cubano",
    "DOP": "Peso dominicano",
    "EUR": "Euro",
    "FKP": "Libra de las Islas Malvinas",
    "GTQ": "Quetzal guatemalteco",
    "GYD": "Dólar guyanés",
    "HNL": "Lempira hondureña",
    "HTG": "Gourde haitiano",
    "JMD": "Dólar jamaiquino",
    "KYD": "Dólar de las Islas Caimán",
    "MXN": "Peso mexicano",
    "NIO": "Córdoba nicaragüense",
    "PAB": "Balboa panameño",
    "PEN": "Sol peruano",
    "PYG": "Guaraní paraguayo",
    "SRD": "Dólar surinamés",
    "SVC": "Colón salvadoreño",
    "TTD": "Dólar de Trinidad y Tobago",
    "USD": "Dólar estadounidense",
    "UYU": "Peso uruguayo",
    "VES": "Bolívar soberano",
    "XCD": "Dólar del Caribe Oriental",
    "XCG": "Florín caribeño",
}

FINANCIAL_TABLES = (
    "tills",
    "debts",
    "debt_payments",
    "inheritance_assets",
    "employees",
    "monthly_budgets",
)


def upgrade() -> None:
    currencies = op.create_table(
        "currencies",
        sa.Column("code", sa.String(3), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_selectable", sa.Boolean(), nullable=False),
    )
    op.bulk_insert(
        currencies,
        [
            {"code": code, "name": name, "is_selectable": True}
            for code, name in CURRENCY_NAMES.items()
        ],
    )
    # Preserve all codes accepted by earlier API versions before enforcing foreign keys.
    existing_codes = sa.union(
        *(
            sa.select(sa.column("currency", sa.String(3)).label("code")).select_from(sa.table(name))
            for name in FINANCIAL_TABLES
        )
    ).subquery()
    op.execute(
        currencies.insert().from_select(
            ["code", "name", "is_selectable"],
            sa.select(existing_codes.c.code, existing_codes.c.code, sa.false()).where(
                existing_codes.c.code.not_in(sa.select(currencies.c.code))
            ),
        )
    )
    for table in FINANCIAL_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(
                op.f(f"fk_{table}_currency_currencies"),
                "currencies",
                ["currency"],
                ["code"],
                ondelete="RESTRICT",
            )


def downgrade() -> None:
    for table in reversed(FINANCIAL_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(op.f(f"fk_{table}_currency_currencies"), type_="foreignkey")
    op.drop_table("currencies")
