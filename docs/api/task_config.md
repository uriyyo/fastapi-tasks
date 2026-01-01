# TaskConfig, Task, and TasksBatch

This page documents the internal data structures used by `fastapi-tasks`.

## TaskConfig

The `TaskConfig` dataclass holds configuration options for a task.

### Definition

```python
@dataclass
class TaskConfig:
    name: str | None = None
    shield: bool | None = None
    on_error: TaskErrorHandler | None = None
```

### Attributes

#### `name: str | None`

Optional name for the task. Used in logging and debugging.

**Default:** `None`

**Example:**

```python
config = TaskConfig(name="process_payment")
```

#### `shield: bool | None`

Whether to protect the task from cancellation during server shutdown.

**Default:** `None` (equivalent to `False`)

**Example:**

```python
config = TaskConfig(shield=True)
```

#### `on_error: TaskErrorHandler | None`

Custom error handler called when the task raises an exception.

**Default:** `None` (errors are logged but not handled)

**Example:**

```python
async def error_handler(task: Task, error: Exception) -> None:
    print(f"Task failed: {error}")

config = TaskConfig(on_error=error_handler)
```

### Properties

#### `shielded: bool`

Returns `True` if the task is shielded (i.e., `shield` is not `None` and is `True`).

```python
config = TaskConfig(shield=True)
assert config.shielded is True

config = TaskConfig(shield=False)
assert config.shielded is False

config = TaskConfig()  # shield=None
assert config.shielded is False
```

### Methods

#### `merge(other: TaskConfig) -> TaskConfig`

Merges this configuration with another configuration, creating a new `TaskConfig` instance.

The `other` config takes precedence for any non-None values.

**Parameters:**

- `other: TaskConfig` - The configuration to merge with

**Returns:** A new `TaskConfig` instance with merged values

**Behavior:**

- Starts with a copy of the current config
- For each field in `other` that is not `None`, overwrites the field in the merged config
- Fields that are `None` in `other` keep their values from the current config

**Example:**

```python
# Base configuration
base = TaskConfig(name="base_task", shield=True)

# Override configuration
override = TaskConfig(shield=False, on_error=error_handler)

# Merge them
merged = base.merge(override)

# Result:
# - name: "base_task" (from base, since override.name is None)
# - shield: False (from override)
# - on_error: error_handler (from override)
assert merged.name == "base_task"
assert merged.shield is False
assert merged.on_error is error_handler
```

**Use Cases:**

The `merge()` method is primarily used internally when you provide a global configuration to `add_tasks()` and then override it for individual tasks:

```python
from fastapi import FastAPI
from fastapi_tasks import add_tasks, TaskConfig

# Global configuration for all tasks
global_config = TaskConfig(shield=True, on_error=global_error_handler)
app = FastAPI()
add_tasks(app, config=global_config)

# Individual tasks can override the global config
@app.post("/task")
async def endpoint(tasks: Tasks) -> dict:
    # This task inherits shield=True but overrides the error handler
    tasks.task(on_error=custom_handler).schedule(my_function)
    
    # Result: shield=True (from global), on_error=custom_handler
    return {}
```

## Task

The `Task` class represents a scheduled task.

### Definition

```python
@dataclass
class Task(Generic[P, T]):
    func: Callable[P, T]
    args: P.args
    kwargs: P.kwargs
    config: TaskConfig = field(default_factory=TaskConfig)
    started: anyio.Event = field(default_factory=anyio.Event)
```

### Attributes

#### `func: Callable[P, T]`

The function to be executed.

#### `args: P.args`

Positional arguments passed to the function.

#### `kwargs: P.kwargs`

Keyword arguments passed to the function.

#### `config: TaskConfig`

The task's configuration (name, shield, error handler).

**Default:** `TaskConfig()` (empty configuration)

#### `started: anyio.Event`

An event that is set when the task starts executing. Useful for testing or waiting for task startup.

```python
task = tasks.schedule(my_function)

# Wait for the task to start
await task.started.wait()
```

### Methods

#### `async __call__() -> T | None`

Execute the task. This is called internally by the task scheduler.

**Returns:** The return value of the task function, or `None` if an error occurred.

**Behavior:**

1. Sets the `started` event
2. Executes the function within a shield scope if configured
3. Calls the error handler if an exception occurs
4. Returns the result or `None` on error

You typically don't call this directly; the scheduler handles it.

### Usage Example

```python
from fastapi_tasks import Task, TaskConfig

# Task objects are usually created by the scheduler
task = tasks.schedule(my_function, arg1, arg2)

# Access task properties
print(f"Task name: {task.config.name}")
print(f"Function: {task.func.__name__}")
print(f"Arguments: {task.args}")
print(f"Is shielded: {task.config.shielded}")

# Wait for task to start
await task.started.wait()
```

## TasksBatch

The `TasksBatch` class manages a batch of tasks that execute together.

### Definition

```python
@dataclass
class TasksBatch(_ConfiguredTaskDefMixin):
    scheduled: list[Task[..., Any]] = field(default_factory=list)
```

### Attributes

#### `scheduled: list[Task]`

The list of tasks scheduled in this batch.

### Methods

#### `schedule(func, /, *args, **kwargs) -> Task`

Schedule a task in this batch.

**Parameters:**

- `func: Callable[P, T]` - The function to execute
- `*args: P.args` - Positional arguments
- `**kwargs: P.kwargs` - Keyword arguments

**Returns:** `Task[P, T]`

#### `task(*, name=None, shield=None, on_error=None) -> _PartialTaskDef`

Create a configured task definition for this batch.

**Parameters:**

- `name: str | None` - Task name
- `shield: bool | None` - Shield setting
- `on_error: TaskErrorHandler | None` - Error handler

**Returns:** `_PartialTaskDef` with a `schedule()` method

### Usage

`TasksBatch` is used internally for `after_route` and `after_response` scheduling:

```python
# tasks.after_route is a TasksBatch
tasks.after_route.schedule(cleanup)

# tasks.after_response is a TasksBatch
tasks.after_response.schedule(send_email)
```

## _PartialTaskDef

The `_PartialTaskDef` class represents a task configuration awaiting a function to schedule.

### Definition

```python
@dataclass
class _PartialTaskDef(Generic[P, T]):
    _config: TaskConfig
    _on_schedule: Callable[[Task[P, T]], None]
```

This is an internal class returned by `tasks.task()`. You interact with it via its `schedule()` method:

```python
# tasks.task() returns a _PartialTaskDef
partial = tasks.task(name="my_task", shield=True)

# Call schedule() on it
task = partial.schedule(my_function, arg1, arg2)
```

### Methods

#### `schedule(func, /, *args, **kwargs) -> Task`

Schedule the configured task with the given function and arguments.

## Complete Example

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks, Task, TaskConfig

app = FastAPI()
add_tasks(app)


async def my_task(x: int) -> int:
    return x * 2


@app.post("/task-details")
async def task_details(tasks: Tasks) -> dict:
    # Create a configured task
    task = tasks.task(
        name="double_task",
        shield=True
    ).schedule(my_task, 21)
    
    # Access task details
    return {
        "task_name": task.config.name,
        "function": task.func.__name__,
        "args": task.args,
        "kwargs": task.kwargs,
        "is_shielded": task.config.shielded,
        "has_started": task.started.is_set(),
    }
```

## Type Parameters

The `Task` class is generic over the function signature:

```python
from typing import Callable

# Task for a function: (int, str) -> dict
task: Task[[int, str], dict]

# Task for a function: () -> None
task: Task[[], None]

# Task for a function: (x: int, *, name: str) -> str
task: Task[[int], str]  # Simplified
```

## See Also

- [Tasks API](tasks.md) - Main Tasks dependency
- [Error Handlers](error_handlers.md) - Error handler reference
- [TaskScheduler](task_scheduler.md) - Internal scheduler details
