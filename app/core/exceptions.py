class AppError(Exception):
    status_code = 400
    default_message = "No se pudo completar la operación."
    headers: dict[str, str] | None = None

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    default_message = "Recurso no encontrado."


class ConflictError(AppError):
    status_code = 409
    default_message = "El recurso ya existe."


class ForbiddenError(AppError):
    status_code = 403
    default_message = "Operación no permitida."
