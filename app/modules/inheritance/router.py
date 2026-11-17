from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import DbSession
from app.core.pagination import Page
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import CurrentUser
from app.modules.inheritance.models import Asset
from app.modules.inheritance.repository import AssetRepository
from app.modules.inheritance.schemas import (
    AssetCreate,
    AssetFilters,
    AssetRead,
    AssetSummary,
    AssetUpdate,
)
from app.modules.inheritance.service import AssetService

router = APIRouter(prefix="/inheritance", tags=["Inheritance"])


@router.post("", response_model=ApiResponse[AssetRead], status_code=201)
async def create_asset(data: AssetCreate, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await AssetService(session).create(user.id, data))


@router.get("", response_model=ApiResponse[Page[AssetRead]])
async def list_assets(
    user: CurrentUser, session: DbSession, filters: Annotated[AssetFilters, Query()]
):
    conditions = [Asset.asset_type == filters.asset_type] if filters.asset_type else []
    return ApiResponse(
        data=await AssetRepository(session).list(user.id, filters, AssetRead, *conditions)
    )


@router.get("/summary", response_model=ApiResponse[list[AssetSummary]])
async def asset_summary(user: CurrentUser, session: DbSession):
    return ApiResponse(data=await AssetRepository(session).summary(user.id))


@router.get("/{asset_id}", response_model=ApiResponse[AssetRead])
async def get_asset(asset_id: UUID, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await AssetRepository(session).get(asset_id, user.id))


@router.patch("/{asset_id}", response_model=ApiResponse[AssetRead])
async def update_asset(asset_id: UUID, data: AssetUpdate, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await AssetService(session).update(user.id, asset_id, data))


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(asset_id: UUID, user: CurrentUser, session: DbSession):
    await AssetService(session).delete(user.id, asset_id)
    return Response(status_code=204)
