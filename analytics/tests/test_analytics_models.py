"""
Test cases for Analytics Models - Phase 8
Tests UsageLog, ConversationMetrics, AgentPerformance, StructuredLog, and AuditLog
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.test import TestCase

from analytics.models import (
    UsageLog,
    ConversationMetrics,
    AgentPerformance,
    StructuredLog,
    AuditLog,
    AnalyticsService
)
from agents.models import Agent
from chat.models import Conversation, Message

User = get_user_model()


@pytest.mark.django_db
class TestUsageLog(TestCase):
    """Test UsageLog model and functionality"""
    
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
    
    def test_usage_log_creation(self):
        """Test creating a usage log entry"""
        log = UsageLog.objects.create(
            user=self.user,
            agent=self.agent,
            event_type=UsageLog.EventType.AGENT_EXECUTED,
            endpoint='/api/agents/1/execute/',
            method='POST',
            status_code=200,
            response_time_ms=150,
            llm_provider='openai',
            llm_model='gpt-4o-mini',
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost=Decimal('0.0015'),
            ip_address='127.0.0.1'
        )
        
        assert log.id is not None
        assert log.user == self.user
        assert log.agent == self.agent
        assert log.event_type == UsageLog.EventType.AGENT_EXECUTED
        assert log.response_time_ms == 150
        assert log.total_tokens == 150
        assert log.cost == Decimal('0.0015')
    
    def test_usage_log_event_convenience_method(self):
        """Test log_event convenience method"""
        log = UsageLog.log_event(
            event_type=UsageLog.EventType.CHAT_MESSAGE,
            user=self.user,
            agent=self.agent,
            response_time_ms=200,
            input_tokens=80,
            output_tokens=120,
            total_tokens=200
        )
        
        assert log.event_type == UsageLog.EventType.CHAT_MESSAGE
        assert log.response_time_ms == 200
        assert log.total_tokens == 200
    
    def test_usage_log_without_agent(self):
        """Test creating usage log without agent"""
        log = UsageLog.log_event(
            event_type=UsageLog.EventType.API_CALL,
            user=self.user,
            endpoint='/api/agents/',
            method='GET',
            status_code=200
        )
        
        assert log.agent is None
        assert log.user == self.user
    
    def test_usage_log_filtering_by_date(self):
        """Test filtering usage logs by date range"""
        # Create logs with different dates
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        
        # Create logs
        UsageLog.objects.create(
            user=self.user,
            agent=self.agent,
            event_type=UsageLog.EventType.AGENT_EXECUTED,
            created_at=now
        )
        UsageLog.objects.create(
            user=self.user,
            agent=self.agent,
            event_type=UsageLog.EventType.AGENT_EXECUTED,
            created_at=yesterday
        )
        UsageLog.objects.create(
            user=self.user,
            agent=self.agent,
            event_type=UsageLog.EventType.AGENT_EXECUTED,
            created_at=week_ago
        )
        
        # Test filtering
        last_day_logs = UsageLog.objects.filter(
            user=self.user,
            created_at__gte=now - timedelta(days=1)
        )
        
        assert last_day_logs.count() == 2
    
    def test_usage_log_token_aggregation(self):
        """Test aggregating token usage from logs"""
        # Create multiple logs
        for i in range(5):
            UsageLog.objects.create(
                user=self.user,
                agent=self.agent,
                event_type=UsageLog.EventType.AGENT_EXECUTED,
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost=Decimal('0.0015')
            )
        
        # Aggregate
        from django.db.models import Sum
        total = UsageLog.objects.filter(user=self.user).aggregate(
            total_tokens=Sum('total_tokens'),
            total_cost=Sum('cost')
        )
        
        assert total['total_tokens'] == 750
        assert total['total_cost'] == Decimal('0.0075')


@pytest.mark.django_db
class TestConversationMetrics(TestCase):
    """Test ConversationMetrics model"""
    
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
        self.conversation = Conversation.objects.create(
            agent=self.agent,
            user=self.user,
            title='Test Conversation'
        )
    
    def test_conversation_metrics_calculation(self):
        """Test calculating conversation metrics"""
        # Create messages
        start_time = timezone.now() - timedelta(minutes=10)
        
        Message.objects.create(
            conversation=self.conversation,
            role='user',
            content='Hello',
            created_at=start_time
        )
        Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='Hi there!',
            created_at=start_time + timedelta(seconds=2)
        )
        Message.objects.create(
            conversation=self.conversation,
            role='user',
            content='How can you help?',
            created_at=start_time + timedelta(minutes=1)
        )
        Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='I can help with...',
            created_at=start_time + timedelta(minutes=1, seconds=3)
        )
        
        # Create metrics
        metrics = ConversationMetrics.objects.create(
            conversation=self.conversation,
            started_at=start_time
        )
        
        # Update metrics
        metrics.update_metrics()
        
        assert metrics.total_messages == 4
        assert metrics.user_messages == 2
        assert metrics.assistant_messages == 2
        assert metrics.duration_seconds > 0
    
    def test_conversation_metrics_with_resolution(self):
        """Test conversation metrics with resolution tracking"""
        metrics = ConversationMetrics.objects.create(
            conversation=self.conversation,
            started_at=timezone.now() - timedelta(minutes=5),
            resolved=True,
            resolution_time_seconds=300,
            satisfaction_rating=5
        )
        
        assert metrics.resolved is True
        assert metrics.resolution_time_seconds == 300
        assert metrics.satisfaction_rating == 5
    
    def test_conversation_metrics_sentiment_tracking(self):
        """Test sentiment tracking in conversation metrics"""
        metrics = ConversationMetrics.objects.create(
            conversation=self.conversation,
            started_at=timezone.now(),
            avg_sentiment_score=0.8,
            min_sentiment_score=0.5,
            max_sentiment_score=0.95
        )
        
        assert metrics.avg_sentiment_score == 0.8
        assert metrics.min_sentiment_score == 0.5
        assert metrics.max_sentiment_score == 0.95
    
    def test_conversation_metrics_token_usage(self):
        """Test token usage tracking in conversation metrics"""
        metrics = ConversationMetrics.objects.create(
            conversation=self.conversation,
            started_at=timezone.now(),
            total_input_tokens=1000,
            total_output_tokens=500,
            total_cost=Decimal('0.015')
        )
        
        assert metrics.total_input_tokens == 1000
        assert metrics.total_output_tokens == 500
        assert metrics.total_cost == Decimal('0.015')


@pytest.mark.django_db
class TestAgentPerformance(TestCase):
    """Test AgentPerformance model and aggregations"""
    
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
    
    def test_agent_performance_aggregation(self):
        """Test creating and aggregating agent performance metrics"""
        today = timezone.now().date()
        
        performance = AgentPerformance.objects.create(
            agent=self.agent,
            date=today,
            execution_count=100,
            unique_users=25,
            conversation_count=50,
            message_count=200,
            avg_response_time_ms=150,
            median_response_time_ms=120,
            p95_response_time_ms=300,
            success_rate=0.95,
            error_rate=0.05,
            total_input_tokens=10000,
            total_output_tokens=5000,
            total_cost=Decimal('0.150')
        )
        
        assert performance.execution_count == 100
        assert performance.unique_users == 25
        assert performance.success_rate == 0.95
        assert performance.total_cost == Decimal('0.150')
    
    def test_agent_performance_use_case_kpis(self):
        """Test use-case specific KPIs calculation"""
        today = timezone.now().date()
        
        performance = AgentPerformance.objects.create(
            agent=self.agent,
            date=today,
            execution_count=50
        )
        
        # Calculate use-case KPIs
        performance.calculate_use_case_kpis()
        
        assert 'use_case_metrics' in performance.__dict__
        assert isinstance(performance.use_case_metrics, dict)
    
    def test_metrics_filter_by_date_range(self):
        """Test filtering performance metrics by date range"""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        # Create performance records
        AgentPerformance.objects.create(
            agent=self.agent,
            date=today,
            execution_count=100
        )
        AgentPerformance.objects.create(
            agent=self.agent,
            date=yesterday,
            execution_count=90
        )
        AgentPerformance.objects.create(
            agent=self.agent,
            date=week_ago,
            execution_count=80
        )
        
        # Filter by date range
        last_week = AgentPerformance.objects.filter(
            agent=self.agent,
            date__gte=week_ago
        )
        
        assert last_week.count() == 3
        
        last_day = AgentPerformance.objects.filter(
            agent=self.agent,
            date__gte=yesterday
        )
        
        assert last_day.count() == 2
    
    def test_agent_performance_hourly_aggregation(self):
        """Test hourly performance aggregation"""
        today = timezone.now().date()
        
        # Create hourly performance record
        performance = AgentPerformance.objects.create(
            agent=self.agent,
            date=today,
            hour=14,  # 2 PM
            execution_count=10,
            avg_response_time_ms=200
        )
        
        assert performance.hour == 14
        assert performance.execution_count == 10


@pytest.mark.django_db
class TestStructuredLog(TestCase):
    """Test StructuredLog model"""
    
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
            message='Test log message',
            user=self.user,
            agent=self.agent,
            metadata={'key': 'value'}
        )
        
        assert log.level == StructuredLog.LogLevel.INFO
        assert log.message == 'Test log message'
        assert log.metadata == {'key': 'value'}
    
    def test_error_log_with_exception(self):
        """Test logging errors with exception details"""
        log = StructuredLog.objects.create(
            level=StructuredLog.LogLevel.ERROR,
            logger_name='test.error',
            message='An error occurred',
            exception_type='ValueError',
            exception_message='Invalid value provided',
            traceback='Traceback details...'
        )
        
        assert log.level == StructuredLog.LogLevel.ERROR
        assert log.exception_type == 'ValueError'
        assert log.exception_message == 'Invalid value provided'
    
    def test_performance_metrics_recorded(self):
        """Test recording performance metrics in logs"""
        log = StructuredLog.objects.create(
            level=StructuredLog.LogLevel.INFO,
            logger_name='performance.monitor',
            message='API call completed',
            execution_time_ms=150,
            memory_usage_mb=45
        )
        
        assert log.execution_time_ms == 150
        assert log.memory_usage_mb == 45
    
    def test_log_filtering_by_level(self):
        """Test filtering logs by level"""
        # Create logs with different levels
        StructuredLog.objects.create(
            level=StructuredLog.LogLevel.DEBUG,
            logger_name='test',
            message='Debug message'
        )
        StructuredLog.objects.create(
            level=StructuredLog.LogLevel.INFO,
            logger_name='test',
            message='Info message'
        )
        StructuredLog.objects.create(
            level=StructuredLog.LogLevel.ERROR,
            logger_name='test',
            message='Error message'
        )
        
        # Filter by level
        error_logs = StructuredLog.objects.filter(
            level=StructuredLog.LogLevel.ERROR
        )
        
        assert error_logs.count() == 1
        assert error_logs.first().message == 'Error message'


@pytest.mark.django_db
class TestAuditLog(TestCase):
    """Test AuditLog model for compliance tracking"""
    
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
    
    def test_audit_log_tracks_actions(self):
        """Test audit log tracks user actions"""
        log = AuditLog.log_action(
            user=self.user,
            action=AuditLog.ActionType.CREATE,
            obj=self.agent,
            ip_address='127.0.0.1',
            user_agent='Mozilla/5.0',
            new_values={'name': 'Test Agent', 'use_case': 'support'}
        )
        
        assert log.user == self.user
        assert log.action == AuditLog.ActionType.CREATE
        assert log.object_type == 'Agent'
        assert log.object_id == str(self.agent.pk)
        assert log.ip_address == '127.0.0.1'
    
    def test_audit_log_tracks_updates(self):
        """Test audit log tracks update actions with old/new values"""
        log = AuditLog.objects.create(
            user=self.user,
            action=AuditLog.ActionType.UPDATE,
            object_type='Agent',
            object_id=str(self.agent.pk),
            object_repr=str(self.agent),
            old_values={'name': 'Old Name'},
            new_values={'name': 'New Name'},
            ip_address='127.0.0.1'
        )
        
        assert log.action == AuditLog.ActionType.UPDATE
        assert log.old_values == {'name': 'Old Name'}
        assert log.new_values == {'name': 'New Name'}
    
    def test_audit_log_tracks_deletions(self):
        """Test audit log tracks deletion actions"""
        log = AuditLog.log_action(
            user=self.user,
            action=AuditLog.ActionType.DELETE,
            obj=self.agent,
            ip_address='127.0.0.1',
            old_values={'name': 'Test Agent', 'use_case': 'support'}
        )
        
        assert log.action == AuditLog.ActionType.DELETE
        assert log.old_values['name'] == 'Test Agent'
    
    def test_audit_log_tracks_data_exports(self):
        """Test audit log tracks data export actions"""
        log = AuditLog.objects.create(
            user=self.user,
            action=AuditLog.ActionType.EXPORT,
            object_type='User',
            object_id=str(self.user.pk),
            object_repr=str(self.user),
            ip_address='127.0.0.1',
            metadata={'format': 'csv', 'date_range': '30d'}
        )
        
        assert log.action == AuditLog.ActionType.EXPORT
        assert log.metadata['format'] == 'csv'
        assert log.metadata['date_range'] == '30d'


@pytest.mark.django_db
class TestAnalyticsService(TestCase):
    """Test AnalyticsService functionality"""
    
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
        
        # Create some usage logs
        for i in range(10):
            UsageLog.objects.create(
                user=self.user,
                agent=self.agent,
                event_type=UsageLog.EventType.AGENT_EXECUTED,
                response_time_ms=150 + (i * 10),
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost=Decimal('0.0015')
            )
    
    def test_get_dashboard_metrics(self):
        """Test getting dashboard metrics"""
        metrics = AnalyticsService.get_dashboard_metrics(self.user, '7d')
        
        assert 'overview' in metrics
        assert 'by_agent' in metrics
        assert 'by_use_case' in metrics
        assert 'timeline' in metrics
        
        # Check overview metrics
        assert metrics['overview']['total_agents'] >= 1
        assert metrics['overview']['total_tokens'] > 0
    
    def test_export_metrics_csv(self):
        """Test exporting metrics as CSV"""
        csv_data = AnalyticsService.export_metrics(
            self.user,
            format='csv',
            date_range='7d'
        )
        
        assert csv_data is not None
        assert isinstance(csv_data, str)
        assert 'Metric,Value' in csv_data or 'Agent' in csv_data
    
    def test_export_metrics_json(self):
        """Test exporting metrics as JSON"""
        json_data = AnalyticsService.export_metrics(
            self.user,
            format='json',
            date_range='7d'
        )
        
        assert json_data is not None
        assert isinstance(json_data, str)
        
        # Verify it's valid JSON
        import json
        parsed = json.loads(json_data)
        assert isinstance(parsed, dict)