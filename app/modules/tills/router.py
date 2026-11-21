from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query

from app.api.dependencies import DbSession
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import CurrentUser
from app.modules.tills.repository import TillRepository
from app.modules.tills.schemas import (
    ConceptCreate,
    ConceptRead,
    MovementCreate,
    MovementFilters,
    MovementRead,
    TillBalance,
    TillCreate,
    TillRead,
    TillSummary,
    TillUpdate,
)
from app.modules.tills.service import TillService

router = APIRouter(prefix="/tills", tags=["Tills"])


@router.post("", response_model=ApiResponse[TillRead], status_code=201)
async def create_till(data: TillCreate, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await TillService(session).create(user.id, data))


@router.get("", response_model=ApiResponse[Page[TillRead]])
async def list_tills(user: CurrentUser, session: DbSession, params: Pagination):
    return ApiResponse(data=await TillRepository(session).list(user.id, params, TillRead))


@router.get("/summary", response_model=ApiResponse[list[TillSummary]])
async def till_summary(user: CurrentUser, session: DbSession):
    return ApiResponse(data=await TillRepository(session).summary(user.id))


@router.get("/movements", response_model=ApiResponse[Page[MovementRead]])
async def list_all_movements(
    user: CurrentUser,
    session: DbSession,
    filters: Annotated[MovementFilters, Query()],
):
    return ApiResponse(data=await TillRepository(session).all_movements(user.id, filters))


@router.get("/{till_id}", response_model=ApiResponse[TillRead])
async def get_till(till_id: UUID, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await TillRepository(session).get(till_id, user.id))


@router.patch("/{till_id}", response_model=ApiResponse[TillRead])
async def update_till(till_id: UUID, data: TillUpdate, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await TillService(session).update(user.id, till_id, data))


@router.get("/{till_id}/balance", response_model=ApiResponse[TillBalance])
async def get_balance(till_id: UUID, user: CurrentUser, session: DbSession):
    repository = TillRepository(session)
    till = await repository.get(till_id, user.id)
    return ApiResponse(data=await repository.balance(till))


@router.post("/{till_id}/concepts", response_model=ApiResponse[ConceptRead], status_code=201)
async def create_concept(till_id: UUID, data: ConceptCreate, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await TillService(session).create_concept(user.id, till_id, data))


@router.get("/{till_id}/concepts", response_model=ApiResponse[Page[ConceptRead]])
async def list_concepts(till_id: UUID, user: CurrentUser, session: DbSession, params: Pagination):
    repository = TillRepository(session)
    await repository.get(till_id, user.id)
    return ApiResponse(data=await repository.concepts(till_id, params))


@router.post(
    "/{till_id}/movements",
    response_model=ApiResponse[MovementRead],
    status_code=201,
    responses={409: {"description": "Clave de idempotencia usada con otros datos"}},
)
async def create_movement(
    till_id: UUID,
    data: MovementCreate,
    user: CurrentUser,
    session: DbSession,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", pattern=r"^[!-~]{1,128}$")
    ] = None,
):
    movement = await TillService(session).create_movement(
        user.id, till_id, data, idempotency_key=idempotency_key
    )
    return ApiResponse(data=movement)


@router.get("/{till_id}/movements", response_model=ApiResponse[Page[MovementRead]])
async def list_movements(
    till_id: UUID,
    user: CurrentUser,
    session: DbSession,
    filters: Annotated[MovementFilters, Query()],
):
    repository = TillRepository(session)
    await repository.get(till_id, user.id)
    return ApiResponse(data=await repository.movements(till_id, filters))
