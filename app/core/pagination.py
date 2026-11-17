from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, description="Número de página.")
    page_size: int = Field(default=20, ge=1, le=100, description="Resultados por página.")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


Pagination = Annotated[PaginationParams, Query()]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, params: PaginationParams) -> "Page[T]":
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            pages=(total + params.page_size - 1) // params.page_size,
        )
