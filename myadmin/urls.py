"""
URL patterns for custom admin app.
"""
from django.urls import path
from . import views

app_name = 'myadmin'

urlpatterns = [
    # Dashboard
    path('', views.admin_dashboard, name='dashboard'),
    
    # User Management
    path('users/', views.AdminUserListView.as_view(), name='user_list'),
    path('users/<int:pk>/', views.AdminUserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/toggle-active/', views.admin_user_toggle_active, name='user_toggle_active'),
    path('users/<int:pk>/toggle-staff/', views.admin_user_toggle_staff, name='user_toggle_staff'),
    path('users/<int:pk>/delete/', views.admin_user_delete, name='user_delete'),
    
    # Agent Management
    path('agents/', views.AdminAgentListView.as_view(), name='agent_list'),
    path('agents/<int:pk>/', views.AdminAgentDetailView.as_view(), name='agent_detail'),
    path('agents/<int:pk>/toggle-active/', views.admin_agent_toggle_active, name='agent_toggle_active'),
    path('agents/<int:pk>/delete/', views.admin_agent_delete, name='agent_delete'),
]