# Real World Examples

This tutorial provides complete, production-ready examples of using `fastapi-tasks` in real-world scenarios.

## Example 1: E-commerce Order Processing

Complete order processing with payment, inventory, and notifications:

```python
from fastapi import FastAPI, HTTPException
from fastapi_tasks import Tasks, add_tasks, Task
from pydantic import BaseModel
import httpx
import asyncio
from typing import List

app = FastAPI()
add_tasks(app)


# Models
class OrderItem(BaseModel):
    product_id: int
    quantity: int
    price: float


class OrderCreate(BaseModel):
    user_id: int
    email: str
    items: List[OrderItem]
    payment_token: str


# Database operations (simplified)
async def create_order_record(user_id: int, items: List[OrderItem]) -> int:
    # Create order in database
    order_id = 12345  # Generated ID
    return order_id


async def update_order_status(order_id: int, status: str) -> None:
    # Update order status
    pass


# Payment processing
async def process_payment(
    order_id: int,
    amount: float,
    payment_token: str
) -> dict:
    """Process payment through payment gateway"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.payment-gateway.com/charge",
            json={
                "amount": amount,
                "currency": "USD",
                "token": payment_token,
                "metadata": {"order_id": order_id}
            },
            headers={"Authorization": "Bearer YOUR_API_KEY"}
        )
        response.raise_for_status()
        return response.json()


async def payment_error_handler(task: Task, error: Exception) -> None:
    """Handle payment failures"""
    order_id = task.kwargs.get("order_id")
    
    # Update order status
    await update_order_status(order_id, "payment_failed")
    
    # Alert admin
    await send_slack_alert(f"Payment failed for order {order_id}: {error}")
    
    # Log to monitoring
    import sentry_sdk
    sentry_sdk.capture_exception(error)


# Inventory management
async def reserve_inventory(order_id: int, items: List[OrderItem]) -> None:
    """Reserve inventory for order"""
    async with db.transaction():
        for item in items:
            result = await db.execute(
                "UPDATE inventory SET reserved = reserved + ? "
                "WHERE product_id = ? AND available >= ?",
                item.quantity, item.product_id, item.quantity
            )
            
            if result.rowcount == 0:
                raise ValueError(f"Insufficient inventory for product {item.product_id}")
        
        # Record reservation
        await db.execute(
            "INSERT INTO reservations (order_id, items) VALUES (?, ?)",
            order_id, json.dumps([item.dict() for item in items])
        )


# Notifications
async def send_order_confirmation(email: str, order_id: int, items: List[OrderItem]) -> None:
    """Send order confirmation email"""
    total = sum(item.price * item.quantity for item in items)
    
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.email-service.com/send",
            json={
                "to": email,
                "subject": f"Order #{order_id} Confirmed",
                "template": "order_confirmation",
                "data": {
                    "order_id": order_id,
                    "items": [item.dict() for item in items],
                    "total": total
                }
            }
        )


async def notify_warehouse(order_id: int, items: List[OrderItem]) -> None:
    """Notify warehouse system to prepare shipment"""
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://warehouse-api.internal/prepare-shipment",
            json={
                "order_id": order_id,
                "items": [{"sku": item.product_id, "qty": item.quantity} for item in items]
            }
        )


# Analytics
async def track_order_event(event: str, order_id: int, metadata: dict) -> None:
    """Send analytics event"""
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://analytics.internal/track",
            json={
                "event": event,
                "properties": {
                    "order_id": order_id,
                    **metadata
                }
            }
        )


# Main endpoint
@app.post("/orders")
async def create_order(order_data: OrderCreate, tasks: Tasks) -> dict:
    """
    Create a new order with complete processing pipeline:
    1. Create order record
    2. Process payment (shielded, critical)
    3. Reserve inventory (before response)
    4. Send confirmation email (after response)
    5. Notify warehouse (after response)
    6. Track analytics (after response)
    """
    
    # Calculate total
    total_amount = sum(item.price * item.quantity for item in order_data.items)
    
    # Create order in database
    order_id = await create_order_record(order_data.user_id, order_data.items)
    
    # Process payment immediately (critical, shielded)
    tasks.task(
        name=f"payment_{order_id}",
        shield=True,
        on_error=payment_error_handler
    ).schedule(
        process_payment,
        order_id=order_id,
        amount=total_amount,
        payment_token=order_data.payment_token
    )
    
    # Reserve inventory before response (must complete)
    tasks.after_route.task(
        name=f"inventory_{order_id}",
        shield=True
    ).schedule(reserve_inventory, order_id, order_data.items)
    
    # Send confirmation email after response
    tasks.after_response.schedule(
        send_order_confirmation,
        order_data.email,
        order_id,
        order_data.items
    )
    
    # Notify warehouse after response
    tasks.after_response.schedule(
        notify_warehouse,
        order_id,
        order_data.items
    )
    
    # Track analytics after response
    tasks.after_response.schedule(
        track_order_event,
        "order_created",
        order_id,
        {
            "user_id": order_data.user_id,
            "total": total_amount,
            "items_count": len(order_data.items)
        }
    )
    
    return {
        "order_id": order_id,
        "status": "processing",
        "total": total_amount
    }
```

## Example 2: User Registration with Email Verification

Complete user registration flow with email verification:

```python
import secrets
from datetime import datetime, timedelta


# Models
class UserRegister(BaseModel):
    email: str
    password: str
    name: str


# Database operations
async def create_user_record(email: str, password_hash: str, name: str) -> int:
    user_id = await db.execute(
        "INSERT INTO users (email, password_hash, name, verified) VALUES (?, ?, ?, ?)",
        email, password_hash, name, False
    )
    return user_id


async def create_verification_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    await db.execute(
        "INSERT INTO verification_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        user_id, token, expires_at
    )
    
    return token


# Email operations
async def send_verification_email(email: str, token: str, name: str) -> None:
    """Send email verification link"""
    verification_url = f"https://yourapp.com/verify?token={token}"
    
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.email-service.com/send",
            json={
                "to": email,
                "subject": "Verify your email",
                "template": "email_verification",
                "data": {
                    "name": name,
                    "verification_url": verification_url
                }
            }
        )


async def send_welcome_email(email: str, name: str) -> None:
    """Send welcome email after verification"""
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.email-service.com/send",
            json={
                "to": email,
                "subject": "Welcome to Our App!",
                "template": "welcome",
                "data": {"name": name}
            }
        )


# Analytics
async def track_user_event(event: str, user_id: int, metadata: dict = None) -> None:
    """Track user events"""
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://analytics.internal/track",
            json={
                "user_id": user_id,
                "event": event,
                "timestamp": datetime.utcnow().isoformat(),
                "properties": metadata or {}
            }
        )


# Error handlers
async def email_error_handler(task: Task, error: Exception) -> None:
    """Handle email sending failures with retry"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            await task()  # Retry
            return
        except Exception as e:
            if attempt == max_retries - 1:
                # Final failure - log and alert
                import logging
                logging.error(f"Email task failed after {max_retries} retries: {e}")
                await send_slack_alert(f"Email delivery failed: {e}")


# Endpoints
@app.post("/register")
async def register_user(user_data: UserRegister, tasks: Tasks) -> dict:
    """Register a new user with email verification"""
    
    # Hash password (sync operation)
    import bcrypt
    password_hash = bcrypt.hashpw(
        user_data.password.encode(),
        bcrypt.gensalt()
    ).decode()
    
    # Create user record
    user_id = await create_user_record(
        user_data.email,
        password_hash,
        user_data.name
    )
    
    # Create verification token
    verification_token = await create_verification_token(user_id)
    
    # Send verification email (with retry on failure)
    tasks.after_response.task(
        name=f"verification_email_{user_id}",
        on_error=email_error_handler
    ).schedule(
        send_verification_email,
        user_data.email,
        verification_token,
        user_data.name
    )
    
    # Track registration event
    tasks.after_response.schedule(
        track_user_event,
        "user_registered",
        user_id,
        {"email": user_data.email}
    )
    
    return {
        "user_id": user_id,
        "message": "Registration successful. Please check your email to verify your account."
    }


@app.post("/verify")
async def verify_email(token: str, tasks: Tasks) -> dict:
    """Verify user email with token"""
    
    # Verify token
    result = await db.fetchone(
        "SELECT user_id FROM verification_tokens "
        "WHERE token = ? AND expires_at > ? AND used = FALSE",
        token, datetime.utcnow()
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    user_id = result["user_id"]
    
    # Mark user as verified
    await db.execute(
        "UPDATE users SET verified = TRUE WHERE id = ?",
        user_id
    )
    
    # Mark token as used
    await db.execute(
        "UPDATE verification_tokens SET used = TRUE WHERE token = ?",
        token
    )
    
    # Get user details
    user = await db.fetchone("SELECT email, name FROM users WHERE id = ?", user_id)
    
    # Send welcome email
    tasks.after_response.schedule(
        send_welcome_email,
        user["email"],
        user["name"]
    )
    
    # Track verification
    tasks.after_response.schedule(
        track_user_event,
        "email_verified",
        user_id
    )
    
    return {"message": "Email verified successfully"}
```

## Example 3: Image Processing Pipeline

Complete image upload and processing with thumbnails and CDN upload:

```python
from PIL import Image
import aiofiles
import os
from pathlib import Path


# Models
class ImageUpload(BaseModel):
    user_id: int


# Image processing (sync operations with PIL)
def create_thumbnail(source_path: str, thumb_path: str, size: tuple) -> None:
    """Create image thumbnail"""
    img = Image.open(source_path)
    img.thumbnail(size)
    img.save(thumb_path, optimize=True, quality=85)


def optimize_image(source_path: str, output_path: str) -> None:
    """Optimize image for web"""
    img = Image.open(source_path)
    img.save(output_path, optimize=True, quality=90)


# CDN upload
async def upload_to_cdn(local_path: str, cdn_path: str) -> str:
    """Upload file to CDN"""
    async with aiofiles.open(local_path, 'rb') as f:
        file_data = await f.read()
    
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"https://cdn-api.example.com/upload/{cdn_path}",
            content=file_data,
            headers={"Authorization": "Bearer YOUR_CDN_KEY"}
        )
        response.raise_for_status()
        return response.json()["url"]


# Database
async def save_image_record(
    user_id: int,
    original_url: str,
    optimized_url: str,
    thumbnail_url: str,
    metadata: dict
) -> int:
    """Save image record to database"""
    image_id = await db.execute(
        "INSERT INTO images (user_id, original_url, optimized_url, thumbnail_url, metadata) "
        "VALUES (?, ?, ?, ?, ?)",
        user_id, original_url, optimized_url, thumbnail_url, json.dumps(metadata)
    )
    return image_id


# Complete processing pipeline
async def process_uploaded_image(
    user_id: int,
    upload_path: str,
    filename: str
) -> None:
    """Complete image processing pipeline"""
    
    # Generate paths
    base_name = Path(filename).stem
    ext = Path(filename).suffix
    
    optimized_path = f"/tmp/{base_name}_optimized{ext}"
    thumb_path = f"/tmp/{base_name}_thumb{ext}"
    
    # Step 1: Create optimized version (sync)
    optimize_image(upload_path, optimized_path)
    
    # Step 2: Create thumbnail (sync)
    create_thumbnail(upload_path, thumb_path, (300, 300))
    
    # Step 3: Upload all versions to CDN (async, parallel)
    upload_tasks = [
        upload_to_cdn(upload_path, f"images/{user_id}/original/{filename}"),
        upload_to_cdn(optimized_path, f"images/{user_id}/optimized/{filename}"),
        upload_to_cdn(thumb_path, f"images/{user_id}/thumb/{filename}"),
    ]
    
    original_url, optimized_url, thumb_url = await asyncio.gather(*upload_tasks)
    
    # Step 4: Save to database
    image_id = await save_image_record(
        user_id,
        original_url,
        optimized_url,
        thumb_url,
        {
            "filename": filename,
            "upload_date": datetime.utcnow().isoformat()
        }
    )
    
    # Step 5: Cleanup temp files
    for path in [upload_path, optimized_path, thumb_path]:
        if os.path.exists(path):
            os.remove(path)
    
    # Step 6: Track analytics
    await track_user_event("image_uploaded", user_id, {"image_id": image_id})


# Error handler for image processing
async def image_processing_error(task: Task, error: Exception) -> None:
    """Handle image processing failures"""
    # Clean up temp files
    upload_path = task.args[1] if len(task.args) > 1 else None
    if upload_path and os.path.exists(upload_path):
        os.remove(upload_path)
    
    # Log error
    import logging
    logging.error(f"Image processing failed: {error}")


# Upload endpoint
@app.post("/upload-image")
async def upload_image(
    file: UploadFile,
    user_id: int,
    tasks: Tasks
) -> dict:
    """Upload and process image"""
    
    # Save uploaded file to temp location
    upload_path = f"/tmp/{file.filename}"
    
    async with aiofiles.open(upload_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Start processing immediately (long-running)
    tasks.task(
        name=f"process_image_{user_id}_{file.filename}",
        on_error=image_processing_error
    ).schedule(
        process_uploaded_image,
        user_id,
        upload_path,
        file.filename
    )
    
    return {
        "status": "processing",
        "message": "Image uploaded successfully and is being processed"
    }
```

## Example 4: Analytics Event Processing

Batch analytics event processing with retry and fallback:

```python
from collections import defaultdict
from datetime import datetime
import asyncio


# In-memory buffer for batching
event_buffer = defaultdict(list)
buffer_lock = asyncio.Lock()


async def flush_events_to_analytics(events: list[dict]) -> None:
    """Send batched events to analytics service"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://analytics.example.com/batch",
            json={"events": events}
        )
        response.raise_for_status()


async def save_events_to_db_fallback(events: list[dict]) -> None:
    """Fallback: Save events to database if analytics service fails"""
    await db.execute_many(
        "INSERT INTO analytics_events (event_type, user_id, properties, timestamp) "
        "VALUES (?, ?, ?, ?)",
        [
            (e["event"], e["user_id"], json.dumps(e["properties"]), e["timestamp"])
            for e in events
        ]
    )


async def analytics_error_handler(task: Task, error: Exception) -> None:
    """Handle analytics failures with fallback"""
    events = task.args[0] if task.args else []
    
    # Try fallback to database
    try:
        await save_events_to_db_fallback(events)
        import logging
        logging.warning(f"Analytics service failed, saved {len(events)} events to DB")
    except Exception as fallback_error:
        # Both failed - alert
        await send_slack_alert(
            f"Analytics pipeline failed completely: {error}\n"
            f"Fallback also failed: {fallback_error}\n"
            f"Lost {len(events)} events"
        )


# Batch processor
async def process_event_batch(events: list[dict], tasks: Tasks) -> None:
    """Process a batch of analytics events"""
    if not events:
        return
    
    tasks.task(
        name=f"analytics_batch_{len(events)}_events",
        on_error=analytics_error_handler
    ).schedule(flush_events_to_analytics, events)


# Track event endpoint
@app.post("/track")
async def track_event(
    event: str,
    user_id: int,
    properties: dict,
    tasks: Tasks
) -> dict:
    """Track an analytics event with batching"""
    
    event_data = {
        "event": event,
        "user_id": user_id,
        "properties": properties,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    async with buffer_lock:
        event_buffer[user_id].append(event_data)
        
        # Flush if buffer is large enough
        if len(event_buffer[user_id]) >= 10:
            events_to_flush = event_buffer[user_id].copy()
            event_buffer[user_id].clear()
            
            # Process batch in background
            await process_event_batch(events_to_flush, tasks)
    
    return {"status": "tracked"}
```

## Common Patterns Across Examples

### Pattern 1: Critical Operations First

Always process critical operations (payment, inventory) before non-critical ones (emails, analytics):

```python
# Critical: Payment
tasks.task(shield=True).schedule(process_payment, ...)

# Non-critical: Email
tasks.after_response.schedule(send_confirmation, ...)
```

### Pattern 2: Proper Error Handling

All production tasks should have error handlers:

```python
tasks.task(
    name="descriptive_name",
    on_error=appropriate_error_handler
).schedule(task_function, ...)
```

### Pattern 3: Shield Sparingly

Only shield operations that absolutely must complete:

```python
# Shield: Payment processing
tasks.task(shield=True).schedule(finalize_payment, ...)

# Don't shield: Email notifications
tasks.schedule(send_email, ...)  # Can retry if it fails
```

### Pattern 4: Use Timing Modes Appropriately

- **Immediate**: Long-running operations that don't affect the response
- **After-route**: Quick operations that must are scheduled before response
- **After-response**: All non-critical notifications and logging

## Next Steps

- [API Reference](../../api/tasks.md) - Complete API documentation
- [FAQ](../../faq/faq.md) - Common questions and answers
- [Error Handling](error_handling.md) - Deep dive into error handling patterns
