import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


class MailUnavailableError(AppError):
    status_code = 503
    default_message = "El correo de recuperación todavía no está configurado."


def ensure_mail_configured() -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        raise MailUnavailableError()


async def send_password_code(recipient: str, code: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = str(settings.smtp_from_email)
    message["To"] = recipient
    message["Subject"] = f"{settings.app_name}: código de recuperación"
    message.set_content(
        f"Tu código de recuperación es: {code}\n\n"
        f"Vence en {settings.password_reset_expire_minutes} minutos y solo se puede usar una vez.\n"
        "Si no solicitaste este cambio, ignora este correo."
    )
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            use_tls=settings.smtp_use_tls,
            start_tls=settings.smtp_start_tls and not settings.smtp_use_tls,
            timeout=15,
        )
    except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
        # El envío ocurre después de responder; no registrar el mensaje ni su código.
        logger.error("No se pudo enviar el código de recuperación (%s).", type(exc).__name__)
