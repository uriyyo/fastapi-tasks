# Scheduling Tasks

Now that you know the basics from [First Steps](first_steps.md), let's dive deeper into the task scheduling API.

## The `schedule()` Method

The most common way to schedule a task is using the `schedule()` method:

```python
tasks.schedule(function, *args, **kwargs)
```

This schedules a task to run immediately, concurrent with your endpoint execution.

### Basic Usage

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)


async def process_data(data: dict) -> None:
    # Your task logic here
    print(f"Processing: {data}")


@app.post("/process")
async def process_endpoint(data: dict, tasks: Tasks) -> dict:
    # Schedule the task
    tasks.schedule(process_data, data)
    
    return {"status": "processing started"}
```

### Passing Arguments

You can pass both positional and keyword arguments to your tasks:

```python
async def send_email(to: str, subject: str, body: str, cc: list[str] | None = None) -> None:
    print(f"Sending email to {to}")
    print(f"Subject: {subject}")
    print(f"CC: {cc}")


@app.post("/send")
async def send_message(tasks: Tasks) -> dict:
    # Positional arguments
    tasks.schedule(send_email, "user@example.com", "Hello", "Welcome!")
    
    # Keyword arguments
    tasks.schedule(
        send_email,
        to="user@example.com",
        subject="Hello",
        body="Welcome!",
        cc=["admin@example.com"]
    )
    
    # Mix of both
    tasks.schedule(
        send_email,
        "user@example.com",
        "Hello",
        body="Welcome!",
        cc=["admin@example.com"]
    )
    
    return {"status": "ok"}
```

## Scheduling Multiple Tasks

You can schedule multiple tasks in the same endpoint:

```python
async def task_1() -> None:
    print("Task 1")


async def task_2() -> None:
    print("Task 2")


async def task_3() -> None:
    print("Task 3")


@app.post("/multiple")
async def schedule_multiple(tasks: Tasks) -> dict:
    # All these tasks start immediately and run concurrently
    tasks.schedule(task_1)
    tasks.schedule(task_2)
    tasks.schedule(task_3)
    
    return {"scheduled": 3}
```

!!! note "Concurrent Execution"
    When you schedule multiple tasks with `tasks.schedule()`, they all start immediately and run concurrently.
    The order of completion is not guaranteed.

## Return Value: The Task Object

The `schedule()` method returns a `Task` object that you can use to track the task:

```python
from fastapi_tasks import Tasks
import anyio


async def my_task() -> None:
    await anyio.sleep(1)
    print("Task completed")


@app.post("/track")
async def track_task(tasks: Tasks) -> dict:
    # Get the task object
    task = tasks.schedule(my_task)
    
    # Check if the task has started
    await anyio.sleep(0.1)
    
    if task.started.is_set():
        return {"status": "task started"}
    else:
        return {"status": "task pending"}
```

The `Task` object has:

- `started` - An `anyio.Event` that's set when the task starts
- `config` - The task configuration (name, shield, error handler)
- `func` - The function being executed
- `args` - The positional arguments
- `kwargs` - The keyword arguments

!!! tip "Waiting for Task Start"
    You can use `await task.started.wait()` to wait until a task has started executing.
    This is useful in tests or when you need to ensure a task has begun before proceeding.

## Scheduling with Different Timing Modes

As covered in [Timing Modes](../background_tasks/timing_modes.md), you have three options:

### Immediate Execution

```python
@app.post("/immediate")
async def immediate_task(tasks: Tasks) -> dict:
    # Starts right now, runs concurrently
    tasks.schedule(my_task)
    return {"status": "ok"}
```

### After Route Execution

```python
@app.post("/after-route")
async def after_route_task(tasks: Tasks) -> dict:
    # Runs after this function returns, before response is sent
    tasks.after_route.schedule(my_task)
    return {"status": "ok"}
```

### After Response

```python
@app.post("/after-response")
async def after_response_task(tasks: Tasks) -> dict:
    # Runs after the response is sent to client
    tasks.after_response.schedule(my_task)
    return {"status": "ok"}
```

## Combining Timing Modes

You can use different timing modes in the same endpoint:

```python
async def validate_data(data: dict) -> None:
    print("Validating data")


async def log_request(endpoint: str) -> None:
    print(f"Request to {endpoint}")


async def send_notification(message: str) -> None:
    print(f"Notification: {message}")


@app.post("/combined")
async def combined_example(data: dict, tasks: Tasks) -> dict:
    # Start validation immediately (parallel with endpoint)
    tasks.schedule(validate_data, data)
    
    # Log before response is sent
    tasks.after_route.schedule(log_request, "/combined")
    
    # Send notification after response
    tasks.after_response.schedule(send_notification, "Request processed")
    
    return {"status": "ok"}
```

Execution order:
1. `validate_data` starts immediately when `schedule()` is called
2. Endpoint function completes and returns `{"status": "ok"}`
3. `log_request` runs
4. Response is sent to client
5. `send_notification` runs

## Scheduling from Other Dependencies

The `Tasks` dependency can be injected into other dependencies too:

```python
from fastapi import Depends


async def audit_log(action: str, tasks: Tasks = Depends()) -> None:
    """Dependency that logs actions as a background task"""
    tasks.after_route.schedule(log_action, action)


@app.post("/protected")
async def protected_endpoint(
    audit: None = Depends(lambda tasks=Depends(): audit_log("access", tasks))
) -> dict:
    return {"status": "ok"}
```

Or more cleanly:

```python
async def get_current_user(tasks: Tasks) -> dict:
    """Example authentication dependency that logs access"""
    user = {"id": 123, "name": "Alice"}
    
    # Log authentication as a background task
    tasks.after_route.schedule(log_auth_attempt, user["id"])
    
    return user


@app.get("/profile")
async def get_profile(
    user: dict = Depends(get_current_user),
    tasks: Tasks = Depends()
) -> dict:
    # Can still use tasks here too
    tasks.schedule(track_profile_view, user["id"])
    
    return user
```

## Dynamic Task Scheduling

You can dynamically choose which tasks to schedule based on conditions:

```python
async def send_sms(phone: str, message: str) -> None:
    print(f"SMS to {phone}: {message}")


async def send_email(email: str, subject: str, body: str) -> None:
    print(f"Email to {email}: {subject}")


@app.post("/notify")
async def notify_user(
    user_id: int,
    notification_type: str,
    tasks: Tasks
) -> dict:
    # Get user preferences
    user = get_user(user_id)  # Assume this exists
    
    # Schedule tasks based on user preferences
    if user.get("sms_enabled") and notification_type in ["urgent", "all"]:
        tasks.schedule(send_sms, user["phone"], "You have a notification")
    
    if user.get("email_enabled"):
        tasks.schedule(
            send_email,
            user["email"],
            "Notification",
            "You have a new notification"
        )
    
    return {"status": "notifications scheduled"}
```

## Task Scheduling Patterns

### Pattern 1: Fire and Forget

For operations you don't need to track:

```python
@app.post("/track")
async def track_event(event: str, tasks: Tasks) -> dict:
    tasks.schedule(send_to_analytics, event)
    return {"status": "ok"}
```

### Pattern 2: Concurrent Processing

For independent operations that can run concurrently:

```python
@app.post("/process")
async def process_upload(file_id: int, tasks: Tasks) -> dict:
    # All these happen concurrently
    tasks.schedule(generate_thumbnail, file_id)
    tasks.schedule(scan_for_viruses, file_id)
    tasks.schedule(extract_metadata, file_id)
    tasks.schedule(update_search_index, file_id)
    
    return {"status": "processing"}
```

### Pattern 3: Staged Execution

For operations that should happen at different times:

```python
@app.post("/order")
async def create_order(order_data: dict, tasks: Tasks) -> dict:
    order_id = save_order(order_data)
    
    # Immediate: Start payment processing
    tasks.schedule(process_payment, order_id)
    
    # After route: Update inventory before confirming
    tasks.after_route.schedule(update_inventory, order_id)
    
    # After response: Send confirmations
    tasks.after_response.schedule(send_order_email, order_id)
    tasks.after_response.schedule(notify_warehouse, order_id)
    
    return {"order_id": order_id}
```

## Common Pitfalls

### Pitfall 1: Capturing Mutable State

```python
# DON'T DO THIS
data = {"count": 0}

@app.post("/increment")
async def increment(tasks: Tasks) -> dict:
    data["count"] += 1
    # This might not work as expected because the task
    # may run after data has been modified again
    tasks.schedule(log_count, data["count"])
    return {"count": data["count"]}


# DO THIS INSTEAD
@app.post("/increment")
async def increment(tasks: Tasks) -> dict:
    count = data["count"] + 1
    data["count"] = count
    # Pass the value directly
    tasks.schedule(log_count, count)
    return {"count": count}
```

### Pitfall 2: Not Handling Task Failures

```python
# Without error handling, failures are just logged
tasks.schedule(might_fail)

# Better: Use error handlers (covered in advanced tutorial)
tasks.task(on_error=handle_error).schedule(might_fail)
```

## Next Steps

Now that you understand task scheduling, learn about:

- [Timing Control](timing_control.md) - Master the three timing modes
- [Task Configuration](task_configuration.md) - Name tasks, shield them, and add error handlers
- [Sync and Async](sync_async.md) - Understand how sync and async tasks work differently
