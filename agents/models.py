"""
Agent models for AI agent configuration and management.
Phase 1: Foundation & Authentication (Skeleton)
Phase 2: Complete implementation
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Agent(models.Model):
    """
    AI Agent model storing configuration and settings.
    """
    
    class UseCase(models.TextChoices):
        SUPPORT = 'support', _('Customer Support')
        RESEARCH = 'research', _('Research & Analysis')
        AUTOMATION = 'automation', _('Workflow Automation')
        SCHEDULING = 'scheduling', _('Smart Scheduling')
        KNOWLEDGE = 'knowledge', _('Knowledge Management')
        SALES = 'sales', _('Sales & Lead Generation')
    
    # Basic Information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agents',
        help_text=_('Owner of this agent')
    )
    
    name = models.CharField(
        _('name'),
        max_length=255,
        help_text=_('Display name for the agent')
    )
    
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Brief description of agent purpose')
    )
    
    use_case = models.CharField(
        _('use case'),
        max_length=20,
        choices=UseCase.choices,
        default=UseCase.SUPPORT,
        help_text=_('Primary use case for this agent')
    )
    
    # AI Configuration (Phase 3)
    prompt_template = models.TextField(
        _('prompt template'),
        blank=True,
        default='',
        help_text=_('System prompt template for the agent')
    )
    
    config_json = models.JSONField(
        _('configuration'),
        default=dict,
        blank=True,
        help_text=_('LLM and tool configuration (provider, model, temperature, etc.)')
    )
    
    # Integration Configuration (Phase 7)
    integration_hooks = models.JSONField(
        _('integration hooks'),
        default=dict,
        blank=True,
        help_text=_('Webhook URLs, API keys, channel configs for integrations')
    )
    
    # Status
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Whether this agent is active and available for use')
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def can_user_chat(self, user):
        """
        Check if a user has permission to chat with this agent.
        Override this method to implement custom permission logic.
        """
        # Basic implementation - agent must be active and belong to the user
        if not self.is_active:
            return False
        
        # If agent is owned by the user, they can chat
        if self.user == user:
            return True
        
        # Add additional logic here as needed:
        # - Check if agent is public
        # - Check team permissions
        # - Check subscription status
        # etc.
        
        return False
    
    def can_user_embed(self, origin=None):
        """
        Check if embedding is allowed for this agent.
        Optionally validate the origin domain.
        """
        # Must be active
        if not self.is_active:
            return False
        
        # Add logic for allowed origins/domains
        # For now, allow if agent is active
        return True
    
    class Meta:
        verbose_name = _('agent')
        verbose_name_plural = _('agents')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['use_case']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_use_case_display()})"
    
    def get_default_config(self):
        """Return default configuration based on use case."""
        defaults = {
            'provider': 'openai',
            'model': 'gpt-4o-mini',
            'temperature': 0.7,
            'max_tokens': 1000,
            'tools_enabled': True,
        }
        return {**defaults, **self.config_json}
    
    def get_conversation_count(self):
        """Return number of conversations for this agent."""
        return self.conversations.count()


class KnowledgeBase(models.Model):
    """
    Knowledge base model for storing documents and embeddings.
    Phase 1: Skeleton only
    Phase 5: Complete implementation with vectors
    """
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='knowledge_bases'
    )
    
    title = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='knowledge/', blank=True, null=True)
    content = models.TextField(blank=True)
    
    # Vector embedding (requires pgvector - Phase 5)
    # embedding = VectorField(dimensions=1536, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('knowledge base')
        verbose_name_plural = _('knowledge bases')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.agent.name}"