from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Any

import anyio
from fastapi import Depends, FastAPI, Request
from fastapi.routing import _merge_lifespan_context

from ._excs import FastAPITasksUninitializedAppError
from ._tasks import TasksScheduler

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from anyio.abc import TaskGroup


@asynccontextmanager
async def _lifespan(_: FastAPI, /) -> AsyncIterator[dict[str, Any]]:
    async with anyio.create_task_group() as tg:
        yield {"fastapi_tasks_tg": tg}

        tg.cancel_scope.cancel("lifespan ended")


def add_tasks(app: FastAPI) -> None:
    app.router.lifespan_context = _merge_lifespan_context(
        _lifespan,
        app.router.lifespan_context,
    )


async def _get_tasks_scheduler_req_scope(req: Request) -> AsyncIterator[TasksScheduler]:
    try:
        tg: TaskGroup = req.state.fastapi_tasks_tg
    except AttributeError:
        msg = (
            "TaskGroup dependency used outside of lifespan context. "
            "Ensure that 'add_tasks(app)' has been called on the FastAPI app instance."
        )

        raise FastAPITasksUninitializedAppError(msg) from None

    scheduler = TasksScheduler(tg)

    yield scheduler

    scheduler.after_request.start(scheduler)


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
    _scheduler.after_endpoint.start(_scheduler)


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
