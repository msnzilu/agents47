"""
Webhook System Models
Phase 7: Integration Layer & Embeddability
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import URLValidator
import secrets
import hashlib
import hmac


class Webhook(models.Model):
    """
    Webhook configuration for event subscriptions
    """
    
    EVENT_CHOICES = [
        ('conversation.created', 'Conversation Created'),
        ('conversation.updated', 'Conversation Updated'),
        ('message.sent', 'Message Sent'),
        ('message.received', 'Message Received'),
        ('escalation.triggered', 'Escalation Triggered'),
        ('agent.created', 'Agent Created'),
        ('agent.updated', 'Agent Updated'),
        ('tool.executed', 'Tool Executed'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='webhooks'
    )
    
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        related_name='webhooks',
        null=True,
        blank=True,
        help_text='Specific agent to subscribe to (optional, leave blank for all)'
    )
    
    url = models.URLField(
        max_length=500,
        validators=[URLValidator()],
        help_text='URL to send webhook events to'
    )
    
    event_types = models.JSONField(
        default=list,
        help_text='List of event types to subscribe to'
    )
    
    secret = models.CharField(
        max_length=64,
        help_text='Secret key for HMAC signature verification'
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text='Enable/disable webhook'
    )
    
    description = models.TextField(
        blank=True,
        help_text='Optional description of webhook purpose'
    )
    
    # Retry configuration
    max_retries = models.IntegerField(
        default=3,
        help_text='Maximum number of retry attempts'
    )
    
    retry_delay_seconds = models.IntegerField(
        default=60,
        help_text='Initial delay between retries (exponential backoff)'
    )
    
    timeout_seconds = models.IntegerField(
        default=30,
        help_text='HTTP request timeout in seconds'
    )
    
    # Statistics
    total_deliveries = models.IntegerField(
        default=0,
        help_text='Total number of delivery attempts'
    )
    
    successful_deliveries = models.IntegerField(
        default=0,
        help_text='Number of successful deliveries'
    )
    
    failed_deliveries = models.IntegerField(
        default=0,
        help_text='Number of failed deliveries'
    )
    
    last_delivery_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp of last delivery attempt'
    )
    
    last_success_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp of last successful delivery'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('webhook')
        verbose_name_plural = _('webhooks')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['agent', 'is_active']),
            models.Index(fields=['event_types']),
        ]
    
    def __str__(self):
        return f"Webhook: {self.url} ({', '.join(self.event_types)})"
    
    def save(self, *args, **kwargs):
        # Generate secret if not set
        if not self.secret:
            self.secret = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
    
    def generate_signature(self, payload: str) -> str:
        """
        Generate HMAC signature for payload
        
        Args:
            payload: JSON string of webhook payload
            
        Returns:
            HMAC signature as hex string
        """
        return hmac.new(
            self.secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify_signature(self, payload: str, signature: str) -> bool:
        """
        Verify HMAC signature
        
        Args:
            payload: JSON string of webhook payload
            signature: Signature to verify
            
        Returns:
            True if signature is valid
        """
        expected_signature = self.generate_signature(payload)
        return hmac.compare_digest(expected_signature, signature)
    
    def should_trigger(self, event_type: str, agent_id: int = None) -> bool:
        """
        Check if webhook should trigger for given event
        
        Args:
            event_type: Type of event
            agent_id: Agent ID associated with event
            
        Returns:
            True if webhook should trigger
        """
        if not self.is_active:
            return False
        
        if event_type not in self.event_types:
            return False
        
        # If webhook is agent-specific, check agent ID
        if self.agent_id and agent_id != self.agent_id:
            return False
        
        return True


class WebhookDelivery(models.Model):
    """
    Record of webhook delivery attempts
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sending', 'Sending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    ]
    
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    
    event_type = models.CharField(
        max_length=50,
        help_text='Type of event that triggered webhook'
    )
    
    payload = models.JSONField(
        help_text='Event payload sent to webhook'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Delivery details
    attempt_count = models.IntegerField(
        default=0,
        help_text='Number of delivery attempts made'
    )
    
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Scheduled time for next retry'
    )
    
    # Response details
    response_status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text='HTTP status code from webhook endpoint'
    )
    
    response_body = models.TextField(
        blank=True,
        help_text='Response body from webhook endpoint'
    )
    
    response_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text='Response time in milliseconds'
    )
    
    error_message = models.TextField(
        blank=True,
        help_text='Error message if delivery failed'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when successfully delivered'
    )
    
    class Meta:
        verbose_name = _('webhook delivery')
        verbose_name_plural = _('webhook deliveries')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook', 'status']),
            models.Index(fields=['status', 'next_retry_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} to {self.webhook.url} - {self.status}"
    
    def is_retryable(self) -> bool:
        """Check if delivery can be retried"""
        return (
            self.status in ['failed', 'retrying'] and
            self.attempt_count < self.webhook.max_retries
        )
    
    def mark_success(self, response_status: int, response_body: str, response_time_ms: int):
        """Mark delivery as successful"""
        from django.utils import timezone
        
        self.status = 'success'
        self.response_status_code = response_status
        self.response_body = response_body[:10000]  # Limit size
        self.response_time_ms = response_time_ms
        self.delivered_at = timezone.now()
        self.save()
        
        # Update webhook stats
        self.webhook.successful_deliveries += 1
        self.webhook.last_success_at = timezone.now()
        self.webhook.last_delivery_at = timezone.now()
        self.webhook.save()
    
    def mark_failed(self, error_message: str, response_status: int = None):
        """Mark delivery as failed"""
        from django.utils import timezone
        
        self.status = 'failed'
        self.error_message = error_message[:5000]  # Limit size
        self.response_status_code = response_status
        self.save()
        
        # Update webhook stats
        self.webhook.failed_deliveries += 1
        self.webhook.last_delivery_at = timezone.now()
        self.webhook.save()
    
    def schedule_retry(self):
        """Schedule next retry with exponential backoff"""
        from django.utils import timezone
        
        if not self.is_retryable():
            return False
        
        self.status = 'retrying'
        self.attempt_count += 1
        
        # Exponential backoff: delay * (2 ^ attempt_count)
        delay_seconds = self.webhook.retry_delay_seconds * (2 ** self.attempt_count)
        self.next_retry_at = timezone.now() + timezone.timedelta(seconds=delay_seconds)
        
        self.save()
        return True