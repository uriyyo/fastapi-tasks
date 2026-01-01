from collections.abc import Callable
from typing import ParamSpec, TypeVar

from starlette._utils import is_async_callable
from starlette.concurrency import run_in_threadpool

P = ParamSpec("P")
T = TypeVar("T")


async def always_async_call(
    func: Callable[P, T],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    if is_async_callable(func):
        return await func(*args, **kwargs)

    return await run_in_threadpool(func, *args, **kwargs)


__all__ = [
    "always_async_call",
]
