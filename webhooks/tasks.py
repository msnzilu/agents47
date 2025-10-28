"""
Webhook Delivery Tasks (Celery)
Phase 7: Integration Layer & Embeddability
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
import requests
import json
import logging
import time
from django.db import models

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def deliver_webhook(self, webhook_delivery_id: int):
    """
    Deliver webhook to configured endpoint
    
    Args:
        webhook_delivery_id: ID of WebhookDelivery instance
    """
    from webhooks.models import WebhookDelivery
    
    try:
        delivery = WebhookDelivery.objects.select_related('webhook').get(
            id=webhook_delivery_id
        )
    except WebhookDelivery.DoesNotExist:
        logger.error(f"WebhookDelivery {webhook_delivery_id} not found")
        return
    
    webhook = delivery.webhook
    
    # Check if webhook is still active
    if not webhook.is_active:
        delivery.mark_failed("Webhook is not active")
        return
    
    # Prepare payload
    payload_str = json.dumps(delivery.payload)
    signature = webhook.generate_signature(payload_str)
    
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'AI-Agent-Platform-Webhook/1.0',
        'X-Webhook-Signature': signature,
        'X-Webhook-Event': delivery.event_type,
        'X-Webhook-Delivery-ID': str(delivery.id),
        'X-Webhook-Timestamp': delivery.created_at.isoformat(),
    }
    
    # Update status
    delivery.status = 'sending'
    delivery.save()
    
    start_time = time.time()
    
    try:
        # Send webhook
        response = requests.post(
            webhook.url,
            json=delivery.payload,
            headers=headers,
            timeout=webhook.timeout_seconds
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Check if successful (2xx status code)
        if 200 <= response.status_code < 300:
            delivery.mark_success(
                response_status=response.status_code,
                response_body=response.text,
                response_time_ms=response_time_ms
            )
            logger.info(
                f"Webhook delivered successfully: {delivery.event_type} to {webhook.url}"
            )
        else:
            # Non-2xx status code
            error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
            
            if delivery.is_retryable():
                delivery.schedule_retry()
                logger.warning(
                    f"Webhook delivery failed, will retry: {delivery.event_type} "
                    f"to {webhook.url} - {error_msg}"
                )
                # Schedule retry task
                deliver_webhook.apply_async(
                    args=[webhook_delivery_id],
                    eta=delivery.next_retry_at
                )
            else:
                delivery.mark_failed(error_msg, response.status_code)
                logger.error(
                    f"Webhook delivery failed (no more retries): "
                    f"{delivery.event_type} to {webhook.url} - {error_msg}"
                )
    
    except requests.exceptions.Timeout:
        error_msg = f"Request timeout after {webhook.timeout_seconds}s"
        
        if delivery.is_retryable():
            delivery.schedule_retry()
            logger.warning(f"Webhook timeout, will retry: {webhook.url}")
            deliver_webhook.apply_async(
                args=[webhook_delivery_id],
                eta=delivery.next_retry_at
            )
        else:
            delivery.mark_failed(error_msg)
            logger.error(f"Webhook timeout (no more retries): {webhook.url}")
    
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Connection error: {str(e)}"
        
        if delivery.is_retryable():
            delivery.schedule_retry()
            logger.warning(f"Webhook connection error, will retry: {webhook.url}")
            deliver_webhook.apply_async(
                args=[webhook_delivery_id],
                eta=delivery.next_retry_at
            )
        else:
            delivery.mark_failed(error_msg)
            logger.error(f"Webhook connection error (no more retries): {webhook.url}")
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        delivery.mark_failed(error_msg)
        logger.error(f"Webhook delivery error: {webhook.url} - {error_msg}", exc_info=True)


@shared_task
def cleanup_old_webhook_deliveries(days=30):
    """
    Clean up old webhook delivery records
    
    Args:
        days: Number of days to keep records
    """
    from webhooks.models import WebhookDelivery
    
    cutoff_date = timezone.now() - timezone.timedelta(days=days)
    
    deleted_count, _ = WebhookDelivery.objects.filter(
        created_at__lt=cutoff_date,
        status='success'
    ).delete()
    
    logger.info(f"Cleaned up {deleted_count} old webhook delivery records")
    return deleted_count


@shared_task
def process_pending_webhook_retries():
    """
    Process webhooks scheduled for retry
    """
    from webhooks.models import WebhookDelivery
    
    now = timezone.now()
    
    # Get deliveries ready for retry
    pending_retries = WebhookDelivery.objects.filter(
        status='retrying',
        next_retry_at__lte=now
    )
    
    count = 0
    for delivery in pending_retries:
        deliver_webhook.delay(delivery.id)
        count += 1
    
    if count > 0:
        logger.info(f"Scheduled {count} webhook retries")
    
    return count


def trigger_webhook_event(event_type: str, payload: dict, agent_id: int = None):
    """
    Trigger webhook event for all subscribed webhooks
    
    Args:
        event_type: Type of event
        payload: Event data
        agent_id: Optional agent ID associated with event
    """
    from webhooks.models import Webhook, WebhookDelivery
    
    # Find matching webhooks
    webhooks = Webhook.objects.filter(is_active=True)
    
    # Filter by event type
    webhooks = webhooks.filter(event_types__contains=[event_type])
    
    # Filter by agent if specified
    if agent_id:
        webhooks = webhooks.filter(
            models.Q(agent_id=agent_id) | models.Q(agent_id__isnull=True)
        )
    
    # Create delivery records and queue tasks
    for webhook in webhooks:
        if webhook.should_trigger(event_type, agent_id):
            delivery = WebhookDelivery.objects.create(
                webhook=webhook,
                event_type=event_type,
                payload=payload,
                status='pending'
            )
            
            # Update webhook stats
            webhook.total_deliveries += 1
            webhook.save()
            
            # Queue delivery task
            deliver_webhook.delay(delivery.id)
            
            logger.debug(
                f"Queued webhook delivery: {event_type} to {webhook.url} "
                f"(delivery_id={delivery.id})"
            )