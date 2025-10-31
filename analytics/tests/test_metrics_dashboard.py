"""
Test cases for Analytics Dashboard Views - Phase 8
Tests dashboard rendering, permissions, and metrics display
"""
import pytest
import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from analytics.models import (
    UsageLog,
    ConversationMetrics,
    AgentPerformance,
    AnalyticsService
)
from agents.models import Agent
from chat.models import Conversation, Message

User = get_user_model()


@pytest.mark.django_db
class TestMetricsDashboard(TestCase):
    """Test analytics dashboard views and functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        # Create test agent
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
                response_time_ms=150 + (i * 10),
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost=Decimal('0.0015')
            )
        
        # Login
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_dashboard_renders_overview(self):
        """Test that dashboard page renders with overview metrics"""
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        assert response.status_code == 200
        assert 'metrics' in response.context
        assert 'timeline_labels' in response.context
        assert 'timeline_executions' in response.context
        
        # Check that metrics contain expected keys
        metrics = response.context['metrics']
        assert 'overview' in metrics
        assert 'by_agent' in metrics
        assert 'timeline' in metrics
    
    def test_dashboard_requires_authentication(self):
        """Test that dashboard requires login"""
        self.client.logout()
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        # Should redirect to login
        assert response.status_code == 302
        assert 'login' in response.url
    
    def test_dashboard_date_range_filter(self):
        """Test dashboard with different date ranges"""
        url = reverse('analytics:dashboard')
        
        # Test 24h range
        response = self.client.get(url, {'range': '24h'})
        assert response.status_code == 200
        assert response.context['date_range'] == '24h'
        
        # Test 7d range
        response = self.client.get(url, {'range': '7d'})
        assert response.status_code == 200
        assert response.context['date_range'] == '7d'
        
        # Test 30d range
        response = self.client.get(url, {'range': '30d'})
        assert response.status_code == 200
        assert response.context['date_range'] == '30d'
    
    def test_agent_stats_display(self):
        """Test that agent statistics are displayed correctly"""
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        metrics = response.context['metrics']
        
        # Check overview stats
        assert 'total_agents' in metrics['overview']
        assert metrics['overview']['total_agents'] >= 1
        
        # Check by_agent metrics
        assert str(self.agent.id) in metrics['by_agent'] or self.agent.id in metrics['by_agent']
        
        # Verify agent metrics structure
        if str(self.agent.id) in metrics['by_agent']:
            agent_metrics = metrics['by_agent'][str(self.agent.id)]
        else:
            agent_metrics = metrics['by_agent'][self.agent.id]
            
        assert 'name' in agent_metrics
        assert 'executions' in agent_metrics
        assert 'total_tokens' in agent_metrics
    
    def test_use_case_metrics_accuracy(self):
        """Test that use case specific metrics are calculated correctly"""
        # Create conversation with metrics
        conversation = Conversation.objects.create(
            agent=self.agent,
            user=self.user,
            title='Test Conversation'
        )
        
        ConversationMetrics.objects.create(
            conversation=conversation,
            started_at=timezone.now() - timedelta(minutes=10),
            resolved=True,
            resolution_time_seconds=300,
            avg_sentiment_score=0.8,
            satisfaction_rating=5
        )
        
        # Create performance record with use case KPIs
        today = timezone.now().date()
        performance = AgentPerformance.objects.create(
            agent=self.agent,
            date=today,
            execution_count=10
        )
        performance.calculate_use_case_kpis()
        
        # Verify KPIs are calculated
        assert performance.use_case_metrics is not None
        assert isinstance(performance.use_case_metrics, dict)
        
        # For support use case, check specific metrics
        if self.agent.use_case == 'support':
            assert 'resolution_rate' in performance.use_case_metrics
            assert 'avg_sentiment' in performance.use_case_metrics
    
    def test_time_series_data_format(self):
        """Test that timeline data is properly formatted for charts"""
        url = reverse('analytics:dashboard')
        response = self.client.get(url, {'range': '7d'})
        
        # Get timeline data
        timeline_labels = json.loads(response.context['timeline_labels'])
        timeline_executions = json.loads(response.context['timeline_executions'])
        timeline_tokens = json.loads(response.context['timeline_tokens'])
        timeline_costs = json.loads(response.context['timeline_costs'])
        
        # Verify data structure
        assert isinstance(timeline_labels, list)
        assert isinstance(timeline_executions, list)
        assert isinstance(timeline_tokens, list)
        assert isinstance(timeline_costs, list)
        
        # Verify arrays have same length
        assert len(timeline_labels) == len(timeline_executions)
        assert len(timeline_labels) == len(timeline_tokens)
        assert len(timeline_labels) == len(timeline_costs)
        
        # Verify data types
        if len(timeline_executions) > 0:
            assert isinstance(timeline_executions[0], int)
        if len(timeline_tokens) > 0:
            assert isinstance(timeline_tokens[0], int)
        if len(timeline_costs) > 0:
            assert isinstance(timeline_costs[0], (int, float))
    
    def test_dashboard_permissions(self):
        """Test that users only see their own data"""
        # Create agent for other user
        other_agent = Agent.objects.create(
            user=self.other_user,
            name='Other Agent',
            description='Other Description',
            use_case='research'
        )
        
        UsageLog.objects.create(
            user=self.other_user,
            agent=other_agent,
            event_type=UsageLog.EventType.AGENT_EXECUTED,
            total_tokens=100
        )
        
        # Get dashboard as first user
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        metrics = response.context['metrics']
        
        # Verify user only sees their own agents
        agent_ids = [str(aid) for aid in metrics['by_agent'].keys()]
        assert str(self.agent.id) in agent_ids
        assert str(other_agent.id) not in agent_ids
    
    def test_agent_analytics_view_permissions(self):
        """Test that agent analytics respects ownership"""
        # Create agent for other user
        other_agent = Agent.objects.create(
            user=self.other_user,
            name='Other Agent',
            description='Other Description',
            use_case='research'
        )
        
        # Try to access other user's agent analytics
        url = reverse('analytics:agent_analytics', kwargs={'agent_id': other_agent.id})
        response = self.client.get(url)
        
        # Should get permission denied (403)
        assert response.status_code == 403
        
        # Access own agent should work
        url = reverse('analytics:agent_analytics', kwargs={'agent_id': self.agent.id})
        response = self.client.get(url)
        assert response.status_code == 200
    
    def test_agent_analytics_detailed_view(self):
        """Test detailed agent analytics view"""
        url = reverse('analytics:agent_analytics', kwargs={'agent_id': self.agent.id})
        response = self.client.get(url)
        
        assert response.status_code == 200
        assert 'agent' in response.context
        assert 'stats' in response.context
        assert 'timeline_data' in response.context
        
        # Verify stats structure
        stats = response.context['stats']
        assert 'total_executions' in stats
        assert 'avg_response_time' in stats
        assert 'total_tokens' in stats
        assert 'error_rate' in stats
        assert 'success_rate' in stats
    
    def test_performance_monitor_view(self):
        """Test performance monitoring view"""
        url = reverse('analytics:performance_monitor')
        response = self.client.get(url)
        
        assert response.status_code == 200
        assert 'metrics' in response.context
        
        metrics = response.context['metrics']
        assert 'requests_per_minute' in metrics
        assert 'avg_response_time' in metrics
        assert 'error_rate' in metrics
    
    def test_log_viewer_renders(self):
        """Test log viewer page renders"""
        url = reverse('analytics:log_viewer')
        response = self.client.get(url)
        
        assert response.status_code == 200
        assert 'logs' in response.context
        assert 'log_levels' in response.context
    
    def test_metrics_api_endpoint(self):
        """Test metrics API endpoint"""
        url = reverse('analytics:api_metrics')
        response = self.client.get(url, {'type': 'overview', 'range': '7d'})
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert 'overview' in data
        assert 'timeline' in data


@pytest.mark.django_db
class TestDashboardEdgeCases(TestCase):
    """Test edge cases in dashboard functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_dashboard_with_no_agents(self):
        """Test dashboard when user has no agents"""
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        assert response.status_code == 200
        metrics = response.context['metrics']
        assert metrics['overview']['total_agents'] == 0
    
    def test_dashboard_with_no_usage_data(self):
        """Test dashboard when agent has no usage data"""
        agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            description='Test Description',
            use_case='support'
        )
        
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        assert response.status_code == 200
        # Should handle gracefully with zero values
    
    def test_timeline_data_with_gaps(self):
        """Test timeline data generation with date gaps"""
        agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            description='Test Description',
            use_case='support'
        )
        
        # Create usage logs with gaps
        UsageLog.objects.create(
            user=self.user,
            agent=agent,
            event_type=UsageLog.EventType.AGENT_EXECUTED,
            created_at=timezone.now() - timedelta(days=5),
            total_tokens=100
        )
        
        UsageLog.objects.create(
            user=self.user,
            agent=agent,
            event_type=UsageLog.EventType.AGENT_EXECUTED,
            created_at=timezone.now() - timedelta(days=1),
            total_tokens=150
        )
        
        url = reverse('analytics:dashboard')
        response = self.client.get(url, {'range': '7d'})
        
        assert response.status_code == 200
        # Timeline should fill gaps with zeros
        timeline_labels = json.loads(response.context['timeline_labels'])
        assert len(timeline_labels) > 2  # Should have entries for all days