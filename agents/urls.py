"""
URL patterns for agents app.
Phase 2: Complete CRUD operations
"""
from django.urls import path
from .views import main, orchestration, advanced_rag, marketplace, tool_builder

app_name = 'agents'

urlpatterns = [
    # =========== Main actions ==============================
    path('', main.AgentListView.as_view(), name='agent_list'),
    path('create/', main.AgentCreateView.as_view(), name='agent_create'),
    
    # ============== Detail, Update, Delete ===============================
    path('<int:pk>/', main.AgentDetailView.as_view(), name='agent_detail'),
    path('<int:pk>/edit/', main.AgentUpdateView.as_view(), name='agent_update'),
    path('<int:pk>/delete/', main.AgentDeleteView.as_view(), name='agent_delete'),
    
    # =========== Additional actions ==============================
    path('<int:pk>/clone/', main.agent_clone, name='agent_clone'),
    path('<int:pk>/toggle-active/', main.agent_toggle_active, name='agent_toggle_active'),

    # =========== LLm integrations setup ==============================
    path('<int:pk>/setup-llm/', main.agent_setup_llm, name='agent_setup_llm'),
    path('<int:pk>/integrations/<int:integration_id>/delete/', main.agent_delete_integration, name='agent_delete_integration'),
    path('<int:agent_id>/knowledge/', main.KnowledgeBaseListView.as_view(), name='knowledge_base_list'),
    path('<int:agent_id>/knowledge/create/', main.KnowledgeBaseCreateView.as_view(), name='knowledge_base_create'),
    path('knowledge/<int:pk>/delete/', main.KnowledgeBaseDeleteView.as_view(), name='knowledge_base_delete'),

    # ======================================= Orchestration Urls and endpoints ===============================================
    path('orchestrations/', orchestration.OrchestrationListView.as_view(),name='orchestration-list'),
    path('orchestrations/create/', orchestration.OrchestrationCreateView.as_view(), name='orchestration-create'),
    path('orchestrations/<int:pk>/', orchestration.OrchestrationDetailView.as_view(), name='orchestration-detail'),
    path('orchestrations/<int:pk>/update/', orchestration.OrchestrationUpdateView.as_view(), name='orchestration-update'),
    path('orchestrations/<int:pk>/delete/', orchestration.OrchestrationDeleteView.as_view(), name='orchestration-delete'),
    path('orchestrations/<int:orchestration_id>/participants/add/', orchestration.OrchestrationParticipantAddView.as_view(), name='orchestration-participant-add'),
    path('orchestrations/<int:orchestration_id>/participants/<int:participant_id>/remove/', orchestration.OrchestrationParticipantRemoveView.as_view(), name='orchestration-participant-remove'),
    path('orchestrations/<int:orchestration_id>/execute/', orchestration.OrchestrationExecuteView.as_view(), name='orchestration-execute'),
    path('orchestrations/<int:orchestration_id>/test/', orchestration.OrchestrationTestView.as_view(), name='orchestration-test'),
    path('orchestrations/<int:orchestration_id>/executions/', orchestration.OrchestrationExecutionListView.as_view(), name='orchestration-execution-list'),
    path('executions/', orchestration.OrchestrationExecutionListView.as_view(), name='execution-list-all'),
    path('executions/<int:pk>/', orchestration.OrchestrationExecutionDetailView.as_view(), name='execution-detail'),
    path('orchestrations/<int:pk>/metrics/', orchestration.OrchestrationMetricsView.as_view(), name='orchestration-metrics'),
    path('orchestrations/<int:orchestration_id>/clone/', orchestration.OrchestrationCloneView.as_view(), name='orchestration-clone'),
    path('orchestrations/<int:pk>/workflow-builder/', orchestration.OrchestrationWorkflowBuilderView.as_view(), name='orchestration-workflow-builder'),
    path('knowledge-base/<int:kb_id>/hybrid-search/create/', advanced_rag.HybridSearchConfigCreateView.as_view(),name='hybrid-search-config-create'),
    path('knowledge-base/<int:kb_id>/hybrid-search/update/', advanced_rag.HybridSearchConfigUpdateView.as_view(), name='hybrid-search-config-update'),
    path('knowledge-base/<int:kb_id>/hybrid-search/test/', advanced_rag.HybridSearchTestView.as_view(), name='hybrid-search-test'),
    path('knowledge-base/<int:kb_id>/hybrid-search/compare/', advanced_rag.HybridSearchCompareView.as_view(), name='hybrid-search-compare'),
    path('query-expansions/', advanced_rag.QueryExpansionListView.as_view(), name='query-expansion-list'),
    path('agent/<int:agent_id>/query-expansions/', advanced_rag.QueryExpansionListView.as_view(), name='agent-query-expansion-list'),
    path('query-expansion/test/', advanced_rag.QueryExpansionTestView.as_view(), name='query-expansion-test'),
    path('api/knowledge-base/<int:kb_id>/search/', advanced_rag.KnowledgeBaseSearchAPIView.as_view(), name='kb-search-api'),
    path('agent/<int:agent_id>/rag/test/', advanced_rag.RAGTestView.as_view(), name='rag-test'),


    # ============================== Marketplace URLs ==============================================================
    path('marketplace/', marketplace.MarketplaceHomeView.as_view(), name='marketplace-home'),
    path('marketplace/dashboard/', marketplace.MarketplaceDashboardView.as_view(), name='marketplace-dashboard'),
    path('marketplace/agent/<int:pk>/', marketplace.MarketplaceAgentDetailView.as_view(), name='marketplace-agent-detail'),
    path('marketplace/agent/<int:pk>/install/', marketplace.AgentInstallView.as_view(), name='marketplace-agent-install'),
    path('marketplace/publish/', marketplace.PublishAgentView.as_view(), name='marketplace-publish'),
    path('marketplace/my-listings/', marketplace.MyListingsView.as_view(), name='marketplace-my-listings'),
    path('marketplace/my-purchases/', marketplace.MyInstallationsView.as_view(), name='marketplace-my-purchases'),
    path('marketplace/agent/<int:pk>/install/', marketplace.AgentInstallView.as_view(), name='marketplace-agent-install'),
    path('marketplace/installation/<int:pk>/uninstall/', marketplace.AgentUninstallView.as_view(), name='marketplace-agent-uninstall'),
    path('marketplace/my-installations/', marketplace.MyInstallationsView.as_view(), name='marketplace-my-installations'),
    path('marketplace/publish/', marketplace.PublishAgentView.as_view(), name='marketplace-publish'),
    path('marketplace/my-listings/', marketplace.MyListingsView.as_view(), name='marketplace-my-listings'),
    path('marketplace/listing/<int:pk>/update/', marketplace.UpdateListingView.as_view(), name='marketplace-update-listing'),
    path('marketplace/agent/<int:agent_id>/review/', marketplace.CreateReviewView.as_view(), name='marketplace-create-review'),
    path('marketplace/review/<int:review_id>/helpful/', marketplace.ReviewHelpfulnessView.as_view(), name='marketplace-review-helpful'),
    path('marketplace/', marketplace.MarketplaceHomeView.as_view(), name='marketplace-home'),
    path('marketplace/agent/<int:pk>/', marketplace.MarketplaceAgentDetailView.as_view(), name='marketplace-agent-detail'),
    path('marketplace/category/<str:category>/', marketplace.MarketplaceCategoryView.as_view(), name='marketplace-category'),

    # =================================== Tool Builder Urls ======================================================================
    path('custom-tools/', tool_builder.CustomToolListView.as_view(), name='custom-tools-list'),
    path('custom-tools/builder/', tool_builder.CustomToolBuilderView.as_view(), name='custom-tools-builder'),
    path('custom-tools/builder/<int:pk>/', tool_builder.CustomToolBuilderView.as_view(), name='custom-tools-edit'),
    path('custom-tools/<int:pk>/', tool_builder.CustomToolDetailView.as_view(), name='custom-tools-detail'),
    path('custom-tools/<int:pk>/delete/', tool_builder.CustomToolDeleteView.as_view(), name='custom-tools-delete'),
    path('custom-tools/templates/', tool_builder.CustomToolTemplatesView.as_view(), name='custom-tools-templates'),
    path('api/custom-tools/create/', tool_builder.CustomToolCreateAPIView.as_view(), name='api-custom-tools-create'),
    path('api/custom-tools/<int:pk>/update/', tool_builder.CustomToolUpdateAPIView.as_view(), name='api-custom-tools-update'),
    path('api/custom-tools/test/', tool_builder.CustomToolTestAPIView.as_view(), name='api-custom-tools-test'),
    path('api/custom-tools/<int:pk>/execute/', tool_builder.CustomToolExecuteView.as_view(), name='api-custom-tools-execute'),
    path('api/custom-tools/<int:pk>/toggle/', tool_builder.CustomToolToggleView.as_view(), name='api-custom-tools-toggle'),
    path('api/custom-tools/<int:pk>/clone/', tool_builder.CustomToolCloneView.as_view(), name='api-custom-tools-clone'),
]