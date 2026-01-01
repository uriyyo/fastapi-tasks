import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from fastapi_tasks import add_tasks


@pytest.fixture
def init_tasks() -> bool:
    return True


@pytest.fixture
def app(init_tasks: bool) -> FastAPI:  # noqa: FBT001
    _app = FastAPI()

    if init_tasks:
        add_tasks(_app)

    return _app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    manager = LifespanManager(app)

    async with (
        manager,
        AsyncClient(
            base_url="http://testserver",
            transport=ASGITransport(app=manager.app),
        ) as ac,
    ):
        yield ac


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    return asyncio.new_event_loop()
