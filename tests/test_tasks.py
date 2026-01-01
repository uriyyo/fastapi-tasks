from typing import Any

import anyio
import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from fastapi_tasks import Tasks

pytestmark = pytest.mark.asyncio


async def test_on_error(app: FastAPI, client: AsyncClient) -> None:
    error_triggered = anyio.Event()

    async def error_handler(*_: Any) -> None:
        error_triggered.set()

    async def faulty_task() -> None:
        raise ValueError

    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        tasks.task(on_error=error_handler).schedule(faulty_task)
        return {}

    response = await client.get("/")

    assert response.status_code == status.HTTP_200_OK

    with anyio.fail_after(3):
        await error_triggered.wait()
        assert error_triggered.is_set()


async def test_tasks_order(app: FastAPI, client: AsyncClient) -> None:
    execution_order: list[str] = []

    async def task_a() -> None:
        execution_order.append("A")

    async def task_b() -> None:
        execution_order.append("B")

    async def task_c() -> None:
        execution_order.append("C")

    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        tasks.schedule(task_a)
        tasks.after_route.schedule(task_b)
        tasks.after_response.schedule(task_c)
        return {}

    response = await client.get("/")

    assert response.status_code == status.HTTP_200_OK

    await anyio.sleep(0.1)

    assert execution_order == ["A", "B", "C"]


async def test_immediate_task(app: FastAPI, client: AsyncClient) -> None:
    async def immediate_task() -> None:
        pass

    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        task = tasks.schedule(immediate_task)

        await anyio.sleep(0.1)
        assert task.started.is_set()

        return {}

    response = await client.get("/")

    assert response.status_code == status.HTTP_200_OK
