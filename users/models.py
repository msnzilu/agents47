"""
User models for authentication and profile management.
Phase 1: Foundation & Authentication
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    Uses email as the primary identifier for authentication.
    """
    
    # Override email to make it unique and required
    email = models.EmailField(
        _('email address'),
        unique=True,
        error_messages={
            'unique': _("A user with that email already exists."),
        },
    )
    
    # Additional profile fields
    phone_number = models.CharField(
        _('phone number'),
        max_length=20,
        blank=True,
        null=True,
    )
    
    company = models.CharField(
        _('company'),
        max_length=255,
        blank=True,
        null=True,
    )
    
    job_title = models.CharField(
        _('job title'),
        max_length=255,
        blank=True,
        null=True,
    )
    
    # Profile settings
    timezone = models.CharField(
        _('timezone'),
        max_length=50,
        default='UTC',
    )
    
    # Email verification
    email_verified = models.BooleanField(
        _('email verified'),
        default=False,
    )
    
    email_verification_token = models.CharField(
        _('email verification token'),
        max_length=255,
        blank=True,
        null=True,
    )
    
    # Account metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Terms acceptance
    terms_accepted = models.BooleanField(
        _('terms accepted'),
        default=False,
    )
    
    terms_accepted_at = models.DateTimeField(
        _('terms accepted at'),
        blank=True,
        null=True,
    )
    
    # Use email as the username field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # username still required for createsuperuser
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return the user's full name."""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email
    
    def get_display_name(self):
        """Return name for display purposes."""
        if self.first_name:
            return self.first_name
        return self.email.split('@')[0]
    
    @property
    def agent_count(self):
        """Return the number of agents owned by this user."""
        return self.agents.count()
    
    @property
    def conversation_count(self):
        """Return the number of conversations for this user's agents."""
        from chat.models import Conversation
        return Conversation.objects.filter(agent__user=self).count()