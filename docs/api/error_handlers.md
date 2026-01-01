# Error Handlers API Reference

Error handlers allow you to customize behavior when tasks fail.

## Type Definition

```python
from typing import TypeAlias, Callable, Awaitable

TaskErrorHandler: TypeAlias = (
    Callable[["Task[..., Any]", Exception], Any] | 
    Callable[["Task[..., Any]", Exception], Awaitable[Any]]
)
```

An error handler can be either:
- A synchronous function: `(Task, Exception) -> Any`
- An asynchronous function: `(Task, Exception) -> Awaitable[Any]`

## Signature

Both sync and async error handlers have the same signature:

```python
# Async error handler
async def my_error_handler(task: Task, error: Exception) -> None:
    pass

# Sync error handler  
def my_sync_error_handler(task: Task, error: Exception) -> None:
    pass
```

### Parameters

#### `task: Task`

The task object that failed. Provides access to:

- `task.config.name` - Task name (if configured)
- `task.func` - The function that was executed
- `task.args` - Positional arguments
- `task.kwargs` - Keyword arguments
- `task.config.shielded` - Whether task is shielded
- `task.started` - Event indicating if task started

#### `error: Exception`

The exception that was raised by the task.

### Return Value

Return value is ignored. Error handlers are called for side effects (logging, alerting, retrying, etc.).

## Usage

### Basic Error Handler

```python
from fastapi_tasks import Task

async def log_error(task: Task, error: Exception) -> None:
    """Simple error logging"""
    print(f"Task {task.config.name} failed: {error}")


@app.post("/example")
async def example(tasks: Tasks) -> dict:
    tasks.task(on_error=log_error).schedule(my_function)
    return {"status": "ok"}
```

### Accessing Task Details

```python
async def detailed_error_handler(task: Task, error: Exception) -> None:
    """Access all task information"""
    error_info = {
        "task_name": task.config.name,
        "function": task.func.__name__,
        "args": task.args,
        "kwargs": task.kwargs,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "is_shielded": task.config.shielded,
    }
    
    # Log structured error data
    import json
    print(json.dumps(error_info))
```

### Sync Error Handler

```python
def sync_error_handler(task: Task, error: Exception) -> None:
    """Synchronous error handler"""
    # Sync operations only
    with open("errors.log", "a") as f:
        f.write(f"Error in {task.config.name}: {error}\n")
```

## Common Patterns

### Pattern 1: Send to Error Tracking

```python
import sentry_sdk

async def send_to_sentry(task: Task, error: Exception) -> None:
    """Send error to Sentry"""
    with sentry_sdk.push_scope() as scope:
        scope.set_context("task", {
            "name": task.config.name,
            "function": task.func.__name__,
        })
        sentry_sdk.capture_exception(error)
```

### Pattern 2: Retry with Backoff

```python
import asyncio

async def retry_handler(task: Task, error: Exception) -> None:
    """Retry task with exponential backoff"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            await asyncio.sleep(2 ** attempt)
            result = await task()
            print(f"Task succeeded on retry {attempt + 1}")
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Task failed after {max_retries} retries")
                raise
```

### Pattern 3: Conditional Handling

```python
async def smart_error_handler(task: Task, error: Exception) -> None:
    """Handle different errors differently"""
    if isinstance(error, ConnectionError):
        # Retry network errors
        await retry_handler(task, error)
    elif isinstance(error, ValueError):
        # Log validation errors
        await send_to_sentry(task, error)
    else:
        # Alert on unknown errors
        await send_alert(f"Unknown error in {task.config.name}: {error}")
```

### Pattern 4: Fallback Action

```python
async def fallback_handler(task: Task, error: Exception) -> None:
    """Perform fallback action on error"""
    # Try alternative approach
    print(f"Primary task failed, trying fallback")
    
    # Extract original arguments
    if task.func.__name__ == "send_email_primary":
        email = task.args[0] if task.args else task.kwargs.get("email")
        await send_email_backup(email)
```

## Error Handler Behavior

### Execution

Error handlers are called when:
1. A task function raises an exception
2. The exception propagates to the task execution wrapper
3. The error is logged (always happens)
4. The error handler is invoked (if configured)

### Exceptions in Error Handlers

If an error handler itself raises an exception:

```python
async def bad_error_handler(task: Task, error: Exception) -> None:
    raise RuntimeError("Handler failed!")  # This will be logged
```

The exception is logged, but the application continues. Error handlers should be defensive:

```python
async def safe_error_handler(task: Task, error: Exception) -> None:
    """Error handler that doesn't fail"""
    try:
        await send_to_sentry(task, error)
    except Exception as handler_error:
        # Fallback logging
        import logging
        logging.error(f"Error handler failed: {handler_error}")
```

### Async vs Sync

Both async and sync error handlers work with both async and sync tasks:

```python
# Async handler + async task ✓
tasks.task(on_error=async_handler).schedule(async_task)

# Async handler + sync task ✓
tasks.task(on_error=async_handler).schedule(sync_task)

# Sync handler + async task ✓
tasks.task(on_error=sync_handler).schedule(async_task)

# Sync handler + sync task ✓
tasks.task(on_error=sync_handler).schedule(sync_task)
```

## Default Behavior (No Handler)

If no error handler is provided:

```python
tasks.schedule(failing_task)  # No on_error
```

The error is logged using Python's logging module:

```python
logger.exception("Exception occurred in task %r", task)
```

The task stops executing, but other tasks continue normally.

## Multiple Error Handlers

You cannot assign multiple error handlers to a single task. If you need multiple actions:

```python
async def combined_error_handler(task: Task, error: Exception) -> None:
    """Combine multiple error handling actions"""
    # Action 1: Log
    await log_error(task, error)
    
    # Action 2: Send to Sentry
    await send_to_sentry(task, error)
    
    # Action 3: Alert
    await send_alert(task, error)
```

## Testing Error Handlers

```python
import pytest

async def test_error_handler():
    """Test that error handler is called"""
    error_handled = False
    
    async def test_handler(task: Task, error: Exception) -> None:
        nonlocal error_handled
        error_handled = True
        assert isinstance(error, ValueError)
    
    async def failing_task() -> None:
        raise ValueError("Test error")
    
    # Create task with error handler
    # (in actual code, within an endpoint)
    task = Task(
        func=failing_task,
        args=(),
        kwargs={},
        config=TaskConfig(on_error=test_handler)
    )
    
    # Execute task
    await task()
    
    # Verify handler was called
    assert error_handled
```

## Best Practices

1. **Always log errors** - Even if you handle them, log for debugging
2. **Be defensive** - Error handlers shouldn't raise exceptions
3. **Use structured logging** - Makes analysis easier
4. **Don't swallow errors** - At minimum, log them
5. **Consider retries carefully** - Not all errors should be retried
6. **Alert on critical failures** - Don't wait to discover problems
7. **Test error handlers** - Ensure they work as expected

## See Also

- [Error Handling Tutorial](../learn/tutorial_advanced/error_handling.md) - Complete error handling guide
- [Tasks API](tasks.md) - Tasks dependency
- [TaskConfig](task_config.md) - Task configuration
