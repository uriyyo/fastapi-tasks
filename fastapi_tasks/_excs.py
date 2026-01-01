class FastAPITasksError(Exception):
    pass


class FastAPITasksUninitializedAppError(FastAPITasksError):
    pass


__all__ = [
    "FastAPITasksError",
    "FastAPITasksUninitializedAppError",
]
