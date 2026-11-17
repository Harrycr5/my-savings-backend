from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await engine.dispose()
