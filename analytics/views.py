# analytics/views.py
"""
Analytics dashboard views for Phase 8: Analytics & Monitoring
"""

import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.core.exceptions import PermissionDenied

from agents.models import Agent
from chat.models import Conversation, Message
from .models import (
    UsageLog, ConversationMetrics, AgentPerformance,
    StructuredLog, AuditLog, AnalyticsService
)
from .services import AnalyticsService

import logging 
logger = logging.getLogger(__name__)



class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """Main analytics dashboard view"""
    template_name = 'users/analytics/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get date range from query params
        date_range = self.request.GET.get('range', '7d')
        
        # Get metrics
        metrics = AnalyticsService.get_dashboard_metrics(user, date_range)
        
        # Prepare chart data
        timeline_labels = [item['date'] for item in metrics['timeline']]
        timeline_executions = [item['executions'] for item in metrics['timeline']]
        timeline_tokens = [item['tokens'] for item in metrics['timeline']]
        timeline_costs = [item['cost'] for item in metrics['timeline']]
        
        context.update({
            'metrics': metrics,
            'date_range': date_range,
            'timeline_labels': json.dumps(timeline_labels),
            'timeline_executions': json.dumps(timeline_executions),
            'timeline_tokens': json.dumps(timeline_tokens),
            'timeline_costs': json.dumps(timeline_costs),
            'current_time': timezone.now()
        })
        
        return context


class AgentAnalyticsView(LoginRequiredMixin, TemplateView):
    """Analytics view for a specific agent"""
    template_name = 'users/analytics/agent_analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = kwargs.get('agent_id')
        
        # Get agent and check permissions
        agent = get_object_or_404(Agent, id=agent_id)
        if agent.user != self.request.user:
            raise PermissionDenied
        
        # Get date range
        date_range = self.request.GET.get('range', '7d')
        end_date = timezone.now()
        
        if date_range == '24h':
            start_date = end_date - timedelta(hours=24)
        elif date_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif date_range == '30d':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=7)
        
        # Get agent-specific metrics
        usage_logs = UsageLog.objects.filter(
            agent=agent,
            created_at__gte=start_date
        )
        
        # Performance metrics
        performance_data = AgentPerformance.objects.filter(
            agent=agent,
            date__gte=start_date.date()
        ).order_by('date')
        
        # Conversation metrics
        conversations = Conversation.objects.filter(
            agent=agent,
            created_at__gte=start_date
        )
        
        conversation_metrics = ConversationMetrics.objects.filter(
            conversation__in=conversations
        )
        
        # Calculate statistics
        stats = {
            'total_executions': usage_logs.count(),
            'unique_users': usage_logs.values('user').distinct().count(),
            'total_conversations': conversations.count(),
            'total_messages': Message.objects.filter(conversation__in=conversations).count(),
            'avg_response_time': usage_logs.aggregate(
                avg=Avg('response_time_ms')
            )['avg'] or 0,
            'total_tokens': usage_logs.aggregate(
                total=Sum('total_tokens')
            )['total'] or 0,
            'total_cost': usage_logs.aggregate(
                total=Sum('cost')
            )['total'] or 0,
            'error_rate': usage_logs.filter(
                status_code__gte=400
            ).count() / max(usage_logs.count(), 1) * 100,
            'success_rate': usage_logs.filter(
                status_code__lt=400
            ).count() / max(usage_logs.count(), 1) * 100,
        }
        
        # Use-case specific metrics
        use_case_metrics = {}
        if agent.use_case == 'support':
            use_case_metrics = {
                'resolution_rate': conversation_metrics.filter(
                    resolved=True
                ).count() / max(conversation_metrics.count(), 1) * 100,
                'escalation_rate': conversation_metrics.filter(
                    escalation_triggered=True
                ).count() / max(conversation_metrics.count(), 1) * 100,
                'avg_sentiment': conversation_metrics.aggregate(
                    avg=Avg('avg_sentiment_score')
                )['avg'] or 0,
                'avg_satisfaction': conversation_metrics.filter(
                    satisfaction_rating__isnull=False
                ).aggregate(
                    avg=Avg('satisfaction_rating')
                )['avg'] or 0,
            }
        elif agent.use_case == 'research':
            from agents.models import ToolExecution
            tool_execs = ToolExecution.objects.filter(
                agent=agent,
                created_at__gte=start_date
            )
            use_case_metrics = {
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
        # Add more use case specific metrics...
        
        # Prepare timeline data for charts
        timeline_data = []
        for perf in performance_data:
            timeline_data.append({
                'date': perf.date.isoformat(),
                'executions': perf.execution_count,
                'response_time': perf.avg_response_time_ms or 0,
                'tokens': perf.total_input_tokens + perf.total_output_tokens,
                'cost': float(perf.total_cost),
                'error_rate': perf.error_rate * 100
            })
        
        context.update({
            'agent': agent,
            'stats': stats,
            'use_case_metrics': use_case_metrics,
            'timeline_data': json.dumps(timeline_data),
            'date_range': date_range,
            'performance_data': performance_data
        })
        
        return context


class MetricsAPIView(LoginRequiredMixin, View):
    """API endpoint for fetching metrics data"""
    
    def get(self, request):
        """Get metrics data as JSON"""
        user = request.user
        date_range = request.GET.get('range', '7d')
        metric_type = request.GET.get('type', 'overview')
        
        if metric_type == 'overview':
            metrics = AnalyticsService.get_dashboard_metrics(user, date_range)
        elif metric_type == 'agents':
            # Get per-agent metrics
            agents = Agent.objects.filter(user=user)
            metrics = []
            for agent in agents:
                perf = AgentPerformance.objects.filter(
                    agent=agent
                ).order_by('-date').first()
                
                metrics.append({
                    'id': agent.id,
                    'name': agent.name,
                    'use_case': agent.use_case,
                    'executions': perf.execution_count if perf else 0,
                    'response_time': perf.avg_response_time_ms if perf else 0,
                    'success_rate': perf.success_rate if perf else 0
                })
        else:
            metrics = {}
        
        return JsonResponse(metrics, safe=False)


class ExportMetricsView(LoginRequiredMixin, View):
    """Export metrics in various formats"""
    
    def get(self, request):
        """Export metrics"""
        user = request.user
        format = request.GET.get('format', 'csv')
        date_range = request.GET.get('range', '30d')
        
        # Generate export
        try:
            export_data = AnalyticsService.export_metrics(user, format, date_range)
            
            if format == 'csv':
                response = HttpResponse(export_data, content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="analytics_{date_range}.csv"'
            elif format == 'json':
                response = HttpResponse(export_data, content_type='application/json')
                response['Content-Disposition'] = f'attachment; filename="analytics_{date_range}.json"'
            else:
                return JsonResponse({'error': 'Invalid format'}, status=400)
            
            # Log export action
            AuditLog.log_action(
                user=user,
                action=AuditLog.ActionType.EXPORT,
                obj=user,
                ip_address=self._get_client_ip(request),
                metadata={'format': format, 'date_range': date_range}
            )
            
            return response
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LogViewerView(LoginRequiredMixin, TemplateView):
    """View for browsing structured logs"""
    template_name = 'users/analytics/log_viewer.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get filters
        level = self.request.GET.get('level')
        agent_id = self.request.GET.get('agent')
        date = self.request.GET.get('date')
        
        # Base queryset
        logs = StructuredLog.objects.all()
        
        # Apply filters
        if level:
            logs = logs.filter(level=level)
        
        if agent_id:
            agent = get_object_or_404(Agent, id=agent_id, user=user)
            logs = logs.filter(agent=agent)
        
        if date:
            logs = logs.filter(created_at__date=date)
        
        # Paginate
        logs = logs[:100]  # Last 100 logs
        
        # Get user's agents for filter dropdown
        agents = Agent.objects.filter(user=user)
        
        context.update({
            'logs': logs,
            'agents': agents,
            'selected_level': level,
            'selected_agent': agent_id,
            'selected_date': date,
            'log_levels': StructuredLog.LogLevel.choices
        })
        
        return context


class PerformanceMonitorView(LoginRequiredMixin, TemplateView):
    """Real-time performance monitoring view"""
    template_name = 'users/analytics/performance_monitor.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get current performance metrics
        last_hour = timezone.now() - timedelta(hours=1)
        
        recent_logs = UsageLog.objects.filter(
            user=user,
            created_at__gte=last_hour
        )
        
        # Calculate real-time metrics
        metrics = {
            'requests_per_minute': recent_logs.count() / 60,
            'avg_response_time': recent_logs.aggregate(
                avg=Avg('response_time_ms')
            )['avg'] or 0,
            'error_rate': recent_logs.filter(
                status_code__gte=400
            ).count() / max(recent_logs.count(), 1) * 100,
            'active_agents': recent_logs.values('agent').distinct().count(),
            'active_users': recent_logs.values('user').distinct().count(),
        }
        
        # Get recent errors
        recent_errors = StructuredLog.objects.filter(
            level__in=['ERROR', 'CRITICAL'],
            created_at__gte=last_hour
        ).select_related('agent')[:10]
        
        # Get slow queries
        slow_queries = recent_logs.filter(
            response_time_ms__gt=5000  # > 5 seconds
        ).order_by('-response_time_ms')[:10]
        
        context.update({
            'metrics': metrics,
            'recent_errors': recent_errors,
            'slow_queries': slow_queries,
            'current_time': timezone.now()
        })
        
        return context


# Webhook for external monitoring services
class MonitoringWebhookView(View):
    """Webhook endpoint for external monitoring services"""
    
    def post(self, request):
        """Receive monitoring events"""
        try:
            data = json.loads(request.body)
            
            # Log the monitoring event
            StructuredLog.objects.create(
                level=StructuredLog.LogLevel.INFO,
                logger_name='monitoring.webhook',
                message=f"Monitoring event: {data.get('event_type')}",
                metadata=data
            )
            
            # Process specific events
            event_type = data.get('event_type')
            if event_type == 'alert':
                # Handle alert
                self._handle_alert(data)
            elif event_type == 'metric':
                # Store metric
                self._store_metric(data)
            
            return JsonResponse({'status': 'received'})
            
        except Exception as e:
            logger.error(f"Error processing monitoring webhook: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def _handle_alert(self, data):
        """Handle monitoring alerts"""
        # Send notification to admin, create incident, etc.
        pass
    
    def _store_metric(self, data):
        """Store external metrics"""
        # Store in appropriate model
        pass