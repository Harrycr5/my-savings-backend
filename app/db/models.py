from importlib import import_module
from pkgutil import iter_modules

import app.modules as modules


def load_models() -> None:
    for module in sorted(
        iter_modules(modules.__path__),
        key=lambda item: item.name,
    ):
        if not module.ispkg:
            continue

        models_path = f"{modules.__name__}.{module.name}.models"

        try:
            import_module(models_path)
        except ModuleNotFoundError as exc:
            # Permite módulos sin models.py, como health.
            # Si falta una dependencia interna, propaga el error.
            if exc.name != models_path:
                raise
