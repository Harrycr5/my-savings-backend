from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.lifespan import lifespan

settings = get_settings()

fastapi_app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "tryItOutEnabled": True,
        "docExpansion": "list",
        "filter": True,
    },
)

register_exception_handlers(fastapi_app)
fastapi_app.include_router(api_router)

# Envolver toda la aplicación permite CORS también en respuestas de error 500.
app = CORSMiddleware(
    fastapi_app,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
