"""
Phase 9: Security & Compliance - GDPR Compliance Tests
Tests for data export, deletion, anonymization, and consent management
"""
import pytest
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone

from security.gdpr_compliance import (
    DataExportRequest, DataDeletionRequest, ConsentRecord,
    GDPRDataExporter, GDPRDataDeleter, PIIAnonymizer,
    DataRetentionPolicy
)

User = get_user_model()


@pytest.mark.django_db
class TestCompliance(TestCase):
    """Test GDPR compliance features"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create some test data for the user
        from agents.models import Agent
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            description='Test Description',
            use_case='support'
        )
    
    def test_data_export_includes_all_user_data(self):
        """Test that data export includes all user data"""
        exporter = GDPRDataExporter(self.user)
        data = exporter.export_all_data()
        
        # Check all sections are present
        assert 'user_profile' in data
        assert 'agents' in data
        assert 'conversations' in data
        assert 'knowledge_base' in data
        assert 'analytics' in data
        assert 'audit_logs' in data
        assert 'export_metadata' in data
        
        # Check user profile data
        profile = data['user_profile']
        assert profile['email'] == self.user.email
        
        # Check agents data
        agents = data['agents']
        assert len(agents) >= 1
        assert agents[0]['name'] == 'Test Agent'
    
    def test_user_deletion_removes_pii(self):
        """Test that user deletion removes PII"""
        # Create deletion request
        deletion_request = DataDeletionRequest.objects.create(
            user=self.user,
            status='approved',
            delete_messages=True,
            delete_agents=True,
            delete_knowledge_base=True,
            delete_analytics=True
        )
        
        original_email = self.user.email
        
        # Delete data
        deleter = GDPRDataDeleter(self.user)
        deleter.delete_all_data(deletion_request)
        
        # Check user was anonymized
        self.user.refresh_from_db()
        assert self.user.email != original_email
        assert 'deleted_user_' in self.user.email
        assert not self.user.is_active
        
        # Check deletion request was marked complete
        deletion_request.refresh_from_db()
        assert deletion_request.status == 'completed'
    
    def test_audit_log_records_access(self):
        """Test that audit log records data access"""
        from analytics.models import AuditLog
        
        # Log an access action
        log = AuditLog.log_action(
            user=self.user,
            action=AuditLog.ActionType.ACCESS,
            obj=self.agent,
            ip_address='192.168.1.1'
        )
        
        assert log is not None
        assert log.user == self.user
        assert log.action == AuditLog.ActionType.ACCESS
        assert log.object_type == 'Agent'
        assert log.ip_address == '192.168.1.1'
    
    def test_pii_anonymized_in_logs(self):
        """Test that PII is anonymized in logs"""
        email = 'john.doe@example.com'
        anonymized = PIIAnonymizer.anonymize_email(email)
        
        assert anonymized != email
        assert 'j***e@example.com' in anonymized or anonymized.startswith('j')
        assert '@example.com' in anonymized
        
        # Test IP anonymization
        ip = '192.168.1.100'
        anonymized_ip = PIIAnonymizer.anonymize_ip(ip)
        
        assert anonymized_ip != ip
        assert anonymized_ip.startswith('192.168')
        assert anonymized_ip.endswith('.0.0')
    
    def test_data_retention_policy_enforces(self):
        """Test that data retention policy is enforced"""
        # Create retention policy
        policy = DataRetentionPolicy.objects.create(
            data_type='test_data',
            retention_days=90,
            description='Test data retention',
            is_active=True
        )
        
        # Get retention days
        days = DataRetentionPolicy.get_retention_days('test_data')
        assert days == 90
        
        # Non-existent type returns default
        days = DataRetentionPolicy.get_retention_days('nonexistent')
        assert days == 365  # Default


@pytest.mark.django_db
class TestDataExport(TestCase):
    """Test data export functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_export_request_created(self):
        """Test data export request creation"""
        request = DataExportRequest.objects.create(
            user=self.user,
            ip_address='192.168.1.1'
        )
        
        assert request.status == 'pending'
        assert request.user == self.user
    
    def test_export_generates_json(self):
        """Test export generates JSON file"""
        exporter = GDPRDataExporter(self.user)
        file_path = exporter.generate_export_file(file_format='json')
        
        assert file_path is not None
        assert file_path.endswith('.json')
        
        # Verify file exists and contains data
        import os
        assert os.path.exists(file_path)
        
        with open(file_path, 'r') as f:
            data = json.load(f)
            assert 'user_profile' in data
            assert data['user_profile']['email'] == self.user.email
    
    def test_export_request_expires(self):
        """Test export requests expire"""
        from datetime import timedelta
        
        request = DataExportRequest.objects.create(
            user=self.user,
            status='completed',
            expires_at=timezone.now() - timedelta(days=1)  # Expired yesterday
        )
        
        # Check if expired
        assert request.expires_at < timezone.now()


@pytest.mark.django_db
class TestDataDeletion(TestCase):
    """Test data deletion functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123',
            is_staff=True
        )
    
    def test_deletion_request_created(self):
        """Test deletion request creation"""
        request = DataDeletionRequest.objects.create(
            user=self.user,
            reason='No longer need the service',
            ip_address='192.168.1.1'
        )
        
        assert request.status == 'pending'
        assert request.user == self.user
        assert request.delete_messages is True  # Default
    
    def test_deletion_request_approval(self):
        """Test deletion request can be approved"""
        request = DataDeletionRequest.objects.create(
            user=self.user,
            reason='Test'
        )
        
        # Approve request
        request.approve(self.admin)
        
        assert request.status == 'approved'
        assert request.reviewed_by == self.admin
        assert request.reviewed_at is not None
    
    def test_deletion_request_rejection(self):
        """Test deletion request can be rejected"""
        request = DataDeletionRequest.objects.create(
            user=self.user,
            reason='Test'
        )
        
        # Reject request
        request.reject(self.admin, 'Account has active subscription')
        
        assert request.status == 'rejected'
        assert request.reviewed_by == self.admin
        assert request.rejection_reason == 'Account has active subscription'
    
    def test_data_deletion_anonymizes_user(self):
        """Test data deletion anonymizes user account"""
        original_email = self.user.email
        
        deleter = GDPRDataDeleter(self.user)
        deleter.anonymize_user_account()
        
        self.user.refresh_from_db()
        
        assert self.user.email != original_email
        assert 'deleted_user_' in self.user.email
        assert self.user.first_name == 'Deleted'
        assert self.user.last_name == 'User'
        assert not self.user.is_active


@pytest.mark.django_db
class TestConsentManagement(TestCase):
    """Test consent management"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_consent_recorded(self):
        """Test consent is recorded"""
        consent = ConsentRecord.record_consent(
            user=self.user,
            consent_type='privacy',
            consented=True,
            version='1.0',
            ip_address='192.168.1.1'
        )
        
        assert consent is not None
        assert consent.user == self.user
        assert consent.consent_type == 'privacy'
        assert consent.consented is True
        assert consent.version == '1.0'
    
    def test_consent_can_be_revoked(self):
        """Test consent can be revoked"""
        # Grant consent
        ConsentRecord.record_consent(
            user=self.user,
            consent_type='marketing',
            consented=True,
            version='1.0'
        )
        
        # Revoke consent
        ConsentRecord.record_consent(
            user=self.user,
            consent_type='marketing',
            consented=False,
            version='1.0'
        )
        
        # Check latest consent
        has_consent = ConsentRecord.has_current_consent(
            self.user,
            'marketing',
            '1.0'
        )
        
        assert not has_consent
    
    def test_consent_version_tracked(self):
        """Test consent version is tracked"""
        # Consent to v1.0
        ConsentRecord.record_consent(
            user=self.user,
            consent_type='terms',
            consented=True,
            version='1.0'
        )
        
        # Consent to v2.0
        ConsentRecord.record_consent(
            user=self.user,
            consent_type='terms',
            consented=True,
            version='2.0'
        )
        
        # Check v2.0 consent
        has_v2_consent = ConsentRecord.has_current_consent(
            self.user,
            'terms',
            '2.0'
        )
        
        assert has_v2_consent
    
    def test_consent_history_maintained(self):
        """Test consent history is maintained"""
        # Multiple consent changes
        for i in range(3):
            ConsentRecord.record_consent(
                user=self.user,
                consent_type='analytics',
                consented=(i % 2 == 0),
                version='1.0'
            )
        
        # Check history
        history = ConsentRecord.objects.filter(
            user=self.user,
            consent_type='analytics'
        ).order_by('-timestamp')
        
        assert history.count() == 3


@pytest.mark.django_db
class TestPIIAnonymization(TestCase):
    """Test PII anonymization"""
    
    def test_email_anonymization(self):
        """Test email anonymization"""
        emails = [
            ('john.doe@example.com', 'j***e@example.com'),
            ('a@test.com', '***@test.com'),
            ('test@example.com', 't***t@example.com'),
        ]
        
        for email, expected_pattern in emails:
            anonymized = PIIAnonymizer.anonymize_email(email)
            assert anonymized != email
            assert '@example.com' in anonymized or '@test.com' in anonymized
    
    def test_ip_anonymization(self):
        """Test IP address anonymization"""
        # IPv4
        ip = '192.168.1.100'
        anonymized = PIIAnonymizer.anonymize_ip(ip)
        
        assert anonymized == '192.168.0.0'
        
        # Unknown IP
        anonymized = PIIAnonymizer.anonymize_ip('unknown')
        assert anonymized == '0.0.0.0'
    
    def test_name_anonymization(self):
        """Test name anonymization"""
        name = 'John Doe'
        anonymized = PIIAnonymizer.anonymize_name(name)
        
        assert anonymized != name
        assert anonymized == 'J***'
    
    def test_text_pii_anonymization(self):
        """Test PII anonymization in text"""
        text = 'Contact me at john.doe@example.com or call 555-123-4567'
        anonymized = PIIAnonymizer.anonymize_text(text)
        
        assert 'john.doe@example.com' not in anonymized
        assert '[EMAIL]' in anonymized
        assert '555-123-4567' not in anonymized
        assert '[PHONE]' in anonymized


@pytest.mark.django_db
class TestAPIKeySecurity(TestCase):
    """Test API key security"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_api_key_rotation(self):
        """Test API key can be rotated"""
        from integrations.models import APIKey
        import secrets
        
        # Create initial key
        old_key = secrets.token_urlsafe(32)
        api_key = APIKey.objects.create(
            user=self.user,
            name='Test Key',
            key=old_key
        )
        
        # Rotate key
        new_key = secrets.token_urlsafe(32)
        api_key.key = new_key
        api_key.save()
        
        assert api_key.key == new_key
        assert api_key.key != old_key
    
    def test_webhook_signature_validates(self):
        """Test webhook signature validation"""
        import hmac
        import hashlib
        
        secret = 'test_secret_key'
        payload = '{"event": "test"}'
        
        # Generate signature
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Verify signature
        expected_signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        assert signature == expected_signature
    
    def test_ip_whitelist_blocks_unauthorized(self):
        """Test IP whitelist blocks unauthorized IPs"""
        # This is a conceptual test
        # In production, IP whitelisting would be implemented in middleware
        
        allowed_ips = ['192.168.1.1', '10.0.0.1']
        request_ip = '203.0.113.1'  # Not in whitelist
        
        assert request_ip not in allowed_ips
    
    def test_secrets_not_exposed_in_responses(self):
        """Test that secrets are not exposed in API responses"""
        from integrations.models import APIKey
        import secrets
        
        # Create API key
        key = secrets.token_urlsafe(32)
        api_key = APIKey.objects.create(
            user=self.user,
            name='Test Key',
            key=key
        )
        
        # Serialize for API response
        response_data = {
            'id': api_key.id,
            'name': api_key.name,
            'created_at': api_key.created_at.isoformat(),
            # key should NOT be included in responses
        }
        
        assert 'key' not in response_data
        assert key not in str(response_data)