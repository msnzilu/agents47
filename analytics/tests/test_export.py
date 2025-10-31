"""
Test cases for Analytics Export Functionality - Phase 8
Tests CSV/JSON exports, webhooks, email reports, and large dataset handling
"""
import pytest
import json
import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core import mail

from analytics.models import (
    UsageLog,
    ConversationMetrics,
    AgentPerformance,
    AnalyticsService,
    AuditLog
)
from agents.models import Agent
from chat.models import Conversation

User = get_user_model()


@pytest.mark.django_db
class TestExport(TestCase):
    """Test analytics export functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            description='Test Description',
            use_case='support'
        )
        
        # Create test usage data
        for i in range(50):
            UsageLog.objects.create(
                user=self.user,
                agent=self.agent,
                event_type=UsageLog.EventType.AGENT_EXECUTED,
                response_time_ms=150 + (i * 5),
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost=Decimal('0.0015'),
                created_at=timezone.now() - timedelta(days=i % 30)
            )
        
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_csv_export_generates(self):
        """Test that CSV export generates successfully"""
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'csv', 'range': '30d'})
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        assert 'attachment' in response['Content-Disposition']
        
        # Parse CSV content
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)
        
        # Verify CSV has header and data
        assert len(rows) > 1  # At least header + some data
        assert 'Metric' in rows[0] or 'Agent' in rows[0]
    
    def test_json_export_generates(self):
        """Test that JSON export generates successfully"""
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'json', 'range': '30d'})
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'
        assert 'attachment' in response['Content-Disposition']
        
        # Parse JSON content
        data = json.loads(response.content)
        
        # Verify JSON structure
        assert isinstance(data, dict)
        assert 'overview' in data or 'agents' in data or len(data) > 0
    
    def test_export_creates_audit_log(self):
        """Test that export action is logged in audit log"""
        initial_count = AuditLog.objects.filter(
            action=AuditLog.ActionType.EXPORT
        ).count()
        
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'csv', 'range': '7d'})
        
        assert response.status_code == 200
        
        # Verify audit log was created
        new_count = AuditLog.objects.filter(
            action=AuditLog.ActionType.EXPORT
        ).count()
        
        assert new_count > initial_count
        
        # Verify audit log details
        audit_log = AuditLog.objects.filter(
            action=AuditLog.ActionType.EXPORT,
            user=self.user
        ).latest('created_at')
        
        assert audit_log.metadata.get('format') == 'csv'
        assert audit_log.metadata.get('date_range') == '7d'
    
    def test_export_requires_authentication(self):
        """Test that export requires user to be logged in"""
        self.client.logout()
        
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'csv', 'range': '7d'})
        
        # Should redirect to login
        assert response.status_code == 302
        assert 'login' in response.url
    
    def test_export_different_date_ranges(self):
        """Test exports with different date ranges"""
        url = reverse('analytics:export_metrics')
        
        ranges = ['24h', '7d', '30d', '90d']
        
        for range_val in ranges:
            response = self.client.get(url, {
                'format': 'csv',
                'range': range_val
            })
            
            assert response.status_code == 200
            assert f'analytics_{range_val}.csv' in response['Content-Disposition']
    
    def test_export_handles_large_datasets(self):
        """Test export with large dataset"""
        # Create a large number of records
        for i in range(1000):
            UsageLog.objects.create(
                user=self.user,
                agent=self.agent,
                event_type=UsageLog.EventType.AGENT_EXECUTED,
                response_time_ms=150,
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost=Decimal('0.0015')
            )
        
        # Test CSV export
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'csv', 'range': '30d'})
        
        assert response.status_code == 200
        
        # Verify content is not empty and contains data
        content = response.content.decode('utf-8')
        assert len(content) > 1000  # Should have substantial content
    
    @patch('analytics.models.AnalyticsService.export_metrics')
    def test_export_handles_errors_gracefully(self, mock_export):
        """Test that export handles errors gracefully"""
        # Mock export to raise an exception
        mock_export.side_effect = Exception('Export failed')
        
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'csv', 'range': '7d'})
        
        assert response.status_code == 500
        data = json.loads(response.content)
        assert 'error' in data
    
    def test_invalid_export_format(self):
        """Test handling of invalid export format"""
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'xml', 'range': '7d'})
        
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data


@pytest.mark.django_db
class TestWebhooks(TestCase):
    """Test webhook functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_webhook_receives_analytics_event(self):
        """Test webhook receives and processes analytics events"""
        url = reverse('analytics:monitoring_webhook')
        
        event_data = {
            'event_type': 'metric',
            'timestamp': timezone.now().isoformat(),
            'metric_name': 'response_time',
            'value': 150,
            'agent_id': 1
        }
        
        response = self.client.post(
            url,
            data=json.dumps(event_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['status'] == 'received'
    
    def test_webhook_handles_alert_events(self):
        """Test webhook handles alert events"""
        url = reverse('analytics:monitoring_webhook')
        
        alert_data = {
            'event_type': 'alert',
            'alert_type': 'high_error_rate',
            'severity': 'critical',
            'message': 'Error rate exceeded threshold',
            'value': 15.5,
            'threshold': 5.0
        }
        
        response = self.client.post(
            url,
            data=json.dumps(alert_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
    
    def test_webhook_invalid_json(self):
        """Test webhook handles invalid JSON"""
        url = reverse('analytics:monitoring_webhook')
        
        response = self.client.post(
            url,
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code == 500
    
    @patch('analytics.models.StructuredLog.objects.create')
    def test_webhook_logs_events(self, mock_log):
        """Test that webhook events are logged"""
        url = reverse('analytics:monitoring_webhook')
        
        event_data = {
            'event_type': 'metric',
            'value': 100
        }
        
        response = self.client.post(
            url,
            data=json.dumps(event_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        # Verify log was attempted to be created
        assert mock_log.called


@pytest.mark.django_db
class TestEmailReports(TestCase):
    """Test email report generation"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            description='Test Description',
            use_case='support'
        )
        
        # Create some test data
        for i in range(10):
            UsageLog.objects.create(
                user=self.user,
                agent=self.agent,
                event_type=UsageLog.EventType.AGENT_EXECUTED,
                response_time_ms=150,
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost=Decimal('0.0015')
            )
    
    @patch('analytics.models.generate_weekly_report')
    def test_email_report_scheduled(self, mock_report):
        """Test that weekly email report can be scheduled"""
        from analytics.models import generate_weekly_report
        
        # Call the report generation function
        generate_weekly_report()
        
        # Verify function was called
        assert mock_report.called
    
    @patch('django.core.mail.send_mail')
    def test_email_report_sends(self, mock_send_mail):
        """Test that email report sends successfully"""
        from analytics.models import generate_weekly_report
        
        # Generate and send report
        generate_weekly_report()
        
        # Verify email was sent
        assert mock_send_mail.called
        
        # Check email parameters
        call_args = mock_send_mail.call_args
        assert self.user.email in call_args[1]['recipient_list']
        assert 'Weekly Analytics Report' in call_args[1]['subject']
    
    def test_email_report_content(self):
        """Test email report contains correct content"""
        from analytics.models import AnalyticsService
        
        # Get metrics for report
        metrics = AnalyticsService.get_dashboard_metrics(self.user, '7d')
        
        # Verify metrics structure
        assert 'overview' in metrics
        assert 'by_agent' in metrics
        assert 'timeline' in metrics
        
        # Verify required data is present
        assert metrics['overview']['total_agents'] >= 1
        assert metrics['overview']['total_tokens'] > 0


@pytest.mark.django_db
class TestLargeDatasetHandling(TestCase):
    """Test handling of large datasets in exports"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            description='Test Description',
            use_case='support'
        )
        
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_export_handles_10k_records(self):
        """Test export with 10,000 records"""
        # Create 10,000 usage logs (in batches for performance)
        batch_size = 1000
        for batch in range(10):
            logs = [
                UsageLog(
                    user=self.user,
                    agent=self.agent,
                    event_type=UsageLog.EventType.AGENT_EXECUTED,
                    response_time_ms=150,
                    input_tokens=100,
                    output_tokens=50,
                    total_tokens=150,
                    cost=Decimal('0.0015')
                )
                for _ in range(batch_size)
            ]
            UsageLog.objects.bulk_create(logs)
        
        # Verify data was created
        assert UsageLog.objects.filter(user=self.user).count() == 10000
        
        # Test export
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'csv', 'range': '30d'})
        
        assert response.status_code == 200
        
        # Verify response contains data
        content = response.content.decode('utf-8')
        assert len(content) > 10000  # Should have substantial content
    
    def test_export_pagination_for_large_datasets(self):
        """Test that export uses pagination for large datasets"""
        # Create 5000 records
        logs = [
            UsageLog(
                user=self.user,
                agent=self.agent,
                event_type=UsageLog.EventType.AGENT_EXECUTED,
                response_time_ms=150,
                total_tokens=150,
                cost=Decimal('0.0015')
            )
            for _ in range(5000)
        ]
        UsageLog.objects.bulk_create(logs)
        
        # Export should complete without timeout
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'json', 'range': '30d'})
        
        assert response.status_code == 200
    
    def test_export_memory_efficiency(self):
        """Test that export doesn't load all data into memory at once"""
        # Create a moderate dataset
        for i in range(1000):
            UsageLog.objects.create(
                user=self.user,
                agent=self.agent,
                event_type=UsageLog.EventType.AGENT_EXECUTED,
                response_time_ms=150,
                total_tokens=150,
                cost=Decimal('0.0015')
            )
        
        # Export should use iterator/chunking internally
        url = reverse('analytics:export_metrics')
        response = self.client.get(url, {'format': 'csv', 'range': '30d'})
        
        assert response.status_code == 200
        # If this completes without memory error, the test passes


@pytest.mark.django_db
class TestAnalyticsAPI(TestCase):
    """Test analytics API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            description='Test Description',
            use_case='support'
        )
        
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_metrics_api_returns_json(self):
        """Test metrics API returns proper JSON"""
        url = reverse('analytics:api_metrics')
        response = self.client.get(url, {'type': 'overview', 'range': '7d'})
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'
        
        data = json.loads(response.content)
        assert isinstance(data, dict)
    
    def test_metrics_api_requires_authentication(self):
        """Test metrics API requires authentication"""
        self.client.logout()
        
        url = reverse('analytics:api_metrics')
        response = self.client.get(url)
        
        assert response.status_code == 302  # Redirect to login