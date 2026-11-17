import logging
from importlib import import_module
from pkgutil import iter_modules

from fastapi import APIRouter

import app.modules as modules

logger = logging.getLogger(__name__)


def register_module_routers(api_router: APIRouter) -> None:
    for module in sorted(
        iter_modules(modules.__path__),
        key=lambda item: item.name,
    ):
        if not module.ispkg:
            continue

        router_path = f"{modules.__name__}.{module.name}.router"

        try:
            router_module = import_module(router_path)
        except Exception:
            logger.exception(
                "Se omite %s por un error al importarlo.",
                router_path,
            )
            continue

        module_router = getattr(router_module, "router", None)

        if not isinstance(module_router, APIRouter):
            logger.warning(
                "Se omite %s: no define un router válido.",
                router_path,
            )
            continue

        try:
            api_router.include_router(module_router)
        except Exception:
            logger.exception(
                "Error al registrar %s.",
                router_path,
            )


api_router = APIRouter(prefix="/api/v1")

register_module_routers(api_router)
