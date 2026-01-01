# Frequently Asked Questions

## General Questions

### What is the difference between `fastapi-tasks` and FastAPI's `BackgroundTasks`?

FastAPI's built-in `BackgroundTasks` only runs tasks **after the response is sent**. `fastapi-tasks` provides three timing modes:

| Feature | FastAPI BackgroundTasks | fastapi-tasks |
|---------|------------------------|---------------|
| Immediate execution | ❌ | ✅ `tasks.schedule()` |
| After endpoint, before response | ❌ | ✅ `tasks.after_route.schedule()` |
| After response | ✅ | ✅ `tasks.after_response.schedule()` |
| Task shielding | ❌ | ✅ `shield=True` |
| Custom error handlers | ❌ | ✅ `on_error=handler` |
| Task naming | ❌ | ✅ `name="my_task"` |

**When to use FastAPI's BackgroundTasks:**
- Simple use case: tasks always run after response
- No need for error handling or shielding
- Minimal dependencies

**When to use fastapi-tasks:**
- Need precise timing control
- Critical tasks that must complete (payments, etc.)
- Complex error handling requirements
- Tasks that should start immediately

### When should I use each timing mode?

Use this decision tree:

```
Does the task affect the response data?
├─ YES → Run in endpoint (not background)
└─ NO → Continue...

should be scheduled before client receives response?
├─ YES → Use tasks.after_route.schedule()
└─ NO → Continue...

Should start as early as possible?
├─ YES → Use tasks.schedule() (immediate)
└─ NO → Use tasks.after_response.schedule()
```

**Examples:**

```python
# Immediate: Start processing ASAP
tasks.schedule(process_large_file, file_path)

# After route: Log before responding
tasks.after_route.schedule(audit_log, user_id, action)

# After response: Send email notification
tasks.after_response.schedule(send_confirmation_email, email)
```

### How many tasks can I schedule concurrently?

There's no hard limit, but consider:

**For async tasks:**
- Hundreds or thousands are fine
- Limited by memory and I/O resources

**For sync tasks:**
- Limited by thread pool size (default: typically 40 threads)
- Each sync task uses one thread

**Best practices:**
```python
# Good: Reasonable number
for user in users[:100]:
    tasks.schedule(notify_user, user.id)

# Risky: Too many at once
for user in all_users:  # 1 million users!
    tasks.schedule(notify_user, user.id)

# Better: Batch or queue
tasks.schedule(notify_users_batch, [u.id for u in all_users])
```

## Error Handling

### What happens when a task fails?

By default:
1. The exception is logged
2. If `on_error` is provided, it's called
3. The task stops
4. Other tasks continue normally
5. The endpoint response is unaffected

```python
async def my_task() -> None:
    raise ValueError("Oops!")

@app.post("/endpoint")
async def endpoint(tasks: Tasks) -> dict:
    tasks.schedule(my_task)  # Will fail
    return {"status": "ok"}  # Still returns successfully
```

### How do I retry failed tasks?

Implement retry logic in your error handler:

```python
import asyncio

async def retry_handler(task: Task, error: Exception) -> None:
    """Retry up to 3 times with exponential backoff"""
    for attempt in range(3):
        try:
            await asyncio.sleep(2 ** attempt)
            await task()
            return
        except Exception:
            if attempt == 2:  # Last attempt
                logger.error(f"Task failed after 3 retries")
                raise

tasks.task(on_error=retry_handler).schedule(flaky_operation)
```

### Can I have a global error handler for all tasks?

Yes, create a reusable error handler:

```python
async def global_error_handler(task: Task, error: Exception) -> None:
    """Handle all task errors"""
    # Log to Sentry
    sentry_sdk.capture_exception(error)
    
    # Alert if critical
    if task.config.shielded:
        await send_alert(f"Critical task failed: {task.config.name}")

# Use it for all tasks
tasks.task(on_error=global_error_handler).schedule(task1)
tasks.task(on_error=global_error_handler).schedule(task2)
```

## Task Shielding

### What exactly does shielding do?

Shielding protects tasks from cancellation when the server shuts down:

**Without shielding:**
```python
tasks.schedule(send_email)
# Server shutdown → task is cancelled → email not sent
```

**With shielding:**
```python
tasks.task(shield=True).schedule(finalize_payment)
# Server shutdown → task completes → payment processed
```

### Should I shield all my tasks?

**No!** Only shield truly critical operations:

```python
# Shield: Payment must complete
tasks.task(shield=True).schedule(charge_card, ...)

# Don't shield: Email can be retried
tasks.schedule(send_email, ...)

# Don't shield: Analytics can be lost
tasks.schedule(track_event, ...)
```

Over-shielding delays server shutdown unnecessarily.

### What happens during shutdown with shielded tasks?

1. Server receives shutdown signal
2. No new requests accepted
3. Non-shielded tasks are cancelled
4. Shielded tasks continue running
5. Server waits for shielded tasks to complete
6. Server shuts down

## Performance

### Do tasks block my endpoint?

**Immediate tasks (`tasks.schedule()`):**
- Start immediately
- Run concurrently with endpoint
- Don't block the response

**After-route tasks (`tasks.after_route.schedule()`):**
- Scheduled after endpoint returns, before response sent
- Minimal scheduling overhead
- Fire-and-forget (don't block response)

**After-response tasks (`tasks.after_response.schedule()`):**
- Scheduled after response sent
- Zero impact on response time

### How can I optimize task performance?

**1. Use async for I/O operations:**
```python
# Good: Async HTTP client
async def send_webhook(url: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(url)

# Slow: Sync HTTP client
def send_webhook_sync(url: str) -> None:
    import requests
    requests.post(url)  # Blocks thread pool
```

**2. Batch similar operations:**
```python
# Good: Batch notifications
async def notify_users(user_ids: list[int]) -> None:
    for user_id in user_ids:
        await send_notification(user_id)

tasks.schedule(notify_users, [1, 2, 3, 4, 5])

# Less efficient: Individual tasks
for user_id in [1, 2, 3, 4, 5]:
    tasks.schedule(send_notification, user_id)
```

**3. Keep after-route tasks fast:**
```python
# Good: Quick database insert
tasks.after_route.schedule(log_event, event_data)

# Bad: Slow external API call
tasks.after_route.schedule(call_slow_api, data)  # Use after_response!
```

## Advanced Usage

### Can I schedule tasks from within tasks?

No, tasks don't have access to the `Tasks` dependency. Instead:

**Option 1: Schedule all tasks upfront:**
```python
@app.post("/process")
async def process(tasks: Tasks) -> dict:
    tasks.schedule(task1)
    tasks.schedule(task2)  # Both scheduled from endpoint
    return {"status": "ok"}
```

**Option 2: Use a task queue:**
For complex workflows, use a proper task queue like Celery or RQ.

### How do I test endpoints with background tasks?

**Option 1: Wait for tasks to complete:**
```python
import anyio
from fastapi.testclient import TestClient

def test_endpoint():
    response = client.post("/endpoint")
    
    # Wait for tasks to complete
    anyio.sleep(1)
    
    # Verify task side effects
    assert email_was_sent()
```

**Option 2: Mock the tasks:**
```python
from unittest.mock import Mock

def test_endpoint(monkeypatch):
    mock_schedule = Mock()
    monkeypatch.setattr("my_module.tasks.schedule", mock_schedule)
    
    response = client.post("/endpoint")
    
    # Verify task was scheduled
    mock_schedule.assert_called_once()
```

### Does this work with other ASGI frameworks?

`fastapi-tasks` is specifically designed for FastAPI. For other frameworks:

- **Starlette**: Could be adapted (FastAPI is built on Starlette)
- **Django**: Use Django's built-in task queue or Celery
- **Flask**: Use Flask-Executor or Celery

### Can I use this with streaming responses?

Yes, but be careful with timing:

```python
from fastapi.responses import StreamingResponse

@app.get("/stream")
async def stream_data(tasks: Tasks):
    # Immediate task: works
    tasks.schedule(log_stream_start)
    
    # After-route: scheduled after generator is created, before streaming starts
    tasks.after_route.schedule(prepare_stream)
    
    # After-response: scheduled after streaming completes
    tasks.after_response.schedule(log_stream_end)
    
    async def generate():
        for i in range(10):
            yield f"data: {i}\n"
    
    return StreamingResponse(generate())
```

### How do I handle database sessions in tasks?

Create a new session in the task:

```python
async def update_database(user_id: int) -> None:
    # Create new database session
    async with get_db_session() as session:
        await session.execute(
            "UPDATE users SET last_active = NOW() WHERE id = ?",
            user_id
        )
        await session.commit()

@app.post("/activity")
async def log_activity(user_id: int, tasks: Tasks) -> dict:
    # Don't pass database session to task
    tasks.schedule(update_database, user_id)
    return {"status": "ok"}
```

Don't pass database sessions from the endpoint to tasks—they may be closed.

## Troubleshooting

### Error: "FastAPITasksUninitializedAppError"

**Cause:** Forgot to call `add_tasks(app)`

**Solution:**
```python
from fastapi import FastAPI
from fastapi_tasks import add_tasks

app = FastAPI()
add_tasks(app)  # Add this line
```

### Tasks aren't running

**Check:**
1. Did you call `add_tasks(app)`?
2. Are you using the `Tasks` dependency correctly?
3. Is the task function raising an exception? (Check logs)
4. For after-route/after-response: Is the endpoint returning normally?

**Debug:**
```python
@app.post("/debug")
async def debug_endpoint(tasks: Tasks) -> dict:
    task = tasks.schedule(my_task)
    
    # Check if task started
    await anyio.sleep(0.1)
    print(f"Task started: {task.started.is_set()}")
    
    return {"status": "ok"}
```

### Server won't shut down

**Cause:** Too many shielded tasks

**Solution:** Review your shielding:
```python
# Only shield critical operations
tasks.task(shield=True).schedule(critical_task)

# Don't shield everything
tasks.schedule(non_critical_task)  # Remove shield=True
```

## Still Have Questions?

- Check the [tutorials](../learn/tutorial_user_guide/first_steps.md)
- Read the [API reference](../api/tasks.md)
- Open an issue on [GitHub](https://github.com/uriyyo/fastapi-tasks)
