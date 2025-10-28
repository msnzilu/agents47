"""
Webhook Management URLs
Phase 7: Integration Layer
"""
from django.urls import path
from . import views

app_name = 'webhooks'

urlpatterns = [
    path('', views.webhook_list, name='webhook-list'),
    path('create/', views.webhook_create, name='webhook-create'),
    path('<int:pk>/', views.webhook_detail, name='webhook-detail'),
    path('<int:pk>/edit/', views.webhook_edit, name='webhook-edit'),
    path('<int:pk>/delete/', views.webhook_delete, name='webhook-delete'),
    path('<int:pk>/toggle/', views.webhook_toggle, name='webhook-toggle'),
    path('deliveries/', views.webhook_deliveries, name='webhook-deliveries'),
    path('test/<int:pk>/', views.webhook_test, name='webhook-test'),
]