{! ../README.md !}

---

## Quick Navigation

### Getting Started

New to `fastapi-tasks`? Start here:

- **[First Steps](learn/tutorial_user_guide/first_steps.md)** - Install and create your first background task
- **[Background Tasks Concepts](learn/background_tasks/general.md)** - Understand what background tasks are and why use them
- **[Timing Modes](learn/background_tasks/timing_modes.md)** - Learn about immediate, after-route, and after-response execution

### Core Tutorials

Learn the fundamentals:

- **[Scheduling Tasks](learn/tutorial_user_guide/scheduling_tasks.md)** - Schedule tasks with different timing modes
- **[Timing Control](learn/tutorial_user_guide/timing_control.md)** - Master after-route and after-response tasks
- **[Task Configuration](learn/tutorial_user_guide/task_configuration.md)** - Name tasks, add error handlers, configure shielding
- **[Sync and Async](learn/tutorial_user_guide/sync_async.md)** - Work with both sync and async functions

### Advanced Topics

For production-ready applications:

- **[Error Handling](learn/tutorial_advanced/error_handling.md)** - Implement robust error handling with retries
- **[Task Shielding](learn/tutorial_advanced/task_shielding.md)** - Protect critical tasks from cancellation
- **[Real World Examples](learn/tutorial_advanced/real_world_examples.md)** - Complete examples: e-commerce, user registration, image processing

### API Reference

Complete API documentation:

- **[Tasks API](api/tasks.md)** - Tasks dependency and scheduling methods
- **[TaskConfig](api/task_config.md)** - Task configuration options
- **[Error Handlers](api/error_handlers.md)** - Error handler types and patterns
- **[Utilities](api/utilities.md)** - `add_tasks()` and helper functions

### Need Help?

- **[FAQ](faq/faq.md)** - Frequently asked questions
- **[Contributing](contributing.md)** - How to contribute to the project

---

## Feature Highlights

### Precise Timing Control

Choose exactly when your tasks run:

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)

@app.post("/orders")
async def create_order(tasks: Tasks) -> dict:
    # Immediate: starts right away
    tasks.schedule(process_payment)
    
    # After route: scheduled before response sent (fire-and-forget)
    tasks.after_route.schedule(update_inventory)
    
    # After response: scheduled after response sent
    tasks.after_response.schedule(send_confirmation_email)
    
    return {"status": "processing"}
```

### Task Shielding

Protect critical tasks from server shutdown:

```python
@app.post("/payment")
async def process_payment(tasks: Tasks) -> dict:
    # This task completes even during server shutdown
    tasks.task(shield=True).schedule(finalize_payment)
    
    return {"status": "processing"}
```

### Error Handling

Custom error handlers for graceful failure recovery:

```python
async def payment_error_handler(task: Task, error: Exception) -> None:
    # Log to error tracking
    await sentry_sdk.capture_exception(error)
    
    # Alert on-call engineer
    await send_alert(f"Payment failed: {error}")


@app.post("/checkout")
async def checkout(tasks: Tasks) -> dict:
    tasks.task(
        name="process_payment",
        shield=True,
        on_error=payment_error_handler
    ).schedule(charge_card)
    
    return {"status": "ok"}
```

### Full Type Safety

Complete type hints for better IDE support:

```python
async def send_email(to: str, subject: str, body: str) -> None:
    ...

@app.post("/send")
async def send(tasks: Tasks) -> dict:
    # IDE knows parameter types and provides autocomplete
    tasks.schedule(send_email, "user@example.com", "Hello", "Welcome!")
    
    return {"status": "ok"}
```

---

## Comparison with Alternatives

### vs FastAPI BackgroundTasks

| Feature | FastAPI BackgroundTasks | fastapi-tasks |
|---------|------------------------|---------------|
| Timing control | After response only | 3 modes: immediate, after-route, after-response |
| Task shielding | ❌ | ✅ |
| Custom error handlers | ❌ | ✅ |
| Task naming | ❌ | ✅ |
| Setup complexity | Minimal | Simple (`add_tasks(app)`) |

### vs Celery

| Feature | Celery | fastapi-tasks |
|---------|--------|---------------|
| Setup complexity | High (broker, workers) | Low (one function call) |
| Distributed tasks | ✅ | ❌ |
| Task persistence | ✅ | ❌ |
| Simple background tasks | Overkill | Perfect fit |
| Production-ready | ✅ | ✅ |

**Use `fastapi-tasks` when:**
- You need simple background tasks within your FastAPI app
- Tasks don't need to survive server restarts
- You don't need distributed task execution
- You want minimal setup

**Use Celery when:**
- You need distributed task processing
- Tasks must survive server restarts
- You need complex task workflows
- You have many workers across multiple servers

---

## Community and Support

- **GitHub**: [uriyyo/fastapi-tasks](https://github.com/uriyyo/fastapi-tasks)
- **Issues**: [Report bugs or request features](https://github.com/uriyyo/fastapi-tasks/issues)
- **Discussions**: [Ask questions](https://github.com/uriyyo/fastapi-tasks/discussions)

---

## License

This project is licensed under the MIT License - see the [License](license.md) page for details.
