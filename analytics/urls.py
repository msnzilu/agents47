"""
Analytics URLs
Phase 8: Analytics & Monitoring
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Main Dashboard
    path('', views.AnalyticsDashboardView.as_view(), name='dashboard'),
    
    # Agent-specific Analytics
    path('agent/<int:agent_id>/', views.AgentAnalyticsView.as_view(), name='agent_analytics'),
    
    # Performance Monitor
    path('performance/', views.PerformanceMonitorView.as_view(), name='performance_monitor'),
    
    # Log Viewer
    path('logs/', views.LogViewerView.as_view(), name='log_viewer'),
    
    # API Endpoints
    path('api/metrics/', views.MetricsAPIView.as_view(), name='api_metrics'),
    
    # Export
    path('export/', views.ExportMetricsView.as_view(), name='export_metrics'),
    
    # Monitoring Webhook (for external services)
    path('webhook/monitoring/', views.MonitoringWebhookView.as_view(), name='monitoring_webhook'),
]