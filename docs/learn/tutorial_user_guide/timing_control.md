# Timing Control

In [Timing Modes](../background_tasks/timing_modes.md), you learned about the three timing modes available in `fastapi-tasks`.
This tutorial focuses on the practical usage of `after_route` and `after_response` timing modes.

!!! important "All Background Tasks are Fire-and-Forget"
    **Critical concept:** All background tasks in fastapi-tasks are fire-and-forget. They are scheduled
    at specific points in the request lifecycle, but they **DO NOT block the response**. The response is
    sent as soon as tasks are scheduled, not after they complete. Tasks run concurrently in the background.

## Quick Recap

- `tasks.schedule()` - Runs immediately (concurrent)
- `tasks.after_route.schedule()` - Scheduled after endpoint, before response
- `tasks.after_response.schedule()` - Runs after response is sent

## Using After-Route Tasks

Tasks scheduled with `after_route` are **scheduled after your endpoint function completes** but **before the response is sent** to the client. These tasks are fire-and-forget - they don't block the response, but are guaranteed to be scheduled before the client receives it.

### Basic Example

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)


async def log_request(endpoint: str, user_id: int) -> None:
    # Log to database
    print(f"User {user_id} accessed {endpoint}")


@app.get("/data")
async def get_data(user_id: int, tasks: Tasks) -> dict:
    data = {"result": [1, 2, 3]}
    
    # This is SCHEDULED after this function returns,
    # before the response is sent (but doesn't block the response)
    tasks.after_route.schedule(log_request, "/data", user_id)
    
    return data
```

### When to Use After-Route

Use `after_route` when you need to:

1. **Schedule tasks before response is sent** - Operations that must be scheduled before the client knows the request succeeded
2. **Audit logging** - Recording that an action was taken before confirming it to the client
3. **Cleanup operations** - Releasing resources or cleaning up state
4. **Pre-response validation** - Last-chance checks that don't affect the response data

### Real-World Example: Request Auditing

```python
from datetime import datetime


async def audit_log_to_db(
    user_id: int,
    action: str,
    resource_id: int,
    timestamp: datetime
) -> None:
    # Save to audit log database
    print(f"AUDIT: User {user_id} performed {action} on {resource_id} at {timestamp}")


@app.delete("/posts/{post_id}")
async def delete_post(post_id: int, user_id: int, tasks: Tasks) -> dict:
    # Delete the post
    delete_post_from_db(post_id)
    
    # Schedule audit log before response is sent
    # This ensures the log is scheduled (fire-and-forget) before confirming to client
    tasks.after_route.schedule(
        audit_log_to_db,
        user_id=user_id,
        action="delete_post",
        resource_id=post_id,
        timestamp=datetime.utcnow()
    )
    
    return {"status": "deleted", "post_id": post_id}
```

!!! warning "Response Time Impact"
    After-route tasks have minimal scheduling overhead. They are fire-and-forget (don't block response) to maintain good performance.

### Multiple After-Route Tasks

You can schedule multiple after-route tasks. They are scheduled in order:

```python
async def update_cache(key: str) -> None:
    print(f"Updating cache: {key}")


async def invalidate_related_cache(keys: list[str]) -> None:
    print(f"Invalidating: {keys}")


async def log_cache_update(key: str) -> None:
    print(f"Logged cache update: {key}")


@app.put("/items/{item_id}")
async def update_item(item_id: int, data: dict, tasks: Tasks) -> dict:
    update_item_in_db(item_id, data)
    
    # These are scheduled in order: update → invalidate → log
    tasks.after_route.schedule(update_cache, f"item:{item_id}")
    tasks.after_route.schedule(invalidate_related_cache, [f"items:list", f"items:count"])
    tasks.after_route.schedule(log_cache_update, f"item:{item_id}")
    
    return {"status": "updated"}
```

## Using After-Response Tasks

Tasks scheduled with `after_response` run **after the HTTP response has been sent** to the client.

This is the most common timing mode because it provides the fastest response times.

### Basic Example

```python
async def send_email(to: str, subject: str, body: str) -> None:
    # Simulate email sending
    print(f"Email sent to {to}: {subject}")


@app.post("/signup")
async def signup(email: str, password: str, tasks: Tasks) -> dict:
    user_id = create_user(email, password)
    
    # Email is sent AFTER the client receives the response
    tasks.after_response.schedule(
        send_email,
        to=email,
        subject="Welcome!",
        body="Thanks for signing up!"
    )
    
    return {"user_id": user_id}
```

### When to Use After-Response

Use `after_response` for:

1. **Notifications** - Emails, SMS, push notifications
2. **External API calls** - Webhooks, third-party integrations
3. **Analytics** - Event tracking, metrics collection
4. **Non-critical operations** - Anything that doesn't affect the response

### Real-World Example: Order Processing

```python
async def send_order_confirmation(email: str, order_id: int) -> None:
    print(f"Sending order confirmation to {email}")


async def notify_warehouse(order_id: int, items: list[dict]) -> None:
    print(f"Notifying warehouse about order {order_id}")


async def track_analytics(event: str, order_id: int, amount: float) -> None:
    print(f"Analytics: {event} - Order {order_id} - ${amount}")


@app.post("/orders")
async def create_order(
    user_email: str,
    items: list[dict],
    tasks: Tasks
) -> dict:
    # Create the order
    order_id = save_order(user_email, items)
    total_amount = calculate_total(items)
    
    # All these happen AFTER the response is sent
    tasks.after_response.schedule(
        send_order_confirmation,
        email=user_email,
        order_id=order_id
    )
    
    tasks.after_response.schedule(
        notify_warehouse,
        order_id=order_id,
        items=items
    )
    
    tasks.after_response.schedule(
        track_analytics,
        event="order_created",
        order_id=order_id,
        amount=total_amount
    )
    
    # Client gets this immediately
    return {
        "order_id": order_id,
        "status": "confirmed",
        "total": total_amount
    }
```

### Multiple After-Response Tasks

Like after-route tasks, multiple after-response tasks run in order:

```python
@app.post("/publish")
async def publish_article(article_id: int, tasks: Tasks) -> dict:
    publish_article_in_db(article_id)
    
    # These are scheduled in order: social → email → analytics
    tasks.after_response.schedule(post_to_social_media, article_id)
    tasks.after_response.schedule(send_newsletter, article_id)
    tasks.after_response.schedule(track_publication, article_id)
    
    return {"status": "published"}
```

## Combining All Three Timing Modes

You can use all three timing modes in a single endpoint for complex workflows:

```python
async def validate_payment(payment_id: int) -> None:
    print(f"Validating payment {payment_id}")


async def finalize_order(order_id: int) -> None:
    print(f"Finalizing order {order_id}")


async def send_confirmation_email(email: str, order_id: int) -> None:
    print(f"Sending confirmation to {email}")


async def notify_shipping(order_id: int) -> None:
    print(f"Notifying shipping for order {order_id}")


@app.post("/checkout")
async def checkout(
    cart_id: int,
    email: str,
    tasks: Tasks
) -> dict:
    # Start payment validation immediately (concurrent)
    payment_id = initiate_payment(cart_id)
    tasks.schedule(validate_payment, payment_id)
    
    # Create order
    order_id = create_order_from_cart(cart_id)
    
    # Schedule finalization before response is sent (fire-and-forget)
    tasks.after_route.schedule(finalize_order, order_id)
    
    # Send notifications after response (background)
    tasks.after_response.schedule(send_confirmation_email, email, order_id)
    tasks.after_response.schedule(notify_shipping, order_id)
    
    return {
        "order_id": order_id,
        "payment_id": payment_id,
        "status": "processing"
    }
```

**Execution timeline:**
1. `initiate_payment()` runs (in endpoint)
2. `validate_payment()` starts immediately (may still be running)
3. `create_order_from_cart()` runs (in endpoint)
4. Endpoint function completes
5. `finalize_order()` is scheduled (after-route, fire-and-forget)
6. Response sent to client: `{"order_id": ..., "payment_id": ..., "status": "processing"}`
7. `send_confirmation_email()` runs (after-response)
8. `notify_shipping()` runs (after-response)

## Accessing the Same Scheduler

The `after_route` and `after_response` properties return a scheduler object that has the same API as `tasks`:

```python
# These are equivalent
tasks.after_route.schedule(my_task)
tasks.after_route.task(name="my_task").schedule(my_function)

# You can also schedule multiple tasks from the same scheduler
after_resp = tasks.after_response
after_resp.schedule(task_1)
after_resp.schedule(task_2)
after_resp.task(shield=True).schedule(task_3)
```

## Choosing the Right Timing Mode

Here's a decision guide:

```
Does the operation affect the response data?
├─ YES → Run in endpoint function (not as background task)
└─ NO → Continue...

Must the operation be scheduled before client receives response?
├─ YES → Use tasks.after_route.schedule()
└─ NO → Continue...

Does the operation need to start as early as possible?
├─ YES → Use tasks.schedule() (immediate)
└─ NO → Use tasks.after_response.schedule()
```

## Timing Mode Comparison Table

| Mode | When it starts | Response blocks? | Use for | Typical duration |
|------|---------------|------------------|---------|------------------|
| **Immediate** | Right away | No | Concurrent processing | Any |
| **After Route** | After endpoint | No (fire-and-forget) | Pre-response scheduling | Any |
| **After Response** | After response | No | Notifications, analytics | Any |

## Performance Tips

### Optimize After-Route Tasks

Since After-route tasks have minimal scheduling overhead, keep them fast:

```python
# Good: Quick database insert
tasks.after_route.schedule(log_to_db, event_data)

# Bad: Slow external API call
tasks.after_route.schedule(call_slow_api, data)  # Use after_response instead!
```

### Use Immediate Tasks for CPU-Intensive Work

If you have CPU-intensive work that doesn't need to complete before responding:

```python
@app.post("/analyze")
async def analyze_data(data: dict, tasks: Tasks) -> dict:
    # Start heavy computation immediately (concurrent)
    tasks.schedule(run_ml_model, data)
    
    return {"status": "analyzing"}
```

### Batch After-Response Tasks

If you have many similar tasks, consider batching:

```python
async def send_bulk_notifications(user_ids: list[int], message: str) -> None:
    # Send to all users in one task
    for user_id in user_ids:
        send_notification(user_id, message)


@app.post("/broadcast")
async def broadcast_message(message: str, tasks: Tasks) -> dict:
    user_ids = get_all_user_ids()
    
    # One task instead of thousands
    tasks.after_response.schedule(send_bulk_notifications, user_ids, message)
    
    return {"recipients": len(user_ids)}
```

## Next Steps

Now that you understand timing control, learn about:

- [Task Configuration](task_configuration.md) - Add names, error handlers, and shielding
- [Sync and Async](sync_async.md) - Understand how sync and async tasks differ
- [Error Handling](../tutorial_advanced/error_handling.md) - Handle task failures gracefully
