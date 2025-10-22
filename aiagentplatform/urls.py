"""
URL configuration for ai_agent_platform project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    path('site/administration/', include('myadmin.urls')),
    
    # Home page
    path('', TemplateView.as_view(template_name='users/home.html'), name='home'),
    
    # App URLs
    path('users/', include('users.urls')),
    path('agents/', include('agents.urls')),
    path('chat/', include('chat.urls')),
    path('api/integrations/', include('integrations.urls')),
    # path('analytics/', include('analytics.urls')),
    
    # Health check endpoint
    path('health/', TemplateView.as_view(template_name='health.html'), name='health'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom admin site configuration
admin.site.site_header = "AI Agent Platform Admin"
admin.site.site_title = "AI Agent Platform"
admin.site.index_title = "Welcome to AI Agent Platform Administration"