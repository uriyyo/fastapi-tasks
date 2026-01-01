# Tasks API Reference

The `Tasks` dependency is the primary interface for scheduling background tasks in `fastapi-tasks`.

## Type Definition

```python
from typing import Annotated
from fastapi import Depends

Tasks = Annotated[
    TasksScheduler,
    Depends(_get_task_scheduler, scope="function"),
]
```

`Tasks` is a type annotation that resolves to a `TasksScheduler` instance via FastAPI dependency injection.

## Usage

Inject `Tasks` into your endpoint functions:

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)

@app.post("/endpoint")
async def my_endpoint(tasks: Tasks) -> dict:
    tasks.schedule(my_task)
    return {"status": "ok"}
```

## TasksScheduler Class

The `TasksScheduler` class provides methods for scheduling and configuring tasks.

### Attributes

#### `after_route: TasksBatch`

A `TasksBatch` instance for scheduling tasks after the endpoint completes but before the response is sent. These tasks are fire-and-forget and don't block the response.

```python
@app.post("/example")
async def example(tasks: Tasks) -> dict:
    tasks.after_route.schedule(cleanup_task)
    return {"status": "ok"}
```

#### `after_response: TasksBatch`

A `TasksBatch` instance for scheduling tasks after the HTTP response has been sent to the client.

```python
@app.post("/example")
async def example(tasks: Tasks) -> dict:
    tasks.after_response.schedule(send_email)
    return {"status": "ok"}
```

### Methods

#### `schedule(func, /, *args, **kwargs) -> Task`

Schedule a task for immediate execution (concurrent with the endpoint).

**Parameters:**

- `func: Callable[P, T]` - The function to execute (can be sync or async)
- `*args: P.args` - Positional arguments to pass to the function
- `**kwargs: P.kwargs` - Keyword arguments to pass to the function

**Returns:**

- `Task[P, T]` - The task object representing the scheduled task

**Example:**

```python
@app.post("/immediate")
async def immediate_task(tasks: Tasks) -> dict:
    task = tasks.schedule(process_data, data_arg, key="value")
    return {"task_started": task.started.is_set()}
```

#### `task(*, name=None, shield=None, on_error=None) -> _PartialTaskDef`

Create a configured task definition that can then be scheduled.

**Parameters:**

- `name: str | None = None` - Optional name for the task (used in logging)
- `shield: bool | None = None` - Whether to protect the task from cancellation
- `on_error: TaskErrorHandler | None = None` - Custom error handler for the task

**Returns:**

- `_PartialTaskDef` - A partial task definition that has a `schedule()` method

**Example:**

```python
@app.post("/configured")
async def configured_task(tasks: Tasks) -> dict:
    tasks.task(
        name="my_task",
        shield=True,
        on_error=my_error_handler
    ).schedule(my_function, arg1, arg2)
    
    return {"status": "ok"}
```

## TasksBatch Class

The `TasksBatch` class is returned by `tasks.after_route` and `tasks.after_response`. It has the same API as `TasksScheduler`.

### Methods

#### `schedule(func, /, *args, **kwargs) -> Task`

Same as `TasksScheduler.schedule()`, but tasks are scheduled for the specific timing mode (after-route or after-response).

#### `task(*, name=None, shield=None, on_error=None) -> _PartialTaskDef`

Same as `TasksScheduler.task()`, for creating configured tasks.

**Example:**

```python
@app.post("/batch-example")
async def batch_example(tasks: Tasks) -> dict:
    # After-route tasks
    tasks.after_route.schedule(task1)
    tasks.after_route.task(name="task2").schedule(task2)
    
    # After-response tasks
    tasks.after_response.schedule(task3)
    tasks.after_response.task(shield=True).schedule(task4)
    
    return {"status": "ok"}
```

## Complete Example

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks, Task

app = FastAPI()
add_tasks(app)


async def my_error_handler(task: Task, error: Exception) -> None:
    print(f"Task {task.config.name} failed: {error}")


async def immediate_task(data: str) -> None:
    print(f"Immediate: {data}")


async def after_route_task(data: str) -> None:
    print(f"After route: {data}")


async def after_response_task(data: str) -> None:
    print(f"After response: {data}")


@app.post("/comprehensive")
async def comprehensive_example(tasks: Tasks) -> dict:
    # Immediate task (no config)
    tasks.schedule(immediate_task, "data1")
    
    # Immediate task (with config)
    tasks.task(
        name="configured_immediate",
        on_error=my_error_handler
    ).schedule(immediate_task, "data2")
    
    # After-route task (no config)
    tasks.after_route.schedule(after_route_task, "data3")
    
    # After-route task (with config)
    tasks.after_route.task(
        name="configured_after_route",
        shield=True
    ).schedule(after_route_task, "data4")
    
    # After-response task (no config)
    tasks.after_response.schedule(after_response_task, "data5")
    
    # After-response task (with config)
    tasks.after_response.task(
        name="configured_after_response",
        on_error=my_error_handler
    ).schedule(after_response_task, "data6")
    
    return {"status": "ok"}
```

## Type Hints

The `Tasks` API is fully type-hinted for IDE support:

```python
from typing import Any
from fastapi_tasks import Tasks

async def my_function(x: int, y: str) -> dict:
    return {"x": x, "y": y}

@app.post("/typed")
async def typed_endpoint(tasks: Tasks) -> dict:
    # IDE knows the parameter types
    task = tasks.schedule(my_function, 42, "hello")
    
    # task is of type Task[..., dict]
    return {"status": "ok"}
```

## See Also

- [TaskConfig](task_config.md) - Task configuration options
- [TaskScheduler](task_scheduler.md) - Internal scheduler details
- [Error Handlers](error_handlers.md) - Error handler reference
- [Utilities](utilities.md) - `add_tasks()` and other utilities
