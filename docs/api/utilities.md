# Utilities API Reference

This page documents utility functions and classes in `fastapi-tasks`.

## add_tasks()

The `add_tasks()` function initializes background task support for your FastAPI application.

### Signature

```python
def add_tasks(
    app: FastAPI,
    *,
    config: TaskConfig | None = None,
) -> None
```

### Parameters

- `app: FastAPI` - The FastAPI application instance
- `config: TaskConfig | None` - Optional global configuration for all tasks (default: `None`)

### Returns

`None`

### Description

This function must be called on your FastAPI app instance before you can use the `Tasks` dependency. It sets up:

1. A lifespan context manager that creates an `anyio` task group
2. Integration with FastAPI's application lifecycle
3. Proper cleanup of tasks on shutdown
4. Optional global configuration that applies to all tasks

### Basic Usage

```python
from fastapi import FastAPI
from fastapi_tasks import add_tasks

app = FastAPI()
add_tasks(app)  # Must be called before endpoints use Tasks
```

### With Global Configuration

You can provide a `TaskConfig` to set defaults for all tasks in your application:

```python
from fastapi import FastAPI
from fastapi_tasks import add_tasks, TaskConfig

# Define global error handler
async def global_error_handler(task, error):
    print(f"Task failed: {error}")

# Global configuration for all tasks
global_config = TaskConfig(
    shield=True,  # All tasks shielded by default
    on_error=global_error_handler
)

app = FastAPI()
add_tasks(app, config=global_config)


# Now all tasks inherit the global config
@app.post("/task")
async def endpoint(tasks: Tasks) -> dict:
    # This task is automatically shielded and uses global_error_handler
    tasks.schedule(my_task)
    
    # You can still override the global config
    tasks.task(shield=False).schedule(other_task)
    
    return {"status": "ok"}
```

### What It Does

Internally, `add_tasks()` merges a lifespan context into your application that:

1. Creates an `anyio` task group for managing background tasks
2. Stores the task group in the application state
3. Optionally stores a global `TaskConfig` in the application state
4. Ensures proper cleanup on shutdown

```python
@asynccontextmanager
async def _lifespan(_: FastAPI, /, config: TaskConfig) -> AsyncIterator[dict[str, Any]]:
    async with anyio.create_task_group() as tg:
        yield {
            "fastapi_tasks_tg": tg,
            "fastapi_tasks_config": config,
        }
        tg.cancel_scope.cancel()
```

This ensures:
- A task group exists for the application lifetime
- A global config (if provided) is available to all tasks
- Tasks are properly cancelled on shutdown (unless shielded)
- The task group and config are accessible via request state

### Error: Missing add_tasks()

If you forget to call `add_tasks()`, you'll get this error:

```python
FastAPITasksUninitializedAppError: TaskGroup dependency used outside of lifespan context. 
Ensure that 'add_tasks(app)' has been called on the FastAPI app instance.
```

### Multiple FastAPI Apps

Call `add_tasks()` for each FastAPI application instance:

```python
app1 = FastAPI()
app2 = FastAPI()

add_tasks(app1)
add_tasks(app2)
```

### Compatibility with Other Lifespans

`add_tasks()` merges with existing lifespan contexts:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def my_lifespan(app: FastAPI):
    print("App starting")
    yield
    print("App stopping")

app = FastAPI(lifespan=my_lifespan)
add_tasks(app)  # Works with existing lifespan
```

## always_async_call()

Internal utility function that runs both sync and async callables, ensuring async execution.

### Signature

```python
async def always_async_call(
    func: Callable[P, T],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> T
```

### Parameters

- `func: Callable[P, T]` - Function to call (sync or async)
- `*args: P.args` - Positional arguments
- `**kwargs: P.kwargs` - Keyword arguments

### Returns

The return value of the function.

### Description

This function checks if `func` is async:
- If async: calls it with `await`
- If sync: runs it in a thread pool using `starlette.concurrency.run_in_threadpool`

This allows `fastapi-tasks` to handle both sync and async task functions transparently.

### Usage

This is an internal utility. You don't typically call it directly:

```python
# Internally used like:
result = await always_async_call(task.func, *task.args, **task.kwargs)
```

## Exceptions

### FastAPITasksError

Base exception for all `fastapi-tasks` errors.

```python
class FastAPITasksError(Exception):
    pass
```

### FastAPITasksUninitializedAppError

Raised when trying to use `Tasks` dependency without calling `add_tasks(app)`.

```python
class FastAPITasksUninitializedAppError(FastAPITasksError):
    pass
```

**When it's raised:**

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks

app = FastAPI()
# Forgot to call add_tasks(app)!

@app.post("/task")
async def endpoint(tasks: Tasks) -> dict:
    # This will raise FastAPITasksUninitializedAppError
    tasks.schedule(my_task)
    return {}
```

**How to fix:**

```python
app = FastAPI()
add_tasks(app)  # Add this line

@app.post("/task")
async def endpoint(tasks: Tasks) -> dict:
    tasks.schedule(my_task)  # Now works
    return {}
```

## Complete Setup Example

Here's a complete application setup with global configuration:

```python
from fastapi import FastAPI, HTTPException
from fastapi_tasks import Tasks, add_tasks, TaskConfig, Task, FastAPITasksError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)


# Define global error handler
async def global_error_handler(task: Task, error: Exception) -> None:
    logging.error(f"Task {task.config.name} failed: {error}", exc_info=error)


# Global configuration for all tasks
global_config = TaskConfig(
    shield=False,  # Allow fast shutdown
    on_error=global_error_handler  # Log all errors
)


# Create app
app = FastAPI(title="My App with Background Tasks")

# Initialize tasks support with global config
add_tasks(app, config=global_config)


# Define tasks
async def my_background_task(data: str) -> None:
    logging.info(f"Processing: {data}")


# Define endpoints
@app.post("/process")
async def process_data(data: str, tasks: Tasks) -> dict:
    try:
        # Uses global config (shield=False, on_error=global_error_handler)
        tasks.schedule(my_background_task, data)
        return {"status": "processing", "data": data}
    except FastAPITasksError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/critical")
async def critical_task(data: str, tasks: Tasks) -> dict:
    # Override global shield setting for critical tasks
    tasks.task(shield=True, name="critical_task").schedule(
        my_background_task, data
    )
    return {"status": "processing"}


# Health check
@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Best Practices

### 1. Call add_tasks() Early

```python
# Good: Call immediately after creating app
app = FastAPI()
add_tasks(app)

# Bad: Call after defining endpoints
app = FastAPI()
@app.post("/endpoint")
async def endpoint(tasks: Tasks):
    pass
add_tasks(app)  # Might work, but bad practice
```

### 2. One Call Per App

```python
# Good: Call once
app = FastAPI()
add_tasks(app)

# Bad: Multiple calls (unnecessary, but harmless)
app = FastAPI()
add_tasks(app)
add_tasks(app)  # Redundant
```

### 3. Handle Initialization Errors

```python
from fastapi_tasks import FastAPITasksUninitializedAppError

@app.post("/task")
async def endpoint(tasks: Tasks) -> dict:
    try:
        tasks.schedule(my_task)
    except FastAPITasksUninitializedAppError:
        raise HTTPException(
            status_code=500,
            detail="Task system not initialized"
        )
    return {"status": "ok"}
```

## See Also

- [First Steps Tutorial](../learn/tutorial_user_guide/first_steps.md) - Getting started guide
- [Tasks API](tasks.md) - Tasks dependency reference
- [TaskScheduler](task_scheduler.md) - Internal scheduler details
