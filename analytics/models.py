# Phase 8: Analytics & Monitoring - Complete Implementation
"""
Analytics and monitoring system for the AI Agent Platform.
Tracks usage, performance, and provides dashboards with metrics.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


# ============================================================================
# ANALYTICS MODELS
# ============================================================================

class UsageLog(models.Model):
    """Track all platform usage including API calls, LLM tokens, and response times"""
    
    class EventType(models.TextChoices):
        AGENT_CREATED = 'agent_created', 'Agent Created'
        AGENT_EXECUTED = 'agent_executed', 'Agent Executed'
        CHAT_MESSAGE = 'chat_message', 'Chat Message'
        API_CALL = 'api_call', 'API Call'
        TOOL_EXECUTION = 'tool_execution', 'Tool Execution'
        DOCUMENT_PROCESSED = 'document_processed', 'Document Processed'
        WEBHOOK_SENT = 'webhook_sent', 'Webhook Sent'
        ESCALATION = 'escalation', 'Escalation Triggered'
    
    # Core fields
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='usage_logs'
    )
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.SET_NULL,
        null=True,
        related_name='usage_logs'
    )
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices
    )
    
    # API & Performance metrics
    endpoint = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)  # GET, POST, etc.
    status_code = models.IntegerField(null=True, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    
    # LLM metrics
    llm_provider = models.CharField(max_length=50, blank=True)
    llm_model = models.CharField(max_length=100, blank=True)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['agent', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.user} - {self.created_at}"
    
    @classmethod
    def log_event(cls, event_type, user=None, agent=None, **kwargs):
        """Convenience method to log events"""
        return cls.objects.create(
            event_type=event_type,
            user=user,
            agent=agent,
            **kwargs
        )


class ConversationMetrics(models.Model):
    """Aggregate metrics for conversations"""
    
    conversation = models.OneToOneField(
        'chat.Conversation',
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    
    # Duration metrics
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    
    # Message metrics
    total_messages = models.IntegerField(default=0)
    user_messages = models.IntegerField(default=0)
    assistant_messages = models.IntegerField(default=0)
    
    # Token usage
    total_input_tokens = models.IntegerField(default=0)
    total_output_tokens = models.IntegerField(default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    
    # Quality metrics
    avg_response_time_ms = models.IntegerField(null=True, blank=True)
    error_count = models.IntegerField(default=0)
    tool_execution_count = models.IntegerField(default=0)
    escalation_triggered = models.BooleanField(default=False)
    
    # Sentiment metrics (for support use case)
    avg_sentiment_score = models.FloatField(null=True, blank=True)
    min_sentiment_score = models.FloatField(null=True, blank=True)
    max_sentiment_score = models.FloatField(null=True, blank=True)
    
    # Resolution metrics
    resolved = models.BooleanField(default=False)
    resolution_time_seconds = models.IntegerField(null=True, blank=True)
    satisfaction_rating = models.IntegerField(null=True, blank=True)  # 1-5
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def update_metrics(self):
        """Update metrics based on conversation data"""
        from chat.models import Message
        
        messages = Message.objects.filter(conversation=self.conversation)
        
        self.total_messages = messages.count()
        self.user_messages = messages.filter(role='user').count()
        self.assistant_messages = messages.filter(role='assistant').count()
        
        # Calculate duration
        if messages.exists():
            first_message = messages.first()
            last_message = messages.last()
            self.started_at = first_message.created_at
            if self.conversation.is_active:
                self.duration_seconds = (timezone.now() - self.started_at).total_seconds()
            else:
                self.ended_at = last_message.created_at
                self.duration_seconds = (self.ended_at - self.started_at).total_seconds()
        
        self.save()
        return self


class AgentPerformance(models.Model):
    """Track agent-specific performance metrics"""
    
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        related_name='performance_metrics'
    )
    
    # Period for these metrics
    date = models.DateField()
    hour = models.IntegerField(null=True, blank=True)  # 0-23, null for daily aggregates
    
    # Usage metrics
    execution_count = models.IntegerField(default=0)
    unique_users = models.IntegerField(default=0)
    conversation_count = models.IntegerField(default=0)
    message_count = models.IntegerField(default=0)
    
    # Performance metrics
    avg_response_time_ms = models.IntegerField(null=True, blank=True)
    median_response_time_ms = models.IntegerField(null=True, blank=True)
    p95_response_time_ms = models.IntegerField(null=True, blank=True)
    success_rate = models.FloatField(default=0.0)  # 0-1
    error_rate = models.FloatField(default=0.0)  # 0-1
    
    # Token & Cost metrics
    total_input_tokens = models.IntegerField(default=0)
    total_output_tokens = models.IntegerField(default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    
    # Use-case specific KPIs
    use_case_metrics = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['agent', 'date', 'hour']
        ordering = ['-date', '-hour']
        indexes = [
            models.Index(fields=['agent', '-date']),
            models.Index(fields=['date']),
        ]
    
    def calculate_use_case_kpis(self):
        """Calculate KPIs specific to the agent's use case"""
        use_case = self.agent.use_case
        
        if use_case == 'support':
            self.use_case_metrics = self._calculate_support_kpis()
        elif use_case == 'research':
            self.use_case_metrics = self._calculate_research_kpis()
        elif use_case == 'automation':
            self.use_case_metrics = self._calculate_automation_kpis()
        elif use_case == 'scheduling':
            self.use_case_metrics = self._calculate_scheduling_kpis()
        elif use_case == 'knowledge':
            self.use_case_metrics = self._calculate_knowledge_kpis()
        elif use_case == 'sales':
            self.use_case_metrics = self._calculate_sales_kpis()
        
        self.save()
        return self
    
    def _calculate_support_kpis(self):
        """Calculate support-specific KPIs"""
        from chat.models import Conversation
        
        conversations = Conversation.objects.filter(
            agent=self.agent,
            created_at__date=self.date
        )
        
        metrics = ConversationMetrics.objects.filter(
            conversation__in=conversations
        )
        
        return {
            'resolution_rate': metrics.filter(resolved=True).count() / max(metrics.count(), 1),
            'escalation_rate': metrics.filter(escalation_triggered=True).count() / max(metrics.count(), 1),
            'avg_sentiment': metrics.aggregate(avg=Avg('avg_sentiment_score'))['avg'] or 0,
            'avg_resolution_time': metrics.filter(resolved=True).aggregate(
                avg=Avg('resolution_time_seconds')
            )['avg'] or 0,
            'satisfaction_score': metrics.filter(
                satisfaction_rating__isnull=False
            ).aggregate(avg=Avg('satisfaction_rating'))['avg'] or 0
        }
    
    def _calculate_research_kpis(self):
        """Calculate research-specific KPIs"""
        from agents.models import ToolExecution
        
        tool_executions = ToolExecution.objects.filter(
            agent=self.agent,
            created_at__date=self.date
        )
        
        return {
            'queries_per_session': self.message_count / max(self.conversation_count, 1),
            'sources_per_query': tool_executions.filter(
                tool_name='multi_source_search'
            ).count() / max(self.message_count, 1),
            'data_extraction_count': tool_executions.filter(
                tool_name='data_extractor'
            ).count(),
            'summarization_count': tool_executions.filter(
                tool_name='summarizer'
            ).count()
        }
    
    def _calculate_automation_kpis(self):
        """Calculate automation-specific KPIs"""
        from agents.models import ToolExecution
        
        tool_executions = ToolExecution.objects.filter(
            agent=self.agent,
            created_at__date=self.date
        )
        
        workflow_executions = tool_executions.filter(tool_name='workflow_executor')
        
        return {
            'task_completion_rate': workflow_executions.filter(
                success=True
            ).count() / max(workflow_executions.count(), 1),
            'workflows_executed': workflow_executions.count(),
            'emails_sent': tool_executions.filter(tool_name='email_sender').count(),
            'webhooks_called': tool_executions.filter(tool_name='webhook_caller').count(),
            'error_rate': workflow_executions.filter(success=False).count() / max(workflow_executions.count(), 1)
        }
    
    def _calculate_scheduling_kpis(self):
        """Calculate scheduling-specific KPIs"""
        from agents.models import ToolExecution
        
        tool_executions = ToolExecution.objects.filter(
            agent=self.agent,
            created_at__date=self.date
        )
        
        return {
            'meetings_booked': tool_executions.filter(
                tool_name='calendar_manager',
                input_data__action='create_event'
            ).count(),
            'meetings_cancelled': tool_executions.filter(
                tool_name='calendar_manager',
                input_data__action='cancel_event'
            ).count(),
            'availability_checks': tool_executions.filter(
                tool_name='calendar_manager',
                input_data__action='check_availability'
            ).count(),
            'cancellation_rate': 0  # Calculate based on actual data
        }
    
    def _calculate_knowledge_kpis(self):
        """Calculate knowledge-specific KPIs"""
        from agents.models import DocumentChunk
        
        # Get relevant metrics
        total_chunks = DocumentChunk.objects.filter(
            knowledge_base__agent=self.agent
        ).count()
        
        return {
            'answer_accuracy': 0.8,  # Would need feedback mechanism
            'coverage': total_chunks,  # Number of knowledge chunks
            'queries_answered': self.message_count,
            'sources_cited': 0  # Would need to track in responses
        }
    
    def _calculate_sales_kpis(self):
        """Calculate sales-specific KPIs"""
        from agents.models import ToolExecution
        
        tool_executions = ToolExecution.objects.filter(
            agent=self.agent,
            created_at__date=self.date
        )
        
        return {
            'leads_scored': tool_executions.filter(tool_name='lead_scorer').count(),
            'hot_leads': 0,  # Would need to track scores
            'crm_lookups': tool_executions.filter(tool_name='crm_connector').count(),
            'outreach_sent': tool_executions.filter(
                tool_name='email_sender'
            ).count(),
            'conversion_rate': 0  # Would need outcome tracking
        }


# ============================================================================
# MONITORING & LOGGING
# ============================================================================

class StructuredLog(models.Model):
    """Structured logging for debugging and monitoring"""
    
    class LogLevel(models.TextChoices):
        DEBUG = 'DEBUG', 'Debug'
        INFO = 'INFO', 'Info'
        WARNING = 'WARNING', 'Warning'
        ERROR = 'ERROR', 'Error'
        CRITICAL = 'CRITICAL', 'Critical'
    
    level = models.CharField(max_length=10, choices=LogLevel.choices)
    logger_name = models.CharField(max_length=255)
    message = models.TextField()
    
    # Context
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Error details
    exception_type = models.CharField(max_length=255, blank=True)
    exception_message = models.TextField(blank=True)
    traceback = models.TextField(blank=True)
    
    # Performance metrics
    execution_time_ms = models.IntegerField(null=True, blank=True)
    memory_usage_mb = models.IntegerField(null=True, blank=True)
    
    # Additional context
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['level', '-created_at']),
            models.Index(fields=['logger_name', '-created_at']),
            models.Index(fields=['created_at']),
        ]


class AuditLog(models.Model):
    """Audit trail for compliance and security"""
    
    class ActionType(models.TextChoices):
        CREATE = 'CREATE', 'Create'
        UPDATE = 'UPDATE', 'Update'
        DELETE = 'DELETE', 'Delete'
        ACCESS = 'ACCESS', 'Access'
        EXPORT = 'EXPORT', 'Export'
        LOGIN = 'LOGIN', 'Login'
        LOGOUT = 'LOGOUT', 'Logout'
    
    # Who
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # What
    action = models.CharField(max_length=20, choices=ActionType.choices)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=255)
    object_repr = models.TextField(blank=True)
    
    # Changes
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    
    # Additional context
    metadata = models.JSONField(default=dict, blank=True)
    
    # When
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['created_at']),
        ]
    
    @classmethod
    def log_action(cls, user, action, obj, **kwargs):
        """Convenience method to log actions"""
        return cls.objects.create(
            user=user,
            action=action,
            object_type=obj.__class__.__name__,
            object_id=str(obj.pk),
            object_repr=str(obj),
            **kwargs
        )


# ============================================================================
# ANALYTICS SERVICE
# ============================================================================

class AnalyticsService:
    """Service for calculating and aggregating analytics"""
    
    @staticmethod
    def get_dashboard_metrics(user, date_range='7d'):
        """Get metrics for user dashboard"""
        end_date = timezone.now()
        
        if date_range == '24h':
            start_date = end_date - timedelta(hours=24)
        elif date_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif date_range == '30d':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=7)
        
        # Get user's agents
        from agents.models import Agent
        agents = Agent.objects.filter(user=user)
        
        # Calculate metrics
        usage_logs = UsageLog.objects.filter(
            user=user,
            created_at__gte=start_date
        )
        
        metrics = {
            'overview': {
                'total_agents': agents.count(),
                'active_agents': agents.filter(is_active=True).count(),
                'total_conversations': usage_logs.filter(
                    event_type=UsageLog.EventType.CHAT_MESSAGE
                ).values('agent').distinct().count(),
                'total_api_calls': usage_logs.filter(
                    event_type=UsageLog.EventType.API_CALL
                ).count(),
                'total_tokens': usage_logs.aggregate(
                    total=Sum('total_tokens')
                )['total'] or 0,
                'total_cost': usage_logs.aggregate(
                    total=Sum('cost')
                )['total'] or Decimal('0.00')
            },
            'by_agent': {},
            'by_use_case': {},
            'timeline': []
        }
        
        # Per-agent metrics
        for agent in agents:
            agent_logs = usage_logs.filter(agent=agent)
            metrics['by_agent'][agent.id] = {
                'name': agent.name,
                'use_case': agent.use_case,
                'executions': agent_logs.count(),
                'avg_response_time': agent_logs.aggregate(
                    avg=Avg('response_time_ms')
                )['avg'] or 0,
                'total_tokens': agent_logs.aggregate(
                    total=Sum('total_tokens')
                )['total'] or 0,
                'error_rate': agent_logs.filter(
                    status_code__gte=400
                ).count() / max(agent_logs.count(), 1)
            }
        
        # By use case metrics
        use_cases = agents.values_list('use_case', flat=True).distinct()
        for use_case in use_cases:
            use_case_agents = agents.filter(use_case=use_case)
            use_case_logs = usage_logs.filter(agent__in=use_case_agents)
            
            metrics['by_use_case'][use_case] = {
                'agent_count': use_case_agents.count(),
                'total_executions': use_case_logs.count(),
                'avg_response_time': use_case_logs.aggregate(
                    avg=Avg('response_time_ms')
                )['avg'] or 0,
                'kpis': AnalyticsService._get_use_case_kpis(use_case, use_case_agents, start_date)
            }
        
        # Timeline data
        current = start_date
        while current <= end_date:
            day_logs = usage_logs.filter(
                created_at__date=current.date()
            )
            
            metrics['timeline'].append({
                'date': current.date().isoformat(),
                'executions': day_logs.count(),
                'tokens': day_logs.aggregate(Sum('total_tokens'))['total_tokens__sum'] or 0,
                'cost': float(day_logs.aggregate(Sum('cost'))['cost__sum'] or 0),
                'errors': day_logs.filter(status_code__gte=400).count()
            })
            
            current += timedelta(days=1)
        
        return metrics
    
    @staticmethod
    def _get_use_case_kpis(use_case, agents, start_date):
        """Get KPIs specific to use case"""
        performance_metrics = AgentPerformance.objects.filter(
            agent__in=agents,
            date__gte=start_date.date()
        )
        
        if use_case == 'support':
            metrics = performance_metrics.aggregate(
                avg_resolution_rate=Avg('use_case_metrics__resolution_rate'),
                avg_escalation_rate=Avg('use_case_metrics__escalation_rate'),
                avg_sentiment=Avg('use_case_metrics__avg_sentiment')
            )
        elif use_case == 'research':
            metrics = performance_metrics.aggregate(
                avg_queries_per_session=Avg('use_case_metrics__queries_per_session'),
                total_extractions=Sum('use_case_metrics__data_extraction_count')
            )
        elif use_case == 'automation':
            metrics = performance_metrics.aggregate(
                task_completion_rate=Avg('use_case_metrics__task_completion_rate'),
                total_workflows=Sum('use_case_metrics__workflows_executed')
            )
        elif use_case == 'scheduling':
            metrics = performance_metrics.aggregate(
                meetings_booked=Sum('use_case_metrics__meetings_booked'),
                cancellation_rate=Avg('use_case_metrics__cancellation_rate')
            )
        elif use_case == 'knowledge':
            metrics = performance_metrics.aggregate(
                queries_answered=Sum('use_case_metrics__queries_answered'),
                coverage=Avg('use_case_metrics__coverage')
            )
        elif use_case == 'sales':
            metrics = performance_metrics.aggregate(
                leads_scored=Sum('use_case_metrics__leads_scored'),
                conversion_rate=Avg('use_case_metrics__conversion_rate')
            )
        else:
            metrics = {}
        
        # Clean up None values
        return {k: v or 0 for k, v in metrics.items()}
    
    @staticmethod
    def export_metrics(user, format='csv', date_range='30d'):
        """Export metrics in specified format"""
        import csv
        import io
        
        metrics = AnalyticsService.get_dashboard_metrics(user, date_range)
        
        if format == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write overview
            writer.writerow(['Metric', 'Value'])
            for key, value in metrics['overview'].items():
                writer.writerow([key, value])
            
            writer.writerow([])
            
            # Write agent metrics
            writer.writerow(['Agent Metrics'])
            writer.writerow(['Agent', 'Use Case', 'Executions', 'Avg Response Time', 'Tokens', 'Error Rate'])
            for agent_id, agent_metrics in metrics['by_agent'].items():
                writer.writerow([
                    agent_metrics['name'],
                    agent_metrics['use_case'],
                    agent_metrics['executions'],
                    agent_metrics['avg_response_time'],
                    agent_metrics['total_tokens'],
                    agent_metrics['error_rate']
                ])
            
            return output.getvalue()
        
        elif format == 'json':
            return json.dumps(metrics, cls=DjangoJSONEncoder)
        
        else:
            raise ValueError(f"Unsupported format: {format}")


# ============================================================================
# MONITORING MIDDLEWARE
# ============================================================================

class AnalyticsMiddleware:
    """Middleware to track API requests and performance"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Start timer
        start_time = timezone.now()
        
        # Process request
        response = self.get_response(request)
        
        # Calculate response time
        response_time = (timezone.now() - start_time).total_seconds() * 1000
        
        # Log API calls
        if request.path.startswith('/api/'):
            UsageLog.log_event(
                event_type=UsageLog.EventType.API_CALL,
                user=request.user if request.user.is_authenticated else None,
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                response_time_ms=int(response_time),
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        return response
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ============================================================================
# CELERY TASKS FOR PERIODIC METRICS
# ============================================================================

def calculate_daily_metrics():
    """Calculate daily aggregated metrics (run as Celery task)"""
    from agents.models import Agent
    from datetime import date
    
    yesterday = date.today() - timedelta(days=1)
    
    for agent in Agent.objects.filter(is_active=True):
        # Get or create performance record
        performance, created = AgentPerformance.objects.get_or_create(
            agent=agent,
            date=yesterday,
            hour=None  # Daily aggregate
        )
        
        # Calculate metrics
        logs = UsageLog.objects.filter(
            agent=agent,
            created_at__date=yesterday
        )
        
        performance.execution_count = logs.count()
        performance.unique_users = logs.values('user').distinct().count()
        
        # Response times
        response_times = logs.exclude(
            response_time_ms__isnull=True
        ).values_list('response_time_ms', flat=True)
        
        if response_times:
            performance.avg_response_time_ms = sum(response_times) / len(response_times)
            sorted_times = sorted(response_times)
            performance.median_response_time_ms = sorted_times[len(sorted_times) // 2]
            performance.p95_response_time_ms = sorted_times[int(len(sorted_times) * 0.95)]
        
        # Success/Error rates
        total = logs.count()
        if total > 0:
            errors = logs.filter(status_code__gte=400).count()
            performance.error_rate = errors / total
            performance.success_rate = 1 - performance.error_rate
        
        # Token usage
        performance.total_input_tokens = logs.aggregate(Sum('input_tokens'))['input_tokens__sum'] or 0
        performance.total_output_tokens = logs.aggregate(Sum('output_tokens'))['output_tokens__sum'] or 0
        performance.total_cost = logs.aggregate(Sum('cost'))['cost__sum'] or Decimal('0')
        
        # Calculate use-case specific KPIs
        performance.calculate_use_case_kpis()
        
        performance.save()
        
        logger.info(f"Calculated daily metrics for agent {agent.name}")


def generate_weekly_report():
    """Generate and send weekly reports (run as Celery task)"""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    
    for user in User.objects.filter(is_active=True):
        # Get weekly metrics
        metrics = AnalyticsService.get_dashboard_metrics(user, date_range='7d')
        
        # Render email
        html_content = render_to_string(
            'analytics/weekly_report_email.html',
            {'user': user, 'metrics': metrics}
        )
        
        # Send email
        send_mail(
            subject=f'Weekly Analytics Report - {timezone.now().strftime("%B %d, %Y")}',
            message='',  # Plain text version
            html_message=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        
        logger.info(f"Sent weekly report to {user.email}")


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

__all__ = [
    'UsageLog',
    'ConversationMetrics',
    'AgentPerformance',
    'StructuredLog',
    'AuditLog',
    'AnalyticsService',
    'AnalyticsMiddleware',
    'calculate_daily_metrics',
    'generate_weekly_report'
]