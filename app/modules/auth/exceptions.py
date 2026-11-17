from app.core.exceptions import AppError


class InvalidCredentialsError(AppError):
    status_code = 401
    default_message = "Credenciales inválidas o cuenta no disponible."
    headers = {"WWW-Authenticate": "Bearer"}
