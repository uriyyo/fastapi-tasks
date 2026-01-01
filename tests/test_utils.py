from collections.abc import Callable
from typing import Any

import pytest

from fastapi_tasks.utils import always_async_call

pytestmark = pytest.mark.asyncio


async def _async_func(x: int) -> int:
    return x + 1


def _sync_func(x: int) -> int:
    return x + 2


@pytest.mark.parametrize(
    ("func", "arg", "expected"),
    [
        pytest.param(_async_func, 1, 2, id="async"),
        pytest.param(_sync_func, 1, 3, id="sync"),
    ],
)
async def test_always_async_call(func: Callable[[int], Any], arg: int, expected: int) -> None:
    result = await always_async_call(func, arg)
    assert result == expected
