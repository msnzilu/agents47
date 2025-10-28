"""
Embeddable Widget URLs
Phase 7: Integration Layer
"""
from django.urls import path
from . import views

app_name = 'embed'

urlpatterns = [
    path('chat/<int:agent_id>/', views.chat_widget, name='chat-widget'),
    path('widget/<int:agent_id>.js', views.widget_loader, name='widget-loader'),
    path('widget/<int:agent_id>.js', views.widget_loader, name='widget-loader-js'),
    path('demo/<int:agent_id>/', views.widget_demo, name='widget-demo'),
]