# Task Shielding

Task shielding protects critical tasks from cancellation during server shutdown. This tutorial explains
when and how to use shielding effectively.

## What is Task Shielding?

When your FastAPI application shuts down (e.g., during deployment or restart), all running tasks are normally cancelled.
Shielding prevents this cancellation, allowing critical tasks to complete even as the server stops.

```python
from fastapi import FastAPI
from fastapi_tasks import Tasks, add_tasks

app = FastAPI()
add_tasks(app)


async def critical_task() -> None:
    # This task MUST complete
    await finalize_database_transaction()


async def non_critical_task() -> None:
    # This task can be cancelled
    await send_newsletter()


@app.post("/tasks")
async def create_tasks(tasks: Tasks) -> dict:
    # This task is protected from cancellation
    tasks.task(shield=True).schedule(critical_task)
    
    # This task will be cancelled if server shuts down
    tasks.schedule(non_critical_task)
    
    return {"status": "ok"}
```

## How Shielding Works

Internally, shielded tasks run within an `anyio.CancelScope` with `shield=True`:

```python
# What happens under the hood
async def run_task(task, shielded: bool) -> None:
    async with anyio.CancelScope(shield=shielded):
        await task()
```

When the server shuts down:
- **Non-shielded tasks**: Cancelled immediately
- **Shielded tasks**: Allowed to complete before shutdown finishes

!!! warning "Shutdown Delay"
    Shielded tasks delay server shutdown. Use them only for truly critical operations.

## When to Use Shielding

Use `shield=True` for tasks that:

1. **Modify critical state** - Database transactions, file writes
2. **Handle money** - Payment processing, refunds
3. **Send important notifications** - Critical alerts, fraud warnings
4. **Release resources** - Cleanup operations that prevent leaks
5. **Must complete for correctness** - Operations where partial completion causes problems

### Example: Payment Processing

```python
async def finalize_payment(
    payment_id: int,
    amount: float,
    card_token: str
) -> None:
    """Critical: Must complete to avoid partial charges"""
    # Start database transaction
    async with db.transaction():
        # Update payment status
        await db.execute(
            "UPDATE payments SET status = 'processing' WHERE id = ?",
            payment_id
        )
        
        # Charge the card (external API)
        charge_result = await stripe.charge(card_token, amount)
        
        # Record the charge
        await db.execute(
            "UPDATE payments SET status = 'completed', charge_id = ? WHERE id = ?",
            charge_result.id, payment_id
        )
        
        # Send receipt
        await send_receipt(payment_id)


@app.post("/payments")
async def process_payment(
    payment_id: int,
    amount: float,
    card_token: str,
    tasks: Tasks
) -> dict:
    # Shield this task - partial payment processing would be bad!
    tasks.task(
        name=f"payment_{payment_id}",
        shield=True
    ).schedule(finalize_payment, payment_id, amount, card_token)
    
    return {"payment_id": payment_id, "status": "processing"}
```

## When NOT to Use Shielding

Don't shield tasks that:

1. **Are idempotent** - Can be safely retried
2. **Don't modify state** - Read-only operations
3. **Take a long time** - Will significantly delay shutdown
4. **Are non-critical** - Emails, analytics, logs

### Example: Don't Shield Emails

```python
# BAD: Don't shield emails
tasks.task(shield=True).schedule(send_welcome_email, email)

# GOOD: Emails can be resent if they fail
tasks.schedule(send_welcome_email, email)
```

If an email doesn't send because the server restarted, it's not the end of the world.
You can retry it later or send it through a proper message queue.

## Shielding with Different Timing Modes

Shielding works with all timing modes:

### Immediate Tasks

```python
@app.post("/immediate")
async def immediate_shielded(tasks: Tasks) -> dict:
    # Starts now, protected from cancellation
    tasks.task(shield=True).schedule(critical_immediate_task)
    
    return {"status": "ok"}
```

### After-Route Tasks

```python
@app.post("/after-route")
async def after_route_shielded(tasks: Tasks) -> dict:
    # Runs before response, protected from cancellation
    tasks.after_route.task(shield=True).schedule(critical_cleanup)
    
    return {"status": "ok"}
```

### After-Response Tasks

```python
@app.post("/after-response")
async def after_response_shielded(tasks: Tasks) -> dict:
    # Runs after response, protected from cancellation
    tasks.after_response.task(shield=True).schedule(critical_notification)
    
    return {"status": "ok"}
```

## Combining Shielding with Error Handling

Critical tasks should have both shielding and error handling:

```python
async def payment_error_handler(task: Task, error: Exception) -> None:
    """Handle payment failures"""
    # Alert immediately
    await send_slack_alert(f"🚨 Payment task failed: {error}")
    
    # Log to error tracking
    await send_to_sentry(task, error)
    
    # Mark payment as failed in database
    payment_id = task.kwargs.get("payment_id")
    if payment_id:
        await mark_payment_failed(payment_id, str(error))


@app.post("/protected-payment")
async def protected_payment(payment_id: int, tasks: Tasks) -> dict:
    tasks.task(
        name=f"payment_{payment_id}",
        shield=True,
        on_error=payment_error_handler
    ).schedule(process_payment_internal, payment_id=payment_id)
    
    return {"status": "processing"}
```

## Real-World Examples

### Example 1: Database Transaction

```python
async def update_inventory_transaction(order_id: int, items: list[dict]) -> None:
    """Critical: Inventory must be updated atomically"""
    async with db.transaction():
        for item in items:
            # Decrement inventory
            await db.execute(
                "UPDATE inventory SET quantity = quantity - ? WHERE product_id = ?",
                item["quantity"], item["product_id"]
            )
            
            # Record the allocation
            await db.execute(
                "INSERT INTO allocations (order_id, product_id, quantity) VALUES (?, ?, ?)",
                order_id, item["product_id"], item["quantity"]
            )
        
        # Mark order as allocated
        await db.execute(
            "UPDATE orders SET status = 'allocated' WHERE id = ?",
            order_id
        )


@app.post("/orders")
async def create_order(items: list[dict], tasks: Tasks) -> dict:
    order_id = await create_order_record(items)
    
    # Shield - partial inventory updates are bad
    tasks.task(
        name=f"inventory_update_{order_id}",
        shield=True
    ).schedule(update_inventory_transaction, order_id, items)
    
    return {"order_id": order_id}
```

### Example 2: File Upload Finalization

```python
import aiofiles
import os


async def finalize_upload(temp_path: str, final_path: str, metadata: dict) -> None:
    """Critical: Must move file and update database atomically"""
    try:
        # Move file from temp to permanent storage
        async with aiofiles.open(temp_path, 'rb') as src:
            async with aiofiles.open(final_path, 'wb') as dst:
                await dst.write(await src.read())
        
        # Delete temp file
        os.remove(temp_path)
        
        # Update database with final path
        await db.execute(
            "INSERT INTO files (path, size, mime_type) VALUES (?, ?, ?)",
            final_path, metadata["size"], metadata["mime_type"]
        )
        
    except Exception as e:
        # Cleanup on error
        if os.path.exists(final_path):
            os.remove(final_path)
        raise


@app.post("/upload")
async def upload_file(file: UploadFile, tasks: Tasks) -> dict:
    # Save to temp location
    temp_path = f"/tmp/{file.filename}"
    final_path = f"/storage/{file.filename}"
    
    metadata = {
        "size": file.size,
        "mime_type": file.content_type
    }
    
    # Shield - partial file operations cause orphaned files
    tasks.task(
        name=f"finalize_upload_{file.filename}",
        shield=True
    ).schedule(finalize_upload, temp_path, final_path, metadata)
    
    return {"status": "uploading", "filename": file.filename}
```

### Example 3: Multi-Service Coordination

```python
async def coordinate_services(order_id: int) -> None:
    """Critical: All services must be notified"""
    services = [
        ("inventory", "http://inventory-service/reserve"),
        ("shipping", "http://shipping-service/prepare"),
        ("billing", "http://billing-service/charge"),
    ]
    
    results = []
    
    for service_name, url in services:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"order_id": order_id})
                results.append((service_name, "success"))
        except Exception as e:
            results.append((service_name, "failed"))
            # Log but continue - we need to notify all services
            logger.error(f"Failed to notify {service_name}: {e}")
    
    # Record coordination results
    await db.execute(
        "INSERT INTO service_coordination (order_id, results) VALUES (?, ?)",
        order_id, json.dumps(results)
    )


@app.post("/coordinate")
async def coordinate_order(order_id: int, tasks: Tasks) -> dict:
    # Shield - all services must be notified
    tasks.task(
        name=f"coordinate_{order_id}",
        shield=True
    ).schedule(coordinate_services, order_id)
    
    return {"status": "coordinating"}
```

## Shielding Best Practices

### 1. Be Selective

Only shield truly critical tasks:

```python
# Good: Critical tasks only
tasks.task(shield=True).schedule(finalize_payment, ...)
tasks.task(shield=True).schedule(commit_transaction, ...)

# Bad: Everything shielded
tasks.task(shield=True).schedule(send_email, ...)  # Not critical!
tasks.task(shield=True).schedule(log_analytics, ...)  # Not critical!
```

### 2. Keep Shielded Tasks Short

Shielded tasks delay shutdown:

```python
# Good: Quick, focused operation
async def quick_critical_task() -> None:
    async with db.transaction():
        await db.execute("UPDATE accounts SET ...")


# Bad: Long-running operation
async def slow_critical_task() -> None:
    for item in huge_list:  # Takes 10 minutes!
        await process_item(item)
```

### 3. Always Add Error Handling

Shielded tasks should never fail silently:

```python
# Good: Shield + error handling
tasks.task(
    shield=True,
    on_error=critical_error_handler
).schedule(important_task)


# Risky: Shield without error handling
tasks.task(shield=True).schedule(important_task)
```

### 4. Name Shielded Tasks

Make it clear which tasks are critical:

```python
# Good: Descriptive name
tasks.task(
    name="finalize_payment_12345",
    shield=True
).schedule(...)


# Less clear
tasks.task(shield=True).schedule(...)
```

### 5. Document Why Tasks Are Shielded

```python
async def finalize_payment(payment_id: int) -> None:
    """
    Finalize payment processing.
    
    This task is shielded because partial payment processing
    could result in charging a customer without recording it,
    or recording a charge without actually charging the customer.
    """
    ...


@app.post("/payments")
async def process_payment(tasks: Tasks) -> dict:
    # Shielded: See finalize_payment docstring for reasoning
    tasks.task(shield=True).schedule(finalize_payment, ...)
    ...
```

## Testing Shielded Tasks

How to test that shielding works:

```python
import pytest
from fastapi.testclient import TestClient
import asyncio


async def test_shielded_task_completes():
    """Test that shielded task completes even with cancellation"""
    completed = False
    
    async def shielded_task() -> None:
        nonlocal completed
        await asyncio.sleep(1)  # Simulate work
        completed = True
    
    @app.post("/test-shield")
    async def test_endpoint(tasks: Tasks) -> dict:
        tasks.task(shield=True).schedule(shielded_task)
        return {"status": "ok"}
    
    # Start the task
    client = TestClient(app)
    response = client.post("/test-shield")
    
    # Simulate server shutdown (cancel scope)
    # In real scenario, this happens when server shuts down
    await asyncio.sleep(0.5)  # Task is running
    
    # Even if we try to cancel, shielded task should complete
    await asyncio.sleep(1)  # Wait for completion
    
    assert completed is True
```

## Common Pitfalls

### Pitfall 1: Over-Shielding

```python
# BAD: Shielding everything
@app.post("/bad")
async def bad_endpoint(tasks: Tasks) -> dict:
    tasks.task(shield=True).schedule(send_email)
    tasks.task(shield=True).schedule(log_event)
    tasks.task(shield=True).schedule(update_cache)
    # Now shutdown takes forever!
```

### Pitfall 2: Long-Running Shielded Tasks

```python
# BAD: Shielding a slow task
async def process_all_users() -> None:
    for user in all_users:  # Could be millions!
        await process_user(user)

tasks.task(shield=True).schedule(process_all_users)
# Server can't shut down until this completes!
```

### Pitfall 3: Shielding Without Idempotency

```python
# BAD: Shielding non-idempotent operation
async def send_duplicate_charges() -> None:
    await charge_customer()  # If this runs twice, customer charged twice!
    # No protection against duplicate charges

tasks.task(shield=True).schedule(send_duplicate_charges)
```

Make sure shielded tasks are idempotent or have safeguards against duplicate execution.

## Graceful Degradation

For operations that are important but can tolerate cancellation:

```python
async def important_but_retriable_task() -> None:
    """Important task that can be retried if cancelled"""
    try:
        async with anyio.CancelScope() as scope:
            # Do important work
            await process_data()
    except anyio.get_cancelled_exc_class():
        # Log that we were cancelled
        logger.warning("Task was cancelled, will be retried later")
        # Add to persistent queue for retry
        await queue.add_for_retry("important_task")
        raise


@app.post("/important")
async def important_endpoint(tasks: Tasks) -> dict:
    # Don't shield, but handle cancellation gracefully
    tasks.schedule(important_but_retriable_task)
    return {"status": "ok"}
```

## Next Steps

- [Real World Examples](real_world_examples.md) - See shielding in complete production scenarios
- [Error Handling](error_handling.md) - Combine shielding with error handling
- [API Reference: TaskConfig](../../api/task_config.md) - Complete API documentation
