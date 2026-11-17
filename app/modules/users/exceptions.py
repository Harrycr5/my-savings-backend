from app.core.exceptions import AppError


class UserAlreadyExistsError(AppError):
    status_code = 409
    default_message = "El correo o username ya está registrado."


class RegistrationUnavailableError(AppError):
    status_code = 503
    default_message = "El registro no está disponible."
