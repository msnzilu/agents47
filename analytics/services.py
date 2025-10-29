"""
Analytics Service Layer
Phase 8: Analytics & Monitoring
Handles all analytics calculations and aggregations
"""

from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
import csv
import json
from io import StringIO
import logging

from agents.models import Agent
from chat.models import Conversation, Message
from .models import (
    UsageLog, ConversationMetrics, AgentPerformance
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics calculations and aggregations"""
    
    @staticmethod
    def get_dashboard_metrics(user, date_range='7d'):
        """
        Get dashboard metrics for a user
        
        Args:
            user: User instance
            date_range: Time range ('24h', '7d', '30d', '90d')
            
        Returns:
            Dictionary with metrics
        """
        # Calculate date range
        end_date = timezone.now()
        
        if date_range == '24h':
            start_date = end_date - timedelta(hours=24)
        elif date_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif date_range == '30d':
            start_date = end_date - timedelta(days=30)
        elif date_range == '90d':
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=7)
        
        # Get user's agents
        agents = Agent.objects.filter(user=user)
        
        # Get conversations
        conversations = Conversation.objects.filter(
            agent__in=agents,
            created_at__gte=start_date
        )
        
        # Get usage logs
        usage_logs = UsageLog.objects.filter(
            user=user,
            created_at__gte=start_date
        )
        
        # Calculate basic metrics
        total_agents = agents.count()
        active_agents = agents.filter(is_active=True).count()
        total_conversations = conversations.count()
        total_messages = Message.objects.filter(conversation__in=conversations).count()
        
        # API and token metrics
        total_api_calls = usage_logs.count()
        total_tokens = usage_logs.aggregate(total=Sum('total_tokens'))['total'] or 0
        total_cost = usage_logs.aggregate(total=Sum('cost'))['total'] or 0
        
        # Success rate
        successful_calls = usage_logs.filter(status_code__lt=400).count()
        success_rate = (successful_calls / total_api_calls * 100) if total_api_calls > 0 else 0
        
        # Average response time
        avg_response_time = usage_logs.aggregate(avg=Avg('response_time_ms'))['avg'] or 0
        
        # Timeline data - group by date
        timeline = usage_logs.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            executions=Count('id'),
            tokens=Sum('total_tokens'),
            cost=Sum('cost')
        ).order_by('date')
        
        # Format timeline for JSON
        timeline_data = []
        for item in timeline:
            timeline_data.append({
                'date': item['date'].strftime('%Y-%m-%d') if item['date'] else '',
                'executions': item['executions'],
                'tokens': item['tokens'] or 0,
                'cost': float(item['cost'] or 0)
            })
        
        # Top agents performance
        top_agents_data = []
        for agent in agents[:10]:  # Top 10 agents
            agent_logs = usage_logs.filter(agent=agent)
            
            # Try to get performance data from AgentPerformance table
            agent_performance = AgentPerformance.objects.filter(
                agent=agent,
                date__gte=start_date.date()
            ).aggregate(
                total_executions=Sum('execution_count'),
                avg_response=Avg('avg_response_time_ms'),
                avg_success_rate=Avg('success_rate')
            )
            
            # If no performance data, calculate from logs
            if not agent_performance['total_executions']:
                log_stats = agent_logs.aggregate(
                    total=Count('id'),
                    avg_response=Avg('response_time_ms')
                )
                successful = agent_logs.filter(status_code__lt=400).count()
                
                top_agents_data.append({
                    'id': agent.id,
                    'name': agent.name,
                    'use_case': agent.use_case,
                    'execution_count': log_stats['total'] or 0,
                    'avg_response_time': log_stats['avg_response'] or 0,
                    'success_rate': (successful / log_stats['total'] * 100) if log_stats['total'] > 0 else 0
                })
            else:
                top_agents_data.append({
                    'id': agent.id,
                    'name': agent.name,
                    'use_case': agent.use_case,
                    'execution_count': agent_performance['total_executions'] or 0,
                    'avg_response_time': agent_performance['avg_response'] or 0,
                    'success_rate': (agent_performance['avg_success_rate'] or 0) * 100
                })
        
        # Sort by execution count
        top_agents_data.sort(key=lambda x: x['execution_count'], reverse=True)
        
        return {
            'total_agents': total_agents,
            'active_agents': active_agents,
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'total_api_calls': total_api_calls,
            'total_tokens': total_tokens,
            'total_cost': float(total_cost),
            'success_rate': success_rate,
            'avg_response_time': avg_response_time,
            'timeline': timeline_data,
            'top_agents': top_agents_data,
            'date_range': date_range,
            'start_date': start_date,
            'end_date': end_date
        }
    
    @staticmethod
    def get_agent_metrics(agent, date_range='7d'):
        """
        Get metrics for a specific agent
        
        Args:
            agent: Agent instance
            date_range: Time range
            
        Returns:
            Dictionary with agent-specific metrics
        """
        # Calculate date range
        end_date = timezone.now()
        
        if date_range == '24h':
            start_date = end_date - timedelta(hours=24)
        elif date_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif date_range == '30d':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=7)
        
        # Get usage logs for this agent
        usage_logs = UsageLog.objects.filter(
            agent=agent,
            created_at__gte=start_date
        )
        
        # Get conversations
        conversations = Conversation.objects.filter(
            agent=agent,
            created_at__gte=start_date
        )
        
        # Calculate stats
        total_executions = usage_logs.count()
        unique_users = usage_logs.values('user').distinct().count()
        total_conversations = conversations.count()
        total_messages = Message.objects.filter(conversation__in=conversations).count()
        
        avg_response_time = usage_logs.aggregate(avg=Avg('response_time_ms'))['avg'] or 0
        total_tokens = usage_logs.aggregate(total=Sum('total_tokens'))['total'] or 0
        total_cost = usage_logs.aggregate(total=Sum('cost'))['total'] or 0
        
        successful = usage_logs.filter(status_code__lt=400).count()
        success_rate = (successful / total_executions * 100) if total_executions > 0 else 0
        
        error_rate = ((total_executions - successful) / total_executions * 100) if total_executions > 0 else 0
        
        return {
            'total_executions': total_executions,
            'unique_users': unique_users,
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'avg_response_time': avg_response_time,
            'total_tokens': total_tokens,
            'total_cost': float(total_cost),
            'success_rate': success_rate,
            'error_rate': error_rate
        }
    
    @staticmethod
    def get_use_case_metrics(agent, start_date):
        """
        Get use-case specific metrics for an agent
        
        Args:
            agent: Agent instance
            start_date: Start date for metrics
            
        Returns:
            Dictionary with use-case specific metrics
        """
        use_case = agent.use_case
        metrics = {}
        
        conversations = Conversation.objects.filter(
            agent=agent,
            created_at__gte=start_date
        )
        
        if use_case == 'support':
            conversation_metrics = ConversationMetrics.objects.filter(
                conversation__in=conversations
            )
            
            total_convs = conversation_metrics.count()
            
            metrics = {
                'resolution_rate': (
                    conversation_metrics.filter(resolved=True).count() / total_convs * 100
                ) if total_convs > 0 else 0,
                'escalation_rate': (
                    conversation_metrics.filter(escalation_triggered=True).count() / total_convs * 100
                ) if total_convs > 0 else 0,
                'avg_sentiment': conversation_metrics.aggregate(
                    avg=Avg('avg_sentiment_score')
                )['avg'] or 0,
                'avg_satisfaction': conversation_metrics.filter(
                    satisfaction_rating__isnull=False
                ).aggregate(
                    avg=Avg('satisfaction_rating')
                )['avg'] or 0,
            }
        
        elif use_case == 'research':
            from agents.models import ToolExecution
            tool_execs = ToolExecution.objects.filter(
                agent=agent,
                created_at__gte=start_date
            )
            
            metrics = {
                'total_searches': tool_execs.filter(
                    tool_name='multi_source_search'
                ).count(),
                'total_summaries': tool_execs.filter(
                    tool_name='summarizer'
                ).count(),
                'data_extractions': tool_execs.filter(
                    tool_name='data_extractor'
                ).count(),
            }
        
        elif use_case == 'sales':
            from agents.models import ToolExecution
            tool_execs = ToolExecution.objects.filter(
                agent=agent,
                created_at__gte=start_date
            )
            
            metrics = {
                'leads_scored': tool_execs.filter(
                    tool_name='lead_scorer'
                ).count(),
                'crm_lookups': tool_execs.filter(
                    tool_name='crm_connector'
                ).count(),
            }
        
        elif use_case == 'automation':
            from agents.models import ToolExecution
            tool_execs = ToolExecution.objects.filter(
                agent=agent,
                created_at__gte=start_date
            )
            
            metrics = {
                'workflows_executed': tool_execs.filter(
                    tool_name='workflow_executor'
                ).count(),
                'emails_sent': tool_execs.filter(
                    tool_name='email_sender'
                ).count(),
                'webhooks_called': tool_execs.filter(
                    tool_name='webhook_caller'
                ).count(),
            }
        
        return metrics
    
    @staticmethod
    def export_metrics(user, format='csv', date_range='30d'):
        """
        Export metrics in specified format
        
        Args:
            user: User instance
            format: Export format ('csv' or 'json')
            date_range: Time range
            
        Returns:
            Exported data as string
        """
        metrics = AnalyticsService.get_dashboard_metrics(user, date_range)
        
        if format == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Metric', 'Value'])
            
            # Write metrics
            writer.writerow(['Total Agents', metrics['total_agents']])
            writer.writerow(['Active Agents', metrics['active_agents']])
            writer.writerow(['Total Conversations', metrics['total_conversations']])
            writer.writerow(['Total Messages', metrics['total_messages']])
            writer.writerow(['Total API Calls', metrics['total_api_calls']])
            writer.writerow(['Total Tokens', metrics['total_tokens']])
            writer.writerow(['Total Cost', f"${metrics['total_cost']:.4f}"])
            writer.writerow(['Success Rate', f"{metrics['success_rate']:.2f}%"])
            writer.writerow(['Avg Response Time', f"{metrics['avg_response_time']:.0f}ms"])
            
            # Write timeline
            writer.writerow([])
            writer.writerow(['Date', 'Executions', 'Tokens', 'Cost'])
            for item in metrics['timeline']:
                writer.writerow([
                    item['date'],
                    item['executions'],
                    item['tokens'],
                    f"${item['cost']:.4f}"
                ])
            
            # Write top agents
            writer.writerow([])
            writer.writerow(['Agent', 'Use Case', 'Executions', 'Avg Response (ms)', 'Success Rate (%)'])
            for agent in metrics['top_agents']:
                writer.writerow([
                    agent['name'],
                    agent['use_case'],
                    agent['execution_count'],
                    f"{agent['avg_response_time']:.0f}",
                    f"{agent['success_rate']:.2f}"
                ])
            
            return output.getvalue()
        
        elif format == 'json':
            # Make datetime objects JSON serializable
            export_data = {
                **metrics,
                'start_date': metrics['start_date'].isoformat(),
                'end_date': metrics['end_date'].isoformat()
            }
            return json.dumps(export_data, indent=2)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    @staticmethod
    def calculate_performance_metrics(agent, date):
        """
        Calculate daily performance metrics for an agent
        Used by Celery tasks to populate AgentPerformance table
        
        Args:
            agent: Agent instance
            date: Date to calculate metrics for
            
        Returns:
            Dictionary with performance metrics
        """
        from datetime import datetime, time
        
        # Get start and end of day
        start_datetime = datetime.combine(date, time.min)
        end_datetime = datetime.combine(date, time.max)
        
        # Get usage logs for the day
        logs = UsageLog.objects.filter(
            agent=agent,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        )
        
        total_logs = logs.count()
        
        if total_logs == 0:
            return None
        
        # Calculate metrics
        successful = logs.filter(status_code__lt=400).count()
        
        metrics = {
            'execution_count': total_logs,
            'success_count': successful,
            'error_count': total_logs - successful,
            'success_rate': successful / total_logs if total_logs > 0 else 0,
            'error_rate': (total_logs - successful) / total_logs if total_logs > 0 else 0,
            'avg_response_time_ms': logs.aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
            'total_input_tokens': logs.aggregate(total=Sum('input_tokens'))['total'] or 0,
            'total_output_tokens': logs.aggregate(total=Sum('output_tokens'))['total'] or 0,
            'total_cost': logs.aggregate(total=Sum('cost'))['total'] or 0,
        }
        
        return metrics