"""
Chat models for conversations and messages.
Phase 1: Foundation & Authentication
Phase 3-4: Complete implementation
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Conversation(models.Model):
    """
    Conversation session between user and agent.
    """
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    
    title = models.CharField(
        max_length=255,
        blank=True,
        default='New Conversation',
        help_text=_('Auto-generated or user-set title')
    )
    # Add the missing user field
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='conversations',
        help_text=_('User who owns this conversation')
    )
    
    # Session tracking
    session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Session identifier for grouping related conversations')
    )
    
    CHANNEL_CHOICES = [
        ('web', 'Web Chat'),
        ('api', 'API'),
        ('email', 'Email'),
        ('slack', 'Slack'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
    ]
    
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default='web'
    )
    
    channel_identifier = models.CharField(
        max_length=255,
        blank=True,
        help_text='External channel ID (email, phone, etc.)'
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Additional metadata about the conversation')
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = _('conversation')
        verbose_name_plural = _('conversations')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['agent', '-updated_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.agent.name}"
    
    def message_count(self):
        """Return number of messages in this conversation."""
        return self.messages.count()
    
    def get_context(self, limit=10):
        """
        Get recent messages for context.
        Phase 3: Implementation with memory window
        """
        return self.messages.order_by('-created_at')[:limit]


class Message(models.Model):
    """
    Individual message in a conversation.
    """
    
    class Role(models.TextChoices):
        USER = 'user', _('User')
        ASSISTANT = 'assistant', _('Assistant')
        SYSTEM = 'system', _('System')
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
        help_text=_('User who sent this message (null for assistant messages)')
    )
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        help_text=_('Role of the message sender')
    )
    
    content = models.TextField(
        help_text=_('Message content')
    )
    
    # Tool execution tracking (Phase 3)
    tool_calls = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Tools called during this message (if any)')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Additional message metadata')
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('message')
        verbose_name_plural = _('messages')
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."