"""
security/models.py
Complete models for Security & Compliance (Phase 9)
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import pyotp
import qrcode
import io
import base64
from django.conf import settings

User = get_user_model()


# =============================================================================
# TWO-FACTOR AUTHENTICATION
# =============================================================================

class TwoFactorAuth(models.Model):
    """Two-Factor Authentication for users"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='two_factor_auth'
    )
    secret_key = models.CharField(max_length=32, unique=True)
    is_enabled = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Two-Factor Authentication"
        verbose_name_plural = "Two-Factor Authentications"
    
    def __str__(self):
        return f"2FA for {self.user.email}"
    
    @classmethod
    def generate_secret_key(cls):
        """Generate a new secret key for TOTP"""
        return pyotp.random_base32()
    
    def get_totp(self):
        """Get TOTP instance"""
        return pyotp.TOTP(self.secret_key)
    
    def verify_token(self, token: str) -> bool:
        """Verify TOTP token"""
        totp = self.get_totp()
        is_valid = totp.verify(token, valid_window=1)
        
        if is_valid:
            self.last_used = timezone.now()
            self.save(update_fields=['last_used'])
        
        return is_valid
    
    def verify_backup_code(self, code: str) -> bool:
        """Verify backup code"""
        if code in self.backup_codes:
            self.backup_codes.remove(code)
            self.save(update_fields=['backup_codes'])
            return True
        return False
    
    def generate_backup_codes(self, count: int = 10) -> list:
        """Generate backup codes"""
        import secrets
        codes = [secrets.token_hex(4).upper() for _ in range(count)]
        self.backup_codes = codes
        self.save(update_fields=['backup_codes'])
        return codes
    
    def get_qr_code_url(self):
        """Get provisioning URL for QR code"""
        from django.conf import settings
        totp = self.get_totp()
        return totp.provisioning_uri(
            name=self.user.email,
            issuer_name=getattr(settings, 'SITE_NAME', 'AI Agent Platform')
        )
    
    def get_qr_code_image(self) -> str:
        """Generate QR code image as base64 string"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(self.get_qr_code_url())
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_base64}"


class LoginAttempt(models.Model):
    """Track login attempts for account lockout"""
    
    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255, blank=True)
    success = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    failure_reason = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['email', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]
    
    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{status} login attempt for {self.email} at {self.timestamp}"
    
    @classmethod
    def record_attempt(cls, email: str, ip_address: str, success: bool,
                       user_agent: str = "", failure_reason: str = ""):
        """Record a login attempt"""
        return cls.objects.create(
            email=email,
            ip_address=ip_address,
            success=success,
            user_agent=user_agent,
            failure_reason=failure_reason
        )
    
    @classmethod
    def get_recent_failures(cls, email: str, minutes: int = 30) -> int:
        """Get count of recent failed login attempts"""
        since = timezone.now() - timedelta(minutes=minutes)
        return cls.objects.filter(
            email=email,
            success=False,
            timestamp__gte=since
        ).count()
    
    @classmethod
    def is_account_locked(cls, email: str, max_attempts: int = 5,
                         lockout_minutes: int = 30) -> bool:
        """Check if account is locked due to failed attempts"""
        failures = cls.get_recent_failures(email, lockout_minutes)
        return failures >= max_attempts


class OAuth2Connection(models.Model):
    """OAuth2 provider connections"""
    
    PROVIDER_CHOICES = [
        ('google', 'Google'),
        ('github', 'GitHub'),
        ('microsoft', 'Microsoft'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='security_oauth_connections'
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_user_id = models.CharField(max_length=255)
    access_token = models.CharField(max_length=500, blank=True)
    refresh_token = models.CharField(max_length=500, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    extra_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['provider', 'provider_user_id']]
        indexes = [
            models.Index(fields=['user', 'provider']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_provider_display()}"
    
    def is_token_expired(self) -> bool:
        """Check if access token is expired"""
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at


class PasswordHistory(models.Model):
    """Store password history for validation"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_history'
    )
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Password histories"
    
    @classmethod
    def add_password(cls, user, password_hash):
        """Add password to history"""
        cls.objects.create(user=user, password_hash=password_hash)
        
        # Keep only last 5 passwords
        old_passwords = cls.objects.filter(user=user).order_by('-created_at')[5:]
        cls.objects.filter(pk__in=old_passwords).delete()


# =============================================================================
# GDPR COMPLIANCE
# =============================================================================

class DataExportRequest(models.Model):
    """Track data export requests (GDPR Article 15)"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='data_export_requests'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    download_url = models.URLField(blank=True)
    file_path = models.FilePathField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Data export for {self.user.email} - {self.status}"
    
    def mark_processing(self):
        """Mark as processing"""
        self.status = 'processing'
        self.save(update_fields=['status'])
    
    def mark_completed(self, file_path: str):
        """Mark as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.file_path = file_path
        self.expires_at = timezone.now() + timedelta(days=7)
        self.save(update_fields=['status', 'completed_at', 'file_path', 'expires_at'])
    
    def mark_failed(self, error_message: str):
        """Mark as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])


class DataDeletionRequest(models.Model):
    """Track data deletion requests (GDPR Article 17)"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='data_deletion_requests'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reason = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_deletion_requests'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    delete_messages = models.BooleanField(default=True)
    delete_agents = models.BooleanField(default=True)
    delete_knowledge_base = models.BooleanField(default=True)
    delete_analytics = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Deletion request for {self.user.email} - {self.status}"
    
    def approve(self, reviewer):
        """Approve deletion request"""
        self.status = 'approved'
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
    
    def reject(self, reviewer, reason: str):
        """Reject deletion request"""
        self.status = 'rejected'
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.rejection_reason = reason
        self.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'rejection_reason'])
    
    def mark_completed(self):
        """Mark as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])


class ConsentRecord(models.Model):
    """Track user consent for data processing (GDPR Article 7)"""
    
    CONSENT_TYPES = [
        ('terms', 'Terms of Service'),
        ('privacy', 'Privacy Policy'),
        ('marketing', 'Marketing Communications'),
        ('analytics', 'Analytics & Cookies'),
        ('third_party', 'Third-Party Data Sharing'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consent_records'
    )
    consent_type = models.CharField(max_length=20, choices=CONSENT_TYPES)
    consented = models.BooleanField(default=False)
    version = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'consent_type']),
        ]
    
    def __str__(self):
        status = "Granted" if self.consented else "Revoked"
        return f"{status} {self.get_consent_type_display()} for {self.user.email}"
    
    @classmethod
    def record_consent(cls, user, consent_type: str, consented: bool,
                       version: str, ip_address: str = None, user_agent: str = None):
        """Record user consent"""
        return cls.objects.create(
            user=user,
            consent_type=consent_type,
            consented=consented,
            version=version,
            ip_address=ip_address,
            user_agent=user_agent
        )

    
    @classmethod
    def has_current_consent(cls, user, consent_type: str, version: str = None) -> bool:
        """Check if user has given consent for specific type"""
        query = cls.objects.filter(user=user, consent_type=consent_type)
        
        if version:
            query = query.filter(version=version)
        
        latest = query.order_by('-timestamp').first()
        return latest and latest.consented if latest else False


class DataRetentionPolicy(models.Model):
    """Define data retention policies"""
    
    data_type = models.CharField(max_length=50, unique=True)
    retention_days = models.IntegerField()
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Data retention policies"
    
    def __str__(self):
        return f"{self.data_type} - {self.retention_days} days"
    
    @classmethod
    def get_retention_days(cls, data_type: str) -> int:
        """Get retention days for data type"""
        try:
            policy = cls.objects.get(data_type=data_type, is_active=True)
            return policy.retention_days
        except cls.DoesNotExist:
            return 365  # Default