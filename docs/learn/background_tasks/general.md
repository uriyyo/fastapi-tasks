# Background Tasks

## What are Background Tasks?

Background tasks are operations that run independently from the main request-response cycle of your web application.
Instead of making the client wait for all operations to complete, you can offload non-critical work to run in the background,
allowing your endpoint to return a response quickly.

## Why Use Background Tasks?

### Performance

Running all operations synchronously within a request handler can significantly slow down your API responses.
Background tasks allow you to defer time-consuming operations, reducing response times and improving overall application performance.

For example, sending an email confirmation might take 2-3 seconds. Without background tasks, your user would have to wait
that entire time before receiving a response. With background tasks, the response is instant.

### User Experience

Users expect fast, responsive applications. By moving non-essential operations to the background, you can provide
immediate feedback to users while still ensuring all necessary work gets done.

### Resource Optimization

Background tasks help you manage server resources more efficiently by:

- Allowing you to process multiple requests concurrently
- Preventing request timeouts on long-running operations
- Enabling better control over when and how tasks execute

### Separation of Concerns

Background tasks help maintain clean code architecture by separating the core business logic (that affects the response)
from ancillary operations (that can be scheduled asynchronously).

## Background Tasks in FastAPI

FastAPI provides a built-in `BackgroundTasks` class that runs tasks after the response is sent to the client.
This is useful for simple use cases, but it has limitations:

- Tasks **always** run after the response is sent
- No control over task execution timing
- Limited error handling options
- Tasks are cancelled if the server shuts down

## Enter `fastapi-tasks`

`fastapi-tasks` extends FastAPI's background task capabilities by providing:

**Precise Timing Control**

Choose exactly when your tasks are scheduled:

- **Immediately** - Start concurrent operations right away
- **After Route** - Schedule tasks before sending the response (fire-and-forget)
- **After Response** - Schedule tasks after the client receives the response

**Task Shielding**

Protect critical tasks from cancellation during server shutdown, ensuring important operations complete even when the server is stopping.

**Enhanced Error Handling**

Define custom error handlers for graceful failure recovery, logging, and retry logic.

**Type Safety**

Full type hints and generic support for better IDE integration and fewer runtime errors.

## When to Use `fastapi-tasks`

Use `fastapi-tasks` when you need:

- **Fine-grained timing control** - Different tasks need to be scheduled at different points in the request lifecycle
- **Critical task protection** - Some operations must complete even during shutdown (e.g., payment processing)
- **Advanced error handling** - Custom error recovery logic for different task types
- **Complex workflows** - Multiple tasks with different timing and error handling requirements

For simple "fire and forget" tasks that always are scheduled after the response, FastAPI's built-in `BackgroundTasks` may be sufficient.

## Common Use Cases

### Email Notifications

Send welcome emails, password reset links, or order confirmations without making users wait.

```python
@app.post("/users")
async def create_user(email: str, tasks: Tasks) -> dict:
    user_id = create_user_in_db(email)
    
    # Send email after response is sent
    tasks.after_response.schedule(send_welcome_email, email)
    
    return {"user_id": user_id}
```

### Analytics and Logging

Track user actions and API usage without impacting response times.

```python
@app.post("/orders")
async def create_order(order_data: dict, tasks: Tasks) -> dict:
    order = save_order(order_data)
    
    # Log analytics immediately, concurrently with response
    tasks.schedule(track_order_event, order.id, "created")
    
    return {"order_id": order.id}
```

### Data Processing

Generate thumbnails, process uploads, or update search indexes asynchronously.

```python
@app.post("/upload")
async def upload_image(file: UploadFile, tasks: Tasks) -> dict:
    file_path = save_file(file)
    
    # Start processing immediately
    tasks.schedule(generate_thumbnails, file_path)
    tasks.schedule(update_search_index, file_path)
    
    return {"status": "uploaded", "path": file_path}
```

### Cache Management

Warm caches or invalidate stale data after updates.

```python
@app.put("/products/{product_id}")
async def update_product(product_id: int, data: dict, tasks: Tasks) -> dict:
    product = update_product_in_db(product_id, data)
    
    # Clear cache after response is sent
    tasks.after_response.schedule(invalidate_product_cache, product_id)
    
    return {"product": product}
```

## Next Steps

Now that you understand what background tasks are and why they're useful, learn about the different timing modes
that make `fastapi-tasks` powerful:

- [Timing Modes](timing_modes.md) - Deep dive into immediate, after-route, and after-response execution
- [First Steps](../tutorial_user_guide/first_steps.md) - Get started with your first background task
