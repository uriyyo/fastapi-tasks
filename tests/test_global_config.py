from typing import Any

import anyio
import pytest
from fastapi import FastAPI, status

from fastapi_tasks import TaskConfig, Tasks, add_tasks
from tests.utils import app_client

pytestmark = pytest.mark.asyncio


def test_merge_empty_configs() -> None:
    config1 = TaskConfig()
    config2 = TaskConfig()
    merged = config1.merge(config2)

    assert merged.name is None
    assert merged.shield is None
    assert merged.on_error is None


def test_merge_override() -> None:
    async def handler1(*_: Any) -> None:
        pass

    async def handler2(*_: Any) -> None:
        pass

    config1 = TaskConfig(name="task1", shield=True, on_error=handler1)
    config2 = TaskConfig(shield=False, on_error=handler2)
    merged = config1.merge(config2)

    assert merged.name == "task1"
    assert merged.shield is False
    assert merged.on_error is handler2


def test_merge_immutable() -> None:
    async def handler(*_: Any) -> None:
        pass

    config1 = TaskConfig(name="task1", shield=True, on_error=handler)
    config2 = TaskConfig(name="task2")

    original_name = config1.name
    merged = config1.merge(config2)

    assert config1.name == original_name
    assert merged.name == "task2"


async def test_global_config_applied() -> None:
    app = FastAPI()
    error_triggered = anyio.Event()

    async def global_error_handler(*_: Any) -> None:
        error_triggered.set()

    global_config = TaskConfig(on_error=global_error_handler)
    add_tasks(app, config=global_config)

    async def faulty_task() -> None:
        raise ValueError

    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        tasks.schedule(faulty_task)
        return {}

    async with app_client(app) as client:
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK

        with anyio.fail_after(3):
            await error_triggered.wait()
            assert error_triggered.is_set()


async def test_task_override_global_config() -> None:
    app = FastAPI()
    global_handler_called = anyio.Event()
    task_handler_called = anyio.Event()

    async def global_error_handler(*_: Any) -> None:
        global_handler_called.set()

    async def task_error_handler(*_: Any) -> None:
        task_handler_called.set()

    global_config = TaskConfig(on_error=global_error_handler)
    add_tasks(app, config=global_config)

    async def faulty_task() -> None:
        raise ValueError

    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        tasks.task(on_error=task_error_handler).schedule(faulty_task)
        return {}

    async with app_client(app) as client:
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK

        with anyio.fail_after(3):
            await task_handler_called.wait()
            assert task_handler_called.is_set()
            assert not global_handler_called.is_set()


async def test_partial_task_override() -> None:
    app = FastAPI()
    error_triggered = anyio.Event()

    async def global_error_handler(*_: Any) -> None:
        error_triggered.set()

    global_config = TaskConfig(shield=True, on_error=global_error_handler)
    add_tasks(app, config=global_config)

    async def faulty_task() -> None:
        raise ValueError

    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        tasks.task(shield=False).schedule(faulty_task)
        return {}

    async with app_client(app) as client:
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK

        with anyio.fail_after(3):
            await error_triggered.wait()
            assert error_triggered.is_set()


async def test_after_response_inherits_global_config() -> None:
    app = FastAPI()
    error_triggered = anyio.Event()

    async def global_error_handler(*_: Any) -> None:
        error_triggered.set()

    global_config = TaskConfig(on_error=global_error_handler)
    add_tasks(app, config=global_config)

    async def faulty_task() -> None:
        raise ValueError

    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        tasks.after_response.schedule(faulty_task)
        return {}

    async with app_client(app) as client:
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK

        with anyio.fail_after(3):
            await error_triggered.wait()
            assert error_triggered.is_set()


async def test_after_route_inherits_global_config() -> None:
    app = FastAPI()
    error_triggered = anyio.Event()

    async def global_error_handler(*_: Any) -> None:
        error_triggered.set()

    global_config = TaskConfig(on_error=global_error_handler)
    add_tasks(app, config=global_config)

    async def faulty_task() -> None:
        raise ValueError

    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        tasks.after_route.schedule(faulty_task)
        return {}

    async with app_client(app) as client:
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK

        with anyio.fail_after(3):
            await error_triggered.wait()
            assert error_triggered.is_set()


async def test_all_batch_types_use_same_global_config() -> None:
    app = FastAPI()
    errors_caught: list[str] = []
    completion_event = anyio.Event()
    expected_error_count = 3

    async def global_error_handler(*args: Any) -> None:
        exc = args[1] if len(args) > 1 else args[0]
        errors_caught.append(str(exc))
        if len(errors_caught) == expected_error_count:
            completion_event.set()

    global_config = TaskConfig(on_error=global_error_handler)
    add_tasks(app, config=global_config)

    async def faulty_task_1() -> None:
        msg = "Error 1"
        raise ValueError(msg)

    async def faulty_task_2() -> None:
        msg = "Error 2"
        raise ValueError(msg)

    async def faulty_task_3() -> None:
        msg = "Error 3"
        raise ValueError(msg)

    @app.get("/")
    async def route(tasks: Tasks) -> dict[str, str]:
        tasks.schedule(faulty_task_1)
        tasks.after_route.schedule(faulty_task_2)
        tasks.after_response.schedule(faulty_task_3)
        return {}

    async with app_client(app) as client:
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK

        with anyio.fail_after(3):
            await completion_event.wait()

        assert len(errors_caught) == expected_error_count
