from pydantic import Field
from sqlalchemy import or_

from app.core.pagination import PaginationParams


class SearchFilters(PaginationParams):
    search: str | None = Field(
        default=None, max_length=100, description="Buscar texto en varios campos."
    )


def apply_filters(statement, model, filters: SearchFilters, searchable: tuple[str, ...]):
    """Solo se consultan campos declarados en el schema; valores siempre parametrizados."""
    values = filters.model_dump(exclude_none=True, exclude={"page", "page_size"})
    for field, value in values.items():
        if field == "search":
            if value.strip():
                statement = statement.where(
                    or_(
                        *[
                            getattr(model, column).icontains(value.strip(), autoescape=True)
                            for column in searchable
                        ]
                    )
                )
        elif isinstance(value, str):
            if value.strip():
                statement = statement.where(
                    getattr(model, field).icontains(value.strip(), autoescape=True)
                )
        else:
            statement = statement.where(getattr(model, field) == value)
    return statement
