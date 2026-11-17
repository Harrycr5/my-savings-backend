from decimal import Decimal
from typing import Literal

from pydantic import model_validator

from app.core.finance import (
    Currency,
    Description,
    FinancialInput,
    FinancialPatch,
    FinancialRead,
    Money,
    Name,
)
from app.core.pagination import PaginationParams

AssetType = Literal["property", "vehicle", "other"]


class AssetCreate(FinancialInput):
    name: Name
    description: Description | None = None
    asset_type: AssetType
    other_type: Name | None = None
    currency: Currency = "PEN"
    current_value: Money
    market_value: Money

    @model_validator(mode="after")
    def validate_other_type(self):
        if self.asset_type == "other" and not self.other_type:
            raise ValueError("Especifica el tipo de bien en other_type.")
        if self.asset_type != "other" and self.other_type is not None:
            raise ValueError("other_type solo corresponde al tipo other.")
        return self


class AssetUpdate(FinancialPatch):
    name: Name | None = None
    description: Description | None = None
    asset_type: AssetType | None = None
    other_type: Name | None = None
    current_value: Money | None = None
    market_value: Money | None = None


class AssetRead(FinancialRead):
    name: str
    description: str | None
    asset_type: AssetType
    other_type: str | None
    currency: str
    current_value: Decimal
    market_value: Decimal


class AssetFilters(PaginationParams):
    asset_type: AssetType | None = None


class AssetSummary(FinancialInput):
    currency: str
    total_assets: int
    current_value: Decimal
    market_value: Decimal
