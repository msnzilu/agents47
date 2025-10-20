"""
Integration models for external services.
Phase 1: Complete models
Phase 7: Full implementation with webhooks
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Integration(models.Model):
    """
    Integration configuration for connecting agents to external services.
    """
    
    class IntegrationType(models.TextChoices):
        WEBHOOK = 'webhook', _('Webhook')
        EMAIL = 'email', _('Email')
        SLACK = 'slack', _('Slack')
        SMS = 'sms', _('SMS/Twilio')
        ZAPIER = 'zapier', _('Zapier')
        CRM = 'crm', _('CRM (Salesforce/HubSpot)')
        CALENDAR = 'calendar', _('Calendar (Google/Outlook)')
        ZENDESK = 'zendesk', _('Zendesk')
        CUSTOM = 'custom', _('Custom API')
    
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        ERROR = 'error', _('Error')
        PENDING = 'pending', _('Pending Setup')
    
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        related_name='integrations'
    )
    
    name = models.CharField(
        _('name'),
        max_length=255,
        help_text=_('Display name for this integration')
    )
    
    integration_type = models.CharField(
        _('integration type'),
        max_length=20,
        choices=IntegrationType.choices,
        help_text=_('Type of integration')
    )
    
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_('Current status of integration')
    )
    
    # Configuration
    config = models.JSONField(
        _('configuration'),
        default=dict,
        blank=True,
        help_text=_('Integration-specific configuration (API keys, URLs, etc.)')
    )
    
    # Webhook specific
    webhook_url = models.URLField(
        _('webhook URL'),
        max_length=500,
        blank=True,
        null=True,
        help_text=_('Webhook endpoint URL')
    )
    
    webhook_secret = models.CharField(
        _('webhook secret'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Secret for webhook signature verification')
    )
    
    # Event triggers
    events = models.JSONField(
        _('events'),
        default=list,
        blank=True,
        help_text=_('List of events that trigger this integration')
    )
    
    # Metadata
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Whether this integration is active')
    )
    
    last_triggered_at = models.DateTimeField(
        _('last triggered at'),
        blank=True,
        null=True,
        help_text=_('When this integration was last triggered')
    )
    
    error_message = models.TextField(
        _('error message'),
        blank=True,
        help_text=_('Last error message if status is error')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('integration')
        verbose_name_plural = _('integrations')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent', 'integration_type']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_integration_type_display()})"


class WebhookLog(models.Model):
    """
    Log of webhook calls and responses.
    """
    
    class Status(models.TextChoices):
        SUCCESS = 'success', _('Success')
        FAILED = 'failed', _('Failed')
        PENDING = 'pending', _('Pending')
        RETRY = 'retry', _('Retry')
    
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='webhook_logs'
    )
    
    # Request details
    event_type = models.CharField(
        _('event type'),
        max_length=100,
        help_text=_('Type of event that triggered webhook')
    )
    
    payload = models.JSONField(
        _('payload'),
        default=dict,
        help_text=_('Request payload sent to webhook')
    )
    
    # Response details
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    status_code = models.IntegerField(
        _('HTTP status code'),
        blank=True,
        null=True
    )
    
    response = models.JSONField(
        _('response'),
        default=dict,
        blank=True,
        help_text=_('Response from webhook endpoint')
    )
    
    error_message = models.TextField(
        _('error message'),
        blank=True,
        help_text=_('Error message if failed')
    )
    
    # Retry tracking
    retry_count = models.IntegerField(
        _('retry count'),
        default=0,
        help_text=_('Number of retry attempts')
    )
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        _('completed at'),
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = _('webhook log')
        verbose_name_plural = _('webhook logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['integration', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.status} ({self.created_at})"


class APIKey(models.Model):
    """
    API keys for accessing the platform programmatically.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys'
    )
    
    name = models.CharField(
        _('name'),
        max_length=255,
        help_text=_('Descriptive name for this API key')
    )
    
    key = models.CharField(
        _('key'),
        max_length=64,
        unique=True,
        help_text=_('The actual API key')
    )
    
    # Permissions
    scopes = models.JSONField(
        _('scopes'),
        default=list,
        help_text=_('API scopes/permissions for this key')
    )
    
    # Rate limiting
    rate_limit = models.IntegerField(
        _('rate limit'),
        default=1000,
        help_text=_('Requests per hour allowed')
    )
    
    # Status
    is_active = models.BooleanField(
        _('is active'),
        default=True
    )
    
    # Usage tracking
    last_used_at = models.DateTimeField(
        _('last used at'),
        blank=True,
        null=True
    )
    
    usage_count = models.IntegerField(
        _('usage count'),
        default=0,
        help_text=_('Total number of API calls made with this key')
    )
    
    # Expiration
    expires_at = models.DateTimeField(
        _('expires at'),
        blank=True,
        null=True,
        help_text=_('When this API key expires (null = never)')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('API key')
        verbose_name_plural = _('API keys')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['key']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.key[:8]}..."


class OAuthConnection(models.Model):
    """
    OAuth connections for third-party services.
    """
    
    class Provider(models.TextChoices):
        GOOGLE = 'google', _('Google')
        MICROSOFT = 'microsoft', _('Microsoft')
        SLACK = 'slack', _('Slack')
        GITHUB = 'github', _('GitHub')
        SALESFORCE = 'salesforce', _('Salesforce')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='oauth_connections'
    )
    
    provider = models.CharField(
        _('provider'),
        max_length=20,
        choices=Provider.choices
    )
    
    provider_user_id = models.CharField(
        _('provider user ID'),
        max_length=255,
        help_text=_('User ID from the OAuth provider')
    )
    
    # Tokens
    access_token = models.TextField(
        _('access token'),
        help_text=_('OAuth access token (encrypted in production)')
    )
    
    refresh_token = models.TextField(
        _('refresh token'),
        blank=True,
        help_text=_('OAuth refresh token (encrypted in production)')
    )
    
    token_expires_at = models.DateTimeField(
        _('token expires at'),
        blank=True,
        null=True
    )
    
    # Scopes
    scopes = models.JSONField(
        _('scopes'),
        default=list,
        help_text=_('OAuth scopes granted')
    )
    
    # Metadata
    is_active = models.BooleanField(
        _('is active'),
        default=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('OAuth connection')
        verbose_name_plural = _('OAuth connections')
        unique_together = ['user', 'provider']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'provider']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_provider_display()}"