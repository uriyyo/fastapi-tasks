from __future__ import annotations

from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING, Annotated, Any

import anyio
from fastapi import Depends, FastAPI, Request
from fastapi.routing import _merge_lifespan_context

from .errors import FastAPITasksUninitializedAppError
from .tasks import TaskConfig, TasksScheduler

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from anyio.abc import TaskGroup


@asynccontextmanager
async def _lifespan(_: FastAPI, /, config: TaskConfig) -> AsyncIterator[dict[str, Any]]:
    async with anyio.create_task_group() as tg:
        yield {
            "fastapi_tasks_tg": tg,
            "fastapi_tasks_config": config,
        }

        tg.cancel_scope.cancel()


def add_tasks(
    app: FastAPI,
    *,
    config: TaskConfig | None = None,
) -> None:
    app.router.lifespan_context = _merge_lifespan_context(
        partial(
            _lifespan,
            config=config or TaskConfig(),
        ),
        app.router.lifespan_context,
    )


async def _get_tasks_scheduler_req_scope(req: Request) -> AsyncIterator[TasksScheduler]:
    try:
        tg: TaskGroup = req.state.fastapi_tasks_tg
        config: TaskConfig = req.state.fastapi_tasks_config
    except AttributeError:
        msg = (
            "TaskGroup dependency used outside of lifespan context. "
            "Ensure that 'add_tasks(app)' has been called on the FastAPI app instance."
        )

        raise FastAPITasksUninitializedAppError(msg) from None

    scheduler = TasksScheduler(tg, config)

    yield scheduler

    scheduler.after_response.__start__(scheduler)


async def _get_task_scheduler(
    *,
    _scheduler: Annotated[
        TasksScheduler,
        Depends(
            _get_tasks_scheduler_req_scope,
            scope="request",
        ),
    ],
) -> AsyncIterator[TasksScheduler]:
    yield _scheduler
    _scheduler.after_route.__start__(_scheduler)


Tasks = Annotated[
    TasksScheduler,
    Depends(
        _get_task_scheduler,
        scope="function",
    ),
]

__all__ = [
    "Tasks",
    "add_tasks",
]
