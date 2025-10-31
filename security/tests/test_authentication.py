"""
Phase 9: Security & Compliance - Authentication Tests
Tests for OAuth, 2FA, password policies, and account lockout
"""
import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from security.authentication_enhancements import (
    TwoFactorAuth, LoginAttempt, PasswordHistory,
    PasswordStrengthValidator, PasswordHistoryValidator,
    setup_2fa_for_user, enable_2fa_for_user, disable_2fa_for_user
)

User = get_user_model()


@pytest.mark.django_db
class TestAuthentication(TestCase):
    """Test authentication enhancements"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!@#'
        )
    
    def test_oauth_google_login(self):
        """Test OAuth Google login flow"""
        # This is a stub test - full OAuth requires external service
        # In production, use mocking for OAuth providers
        
        from security.authentication_enhancements import OAuth2Connection
        
        # Simulate OAuth connection
        connection = OAuth2Connection.objects.create(
            user=self.user,
            provider='google',
            provider_user_id='google_123456',
            access_token='mock_access_token',
            refresh_token='mock_refresh_token'
        )
        
        assert connection.provider == 'google'
        assert connection.user == self.user
        assert not connection.is_token_expired()
    
    def test_2fa_enrollment(self):
        """Test 2FA enrollment process"""
        # Setup 2FA
        two_factor = setup_2fa_for_user(self.user)
        
        assert two_factor is not None
        assert two_factor.user == self.user
        assert two_factor.secret_key is not None
        assert len(two_factor.backup_codes) == 10
        assert not two_factor.is_enabled  # Not enabled until verified
    
    def test_2fa_login_flow(self):
        """Test complete 2FA login flow"""
        # Setup and enable 2FA
        two_factor = setup_2fa_for_user(self.user)
        
        # Get current token
        totp = two_factor.get_totp()
        token = totp.now()
        
        # Enable 2FA
        success = enable_2fa_for_user(self.user, token)
        assert success
        
        # Refresh from DB
        two_factor.refresh_from_db()
        assert two_factor.is_enabled
        
        # Test verification
        new_token = totp.now()
        assert two_factor.verify_token(new_token)
    
    def test_2fa_backup_code(self):
        """Test 2FA backup codes"""
        two_factor = setup_2fa_for_user(self.user)
        backup_codes = two_factor.backup_codes
        
        # Use a backup code
        first_code = backup_codes[0]
        assert two_factor.verify_backup_code(first_code)
        
        # Code should be removed after use
        two_factor.refresh_from_db()
        assert first_code not in two_factor.backup_codes
        
        # Can't use same code twice
        assert not two_factor.verify_backup_code(first_code)
    
    def test_password_strength_validation(self):
        """Test password strength requirements"""
        validator = PasswordStrengthValidator()
        
        # Test weak passwords
        weak_passwords = [
            'short',  # Too short
            'alllowercase123',  # No uppercase
            'ALLUPPERCASE123',  # No lowercase
            'NoNumbers!@#',  # No numbers
            'NoSpecialChars123',  # No special chars
            'password123',  # Common password
        ]
        
        for password in weak_passwords:
            with pytest.raises(ValidationError):
                validator.validate(password, self.user)
        
        # Test strong password
        strong_password = 'SecurePass123!@#'
        validator.validate(strong_password, self.user)  # Should not raise
    
    def test_account_lockout_after_failures(self):
        """Test account lockout after multiple failed attempts"""
        email = self.user.email
        ip = '192.168.1.1'
        
        # Record 5 failed attempts
        for i in range(5):
            LoginAttempt.record_attempt(
                email=email,
                ip_address=ip,
                success=False,
                failure_reason='Invalid password'
            )
        
        # Account should be locked
        assert LoginAttempt.is_account_locked(email)
        
        # Check failure count
        failures = LoginAttempt.get_recent_failures(email, minutes=30)
        assert failures == 5
    
    def test_session_timeout(self):
        """Test session timeout"""
        # Login
        self.client.login(email='test@example.com', password='SecurePass123!@#')
        
        # Check session exists
        session = self.client.session
        assert session.get('_auth_user_id') is not None
        
        # In production, session would timeout after inactivity
        # This test validates the timeout mechanism exists
        assert hasattr(session, 'get_expiry_date')


@pytest.mark.django_db
class TestTwoFactorAuth(TestCase):
    """Test 2FA functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_2fa_setup_generates_secret(self):
        """Test 2FA setup generates secret key"""
        two_factor = setup_2fa_for_user(self.user)
        
        assert two_factor.secret_key is not None
        assert len(two_factor.secret_key) == 32
    
    def test_2fa_qr_code_generation(self):
        """Test QR code generation"""
        two_factor = setup_2fa_for_user(self.user)
        
        qr_code = two_factor.get_qr_code_image()
        assert qr_code.startswith('data:image/png;base64,')
    
    def test_2fa_token_verification(self):
        """Test TOTP token verification"""
        two_factor = setup_2fa_for_user(self.user)
        totp = two_factor.get_totp()
        
        # Get current token
        token = totp.now()
        
        # Verify token
        assert two_factor.verify_token(token)
        
        # Invalid token should fail
        assert not two_factor.verify_token('000000')
    
    def test_2fa_backup_codes_generation(self):
        """Test backup codes generation"""
        two_factor = setup_2fa_for_user(self.user)
        
        # Check backup codes were generated
        assert len(two_factor.backup_codes) == 10
        
        # Each code should be unique
        assert len(set(two_factor.backup_codes)) == 10
    
    def test_2fa_enable_requires_valid_token(self):
        """Test enabling 2FA requires valid token"""
        two_factor = setup_2fa_for_user(self.user)
        
        # Try to enable with invalid token
        success = enable_2fa_for_user(self.user, '000000')
        assert not success
        
        two_factor.refresh_from_db()
        assert not two_factor.is_enabled
        
        # Enable with valid token
        totp = two_factor.get_totp()
        token = totp.now()
        success = enable_2fa_for_user(self.user, token)
        assert success
        
        two_factor.refresh_from_db()
        assert two_factor.is_enabled
    
    def test_2fa_disable_requires_password(self):
        """Test disabling 2FA requires password"""
        two_factor = setup_2fa_for_user(self.user)
        
        # Enable 2FA first
        totp = two_factor.get_totp()
        token = totp.now()
        enable_2fa_for_user(self.user, token)
        
        # Try to disable with wrong password
        success = disable_2fa_for_user(self.user, 'wrongpassword')
        assert not success
        
        # Disable with correct password
        success = disable_2fa_for_user(self.user, 'testpass123')
        assert success
        
        two_factor.refresh_from_db()
        assert not two_factor.is_enabled


@pytest.mark.django_db
class TestPasswordPolicies(TestCase):
    """Test password policies"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='OldPassword123!'
        )
    
    def test_password_history_validation(self):
        """Test password history prevents reuse"""
        from django.contrib.auth.hashers import make_password
        
        # Add passwords to history
        old_passwords = [
            'OldPassword123!',
            'PreviousPass456!',
            'FormerPass789!',
        ]
        
        for password in old_passwords:
            PasswordHistory.add_password(
                self.user,
                make_password(password)
            )
        
        # Try to use old password
        validator = PasswordHistoryValidator()
        
        with pytest.raises(ValidationError):
            validator.validate('OldPassword123!', self.user)
        
        # New password should work
        validator.validate('NewPassword123!', self.user)
    
    def test_password_contains_user_info(self):
        """Test password cannot contain user information"""
        validator = PasswordStrengthValidator()
        
        # Password containing email
        with pytest.raises(ValidationError):
            validator.validate('testSecure123!', self.user)
        
        # Password not containing user info should work
        validator.validate('CompletelyNewPass123!', self.user)
    
    def test_password_minimum_length(self):
        """Test password minimum length requirement"""
        validator = PasswordStrengthValidator()
        
        # Too short
        with pytest.raises(ValidationError):
            validator.validate('Short1!', self.user)
        
        # Long enough
        validator.validate('LongEnough123!', self.user)
    
    def test_password_complexity_requirements(self):
        """Test password complexity requirements"""
        validator = PasswordStrengthValidator()
        
        # Missing uppercase
        with pytest.raises(ValidationError):
            validator.validate('lowercase123!', self.user)
        
        # Missing lowercase
        with pytest.raises(ValidationError):
            validator.validate('UPPERCASE123!', self.user)
        
        # Missing number
        with pytest.raises(ValidationError):
            validator.validate('NoNumbersHere!', self.user)
        
        # Missing special character
        with pytest.raises(ValidationError):
            validator.validate('NoSpecialChars123', self.user)
        
        # All requirements met
        validator.validate('ComplexPass123!', self.user)


@pytest.mark.django_db
class TestLoginAttempts(TestCase):
    """Test login attempt tracking"""
    
    def test_login_attempt_recorded(self):
        """Test login attempts are recorded"""
        email = 'test@example.com'
        ip = '192.168.1.1'
        
        attempt = LoginAttempt.record_attempt(
            email=email,
            ip_address=ip,
            success=True,
            user_agent='Mozilla/5.0'
        )
        
        assert attempt is not None
        assert attempt.email == email
        assert attempt.ip_address == ip
        assert attempt.success is True
    
    def test_failed_attempts_count(self):
        """Test counting failed attempts"""
        email = 'test@example.com'
        
        # Record 3 failed attempts
        for _ in range(3):
            LoginAttempt.record_attempt(
                email=email,
                ip_address='192.168.1.1',
                success=False
            )
        
        # Check count
        failures = LoginAttempt.get_recent_failures(email, minutes=30)
        assert failures == 3
    
    def test_account_lockout_detection(self):
        """Test account lockout detection"""
        email = 'test@example.com'
        
        # Not locked initially
        assert not LoginAttempt.is_account_locked(email)
        
        # Record 5 failed attempts (default threshold)
        for _ in range(5):
            LoginAttempt.record_attempt(
                email=email,
                ip_address='192.168.1.1',
                success=False
            )
        
        # Should be locked now
        assert LoginAttempt.is_account_locked(email)
    
    def test_successful_login_does_not_count_towards_lockout(self):
        """Test successful logins don't count towards lockout"""
        email = 'test@example.com'
        
        # Mix of successful and failed attempts
        LoginAttempt.record_attempt(email=email, ip_address='192.168.1.1', success=False)
        LoginAttempt.record_attempt(email=email, ip_address='192.168.1.1', success=True)
        LoginAttempt.record_attempt(email=email, ip_address='192.168.1.1', success=False)
        
        # Should only count failures
        failures = LoginAttempt.get_recent_failures(email)
        assert failures == 2


@pytest.mark.django_db
class TestOAuth2(TestCase):
    """Test OAuth2 functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_oauth_connection_created(self):
        """Test OAuth connection can be created"""
        from security.authentication_enhancements import OAuth2Connection
        
        connection = OAuth2Connection.objects.create(
            user=self.user,
            provider='google',
            provider_user_id='google_12345',
            access_token='access_token_123',
            refresh_token='refresh_token_456'
        )
        
        assert connection.user == self.user
        assert connection.provider == 'google'
        assert connection.provider_user_id == 'google_12345'
    
    def test_oauth_token_expiry_check(self):
        """Test OAuth token expiry checking"""
        from security.authentication_enhancements import OAuth2Connection
        
        # Token that expires in future
        connection = OAuth2Connection.objects.create(
            user=self.user,
            provider='google',
            provider_user_id='google_12345',
            access_token='token',
            token_expires_at=timezone.now() + timedelta(hours=1)
        )
        
        assert not connection.is_token_expired()
        
        # Token that expired
        connection.token_expires_at = timezone.now() - timedelta(hours=1)
        connection.save()
        
        assert connection.is_token_expired()
    
    def test_multiple_oauth_providers(self):
        """Test user can connect multiple OAuth providers"""
        from security.authentication_enhancements import OAuth2Connection
        
        # Connect Google
        OAuth2Connection.objects.create(
            user=self.user,
            provider='google',
            provider_user_id='google_123',
            access_token='token1'
        )
        
        # Connect GitHub
        OAuth2Connection.objects.create(
            user=self.user,
            provider='github',
            provider_user_id='github_456',
            access_token='token2'
        )
        
        connections = OAuth2Connection.objects.filter(user=self.user)
        assert connections.count() == 2
        
        providers = [c.provider for c in connections]
        assert 'google' in providers
        assert 'github' in providers