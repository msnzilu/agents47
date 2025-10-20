"""
URL patterns for agents app.
Phase 2: Complete CRUD operations
"""
from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    # List and Create
    path('', views.AgentListView.as_view(), name='agent_list'),
    path('create/', views.AgentCreateView.as_view(), name='agent_create'),
    
    # Detail, Update, Delete
    path('<int:pk>/', views.AgentDetailView.as_view(), name='agent_detail'),
    path('<int:pk>/edit/', views.AgentUpdateView.as_view(), name='agent_update'),
    path('<int:pk>/delete/', views.AgentDeleteView.as_view(), name='agent_delete'),
    
    # Additional actions
    path('<int:pk>/clone/', views.agent_clone, name='agent_clone'),
    path('<int:pk>/toggle-active/', views.agent_toggle_active, name='agent_toggle_active'),
]