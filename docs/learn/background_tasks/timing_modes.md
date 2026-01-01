# Timing Modes

One of the most powerful features of `fastapi-tasks` is its precise control over **when** your background tasks execute.
Unlike traditional background task systems that only run tasks after the response is sent, `fastapi-tasks` gives you three distinct timing modes.

## The Three Timing Modes

### 1. Immediate (`tasks.schedule()`)

Tasks scheduled with `tasks.schedule()` start running **immediately**, concurrently with your endpoint function.

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)

@app.post("/process")
async def process_data(data: dict, tasks: Tasks) -> dict:
    # This task starts RIGHT NOW, concurrently
    tasks.schedule(long_running_computation, data)
    
    # Your endpoint continues executing
    result = {"status": "processing"}
    
    return result  # Response sent while task still runs
```

**When it starts:** As soon as `schedule()` is called  
**Execution:** Runs concurrently with endpoint  
**Response timing:** Response can be sent before task completes

**Use cases:**

- Fire-and-forget operations
- Long-running computations that don't affect the response
- Starting processes that will complete asynchronously
- Concurrent data processing

!!! warning
    Because immediate tasks run concurrently with your endpoint, they don't block the response.
    Make sure these tasks don't depend on the response being sent or the request context being available after the function returns.

---

### 2. After Route (`tasks.after_route.schedule()`)

Tasks scheduled with `tasks.after_route.schedule()` are **scheduled** after your endpoint function completes, but before the response is sent to the client.

```python
@app.post("/orders")
async def create_order(order_data: dict, tasks: Tasks) -> dict:
    order = create_order_in_db(order_data)
    
    # This task is scheduled AFTER this function returns,
    # but BEFORE the response is sent to the client
    tasks.after_route.schedule(log_order_created, order.id)
    
    return {"order_id": order.id}
    # Response is sent after tasks are scheduled (not after completion)
```

**When it starts:** After the endpoint function returns  
**Execution:** Fire-and-forget (runs concurrently, doesn't block response)  
**Response timing:** Response is sent after tasks are scheduled

**Use cases:**

- Tasks that should be scheduled in the "after endpoint" phase
- Logging operations that should be started before responding
- Tasks that logically belong between endpoint completion and response
- Maintaining execution order (after endpoint, before after-response tasks)

!!! warning "Fire-and-Forget"
    After-route tasks are fire-and-forget! They are **scheduled** before the response is sent, but they
    don't block the response. The response is sent once tasks are scheduled, not after they complete.

---

### 3. After Response (`tasks.after_response.schedule()`)

Tasks scheduled with `tasks.after_response.schedule()` are **scheduled** after the HTTP response has been sent to the client.

This is equivalent to FastAPI's built-in `BackgroundTasks`, but with additional features like shielding and error handling.

```python
@app.post("/signup")
async def signup(email: str, password: str, tasks: Tasks) -> dict:
    user = create_user_in_db(email, password)
    
    # These tasks are scheduled AFTER the client receives the response
    tasks.after_response.schedule(send_welcome_email, email)
    tasks.after_response.schedule(send_slack_notification, f"New user: {email}")
    
    return {"user_id": user.id}
    # Client receives this immediately, then tasks are scheduled
```

**When it starts:** After the response is sent to the client  
**Execution:** Fire-and-forget (runs concurrently)  
**Response timing:** Response is sent immediately, tasks scheduled afterward

**Use cases:**

- Email notifications
- External API calls (webhooks, analytics)
- Cache warming or invalidation
- Any operation that doesn't affect the response

!!! tip
    This is the most common timing mode for background tasks because it provides the fastest response times
    while still ensuring work gets done.

---

## Visual Timeline

Here's how the three timing modes relate to the request lifecycle:

```
+-------------------------------------------------------------------+
|                        Request Arrives                            |
+-------------------------------------------------------------------+
                               |
                               v
                  +------------------------+
                  |  tasks.schedule()      |----------> Starts immediately
                  |  (immediate tasks)     |            (runs concurrently)
                  +------------------------+
                               |
                               v
+-------------------------------------------------------------------+
|                  Endpoint Function Executes                       |
|                 (your business logic runs)                        |
+-------------------------------------------------------------------+
                               |
                               v
                  +------------------------+
                  |  tasks.after_route     |----------> Scheduled here
                  |  .schedule()           |            (fire-and-forget)
                  +------------------------+
                               |
                               v
+-------------------------------------------------------------------+
|                   Response Sent to Client                         |
+-------------------------------------------------------------------+
                               |
                               v
                  +------------------------+
                  |  tasks.after_response  |----------> Scheduled here
                  |  .schedule()           |            (fire-and-forget)
                  +------------------------+
                               |
                               v
+-------------------------------------------------------------------+
|                      Request Complete                             |
+-------------------------------------------------------------------+
```

## Choosing the Right Timing Mode

Use this decision tree to choose the appropriate timing mode:

**Does the task affect the response data?**
- **Yes** → Run it in your endpoint function directly (not as a background task)
- **No** → Continue...

**Should the task be scheduled before the response?**
- **Yes** → Use `tasks.after_route.schedule()`
- **No** → Continue...

**Does the task need to start as early as possible?**
- **Yes** → Use `tasks.schedule()` (immediate)
- **No** → Use `tasks.after_response.schedule()`

## Combining Timing Modes

You can use multiple timing modes in the same endpoint:

```python
@app.post("/checkout")
async def checkout(cart_id: int, tasks: Tasks) -> dict:
    # Start payment processing immediately (concurrent)
    tasks.schedule(process_payment, cart_id)
    
    # Create order
    order = create_order_from_cart(cart_id)
    
    # Schedule logging before response is sent
    tasks.after_route.schedule(log_checkout_event, order.id)
    
    # Schedule notifications after response is sent
    tasks.after_response.schedule(send_order_confirmation, order.id)
    tasks.after_response.schedule(notify_warehouse, order.id)
    
    return {"order_id": order.id, "status": "processing"}
```

In this example:
1. Payment processing starts immediately (runs concurrently with endpoint)
2. Checkout event logging is scheduled after endpoint returns, before response
3. Email and warehouse notification are scheduled after response is sent

## Performance Considerations

### Immediate Tasks

- **Pros:** Maximize concurrency, utilize wait time
- **Cons:** May consume resources during request handling
- **Best for:** I/O-bound operations that don't compete with the main request

### After Route Tasks

- **Pros:** Scheduled before response, maintains execution ordering
- **Cons:** Minimal scheduling overhead
- **Best for:** Tasks that logically belong in the "after endpoint" phase

### After Response Tasks

- **Pros:** Fastest response time (no pre-response scheduling)
- **Cons:** Client doesn't know if task succeeded
- **Best for:** Non-critical operations, notifications, analytics

!!! note "Response Time Impact"
    All timing modes are fire-and-forget. The only impact on response time is the minimal overhead of scheduling tasks.
    Tasks themselves don't block the response - they run concurrently in the background.

## Execution Order Guarantees

Within a single endpoint:

1. **Immediate tasks** start first (when `schedule()` is called)
2. **After-route tasks** are scheduled in order after the endpoint returns
3. **After-response tasks** are scheduled in order after the response is sent

Between different timing modes, the scheduling order is guaranteed:
```
immediate → after_route → after_response
```

However, multiple immediate tasks run concurrently, so their completion order is not guaranteed.

## Next Steps

Now that you understand timing modes, learn how to get started:

- [First Steps](../tutorial_user_guide/first_steps.md) - Set up your first background task
- [Scheduling Tasks](../tutorial_user_guide/scheduling_tasks.md) - Learn the scheduling API in detail
