from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from copy import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, ParamSpec, TypeAlias, TypeVar

import anyio
import anyio.from_thread
from anyio._core._eventloop import current_async_library
from typing_extensions import Self

from .utils import always_async_call

if TYPE_CHECKING:
    from anyio.abc import TaskGroup

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

TaskErrorHandler: TypeAlias = (
    Callable[["Task[..., Any]", Exception], Any] | Callable[["Task[..., Any]", Exception], Awaitable[Any]]
)


@dataclass
class TaskConfig:
    name: str | None = None
    shield: bool | None = None
    on_error: TaskErrorHandler | None = None

    @property
    def shielded(self) -> bool:
        return bool(self.shield)

    def merge(self, other: Self, /) -> Self:
        merged = copy(self)

        if other.name is not None:
            merged.name = other.name

        if other.shield is not None:
            merged.shield = other.shield

        if other.on_error is not None:
            merged.on_error = other.on_error

        return merged


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
                return await always_async_call(self.func, *self.args, **self.kwargs)
        except Exception as e:
            logger.exception("Exception occurred in task %r", self)

            if self.config.on_error is not None:
                await always_async_call(self.config.on_error, self, e)

        return None

    def __start__(self, scheduler: TasksScheduler, /) -> None:
        def _start_task() -> None:
            scheduler.tg.start_soon(self, name=self.config.name)

        # if we're not in an async context
        # then we assume we're in anyio worker thread
        if current_async_library() is None:
            anyio.from_thread.run_sync(_start_task)
        else:
            _start_task()


@dataclass
class _PartialTaskDef(Generic[P, T]):
    _config: TaskConfig
    _on_schedule: Callable[[Task[P, T]], None]

    def schedule(
        self,
        func: Callable[P, T],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Task[P, T]:
        task = Task(
            func=func,
            args=args,
            kwargs=kwargs,
            config=self._config,
        )
        self._on_schedule(task)

        return task


class _ConfiguredTaskDefMixin(ABC):
    config: TaskConfig

    @abstractmethod
    def _on_task_schedule(self, task: Task[P, T], /) -> None:
        pass

    def schedule(
        self,
        func: Callable[P, T],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Task[P, T]:
        task = Task(func=func, args=args, kwargs=kwargs, config=self.config)
        self._on_task_schedule(task)

        return task

    def task(
        self,
        *,
        name: str | None = None,
        shield: bool | None = None,
        on_error: TaskErrorHandler | None = None,
    ) -> _PartialTaskDef[..., Any]:
        return _PartialTaskDef(
            _config=self.config.merge(
                TaskConfig(
                    name=name,
                    shield=shield,
                    on_error=on_error,
                ),
            ),
            _on_schedule=self._on_task_schedule,
        )


@dataclass(kw_only=True)
class TasksBatch(_ConfiguredTaskDefMixin):
    config: TaskConfig
    scheduled: list[Task[..., Any]] = field(default_factory=list)

    def __start__(self, scheduler: TasksScheduler, /) -> None:
        for task_def in self.scheduled:
            task_def.__start__(scheduler)

    def _on_task_schedule(self, task: Task[P, T], /) -> None:
        self.scheduled.append(task)


@dataclass
class TasksScheduler(_ConfiguredTaskDefMixin):
    tg: TaskGroup
    config: TaskConfig

    after_response: TasksBatch = field(init=False)
    after_route: TasksBatch = field(init=False)

    def __post_init__(self) -> None:
        self.after_response = TasksBatch(config=self.config)
        self.after_route = TasksBatch(config=self.config)

    def _on_task_schedule(self, task: Task[P, T], /) -> None:
        task.__start__(self)


__all__ = [
    "Task",
    "TaskConfig",
    "TaskErrorHandler",
    "TasksBatch",
    "TasksScheduler",
]
