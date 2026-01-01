# Task Configuration

Beyond just scheduling tasks, `fastapi-tasks` allows you to configure tasks with names, error handlers, and shielding.
This tutorial covers the `task()` method and configuration options.

## The `task()` Method

The `task()` method creates a configured task definition that you then schedule:

```python
tasks.task(
    name="my_task",           # Optional: task name for logging
    shield=True,              # Optional: protect from cancellation
    on_error=error_handler    # Optional: custom error handler
).schedule(my_function, arg1, arg2)
```

All configuration parameters are optional.

## Naming Tasks

Giving tasks descriptive names helps with debugging and logging:

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)


async def send_email(to: str, subject: str) -> None:
    print(f"Sending email to {to}")


@app.post("/notify")
async def notify_user(email: str, tasks: Tasks) -> dict:
    # Name the task for better logging
    tasks.task(name="send_welcome_email").schedule(
        send_email,
        to=email,
        subject="Welcome!"
    )
    
    return {"status": "ok"}
```

Task names appear in logs and can help you identify which tasks are running or failing.

### Naming Conventions

Use descriptive names that indicate what the task does:

```python
# Good names
tasks.task(name="send_order_confirmation").schedule(send_email, ...)
tasks.task(name="process_payment").schedule(process_payment, ...)
tasks.task(name="generate_thumbnail").schedule(create_thumbnail, ...)

# Less helpful names
tasks.task(name="task1").schedule(send_email, ...)
tasks.task(name="email").schedule(send_email, ...)
```

### Dynamic Task Names

You can include dynamic information in task names:

```python
@app.post("/process/{user_id}")
async def process_user_data(user_id: int, tasks: Tasks) -> dict:
    task_name = f"process_user_{user_id}"
    
    tasks.task(name=task_name).schedule(process_data, user_id)
    
    return {"status": "processing"}
```

## Task Shielding

Shielding protects tasks from cancellation when the server shuts down.

### Basic Usage

```python
async def critical_operation() -> None:
    # This operation MUST complete
    print("Performing critical operation")


@app.post("/critical")
async def critical_endpoint(tasks: Tasks) -> dict:
    # This task will complete even during server shutdown
    tasks.task(shield=True).schedule(critical_operation)
    
    return {"status": "ok"}
```

### When to Use Shielding

Use `shield=True` for tasks that:

1. **Modify critical state** - Database writes, file operations
2. **Handle payments** - Financial transactions that must complete
3. **Send important notifications** - Alerts that users must receive
4. **Release resources** - Cleanup operations that prevent resource leaks

!!! warning "Use Sparingly"
    Shielded tasks prevent your application from shutting down quickly.
    Only shield truly critical operations.

### Real-World Example: Payment Processing

```python
async def finalize_payment(payment_id: int, amount: float) -> None:
    # Update payment status in database
    update_payment_status(payment_id, "completed")
    # Charge the credit card
    charge_card(payment_id, amount)
    # Send receipt
    send_receipt(payment_id)


@app.post("/payments")
async def process_payment(
    payment_id: int,
    amount: float,
    tasks: Tasks
) -> dict:
    # Shield this task - payments MUST complete
    tasks.task(
        name=f"finalize_payment_{payment_id}",
        shield=True
    ).schedule(finalize_payment, payment_id, amount)
    
    return {"status": "processing", "payment_id": payment_id}
```

### Shielding with Different Timing Modes

You can shield tasks with any timing mode:

```python
@app.post("/order")
async def create_order(order_data: dict, tasks: Tasks) -> dict:
    order_id = save_order(order_data)
    
    # Shield after-route task
    tasks.after_route.task(
        name="finalize_order",
        shield=True
    ).schedule(finalize_order, order_id)
    
    # Shield after-response task
    tasks.after_response.task(
        name="send_confirmation",
        shield=True
    ).schedule(send_critical_notification, order_id)
    
    return {"order_id": order_id}
```

## Error Handlers

Custom error handlers allow you to control what happens when a task fails.

### Basic Error Handler

```python
from fastapi_tasks import Task


async def my_error_handler(task: Task, error: Exception) -> None:
    print(f"Task {task.config.name} failed: {error}")


async def risky_operation() -> None:
    raise ValueError("Something went wrong")


@app.post("/risky")
async def risky_endpoint(tasks: Tasks) -> dict:
    tasks.task(
        name="risky_task",
        on_error=my_error_handler
    ).schedule(risky_operation)
    
    return {"status": "ok"}
```

When `risky_operation` fails, `my_error_handler` is called with:
- `task` - The Task object that failed
- `error` - The exception that was raised

### Error Handler Signature

Error handlers can be sync or async:

```python
# Async error handler
async def async_error_handler(task: Task, error: Exception) -> None:
    await log_error_to_service(error)


# Sync error handler
def sync_error_handler(task: Task, error: Exception) -> None:
    print(f"Error: {error}")
```

### Accessing Task Information in Error Handlers

The `task` parameter provides access to task details:

```python
async def detailed_error_handler(task: Task, error: Exception) -> None:
    print(f"Task name: {task.config.name}")
    print(f"Function: {task.func.__name__}")
    print(f"Arguments: {task.args}")
    print(f"Keyword arguments: {task.kwargs}")
    print(f"Error: {error}")
    print(f"Error type: {type(error).__name__}")
```

### Real-World Example: Error Tracking

```python
import sentry_sdk


async def send_to_error_tracking(task: Task, error: Exception) -> None:
    """Send task errors to Sentry"""
    with sentry_sdk.push_scope() as scope:
        scope.set_context("task", {
            "name": task.config.name,
            "function": task.func.__name__,
            "args": str(task.args),
            "kwargs": str(task.kwargs),
        })
        sentry_sdk.capture_exception(error)


@app.post("/process")
async def process_data(data: dict, tasks: Tasks) -> dict:
    tasks.task(
        name="process_user_data",
        on_error=send_to_error_tracking
    ).schedule(process_user_data, data)
    
    return {"status": "processing"}
```

### Error Handler with Retry Logic

```python
import asyncio


async def retry_handler(task: Task, error: Exception) -> None:
    """Retry the task up to 3 times"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            # Retry the task
            await task.func(*task.args, **task.kwargs)
            
            print(f"Task {task.config.name} succeeded on retry {attempt + 1}")
            return
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Task {task.config.name} failed after {max_retries} retries")
                raise
            print(f"Retry {attempt + 1} failed: {e}")


async def flaky_operation() -> None:
    # Simulates an operation that might fail
    import random
    if random.random() < 0.7:
        raise ValueError("Random failure")
    print("Operation succeeded")


@app.post("/flaky")
async def flaky_endpoint(tasks: Tasks) -> dict:
    tasks.task(
        name="flaky_task",
        on_error=retry_handler
    ).schedule(flaky_operation)
    
    return {"status": "ok"}
```

## Combining Configuration Options

You can combine name, shield, and error handler:

```python
async def payment_error_handler(task: Task, error: Exception) -> None:
    # Log to error tracking
    await log_to_sentry(error)
    
    # Alert on-call engineer
    await send_alert(f"Payment task failed: {error}")
    
    # Attempt to refund if needed
    payment_id = task.kwargs.get("payment_id")
    if payment_id:
        await initiate_refund(payment_id)


@app.post("/payments")
async def create_payment(payment_id: int, amount: float, tasks: Tasks) -> dict:
    # Fully configured task
    tasks.task(
        name=f"process_payment_{payment_id}",
        shield=True,
        on_error=payment_error_handler
    ).schedule(process_payment_async, payment_id=payment_id, amount=amount)
    
    return {"status": "processing"}
```

## Configuration with Different Timing Modes

Task configuration works with all timing modes:

```python
@app.post("/comprehensive")
async def comprehensive_example(tasks: Tasks) -> dict:
    # Immediate task with configuration
    tasks.task(
        name="immediate_task",
        on_error=log_error
    ).schedule(immediate_operation)
    
    # After-route task with configuration
    tasks.after_route.task(
        name="cleanup_task",
        shield=True
    ).schedule(cleanup_resources)
    
    # After-response task with configuration
    tasks.after_response.task(
        name="notification_task",
        on_error=notification_error_handler
    ).schedule(send_notification)
    
    return {"status": "ok"}
```

## Configuration Best Practices

### 1. Always Name Critical Tasks

```python
# Good
tasks.task(name="process_payment", shield=True).schedule(...)

# Less good
tasks.task(shield=True).schedule(...)  # Missing name
```

### 2. Use Descriptive Error Handlers

```python
# Good - specific handler for specific task type
async def payment_error_handler(task: Task, error: Exception) -> None:
    await handle_payment_error(task, error)

tasks.task(on_error=payment_error_handler).schedule(process_payment)


# Also good - generic handler for logging
async def log_all_errors(task: Task, error: Exception) -> None:
    logger.error(f"Task {task.config.name} failed", exc_info=error)
```

### 3. Shield Only When Necessary

```python
# Good - shield critical operations
tasks.task(shield=True).schedule(finalize_payment)

# Bad - unnecessary shielding
tasks.task(shield=True).schedule(send_email)  # Emails can fail/retry
```

### 4. Combine Configuration Logically

```python
# Good - critical task with name, shield, and error handler
tasks.task(
    name="critical_operation",
    shield=True,
    on_error=critical_error_handler
).schedule(critical_function)


# Good - non-critical task with just error logging
tasks.task(
    name="send_notification",
    on_error=log_error
).schedule(send_email)
```

## Default Configuration

If you don't provide configuration, tasks use defaults:

- `name` = `None` (anyio will auto-generate a name)
- `shield` = `False` (tasks can be cancelled)
- `on_error` = `None` (errors are logged but not handled)

```python
# These are equivalent
tasks.schedule(my_task)
tasks.task().schedule(my_task)
tasks.task(name=None, shield=False, on_error=None).schedule(my_task)
```

## Global Configuration

You can set default configuration for **all tasks** in your application by passing a `TaskConfig` to `add_tasks()`:

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks, TaskConfig

# Define global error handler
async def global_error_handler(task: Task, error: Exception) -> None:
    print(f"Task {task.config.name} failed: {error}")
    # Send to error tracking service
    await track_error(error)

# Global configuration applied to all tasks
global_config = TaskConfig(
    shield=True,  # All tasks shielded by default
    on_error=global_error_handler
)

app = FastAPI()
add_tasks(app, config=global_config)


@app.post("/task")
async def endpoint(tasks: Tasks) -> dict:
    # This task inherits global configuration
    # shield=True, on_error=global_error_handler
    tasks.schedule(my_function)
    
    return {"status": "scheduled"}
```

### How Global Configuration Works

When you provide a global `TaskConfig` to `add_tasks()`:

1. The config is stored in the application's lifespan context
2. It's propagated to the `TasksScheduler` on every request
3. Individual tasks **merge** their config with the global config
4. Task-specific settings override global settings

### Overriding Global Configuration

Individual tasks can override any part of the global configuration:

```python
# Global config: all tasks shielded with global error handler
global_config = TaskConfig(shield=True, on_error=global_error_handler)
app = FastAPI()
add_tasks(app, config=global_config)


async def custom_error_handler(task: Task, error: Exception) -> None:
    print("Custom handler")


@app.post("/tasks")
async def endpoint(tasks: Tasks) -> dict:
    # Task 1: Uses global config completely
    # shield=True, on_error=global_error_handler
    tasks.schedule(task1)
    
    # Task 2: Overrides error handler only
    # shield=True (from global), on_error=custom_error_handler
    tasks.task(on_error=custom_error_handler).schedule(task2)
    
    # Task 3: Overrides shield only
    # shield=False, on_error=global_error_handler (from global)
    tasks.task(shield=False).schedule(task3)
    
    # Task 4: Overrides everything
    # shield=False, on_error=custom_error_handler, name="my_task"
    tasks.task(
        name="my_task",
        shield=False,
        on_error=custom_error_handler
    ).schedule(task4)
    
    return {"status": "ok"}
```

### Configuration Merge Behavior

The merge follows these rules:

- For each field (`name`, `shield`, `on_error`):
  - If the task-specific value is **not None**, use it
  - Otherwise, use the global value

```python
global_config = TaskConfig(name="global", shield=True, on_error=handler1)

# Task config only sets shield=False
task_config = TaskConfig(shield=False)

# After merge:
# - name: "global" (from global, task didn't specify)
# - shield: False (from task, overrides global)
# - on_error: handler1 (from global, task didn't specify)
merged = global_config.merge(task_config)
```

### Real-World Example: Production App

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks, TaskConfig, Task
import sentry_sdk


# Global error handler for production monitoring
async def production_error_handler(task: Task, error: Exception) -> None:
    # Log to application logs
    logger.error(f"Task failed: {task.config.name}", exc_info=error)
    
    # Send to Sentry with context
    with sentry_sdk.push_scope() as scope:
        scope.set_context("task", {
            "name": task.config.name,
            "function": task.func.__name__,
        })
        sentry_sdk.capture_exception(error)


# All tasks in production should:
# 1. Report errors to Sentry
# 2. NOT be shielded by default (allow quick shutdown)
production_config = TaskConfig(
    on_error=production_error_handler,
    shield=False
)

app = FastAPI()
add_tasks(app, config=production_config)


async def process_payment(payment_id: int, amount: float) -> None:
    # Process payment...
    pass


async def send_notification(user_id: int, message: str) -> None:
    # Send notification...
    pass


@app.post("/payments")
async def create_payment(payment_id: int, amount: float, tasks: Tasks) -> dict:
    # Critical payment task - override global config to shield
    tasks.task(
        name=f"process_payment_{payment_id}",
        shield=True  # Override: payments must complete
        # on_error still uses production_error_handler from global
    ).schedule(process_payment, payment_id, amount)
    
    return {"status": "processing"}


@app.post("/notify")
async def notify_user(user_id: int, message: str, tasks: Tasks) -> dict:
    # Non-critical notification - use global config
    # shield=False, on_error=production_error_handler
    tasks.task(name=f"notify_{user_id}").schedule(
        send_notification, user_id, message
    )
    
    return {"status": "scheduled"}
```

### When to Use Global Configuration

Use global configuration when you want to:

1. **Standardize error handling** - All tasks report to the same monitoring service
2. **Set security defaults** - Shield or unshield all tasks by default
3. **Reduce boilerplate** - Avoid repeating the same config on every task
4. **Enforce policies** - Ensure all tasks follow company standards

### When Not to Use Global Configuration

Don't use global configuration if:

1. **Tasks are too diverse** - Different tasks need very different configs
2. **You need explicit control** - You want to see config at each task site
3. **Team prefers explicit** - Your team values explicitness over DRY

### Global Configuration Best Practices

#### 1. Set Conservative Defaults

```python
# Good - conservative defaults, override when needed
global_config = TaskConfig(
    shield=False,  # Fast shutdown by default
    on_error=log_errors  # Always log errors
)

# Tasks opt-in to shielding when critical
tasks.task(shield=True).schedule(critical_task)
```

#### 2. Document Your Global Config

```python
# Global task configuration for this application:
# - All tasks report errors to Sentry
# - Tasks are NOT shielded (can be cancelled during shutdown)
# - Individual tasks can override these defaults
global_config = TaskConfig(
    on_error=sentry_error_handler,
    shield=False
)
add_tasks(app, config=global_config)
```

#### 3. Keep It Simple

```python
# Good - simple, clear global config
global_config = TaskConfig(on_error=error_handler)

# Avoid - too much in global config
global_config = TaskConfig(
    name="default_task",  # Don't set names globally
    shield=True,  # Risky default
    on_error=complex_handler
)
```

## Next Steps

Now that you understand task configuration, learn about:

- [Sync and Async](sync_async.md) - How sync and async tasks are handled differently
- [Error Handling](../tutorial_advanced/error_handling.md) - Advanced error handling patterns
- [Task Shielding](../tutorial_advanced/task_shielding.md) - Deep dive into shielding
