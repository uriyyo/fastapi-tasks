# Error Handling

Robust error handling is crucial for production applications. This tutorial covers advanced error handling patterns
for background tasks in `fastapi-tasks`.

## Default Error Behavior

By default, when a task fails:

1. The exception is logged
2. The error handler (if provided) is called
3. The task stops executing
4. Other tasks continue running normally

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)


async def failing_task() -> None:
    raise ValueError("Something went wrong!")


@app.post("/fail")
async def failing_endpoint(tasks: Tasks) -> dict:
    # This task will fail, but the endpoint returns successfully
    tasks.schedule(failing_task)
    
    return {"status": "ok"}
```

The client receives `{"status": "ok"}` immediately, and the error is logged on the server.

## Custom Error Handlers

Define custom error handlers to control failure behavior:

```python
from fastapi_tasks import Task


async def my_error_handler(task: Task, error: Exception) -> None:
    """Called when a task fails"""
    print(f"Task failed: {task.config.name}")
    print(f"Error: {error}")
    print(f"Error type: {type(error).__name__}")


async def risky_task() -> None:
    raise ValueError("Oops!")


@app.post("/custom-error")
async def custom_error_endpoint(tasks: Tasks) -> dict:
    tasks.task(
        name="risky_operation",
        on_error=my_error_handler
    ).schedule(risky_task)
    
    return {"status": "ok"}
```

## Error Handler Patterns

### Pattern 1: Logging to External Service

Send errors to a monitoring service like Sentry:

```python
import sentry_sdk


async def send_to_sentry(task: Task, error: Exception) -> None:
    """Send task errors to Sentry"""
    with sentry_sdk.push_scope() as scope:
        # Add task context
        scope.set_context("task", {
            "name": task.config.name,
            "function": task.func.__name__,
            "args": str(task.args),
            "kwargs": str(task.kwargs),
        })
        
        # Capture the exception
        sentry_sdk.capture_exception(error)


@app.post("/monitored")
async def monitored_endpoint(tasks: Tasks) -> dict:
    tasks.task(
        name="monitored_task",
        on_error=send_to_sentry
    ).schedule(potentially_failing_task)
    
    return {"status": "ok"}
```

### Pattern 2: Retry Logic

Implement automatic retries with exponential backoff:

```python
import asyncio
from typing import Any


async def retry_handler(
    task: Task,
    error: Exception,
    max_retries: int = 3,
    base_delay: float = 1.0
) -> None:
    """Retry the task with exponential backoff"""
    
    for attempt in range(max_retries):
        try:
            # Exponential backoff: 1s, 2s, 4s, ...
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)
            
            print(f"Retrying {task.config.name} (attempt {attempt + 1}/{max_retries})")
            
            # Retry the task
            result = await task()
            
            print(f"Task {task.config.name} succeeded on retry {attempt + 1}")
            return result
            
        except Exception as e:
            if attempt == max_retries - 1:
                # Final attempt failed
                print(f"Task {task.config.name} failed after {max_retries} retries")
                await send_to_sentry(task, e)
                raise
            
            print(f"Retry {attempt + 1} failed: {e}")


async def flaky_task(success_rate: float = 0.3) -> None:
    """Simulates a task that fails randomly"""
    import random
    if random.random() > success_rate:
        raise ValueError("Random failure")
    print("Task succeeded!")


@app.post("/retry")
async def retry_endpoint(tasks: Tasks) -> dict:
    tasks.task(
        name="flaky_task",
        on_error=retry_handler
    ).schedule(flaky_task)
    
    return {"status": "ok"}
```

### Pattern 3: Fallback Actions

Perform alternative actions when a task fails:

```python
async def send_email_primary(to: str, subject: str, body: str) -> None:
    # Primary email service
    raise ConnectionError("Primary service unavailable")


async def send_email_fallback(to: str, subject: str, body: str) -> None:
    # Backup email service
    print(f"Sending via fallback service to {to}")


async def email_error_handler(task: Task, error: Exception) -> None:
    """Use fallback email service if primary fails"""
    if isinstance(error, ConnectionError):
        print("Primary email service failed, using fallback")
        
        # Extract original arguments
        to = task.kwargs.get("to") or task.args[0]
        subject = task.kwargs.get("subject") or task.args[1]
        body = task.kwargs.get("body") or task.args[2]
        
        # Try fallback service
        await send_email_fallback(to, subject, body)
    else:
        # For other errors, just log
        print(f"Email task failed: {error}")


@app.post("/email-fallback")
async def email_endpoint(email: str, tasks: Tasks) -> dict:
    tasks.task(
        name="send_email",
        on_error=email_error_handler
    ).schedule(
        send_email_primary,
        to=email,
        subject="Welcome",
        body="Thanks for signing up!"
    )
    
    return {"status": "ok"}
```

### Pattern 4: Error Notification

Alert administrators when critical tasks fail:

```python
import httpx


async def send_slack_alert(message: str) -> None:
    """Send alert to Slack"""
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
            json={"text": message}
        )


async def critical_error_handler(task: Task, error: Exception) -> None:
    """Alert on-call engineer when critical task fails"""
    alert_message = (
        f"🚨 Critical Task Failed!\n"
        f"Task: {task.config.name}\n"
        f"Function: {task.func.__name__}\n"
        f"Error: {type(error).__name__}: {error}\n"
        f"Arguments: {task.args}\n"
        f"Keyword Arguments: {task.kwargs}"
    )
    
    # Send to Slack
    await send_slack_alert(alert_message)
    
    # Also send to error tracking
    await send_to_sentry(task, error)


@app.post("/critical")
async def critical_endpoint(tasks: Tasks) -> dict:
    tasks.task(
        name="critical_payment_processing",
        shield=True,
        on_error=critical_error_handler
    ).schedule(process_payment, payment_id=12345)
    
    return {"status": "processing"}
```

## Handling Specific Error Types

Handle different errors differently:

```python
async def smart_error_handler(task: Task, error: Exception) -> None:
    """Handle different error types appropriately"""
    
    if isinstance(error, ConnectionError):
        # Network errors: retry
        print("Network error, will retry...")
        await retry_handler(task, error, max_retries=5)
        
    elif isinstance(error, ValueError):
        # Validation errors: log and alert
        print(f"Validation error in task {task.config.name}: {error}")
        await send_slack_alert(f"Validation error: {error}")
        
    elif isinstance(error, PermissionError):
        # Permission errors: critical alert
        await send_slack_alert(f"🚨 Permission error in {task.config.name}!")
        await send_to_sentry(task, error)
        
    else:
        # Unknown errors: log to Sentry
        print(f"Unknown error: {error}")
        await send_to_sentry(task, error)


@app.post("/smart-handling")
async def smart_handling_endpoint(tasks: Tasks) -> dict:
    tasks.task(
        name="smart_task",
        on_error=smart_error_handler
    ).schedule(complex_operation)
    
    return {"status": "ok"}
```

## Global Error Handler

Create a reusable error handler for all tasks:

```python
import logging
from typing import Dict, Type, Callable, Awaitable


logger = logging.getLogger(__name__)


class ErrorHandlerRegistry:
    """Registry for different error handlers based on error type"""
    
    def __init__(self):
        self.handlers: Dict[Type[Exception], Callable] = {}
        self.default_handler: Callable | None = None
    
    def register(self, error_type: Type[Exception], handler: Callable) -> None:
        """Register a handler for a specific error type"""
        self.handlers[error_type] = handler
    
    def set_default(self, handler: Callable) -> None:
        """Set the default handler for unregistered error types"""
        self.default_handler = handler
    
    async def handle(self, task: Task, error: Exception) -> None:
        """Route error to appropriate handler"""
        error_type = type(error)
        
        # Find handler for this error type
        handler = self.handlers.get(error_type, self.default_handler)
        
        if handler:
            await handler(task, error)
        else:
            logger.error(f"Unhandled error in task {task.config.name}: {error}")


# Create global registry
error_registry = ErrorHandlerRegistry()


# Register handlers for specific error types
async def handle_connection_error(task: Task, error: ConnectionError) -> None:
    logger.warning(f"Connection error in {task.config.name}, will retry")
    await retry_handler(task, error)


async def handle_validation_error(task: Task, error: ValueError) -> None:
    logger.error(f"Validation error in {task.config.name}: {error}")
    await send_to_sentry(task, error)


async def handle_default(task: Task, error: Exception) -> None:
    logger.exception(f"Error in task {task.config.name}")
    await send_to_sentry(task, error)


error_registry.register(ConnectionError, handle_connection_error)
error_registry.register(ValueError, handle_validation_error)
error_registry.set_default(handle_default)


@app.post("/global-handler")
async def global_handler_endpoint(tasks: Tasks) -> dict:
    # All tasks use the global error handler
    tasks.task(
        name="task1",
        on_error=error_registry.handle
    ).schedule(operation1)
    
    tasks.task(
        name="task2",
        on_error=error_registry.handle
    ).schedule(operation2)
    
    return {"status": "ok"}
```

## Error Handling with Different Timing Modes

Error handlers work with all timing modes:

```python
async def immediate_error_handler(task: Task, error: Exception) -> None:
    print(f"Immediate task {task.config.name} failed: {error}")


async def after_route_error_handler(task: Task, error: Exception) -> None:
    print(f"After-route task {task.config.name} failed: {error}")
    # This is serious - task failed before response was sent
    await send_slack_alert(f"After-route task failed: {error}")


async def after_response_error_handler(task: Task, error: Exception) -> None:
    print(f"After-response task {task.config.name} failed: {error}")


@app.post("/timing-errors")
async def timing_errors_endpoint(tasks: Tasks) -> dict:
    # Immediate task with error handler
    tasks.task(
        name="immediate",
        on_error=immediate_error_handler
    ).schedule(task1)
    
    # After-route task with error handler
    tasks.after_route.task(
        name="after_route",
        on_error=after_route_error_handler
    ).schedule(task2)
    
    # After-response task with error handler
    tasks.after_response.task(
        name="after_response",
        on_error=after_response_error_handler
    ).schedule(task3)
    
    return {"status": "ok"}
```

## Structured Error Logging

Create detailed, structured error logs:

```python
import json
from datetime import datetime


async def structured_error_handler(task: Task, error: Exception) -> None:
    """Create structured error logs for analysis"""
    
    error_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "task": {
            "name": task.config.name,
            "function": task.func.__name__,
            "args": str(task.args),
            "kwargs": str(task.kwargs),
            "shielded": task.config.shielded,
        },
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        },
    }
    
    # Log as JSON for easy parsing
    logger.error(json.dumps(error_data))
    
    # Also send to error tracking
    await send_to_sentry(task, error)


@app.post("/structured-logging")
async def structured_logging_endpoint(tasks: Tasks) -> dict:
    tasks.task(
        name="important_operation",
        on_error=structured_error_handler
    ).schedule(important_task)
    
    return {"status": "ok"}
```

## Testing Error Handlers

How to test your error handlers:

```python
import pytest
from fastapi.testclient import TestClient


async def test_error_handler():
    """Test that error handler is called on failure"""
    error_was_handled = False
    
    async def test_error_handler(task: Task, error: Exception) -> None:
        nonlocal error_was_handled
        error_was_handled = True
        assert isinstance(error, ValueError)
        assert task.config.name == "test_task"
    
    async def failing_task() -> None:
        raise ValueError("Test error")
    
    # In your test endpoint
    @app.post("/test")
    async def test_endpoint(tasks: Tasks) -> dict:
        tasks.task(
            name="test_task",
            on_error=test_error_handler
        ).schedule(failing_task)
        return {"status": "ok"}
    
    # Make request
    client = TestClient(app)
    response = client.post("/test")
    
    # Wait for task to complete
    await asyncio.sleep(0.5)
    
    assert response.status_code == 200
    assert error_was_handled
```

## Best Practices

1. **Always handle critical task errors** - Don't let payment or data corruption errors silently fail
2. **Log all errors** - Even if you handle them, log for debugging
3. **Use structured logging** - Makes analysis easier
4. **Alert on critical failures** - Don't wait to discover problems
5. **Implement retries for transient failures** - Network errors often resolve themselves
6. **Don't swallow errors silently** - Always log or alert
7. **Test error handlers** - Ensure they work as expected

## Common Pitfalls

### Pitfall 1: Error Handler That Raises

```python
# BAD: Error handler that raises
async def bad_error_handler(task: Task, error: Exception) -> None:
    raise RuntimeError("Error handler failed!")  # Don't do this!


# GOOD: Error handler that catches its own errors
async def good_error_handler(task: Task, error: Exception) -> None:
    try:
        await send_to_sentry(task, error)
    except Exception as e:
        # Fallback: at least log it
        logger.exception(f"Error handler failed: {e}")
```

### Pitfall 2: Forgetting to Await Async Calls

```python
# BAD: Not awaiting async function
async def bad_handler(task: Task, error: Exception) -> None:
    send_to_sentry(task, error)  # Missing await!


# GOOD: Properly awaiting
async def good_handler(task: Task, error: Exception) -> None:
    await send_to_sentry(task, error)
```

### Pitfall 3: Ignoring Error Types

```python
# BAD: Treating all errors the same
async def generic_handler(task: Task, error: Exception) -> None:
    await retry_handler(task, error)  # Don't retry validation errors!


# GOOD: Handle different errors appropriately
async def specific_handler(task: Task, error: Exception) -> None:
    if isinstance(error, ConnectionError):
        await retry_handler(task, error)
    else:
        await log_error(task, error)
```

## Next Steps

- [Task Shielding](task_shielding.md) - Protect critical tasks from cancellation
- [Real World Examples](real_world_examples.md) - See complete error handling in production scenarios
- [API Reference: Error Handlers](../../api/error_handlers.md) - Complete error handler API documentation
