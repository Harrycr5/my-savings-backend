from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: Literal[True] = True
    message: str = "Operación realizada correctamente."
    data: T
