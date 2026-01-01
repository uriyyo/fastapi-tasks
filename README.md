<h1 align="center">
fastapi-tasks
</h1>

<div align="center">
<img alt="license" src="https://img.shields.io/badge/License-MIT-lightgrey">
<img alt="test" src="https://github.com/uriyyo/fastapi-tasks/workflows/Test/badge.svg">
<a href="https://pypi.org/project/fastapi-tasks"><img alt="pypi" src="https://img.shields.io/pypi/v/fastapi-tasks"></a>
<img alt="python" src="https://img.shields.io/pypi/pyversions/fastapi-tasks">
</div>

## Introduction

`fastapi-tasks` is a Python library for managing background tasks in FastAPI applications with precise timing control.

Unlike FastAPI's built-in `BackgroundTasks` which only runs tasks after the response is sent, `fastapi-tasks` gives you
fine-grained control over **when** your background tasks execute:

- **Immediately** - Task starts right away, concurrently with your endpoint
- **After Route** - Task runs after your endpoint function completes, but before the response is sent
- **After Response** - Task runs after the response is sent to the client

Features:

* **Precise timing control** - Choose exactly when your background tasks run
* **Task shielding** - Protect critical tasks from cancellation during shutdown
* **Error handling** - Custom error handlers for graceful failure recovery
* **Full async support** - Works with both sync and async task functions
* **Type safe** - Full type hints and generic support
* **Lightweight** - Built on top of `anyio` with minimal dependencies

---

## Installation

```bash
pip install fastapi-tasks
```

## Quickstart

All you need to do is call `add_tasks(app)` and use the `Tasks` dependency in your endpoints.

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)  # important! add tasks support to your app


async def send_welcome_email(email: str) -> None:
    # your email sending logic here
    ...


async def log_analytics(event: str, user_id: int) -> None:
    # your analytics logic here
    ...


@app.post("/users")
async def create_user(email: str, tasks: Tasks) -> dict:
    user_id = 1  # create user in database
    
    # Schedule tasks with different timing
    tasks.schedule(send_welcome_email, email)  # starts immediately
    tasks.after_route.schedule(log_analytics, "user_created", user_id)  # after endpoint
    tasks.after_response.schedule(log_analytics, "response_sent", user_id)  # after response
    
    return {"user_id": user_id}
```

## Timing Modes

| Mode | When it runs | Use case |
|------|--------------|----------|
| `tasks.schedule()` | Immediately (concurrent) | Fire-and-forget, non-blocking operations |
| `tasks.after_route.schedule()` | After endpoint returns | Cleanup, logging before response |
| `tasks.after_response.schedule()` | After response sent | Notifications, analytics, emails |

### Timing Visualization

```
Request arrives
    │
    ├─► tasks.schedule() ──────────────────────► Runs immediately (concurrent)
    │
    ▼
Endpoint function executes
    │
    ▼
Endpoint returns
    │
    ├─► tasks.after_route.schedule() ─────────► Runs here
    │
    ▼
Response sent to client
    │
    ├─► tasks.after_response.schedule() ──────► Runs here
    │
    ▼
Request complete
```

## Task Configuration

You can configure tasks with a name, shielding, and custom error handlers:

```python
async def on_task_error(task, exception: Exception) -> None:
    print(f"Task {task.config.name} failed: {exception}")


@app.post("/orders")
async def create_order(order_id: int, tasks: Tasks) -> dict:
    # Configure task with name and error handler
    tasks.task(
        name="process_order",
        shield=True,  # protect from cancellation
        on_error=on_task_error,
    ).schedule(process_order, order_id)
    
    return {"order_id": order_id}
```

### Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `name` | `str \| None` | Task name for logging and debugging |
| `shield` | `bool \| None` | Protect task from cancellation during shutdown |
| `on_error` | `Callable \| None` | Custom error handler for task failures |

## Shielding Critical Tasks

When your application shuts down, running tasks are cancelled. Use `shield=True` to protect critical tasks:

```python
@app.post("/payments")
async def process_payment(payment_id: int, tasks: Tasks) -> dict:
    # This task will complete even if the server is shutting down
    tasks.task(shield=True).schedule(finalize_payment, payment_id)
    
    return {"status": "processing"}
```

## Sync and Async Tasks

`fastapi-tasks` works with both sync and async functions. Sync functions are automatically
run in a thread pool to avoid blocking the event loop:

```python
def sync_task(data: str) -> None:
    # This runs in a thread pool
    time.sleep(1)
    print(f"Processed: {data}")


async def async_task(data: str) -> None:
    # This runs in the event loop
    await asyncio.sleep(1)
    print(f"Processed: {data}")


@app.post("/process")
async def process(tasks: Tasks) -> dict:
    tasks.schedule(sync_task, "sync data")   # runs in thread pool
    tasks.schedule(async_task, "async data") # runs in event loop
    
    return {"status": "ok"}
```

## Error Handling

By default, task exceptions are logged but don't affect the response. You can provide custom error handlers:

```python
from fastapi_tasks import Task


async def handle_error(task: Task, error: Exception) -> None:
    # Log to your error tracking service
    await sentry_sdk.capture_exception(error)
    
    # Or retry the task, send alerts, etc.


@app.post("/risky")
async def risky_operation(tasks: Tasks) -> dict:
    tasks.task(on_error=handle_error).schedule(might_fail)
    
    return {"status": "started"}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
