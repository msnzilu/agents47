"""
security/validators.py
Complete validators for Security & Compliance (Phase 9)
"""
from django.core.exceptions import ValidationError
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
import re
import bleach
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


# =============================================================================
# PROMPT INJECTION DETECTION
# =============================================================================

class PromptInjectionDetector:
    """Detect and prevent prompt injection attacks"""
    
    SUSPICIOUS_PATTERNS = [
        r'ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|commands|rules)',
        r'disregard\s+(all\s+)?(previous|above|prior)',
        r'forget\s+(everything|all)',
        r'new\s+instructions',
        r'system\s*:',
        r'assistant\s*:',
        r'\[INST\]',
        r'\[/INST\]',
        r'<\|im_start\|>',
        r'<\|im_end\|>',
        r'###\s*instruction',
        r'you\s+are\s+now',
    ]
    
    @classmethod
    def detect(cls, text: str) -> tuple[bool, str]:
        """
        Detect potential prompt injection
        Returns: (is_suspicious, reason)
        """
        if not text:
            return False, ""
        
        text_lower = text.lower()
        
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True, f"Suspicious pattern detected: {pattern}"
        
        return False, ""
    
    @classmethod
    def sanitize(cls, text: str, raise_on_detection: bool = False) -> str:
        """
        Sanitize text by removing or redacting suspicious content
        """
        is_suspicious, reason = cls.detect(text)
        
        if is_suspicious:
            logger.warning(f"Prompt injection detected: {reason}")
            
            if raise_on_detection:
                raise ValidationError("Suspicious input detected")
            
            # Redact suspicious content
            sanitized = text
            for pattern in cls.SUSPICIOUS_PATTERNS:
                sanitized = re.sub(
                    pattern,
                    '[REDACTED]',
                    sanitized,
                    flags=re.IGNORECASE
                )
            
            return sanitized
        
        return text


# =============================================================================
# SQL INJECTION VALIDATION
# =============================================================================

class SQLInjectionValidator:
    """Validate inputs against SQL injection attempts"""
    
    SQL_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
        r"(--|;|\/\*|\*\/)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)",
        r"(\bUNION\b.*\bSELECT\b)",
        r"('.*--)",
        r"(;.*DROP)",
    ]
    
    @classmethod
    def is_suspicious(cls, value: str) -> bool:
        """Check if value contains SQL injection patterns"""
        if not value:
            return False
        
        value_upper = value.upper()
        
        for pattern in cls.SQL_PATTERNS:
            if re.search(pattern, value_upper, re.IGNORECASE):
                return True
        
        return False
    
    @classmethod
    def validate(cls, value: str, field_name: str = 'input'):
        """Validate and raise error if SQL injection detected"""
        if cls.is_suspicious(value):
            logger.warning(f"SQL injection attempt detected in {field_name}: {value}")
            raise ValidationError(
                f"Invalid characters detected in {field_name}",
                code='sql_injection'
            )


# =============================================================================
# XSS PROTECTION
# =============================================================================

class XSSProtection:
    """Protect against Cross-Site Scripting (XSS) attacks"""
    
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'blockquote', 'code', 'pre'
    ]
    
    ALLOWED_ATTRIBUTES = {
        '*': ['class'],
        'a': ['href', 'title'],
        'img': ['src', 'alt'],
    }
    
    @classmethod
    def sanitize_html(cls, html: str) -> str:
        """Sanitize HTML to remove dangerous elements"""
        return bleach.clean(
            html,
            tags=cls.ALLOWED_TAGS,
            attributes=cls.ALLOWED_ATTRIBUTES,
            strip=True
        )
    
    @classmethod
    def escape_html(cls, text: str) -> str:
        """Escape HTML entities"""
        import html
        return html.escape(text)


# =============================================================================
# INPUT SANITIZER
# =============================================================================

class InputSanitizer:
    """General input sanitization utilities"""
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitize plain text input"""
        if not text:
            return text
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Escape HTML
        return XSSProtection.escape_html(text)
    
    @staticmethod
    def sanitize_html(html: str) -> str:
        """Sanitize HTML input"""
        if not html:
            return html
        
        return XSSProtection.sanitize_html(html)
    
    @staticmethod
    def sanitize_prompt(prompt: str) -> str:
        """Sanitize LLM prompt input"""
        if not prompt:
            return prompt
        
        # Check for prompt injection
        sanitized = PromptInjectionDetector.sanitize(prompt)
        
        # Remove dangerous HTML
        sanitized = XSSProtection.sanitize_html(sanitized)
        
        return sanitized
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename"""
        if not filename:
            return filename
        
        # Remove path traversal attempts
        filename = filename.replace('..', '')
        filename = filename.replace('/', '')
        filename = filename.replace('\\', '')
        
        # Allow only alphanumeric, dash, underscore, and dot
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        return filename


# =============================================================================
# COMPREHENSIVE INPUT VALIDATION
# =============================================================================

def validate_and_sanitize_input(data: dict, field_rules: dict) -> dict:
    """
    Validate and sanitize input data based on field rules
    
    Args:
        data: Dictionary of input data
        field_rules: Dictionary of validation rules per field
            Example: {
                'name': {'type': 'text', 'required': True, 'max_length': 100},
                'description': {'type': 'html', 'required': False},
                'prompt': {'type': 'prompt', 'required': True}
            }
    
    Returns:
        Dictionary of sanitized data
    
    Raises:
        ValidationError: If validation fails
    """
    sanitized = {}
    errors = {}
    
    for field_name, rules in field_rules.items():
        value = data.get(field_name)
        
        # Check required
        if rules.get('required') and not value:
            errors[field_name] = f"{field_name} is required"
            continue
        
        if not value:
            sanitized[field_name] = value
            continue
        
        # Type-specific validation and sanitization
        field_type = rules.get('type', 'text')
        
        try:
            if field_type == 'text':
                value = str(value)
                SQLInjectionValidator.validate(value, field_name)
                sanitized[field_name] = InputSanitizer.sanitize_text(value)
            
            elif field_type == 'html':
                value = str(value)
                sanitized[field_name] = InputSanitizer.sanitize_html(value)
            
            elif field_type == 'prompt':
                value = str(value)
                sanitized[field_name] = InputSanitizer.sanitize_prompt(value)
            
            elif field_type == 'filename':
                value = str(value)
                sanitized[field_name] = InputSanitizer.sanitize_filename(value)
            
            else:
                sanitized[field_name] = value
            
            # Check max length
            max_length = rules.get('max_length')
            if max_length and len(str(sanitized[field_name])) > max_length:
                errors[field_name] = f"{field_name} exceeds maximum length of {max_length}"
        
        except ValidationError as e:
            errors[field_name] = str(e)
    
    if errors:
        raise ValidationError(errors)
    
    return sanitized


# =============================================================================
# PASSWORD VALIDATORS
# =============================================================================

class PasswordStrengthValidator:
    """Enhanced password strength validation"""
    
    def validate(self, password, user=None):
        """Validate password strength"""
        errors = []
        
        # Minimum length
        if len(password) < 12:
            errors.append("Password must be at least 12 characters long.")
        
        # Must contain uppercase
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter.")
        
        # Must contain lowercase
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter.")
        
        # Must contain digit
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number.")
        
        # Must contain special character
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character.")
        
        # Check against common passwords
        common_passwords = [
            'password', '12345678', 'qwerty', 'abc123',
            'password123', 'admin', 'letmein'
        ]
        if password.lower() in common_passwords:
            errors.append("This password is too common.")
        
        # Check if password contains user info
        if user:
            user_info = [
                user.email.split('@')[0].lower(),
                user.get_full_name().lower(),
            ]
            if hasattr(user, 'username'):
                user_info.append(user.username.lower())
            
            for info in user_info:
                if info and len(info) > 2 and info in password.lower():
                    errors.append("Password cannot contain your personal information.")
                    break
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        return (
            "Your password must contain at least 12 characters, "
            "including uppercase and lowercase letters, numbers, "
            "and special characters."
        )


class PasswordHistoryValidator:
    """Prevent password reuse"""
    
    def __init__(self, history_count=5):
        self.history_count = history_count
    
    def validate(self, password, user=None):
        """Check against password history"""
        if not user or not user.pk:
            return
        
        from .models import PasswordHistory
        
        # Get password history
        history = PasswordHistory.objects.filter(user=user).order_by('-created_at')[:self.history_count]
        
        for old_password in history:
            if check_password(password, old_password.password_hash):
                raise ValidationError(
                    f"Password has been used recently. Please choose a different password. "
                    f"You cannot reuse your last {self.history_count} passwords."
                )
    
    def get_help_text(self):
        return f"You cannot reuse your last {self.history_count} passwords."


# =============================================================================
# AUTHENTICATION BACKEND WITH 2FA
# =============================================================================

class TwoFactorAuthBackend(ModelBackend):
    """Authentication backend with 2FA support"""
    
    def authenticate(self, request, email=None, password=None, totp_token=None, **kwargs):
        """Authenticate user with optional 2FA"""
        from .models import LoginAttempt
        
        # Get IP and user agent
        ip_address = self._get_client_ip(request) if request else 'unknown'
        user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''
        
        # Check if account is locked
        if LoginAttempt.is_account_locked(email):
            LoginAttempt.record_attempt(
                email=email,
                ip_address=ip_address,
                success=False,
                user_agent=user_agent,
                failure_reason='Account locked'
            )
            logger.warning(f"Login attempt for locked account: {email}")
            return None
        
        # Get user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            LoginAttempt.record_attempt(
                email=email,
                ip_address=ip_address,
                success=False,
                user_agent=user_agent,
                failure_reason='Invalid email'
            )
            return None
        
        # Check password
        if not user.check_password(password):
            LoginAttempt.record_attempt(
                email=email,
                ip_address=ip_address,
                success=False,
                user_agent=user_agent,
                failure_reason='Invalid password'
            )
            return None
        
        # Check 2FA if enabled
        if hasattr(user, 'two_factor_auth') and user.two_factor_auth.is_enabled:
            if not totp_token:
                # Need 2FA token
                return None
            
            if not user.two_factor_auth.verify_token(totp_token):
                LoginAttempt.record_attempt(
                    email=email,
                    ip_address=ip_address,
                    success=False,
                    user_agent=user_agent,
                    failure_reason='Invalid 2FA token'
                )
                return None
        
        # Success
        LoginAttempt.record_attempt(
            email=email,
            ip_address=ip_address,
            success=True,
            user_agent=user_agent
        )
        
        return user
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip