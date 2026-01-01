from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

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

    async def __call__(self) -> T | None:
        self.started.set()

        try:
            with anyio.CancelScope(shield=self.config.shielded):
                if is_async_callable(self.func):
                    return await self.func(*self.args, **self.kwargs)

                return await run_in_threadpool(self.func, *self.args, **self.kwargs)
        except Exception:
            logger.exception("Exception occurred in task %r", self)

        return None

    def __start__(self, scheduler: TasksScheduler, /) -> None:
        def _start_task() -> None:
            scheduler.tg.start_soon(self, name=self.config.name)

        # if we're not in an async context
        # then we assume we're in anyio worker thread
        if current_async_library() is None:
            from_thread.run_sync(_start_task)
        else:
            _start_task()


class _ConfiguredTaskDefMixin:
    def _on_task(self, task: Task[P, T], /) -> None:
        pass

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
            self._on_task(task_def)

            return task_def

        return decorator


@dataclass
class TasksBatch(_ConfiguredTaskDefMixin):
    scheduled: list[Task[..., Any]] = field(default_factory=list)

    def schedule(
        self,
        func: Callable[P, T],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Task[P, T]:
        task = Task(func=func, args=args, kwargs=kwargs)
        self.scheduled.append(task)

        return task

    def __start__(self, scheduler: TasksScheduler, /) -> None:
        for task_def in self.scheduled:
            task_def.__start__(scheduler)

    def _on_task(self, task: Task[P, T], /) -> None:
        self.scheduled.append(task)


@dataclass
class TasksScheduler(_ConfiguredTaskDefMixin):
    tg: TaskGroup

    after_request: TasksBatch = field(default_factory=TasksBatch)
    after_endpoint: TasksBatch = field(default_factory=TasksBatch)

    def schedule(
        self,
        func: Callable[P, T],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        task = Task(func=func, args=args, kwargs=kwargs)
        task.__start__(self)

    def _on_task(self, task: Task[P, T], /) -> None:
        task.__start__(self)


__all__ = [
    "Task",
    "TaskConfig",
    "TasksBatch",
    "TasksScheduler",
]
