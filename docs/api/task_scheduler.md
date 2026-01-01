# TaskScheduler API Reference

The `TasksScheduler` is the internal class that manages task execution. It's typically accessed via the `Tasks` dependency.

## Class Definition

```python
@dataclass
class TasksScheduler(_ConfiguredTaskDefMixin):
    tg: TaskGroup
    after_response: TasksBatch = field(default_factory=TasksBatch)
    after_route: TasksBatch = field(default_factory=TasksBatch)
```

## Attributes

### `tg: TaskGroup`

The `anyio` task group that manages all background tasks. This is created during application lifespan and handles task execution.

### `after_response: TasksBatch`

A `TasksBatch` containing tasks scheduled to run after the HTTP response is sent.

### `after_route: TasksBatch`

A `TasksBatch` containing tasks scheduled after the endpoint completes but before the response is sent. These are fire-and-forget and don't block the response.

## Lifecycle

The `TasksScheduler` lifecycle is managed by FastAPI's lifespan context:

1. **Application startup**: Task group is created via `add_tasks(app)`
2. **Per request**: New `TasksScheduler` instance created with reference to the task group
3. **During request**: Tasks are scheduled into the scheduler
4. **End of endpoint**: After-route tasks are scheduled (fire-and-forget)
5. **After response**: After-response tasks are scheduled
6. **Application shutdown**: Task group is cancelled (non-shielded tasks stop)

## Internal Flow

```
Application Lifespan
    │
    ├─► Create TaskGroup (via add_tasks)
    │
    └─► Per Request:
            │
            ├─► Create TasksScheduler instance
            │
            ├─► Endpoint executes
            │   └─► tasks.schedule() → starts immediately
            │
            ├─► Endpoint returns
            │   └─► tasks.after_route tasks execute
            │
            ├─► Response sent
            │   └─► tasks.after_response tasks execute
            │
            └─► Request complete
```

## Methods

### `schedule(func, /, *args, **kwargs) -> Task`

Inherited from `_ConfiguredTaskDefMixin`. Schedules a task for immediate execution.

### `task(*, name=None, shield=None, on_error=None) -> _PartialTaskDef`

Inherited from `_ConfiguredTaskDefMixin`. Creates a configured task definition.

## Integration with FastAPI

The `TasksScheduler` integrates with FastAPI via dependency injection:

```python
# In dependencies.py
async def _get_task_scheduler(...) -> AsyncIterator[TasksScheduler]:
    # Get task group from request state
    tg: TaskGroup = req.state.fastapi_tasks_tg
    
    # Create scheduler for this request
    scheduler = TasksScheduler(tg)
    
    yield scheduler
    
    # After endpoint completes, execute after-route tasks
    scheduler.after_route.__start__(scheduler)
    
    # After this dependency exits, response is sent
    # Then after-response tasks execute (in outer scope)
```

## Task Execution

Tasks are executed within the shared task group:

```python
# When you call tasks.schedule(my_func, arg)
task = Task(func=my_func, args=(arg,), kwargs={})
task.__start__(scheduler)  # Starts task in the task group
```

## Error Handling

The scheduler doesn't handle errors directly; errors are handled by individual tasks:

- If a task has an `on_error` handler, it's called
- Otherwise, the exception is logged
- Other tasks continue executing normally

## Example: Direct Usage (Advanced)

You typically use `TasksScheduler` through the `Tasks` dependency, but you can access it directly:

```python
from fastapi_tasks import TasksScheduler
from fastapi import Request

@app.post("/advanced")
async def advanced_endpoint(request: Request) -> dict:
    # Get the task group from request state
    tg = request.state.fastapi_tasks_tg
    
    # Create scheduler manually
    scheduler = TasksScheduler(tg)
    
    # Schedule tasks
    scheduler.schedule(my_task)
    scheduler.after_response.schedule(another_task)
    
    return {"status": "ok"}
```

!!! warning
    Direct usage is not recommended. Use the `Tasks` dependency instead, which handles the lifecycle correctly.

## See Also

- [Tasks API](tasks.md) - High-level Tasks dependency
- [TaskConfig](task_config.md) - Task configuration
- [Utilities](utilities.md) - `add_tasks()` setup function
