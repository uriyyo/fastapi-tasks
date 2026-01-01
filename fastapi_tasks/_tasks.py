from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, ParamSpec, TypeVar

import anyio
from anyio import from_thread
from anyio._core._eventloop import current_async_library
from starlette._utils import is_async_callable
from starlette.concurrency import run_in_threadpool

if TYPE_CHECKING:
    from collections.abc import Callable

    from anyio.abc import TaskGroup

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class TaskConfig:
    name: str | None = None
    shield: bool | None = None

    @property
    def shielded(self) -> bool:
        return self.shield is not None and self.shield


@dataclass
class Task(Generic[P, T]):
    func: Callable[P, T]
    args: P.args
    kwargs: P.kwargs

    config: TaskConfig = field(default_factory=TaskConfig)

    started: anyio.Event = field(default_factory=anyio.Event)

    async def __call__(self) -> T:
        self.started.set()

        with anyio.CancelScope(shield=self.config.shielded):
            if is_async_callable(self.func):
                return await self.func(*self.args, **self.kwargs)

            return await run_in_threadpool(self.func, *self.args, **self.kwargs)

    def start(self, scheduler: TasksScheduler, /) -> None:
        def _start_task() -> None:
            scheduler.tg.start_soon(self, name=self.config.name)

        # if we're not in an async context
        # then we assume we're in anyio worker thread
        if current_async_library() is None:
            from_thread.run_sync(_start_task)
        else:
            _start_task()


@dataclass
class TasksBatch:
    scheduled: list[Task[..., Any]] = field(default_factory=list)

    def add(
        self,
        func: Callable[P, T],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Task[P, T]:
        task = Task(func=func, args=args, kwargs=kwargs)
        self.scheduled.append(task)

        return task

    def start(self, scheduler: TasksScheduler, /) -> None:
        for task_def in self.scheduled:
            task_def.start(scheduler)

    def task(
        self,
        *,
        name: str | None = None,
        shield: bool | None = None,
    ) -> Callable[[Callable[P, T]], Task[P, T]]:
        def decorator(
            func: Callable[P, T],
            /,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> Task[P, T]:
            task_def = Task(
                func=func,
                args=args,
                kwargs=kwargs,
                config=TaskConfig(
                    name=name,
                    shield=shield,
                ),
            )
            self.scheduled.append(task_def)

            return task_def

        return decorator


@dataclass
class TasksScheduler:
    tg: TaskGroup

    after_request: TasksBatch = field(default_factory=TasksBatch)
    after_endpoint: TasksBatch = field(default_factory=TasksBatch)

    def start(
        self,
        func: Callable[P, T],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        task = Task(func=func, args=args, kwargs=kwargs)
        task.start(self)

    def task(
        self,
        *,
        name: str | None = None,
        shield: bool | None = None,
    ) -> Callable[[Callable[P, T]], Task[P, T]]:
        def decorator(
            func: Callable[P, T],
            /,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> Task[P, T]:
            task_def = Task(
                func=func,
                args=args,
                kwargs=kwargs,
                config=TaskConfig(
                    name=name,
                    shield=shield,
                ),
            )
            task_def.start(self)

            return task_def

        return decorator


__all__ = [
    "Task",
    "TaskConfig",
    "TasksBatch",
    "TasksScheduler",
]
