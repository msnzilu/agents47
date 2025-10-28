"""
REST API URLs
Phase 7: Integration Layer
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Try importing drf-spectacular views safely
try:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
    DRF_SPECTACULAR_AVAILABLE = True
except ImportError:
    DRF_SPECTACULAR_AVAILABLE = False

# Setup DRF router
router = DefaultRouter()
router.register(r'agents', views.AgentViewSet, basename='agent')
router.register(r'conversations', views.ConversationViewSet, basename='conversation')

app_name = 'api'

urlpatterns = [
    # API Root and Health
    path('', views.api_root, name='root'),
    path('health/', views.health_check, name='health-check'),
    
    # Authentication
    path('auth/generate-key/', views.generate_api_key, name='generate-api-key'),
]

# Add API documentation endpoints if drf-spectacular is available
if DRF_SPECTACULAR_AVAILABLE:
    # The schema endpoint must be defined first
    schema_patterns = [
        path('schema/', SpectacularAPIView.as_view(), name='schema'),
    ]
    
    # Then reference it in docs/redoc with the fully qualified name
    doc_patterns = [
        path('docs/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='docs'),
        path('redoc/', SpectacularRedocView.as_view(url_name='api:schema'), name='redoc'),
    ]
    
    urlpatterns = urlpatterns + schema_patterns + doc_patterns

# Add router URLs last (so they don't override other patterns)
urlpatterns += [
    path('', include(router.urls)),
]