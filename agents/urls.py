"""
URL patterns for agents app.
Phase 2: Complete CRUD operations
"""
from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    # =========== Main actions ==============================
    path('', views.AgentListView.as_view(), name='agent_list'),
    path('create/', views.AgentCreateView.as_view(), name='agent_create'),
    
    # ============== Detail, Update, Delete ===============================
    path('<int:pk>/', views.AgentDetailView.as_view(), name='agent_detail'),
    path('<int:pk>/edit/', views.AgentUpdateView.as_view(), name='agent_update'),
    path('<int:pk>/delete/', views.AgentDeleteView.as_view(), name='agent_delete'),
    
    # =========== Additional actions ==============================
    path('<int:pk>/clone/', views.agent_clone, name='agent_clone'),
    path('<int:pk>/toggle-active/', views.agent_toggle_active, name='agent_toggle_active'),

    # =========== LLm integrations setup ==============================
    path('<int:pk>/setup-llm/', views.agent_setup_llm, name='agent_setup_llm'),
    path('<int:pk>/integrations/<int:integration_id>/delete/', views.agent_delete_integration, name='agent_delete_integration'),
    path('<int:agent_id>/knowledge/', views.KnowledgeBaseListView.as_view(), name='knowledge_base_list'),
    path('<int:agent_id>/knowledge/create/', views.KnowledgeBaseCreateView.as_view(), name='knowledge_base_create'),
    path('knowledge/<int:pk>/delete/', views.KnowledgeBaseDeleteView.as_view(), name='knowledge_base_delete'),
]