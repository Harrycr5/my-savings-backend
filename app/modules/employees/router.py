from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import DbSession
from app.core.finance import OwnedRepository
from app.core.pagination import Page, PaginationParams
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import CurrentUser
from app.modules.currencies.service import require_selectable_currency
from app.modules.employees.models import Employee
from app.modules.employees.schemas import EmployeeCreate, EmployeeRead, EmployeeUpdate

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.post("", response_model=ApiResponse[EmployeeRead], status_code=201)
async def create_employee(data: EmployeeCreate, user: CurrentUser, session: DbSession):
    await require_selectable_currency(session, data.currency)
    employee = await OwnedRepository(session, Employee).save(
        Employee(user_id=user.id, **data.model_dump())
    )
    await session.commit()
    return ApiResponse(data=employee)


@router.get("", response_model=ApiResponse[Page[EmployeeRead]])
async def list_employees(
    user: CurrentUser, session: DbSession, params: Annotated[PaginationParams, Query()]
):
    return ApiResponse(
        data=await OwnedRepository(session, Employee).list(user.id, params, EmployeeRead)
    )


@router.get("/{employee_id}", response_model=ApiResponse[EmployeeRead])
async def get_employee(employee_id: UUID, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await OwnedRepository(session, Employee).get(employee_id, user.id))


@router.patch("/{employee_id}", response_model=ApiResponse[EmployeeRead])
async def update_employee(
    employee_id: UUID, data: EmployeeUpdate, user: CurrentUser, session: DbSession
):
    repository = OwnedRepository(session, Employee)
    employee = await repository.get(employee_id, user.id, lock=True)
    if data.currency is not None and data.currency != employee.currency:
        await require_selectable_currency(session, data.currency)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    await repository.save(employee)
    await session.commit()
    return ApiResponse(data=employee)


@router.delete("/{employee_id}", status_code=204)
async def delete_employee(employee_id: UUID, user: CurrentUser, session: DbSession):
    employee = await OwnedRepository(session, Employee).get(employee_id, user.id, lock=True)
    await session.delete(employee)
    await session.commit()
    return Response(status_code=204)
