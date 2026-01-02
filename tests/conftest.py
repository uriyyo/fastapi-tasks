import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient

from fastapi_tasks import add_tasks
from tests.utils import app_client


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
    async with app_client(app) as ac:
        yield ac


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    return asyncio.new_event_loop()
