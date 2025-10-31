"""
Test cases for Logging and Monitoring - Phase 8
Tests structured logs, error logging, performance tracking, and audit logs
"""
import pytest
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from analytics.models import (
    StructuredLog,
    AuditLog,
    UsageLog,
    AnalyticsMiddleware
)
from agents.models import Agent

User = get_user_model()
logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestLogging(TestCase):
    """Test logging functionality"""
    
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
    
    def test_structured_logs_created(self):
        """Test creating structured log entries"""
        log = StructuredLog.objects.create(
            level=StructuredLog.LogLevel.INFO,
            logger_name='test.logger',
            message='Test message',
            user=self.user,
            agent=self.agent,
            execution_time_ms=100,
            metadata={'key': 'value'}
        )
        
        assert log.id is not None
        assert log.level == StructuredLog.LogLevel.INFO
        assert log.message == 'Test message'
        assert log.execution_time_ms == 100
        assert log.metadata == {'key': 'value'}
        
        # Verify it can be retrieved
        retrieved = StructuredLog.objects.get(id=log.id)
        assert retrieved.message == 'Test message'
    
    def test_structured_log_levels(self):
        """Test all log levels"""
        levels = [
            StructuredLog.LogLevel.DEBUG,
            StructuredLog.LogLevel.INFO,
            StructuredLog.LogLevel.WARNING,
            StructuredLog.LogLevel.ERROR,
            StructuredLog.LogLevel.CRITICAL
        ]
        
        for level in levels:
            log = StructuredLog.objects.create(
                level=level,
                logger_name='test',
                message=f'Message at {level} level'
            )
            assert log.level == level
        
        # Verify all were created
        assert StructuredLog.objects.count() == 5
    
    def test_error_logged_with_exception_details(self):
        """Test logging errors with exception information"""
        try:
            # Trigger an exception
            result = 1 / 0
        except ZeroDivisionError as e:
            import traceback
            
            log = StructuredLog.objects.create(
                level=StructuredLog.LogLevel.ERROR,
                logger_name='test.error',
                message='Division by zero error occurred',
                exception_type='ZeroDivisionError',
                exception_message=str(e),
                traceback=traceback.format_exc(),
                user=self.user,
                agent=self.agent
            )
            
            assert log.exception_type == 'ZeroDivisionError'
            assert 'division by zero' in log.exception_message.lower()
            assert log.traceback is not None
            assert 'ZeroDivisionError' in log.traceback
    
    @override_settings(SENTRY_DSN='https://test@sentry.io/test')
    def test_error_logged_to_sentry(self):
        """Test that errors can be logged to external monitoring (Sentry simulation)"""
        # Note: In real implementation, you'd use sentry_sdk
        # This test simulates the logging flow
        
        log = StructuredLog.objects.create(
            level=StructuredLog.LogLevel.ERROR,
            logger_name='sentry.test',
            message='Critical error for Sentry',
            exception_type='CriticalError',
            exception_message='Something went wrong',
            metadata={
                'sentry_logged': True,
                'sentry_event_id': 'test-event-123'
            }
        )
        
        assert log.metadata.get('sentry_logged') is True
        assert 'sentry_event_id' in log.metadata
    
    def test_performance_metrics_recorded(self):
        """Test recording performance metrics in logs"""
        log = StructuredLog.objects.create(
            level=StructuredLog.LogLevel.INFO,
            logger_name='performance.api',
            message='API request completed',
            execution_time_ms=250,
            memory_usage_mb=128,
            metadata={
                'endpoint': '/api/agents/1/execute/',
                'method': 'POST',
                'status_code': 200
            }
        )
        
        assert log.execution_time_ms == 250
        assert log.memory_usage_mb == 128
        assert log.metadata['status_code'] == 200
        
        # Verify performance queries work
        slow_queries = StructuredLog.objects.filter(
            execution_time_ms__gt=200
        )
        assert slow_queries.count() == 1
    
    def test_audit_log_tracks_actions(self):
        """Test that audit log tracks user actions"""
        # Test CREATE action
        log = AuditLog.log_action(
            user=self.user,
            action=AuditLog.ActionType.CREATE,
            obj=self.agent,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            new_values={
                'name': 'Test Agent',
                'use_case': 'support'
            }
        )
        
        assert log.user == self.user
        assert log.action == AuditLog.ActionType.CREATE
        assert log.object_type == 'Agent'
        assert log.object_id == str(self.agent.pk)
        assert log.ip_address == '192.168.1.1'
        assert log.new_values['name'] == 'Test Agent'
    
    def test_audit_log_tracks_updates(self):
        """Test audit log for update actions"""
        log = AuditLog.objects.create(
            user=self.user,
            action=AuditLog.ActionType.UPDATE,
            object_type='Agent',
            object_id=str(self.agent.pk),
            object_repr=str(self.agent),
            old_values={'name': 'Old Name', 'description': 'Old desc'},
            new_values={'name': 'New Name', 'description': 'New desc'},
            ip_address='192.168.1.1'
        )
        
        assert log.action == AuditLog.ActionType.UPDATE
        assert log.old_values['name'] == 'Old Name'
        assert log.new_values['name'] == 'New Name'
        
        # Verify change tracking
        assert log.old_values != log.new_values
    
    def test_audit_log_tracks_deletions(self):
        """Test audit log for deletion actions"""
        agent_data = {
            'id': self.agent.id,
            'name': self.agent.name,
            'use_case': self.agent.use_case
        }
        
        log = AuditLog.objects.create(
            user=self.user,
            action=AuditLog.ActionType.DELETE,
            object_type='Agent',
            object_id=str(self.agent.pk),
            object_repr=str(self.agent),
            old_values=agent_data,
            ip_address='192.168.1.1'
        )
        
        assert log.action == AuditLog.ActionType.DELETE
        assert log.old_values['name'] == self.agent.name
        assert log.new_values == {}  # No new values for deletion
    
    def test_audit_log_tracks_access(self):
        """Test audit log for access/view actions"""
        log = AuditLog.objects.create(
            user=self.user,
            action=AuditLog.ActionType.ACCESS,
            object_type='Agent',
            object_id=str(self.agent.pk),
            object_repr=str(self.agent),
            ip_address='192.168.1.1',
            metadata={
                'access_type': 'view',
                'accessed_at': timezone.now().isoformat()
            }
        )
        
        assert log.action == AuditLog.ActionType.ACCESS
        assert log.metadata['access_type'] == 'view'
    
    def test_audit_log_queryable_by_user(self):
        """Test querying audit logs by user"""
        # Create logs for different users
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        AuditLog.log_action(
            user=self.user,
            action=AuditLog.ActionType.CREATE,
            obj=self.agent,
            ip_address='192.168.1.1'
        )
        
        other_agent = Agent.objects.create(
            user=other_user,
            name='Other Agent',
            description='Other',
            use_case='research'
        )
        
        AuditLog.log_action(
            user=other_user,
            action=AuditLog.ActionType.CREATE,
            obj=other_agent,
            ip_address='192.168.1.2'
        )
        
        # Query by user
        user_logs = AuditLog.objects.filter(user=self.user)
        assert user_logs.count() == 1
        assert user_logs.first().user == self.user
    
    def test_audit_log_queryable_by_action(self):
        """Test querying audit logs by action type"""
        # Create different action types
        AuditLog.log_action(
            user=self.user,
            action=AuditLog.ActionType.CREATE,
            obj=self.agent,
            ip_address='192.168.1.1'
        )
        
        AuditLog.log_action(
            user=self.user,
            action=AuditLog.ActionType.UPDATE,
            obj=self.agent,
            ip_address='192.168.1.1'
        )
        
        AuditLog.log_action(
            user=self.user,
            action=AuditLog.ActionType.DELETE,
            obj=self.agent,
            ip_address='192.168.1.1'
        )
        
        # Query by action
        create_logs = AuditLog.objects.filter(action=AuditLog.ActionType.CREATE)
        assert create_logs.count() == 1
        
        all_actions = AuditLog.objects.filter(user=self.user)
        assert all_actions.count() == 3
    
    def test_log_filtering_by_time_range(self):
        """Test filtering logs by date range"""
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        
        # Create logs at different times
        StructuredLog.objects.create(
            level=StructuredLog.LogLevel.INFO,
            logger_name='test',
            message='Recent log',
            created_at=now
        )
        
        StructuredLog.objects.create(
            level=StructuredLog.LogLevel.INFO,
            logger_name='test',
            message='Yesterday log',
            created_at=yesterday
        )
        
        StructuredLog.objects.create(
            level=StructuredLog.LogLevel.INFO,
            logger_name='test',
            message='Old log',
            created_at=week_ago
        )
        
        # Filter by date range
        recent_logs = StructuredLog.objects.filter(
            created_at__gte=yesterday
        )
        assert recent_logs.count() == 2
        
        week_logs = StructuredLog.objects.filter(
            created_at__gte=week_ago
        )
        assert week_logs.count() == 3
    
    def test_log_aggregation_by_level(self):
        """Test aggregating logs by level"""
        # Create logs with different levels
        for _ in range(5):
            StructuredLog.objects.create(
                level=StructuredLog.LogLevel.INFO,
                logger_name='test',
                message='Info log'
            )
        
        for _ in range(3):
            StructuredLog.objects.create(
                level=StructuredLog.LogLevel.ERROR,
                logger_name='test',
                message='Error log'
            )
        
        for _ in range(2):
            StructuredLog.objects.create(
                level=StructuredLog.LogLevel.WARNING,
                logger_name='test',
                message='Warning log'
            )
        
        # Count by level
        info_count = StructuredLog.objects.filter(
            level=StructuredLog.LogLevel.INFO
        ).count()
        error_count = StructuredLog.objects.filter(
            level=StructuredLog.LogLevel.ERROR
        ).count()
        warning_count = StructuredLog.objects.filter(
            level=StructuredLog.LogLevel.WARNING
        ).count()
        
        assert info_count == 5
        assert error_count == 3
        assert warning_count == 2


@pytest.mark.django_db
class TestAnalyticsMiddleware(TestCase):
    """Test analytics middleware functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_middleware_logs_api_requests(self):
        """Test that middleware logs API requests"""
        from django.test import RequestFactory
        from django.http import HttpResponse
        
        factory = RequestFactory()
        request = factory.get('/api/agents/')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        request.META['HTTP_USER_AGENT'] = 'Test Agent'
        
        # Create mock middleware
        def get_response(req):
            return HttpResponse('OK')
        
        middleware = AnalyticsMiddleware(get_response)
        
        # Process request
        response = middleware(request)
        
        # Verify log was created
        logs = UsageLog.objects.filter(
            endpoint='/api/agents/',
            method='GET'
        )
        assert logs.exists()
        
        log = logs.first()
        assert log.user == self.user
        assert log.status_code == 200
    
    def test_middleware_records_response_time(self):
        """Test that middleware records response time"""
        from django.test import RequestFactory
        from django.http import HttpResponse
        import time
        
        factory = RequestFactory()
        request = factory.get('/api/agents/')
        request.user = self.user
        
        def slow_response(req):
            time.sleep(0.1)  # 100ms delay
            return HttpResponse('OK')
        
        middleware = AnalyticsMiddleware(slow_response)
        response = middleware(request)
        
        log = UsageLog.objects.filter(endpoint='/api/agents/').first()
        assert log is not None
        assert log.response_time_ms >= 100  # Should be at least 100ms