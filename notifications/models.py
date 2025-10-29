"""
Notifications models
Real-time user notifications system
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class Notification(models.Model):
    """User notifications"""
    
    NOTIFICATION_TYPES = [
        ('agent_created', 'Agent Created'),
        ('agent_deleted', 'Agent Deleted'),
        ('agent_deployed', 'Agent Deployed'),
        ('agent_error', 'Agent Error'),
        ('conversation_started', 'Conversation Started'),
        ('message_received', 'Message Received'),
        ('escalation_triggered', 'Escalation Triggered'),
        ('performance_alert', 'Performance Alert'),
        ('usage_limit', 'Usage Limit'),
        ('integration_connected', 'Integration Connected'),
        ('integration_failed', 'Integration Failed'),
        ('document_processed', 'Document Processed'),
        ('webhook_failed', 'Webhook Failed'),
        ('system_update', 'System Update'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        db_index=True
    )
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_LEVELS,
        default='medium',
        db_index=True
    )
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Optional link
    link_url = models.CharField(max_length=500, blank=True, null=True)
    link_text = models.CharField(max_length=100, blank=True, null=True)
    
    # Related objects (optional)
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    conversation = models.ForeignKey(
        'chat.Conversation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['user', 'notification_type']),
            models.Index(fields=['priority', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def mark_as_unread(self):
        """Mark notification as unread"""
        self.is_read = False
        self.read_at = None
        self.save()
    
    def archive(self):
        """Archive notification"""
        self.is_archived = True
        self.archived_at = timezone.now()
        self.save()
    
    def get_icon_class(self):
        """Get CSS class for notification icon"""
        icon_map = {
            'agent_created': 'bg-blue-100 text-blue-600',
            'agent_deleted': 'bg-red-100 text-red-600',
            'agent_deployed': 'bg-green-100 text-green-600',
            'agent_error': 'bg-red-100 text-red-600',
            'conversation_started': 'bg-indigo-100 text-indigo-600',
            'escalation_triggered': 'bg-red-100 text-red-600',
            'performance_alert': 'bg-yellow-100 text-yellow-600',
            'document_processed': 'bg-purple-100 text-purple-600',
            'system_update': 'bg-gray-100 text-gray-600',
        }
        return icon_map.get(self.notification_type, 'bg-gray-100 text-gray-600')
    
    def get_icon_svg(self):
        """Get SVG path for notification icon"""
        icons = {
            'agent_created': 'M12 4v16m8-8H4',
            'agent_deleted': 'M12 4v16m8-8H4',
            'agent_deployed': 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
            'agent_error': 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
            'conversation_started': 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
            'escalation_triggered': 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
            'performance_alert': 'M13 10V3L4 14h7v7l9-11h-7z',
            'document_processed': 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
            'system_update': 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
        }
        return icons.get(self.notification_type, 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9')
    
    @staticmethod
    def create_notification(user, notification_type, title, message, **kwargs):
        """Helper method to create notifications"""
        return Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            **kwargs
        )


class NotificationPreference(models.Model):
    """User notification preferences"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Email notifications
    email_enabled = models.BooleanField(default=True)
    email_agent_created = models.BooleanField(default=True)
    email_agent_error = models.BooleanField(default=True)
    email_escalation = models.BooleanField(default=True)
    email_performance_alert = models.BooleanField(default=True)
    
    # In-app notifications
    inapp_enabled = models.BooleanField(default=True)
    inapp_agent_created = models.BooleanField(default=True)
    inapp_conversation_started = models.BooleanField(default=True)
    inapp_document_processed = models.BooleanField(default=True)
    
    # Digest settings
    daily_digest = models.BooleanField(default=False)
    weekly_digest = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.user.email}"