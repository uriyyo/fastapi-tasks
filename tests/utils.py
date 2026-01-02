from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@asynccontextmanager
async def app_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    manager = LifespanManager(app)

    async with (
        manager,
        AsyncClient(
            base_url="http://testserver",
            transport=ASGITransport(app=manager.app),
        ) as ac,
    ):
        yield ac
