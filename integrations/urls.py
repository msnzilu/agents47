"""
URL patterns for integrations app.
"""
from django.urls import path
from . import views

app_name = 'integrations'

urlpatterns = [
    # Integration Management (per agent)
    path('agent/<int:agent_id>/', views.integration_list, name='integration_list'),
    path('agent/<int:agent_id>/create/', views.integration_create, name='integration_create'),
    path('agent/<int:agent_id>/<int:pk>/', views.integration_detail, name='integration_detail'),
    path('agent/<int:agent_id>/<int:pk>/edit/', views.integration_update, name='integration_update'),
    path('agent/<int:agent_id>/<int:pk>/delete/', views.integration_delete, name='integration_delete'),
    path('agent/<int:agent_id>/<int:pk>/toggle-active/', views.integration_toggle_active, name='integration_toggle_active'),
    path('agent/<int:agent_id>/<int:pk>/test/', views.integration_test, name='integration_test'),
    
    # API Keys
    path('api-keys/', views.api_key_list, name='api_key_list'),
    path('api-keys/create/', views.api_key_create, name='api_key_create'),
    path('api-keys/<int:pk>/', views.api_key_detail, name='api_key_detail'),
    path('api-keys/<int:pk>/delete/', views.api_key_delete, name='api_key_delete'),
    
    # Public Webhook Receiver
    path('webhook/<int:integration_id>/<str:secret>/', views.webhook_receiver, name='webhook_receiver'),
]