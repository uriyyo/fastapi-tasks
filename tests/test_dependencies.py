import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from fastapi_tasks import Tasks
from fastapi_tasks.errors import FastAPITasksUninitializedAppError

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("init_tasks", [False])
async def test_uninited_app(app: FastAPI, client: AsyncClient, init_tasks: bool) -> None:  # noqa: FBT001
    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        return {}

    with pytest.raises(FastAPITasksUninitializedAppError):
        await client.get("/")


@pytest.mark.parametrize("init_tasks", [True])
async def test_inited_app(app: FastAPI, client: AsyncClient, init_tasks: bool) -> None:  # noqa: FBT001
    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        return {}

    response = await client.get("/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {}
