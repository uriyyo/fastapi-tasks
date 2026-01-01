# First Steps

This tutorial will guide you through creating your first FastAPI application with background tasks using `fastapi-tasks`.

## Installation

First, install `fastapi-tasks` using pip:

```bash
pip install fastapi-tasks
```

## Minimal Example

Here's a complete minimal example:

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)  # Important! Initialize tasks support


async def send_notification(message: str) -> None:
    # Simulate sending a notification
    print(f"Sending notification: {message}")


@app.post("/notify")
async def create_notification(message: str, tasks: Tasks) -> dict:
    # Schedule a background task
    tasks.schedule(send_notification, message)
    
    return {"status": "notification scheduled"}
```

Let's break down what's happening step by step.

## Step 1: Import Dependencies

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks
```

You need to import:

- `FastAPI` - The FastAPI application class
- `Tasks` - A type annotation for dependency injection
- `add_tasks` - A function to add background task support to your app

## Step 2: Create the FastAPI Application

```python
app = FastAPI()
```

Create your FastAPI application instance as usual.

## Step 3: Add Tasks Support

```python
add_tasks(app)
```

This is a **critical step**. You must call `add_tasks(app)` to initialize background task support.

!!! warning "Don't Forget This Step"
    If you forget to call `add_tasks(app)`, you'll get a `FastAPITasksUninitializedAppError` when trying to use the `Tasks` dependency.

### What does `add_tasks(app)` do?

Internally, `add_tasks(app)` sets up a task group using `anyio` that manages all background tasks throughout your application's lifecycle.
It integrates with FastAPI's lifespan context to ensure tasks are properly managed during startup and shutdown.

## Step 4: Define Your Task Function

```python
async def send_notification(message: str) -> None:
    print(f"Sending notification: {message}")
```

Task functions can be either async or sync (more on this in [Sync and Async](sync_async.md)).

For now, just know that your task function:

- Can accept any arguments
- Can be async or sync
- Should handle its own errors (or use error handlers - covered in [Error Handling](../tutorial_advanced/error_handling.md))

## Step 5: Create an Endpoint with Tasks

```python
@app.post("/notify")
async def create_notification(message: str, tasks: Tasks) -> dict:
    tasks.schedule(send_notification, message)
    return {"status": "notification scheduled"}
```

The magic happens here:

1. **Inject `Tasks` dependency**: Add `tasks: Tasks` to your endpoint parameters
2. **Schedule a task**: Call `tasks.schedule(function, *args, **kwargs)`
3. **Return normally**: Your endpoint returns immediately while the task runs in the background

### The `Tasks` Dependency

`Tasks` is a type-annotated dependency that gives you access to the task scheduler.

```python
def my_endpoint(tasks: Tasks) -> dict:
    #              ^^^^^ This is dependency injection
    ...
```

FastAPI automatically injects the `Tasks` instance, giving you access to:

- `tasks.schedule()` - Schedule immediate tasks
- `tasks.after_route` - Access after-route task scheduler
- `tasks.after_response` - Access after-response task scheduler
- `tasks.task()` - Configure tasks with names, shielding, and error handlers

## Testing Your Application

Run your application with uvicorn:

```bash
uvicorn main:app --reload
```

Then make a request:

```bash
curl -X POST "http://localhost:8000/notify?message=Hello"
```

You should see:

1. Immediate response: `{"status": "notification scheduled"}`
2. In your server logs: `Sending notification: Hello`

The response is sent immediately, and the task runs in the background.

## Complete Working Example

Here's a more realistic example with multiple endpoints:

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks
import asyncio

app = FastAPI()
add_tasks(app)


async def send_email(to: str, subject: str, body: str) -> None:
    # Simulate email sending delay
    await asyncio.sleep(2)
    print(f"Email sent to {to}: {subject}")


async def log_event(event_type: str, user_id: int) -> None:
    print(f"Event logged: {event_type} for user {user_id}")


@app.post("/users")
async def create_user(email: str, tasks: Tasks) -> dict:
    # Simulate user creation
    user_id = 12345
    
    # Send welcome email in background
    tasks.schedule(
        send_email,
        to=email,
        subject="Welcome!",
        body="Thanks for signing up!"
    )
    
    # Log the event
    tasks.schedule(log_event, "user_created", user_id)
    
    # Return immediately
    return {"user_id": user_id, "email": email}


@app.post("/orders")
async def create_order(user_id: int, tasks: Tasks) -> dict:
    order_id = 67890
    
    # Send order confirmation
    tasks.schedule(
        send_email,
        to=f"user_{user_id}@example.com",
        subject="Order Confirmed",
        body=f"Your order #{order_id} is confirmed!"
    )
    
    return {"order_id": order_id}
```

## What You've Learned

In this tutorial, you learned:

1. How to install `fastapi-tasks`
2. How to initialize background task support with `add_tasks(app)`
3. How to inject the `Tasks` dependency into your endpoints
4. How to schedule basic background tasks with `tasks.schedule()`
5. How to pass arguments to your task functions

## Next Steps

Now that you know the basics, explore more advanced features:

- [Scheduling Tasks](scheduling_tasks.md) - Learn about the task scheduling API in detail
- [Timing Control](timing_control.md) - Use `after_route` and `after_response` for precise timing
- [Task Configuration](task_configuration.md) - Name tasks, add error handlers, and configure shielding
