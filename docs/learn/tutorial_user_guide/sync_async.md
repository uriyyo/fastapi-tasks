# Sync and Async Tasks

`fastapi-tasks` seamlessly handles both synchronous (sync) and asynchronous (async) task functions.
This tutorial explains how each type works and when to use them.

## The Basics

You can schedule both async and sync functions as tasks:

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks
import time
import asyncio

app = FastAPI()
add_tasks(app)


# Async task
async def async_task(data: str) -> None:
    await asyncio.sleep(1)
    print(f"Async: {data}")


# Sync task
def sync_task(data: str) -> None:
    time.sleep(1)
    print(f"Sync: {data}")


@app.post("/tasks")
async def schedule_tasks(tasks: Tasks) -> dict:
    # Both work the same way
    tasks.schedule(async_task, "async data")
    tasks.schedule(sync_task, "sync data")
    
    return {"status": "scheduled"}
```

## How Async Tasks Work

Async tasks run directly in the event loop using `await`:

```python
async def fetch_data_from_api(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()


@app.post("/fetch")
async def fetch_endpoint(url: str, tasks: Tasks) -> dict:
    # This task runs in the event loop
    tasks.schedule(fetch_data_from_api, url)
    
    return {"status": "fetching"}
```

**Advantages of async tasks:**

- Non-blocking I/O operations
- Efficient use of system resources
- Can handle many concurrent operations
- No thread pool overhead

**Best for:**

- Network requests (HTTP, database, etc.)
- File I/O (when using async file operations)
- Any I/O-bound operation with async support

## How Sync Tasks Work

Sync tasks are automatically run in a thread pool to avoid blocking the event loop:

```python
import requests


def fetch_data_sync(url: str) -> dict:
    # This uses the synchronous requests library
    response = requests.get(url)
    return response.json()


@app.post("/fetch-sync")
async def fetch_sync_endpoint(url: str, tasks: Tasks) -> dict:
    # This task runs in a thread pool
    tasks.schedule(fetch_data_sync, url)
    
    return {"status": "fetching"}
```

Internally, `fastapi-tasks` uses Starlette's `run_in_threadpool` to execute sync functions in a thread pool,
preventing them from blocking the main event loop.

**Advantages of sync tasks:**

- Use existing synchronous libraries
- Simpler code (no async/await)
- Compatible with thread-safe code

**Best for:**

- Using libraries without async support
- CPU-bound operations (though see caveats below)
- Legacy code integration

!!! warning "Thread Pool Limitations"
    Thread pools have overhead and limited concurrency.
    Prefer async tasks when possible, especially for I/O operations.

## Choosing Between Sync and Async

### Use Async When:

1. **The library supports async** - Most modern HTTP clients, database drivers, etc.
2. **You need high concurrency** - Async can handle thousands of concurrent tasks
3. **I/O-bound operations** - Network calls, file I/O, database queries

```python
# Good: Async for HTTP requests
async def notify_webhook(url: str, data: dict) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(url, json=data)


# Good: Async for database operations
async def save_to_db(data: dict) -> None:
    async with get_async_session() as session:
        await session.execute(insert(Table).values(data))
```

### Use Sync When:

1. **The library is sync-only** - No async version available
2. **Legacy code** - Existing synchronous code you can't easily convert
3. **Simple operations** - Quick operations where async overhead isn't worth it

```python
# Good: Sync for sync-only library
def process_image(path: str) -> None:
    from PIL import Image  # Synchronous library
    img = Image.open(path)
    img.thumbnail((200, 200))
    img.save(f"{path}.thumb.jpg")


# Good: Sync for simple operations
def log_to_file(message: str) -> None:
    with open("log.txt", "a") as f:
        f.write(f"{message}\n")
```

## CPU-Bound Operations

For CPU-intensive tasks, both async and sync have limitations:

### Problem with CPU-Bound Tasks

```python
def cpu_intensive_task(n: int) -> int:
    # This blocks the thread
    result = 0
    for i in range(n):
        result += i ** 2
    return result


@app.post("/compute")
async def compute(tasks: Tasks) -> dict:
    # This runs in a thread, but still blocks that thread
    tasks.schedule(cpu_intensive_task, 1_000_000)
    return {"status": "computing"}
```

!!! warning "CPU-Bound Tasks"
    For truly CPU-intensive work, consider using a dedicated task queue like Celery, 
    or process-based parallelism with `multiprocessing`.

### Workaround: Process Pool

If you must do CPU-intensive work:

```python
from concurrent.futures import ProcessPoolExecutor
import asyncio


def cpu_bound_work(data: list[int]) -> int:
    return sum(x ** 2 for x in data)


async def run_cpu_intensive(data: list[int]) -> None:
    # Run in a separate process
    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, cpu_bound_work, data)
        print(f"Result: {result}")


@app.post("/heavy-compute")
async def heavy_compute(tasks: Tasks) -> dict:
    tasks.schedule(run_cpu_intensive, list(range(1_000_000)))
    return {"status": "computing"}
```

## Mixing Sync and Async

You can freely mix sync and async tasks:

```python
async def async_operation() -> None:
    await asyncio.sleep(1)
    print("Async done")


def sync_operation() -> None:
    time.sleep(1)
    print("Sync done")


@app.post("/mixed")
async def mixed_tasks(tasks: Tasks) -> dict:
    # Schedule both types
    tasks.schedule(async_operation)
    tasks.schedule(sync_operation)
    tasks.after_route.schedule(async_operation)
    tasks.after_response.schedule(sync_operation)
    
    return {"status": "ok"}
```

## Performance Considerations

### Async Tasks Are Usually Faster

For I/O operations, async is typically more efficient:

```python
import httpx
import requests


# Faster: Async version
async def fetch_multiple_async(urls: list[str]) -> None:
    async with httpx.AsyncClient() as client:
        tasks = [client.get(url) for url in urls]
        await asyncio.gather(*tasks)


# Slower: Sync version (runs one at a time in thread pool)
def fetch_multiple_sync(urls: list[str]) -> None:
    for url in urls:
        requests.get(url)
```

### Thread Pool Overhead

Each sync task uses a thread from the pool:

```python
# This is fine
tasks.schedule(sync_task_1)
tasks.schedule(sync_task_2)

# This might exhaust the thread pool
for i in range(1000):
    tasks.schedule(sync_task, i)  # 1000 threads!
```

## Converting Sync to Async

If you have sync code, you can wrap it to make it async:

```python
import asyncio
from functools import partial


def sync_operation(a: int, b: int) -> int:
    time.sleep(1)
    return a + b


async def async_wrapper(a: int, b: int) -> None:
    # Run sync function in thread pool
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, partial(sync_operation, a, b))
    print(f"Result: {result}")


@app.post("/convert")
async def convert_example(tasks: Tasks) -> dict:
    # Now you can use it as an async task
    tasks.schedule(async_wrapper, 10, 20)
    return {"status": "ok"}
```

But this is usually unnecessary since `fastapi-tasks` handles sync functions automatically!

## Error Handling: Sync vs Async

Error handlers can also be sync or async, regardless of the task type:

```python
# Async error handler works with both sync and async tasks
async def async_error_handler(task: Task, error: Exception) -> None:
    await log_error_async(error)


# Sync error handler works with both sync and async tasks
def sync_error_handler(task: Task, error: Exception) -> None:
    print(f"Error: {error}")


@app.post("/errors")
async def error_handling(tasks: Tasks) -> dict:
    # Async task + async error handler
    tasks.task(on_error=async_error_handler).schedule(async_task)
    
    # Async task + sync error handler
    tasks.task(on_error=sync_error_handler).schedule(async_task)
    
    # Sync task + async error handler
    tasks.task(on_error=async_error_handler).schedule(sync_task)
    
    # Sync task + sync error handler
    tasks.task(on_error=sync_error_handler).schedule(sync_task)
    
    return {"status": "ok"}
```

## Real-World Examples

### Example 1: Email Service (Async)

```python
import httpx


async def send_email_via_api(to: str, subject: str, body: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.emailservice.com/send",
            json={"to": to, "subject": subject, "body": body}
        )


@app.post("/register")
async def register(email: str, tasks: Tasks) -> dict:
    # Use async for HTTP-based email service
    tasks.after_response.schedule(
        send_email_via_api,
        to=email,
        subject="Welcome",
        body="Thanks for registering!"
    )
    return {"status": "registered"}
```

### Example 2: Image Processing (Sync)

```python
from PIL import Image


def create_thumbnail(image_path: str) -> None:
    # PIL is synchronous
    img = Image.open(image_path)
    img.thumbnail((200, 200))
    img.save(f"{image_path}.thumb.jpg")


@app.post("/upload")
async def upload_image(file_path: str, tasks: Tasks) -> dict:
    # Use sync for PIL operations
    tasks.schedule(create_thumbnail, file_path)
    return {"status": "uploaded"}
```

### Example 3: Mixed Operations

```python
import httpx
from PIL import Image


async def process_uploaded_image(image_path: str, user_email: str) -> None:
    # Sync: Create thumbnail (PIL is sync)
    img = Image.open(image_path)
    img.thumbnail((200, 200))
    thumb_path = f"{image_path}.thumb.jpg"
    img.save(thumb_path)
    
    # Async: Upload to CDN
    async with httpx.AsyncClient() as client:
        with open(thumb_path, "rb") as f:
            await client.post("https://cdn.example.com/upload", files={"file": f})
    
    # Async: Send notification
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.emailservice.com/send",
            json={
                "to": user_email,
                "subject": "Image processed",
                "body": "Your image has been processed!"
            }
        )


@app.post("/process-image")
async def process_image(file_path: str, email: str, tasks: Tasks) -> dict:
    # This async task internally uses both sync and async operations
    tasks.schedule(process_uploaded_image, file_path, email)
    return {"status": "processing"}
```

## Best Practices

1. **Prefer async for I/O** - Use async libraries when available
2. **Use sync for sync-only libraries** - Don't fight the ecosystem
3. **Keep tasks simple** - Complex sync/async mixing in one task can be hard to debug
4. **Don't block the event loop** - Never use `time.sleep()` in async functions (use `asyncio.sleep()`)
5. **Handle errors in both** - Error handling works the same for sync and async

## Next Steps

You've completed the User Guide! Now explore advanced topics:

- [Error Handling](../tutorial_advanced/error_handling.md) - Advanced error handling patterns
- [Task Shielding](../tutorial_advanced/task_shielding.md) - Protect critical tasks from cancellation
- [Real World Examples](../tutorial_advanced/real_world_examples.md) - Complete real-world implementations
