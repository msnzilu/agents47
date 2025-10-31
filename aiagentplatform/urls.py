"""
URL configuration for ai_agent_platform project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # =================== Admin =================================
    path('admin/', admin.site.urls),
    path('site/administration/', include('myadmin.urls')),
    
    # ========================== Static Page ===========================================================
    path('', TemplateView.as_view(template_name='users/home.html'), name='home'),
    path('privacy-policy/', TemplateView.as_view(template_name='users/legal/privacy.html'), name='privacy'),
    path('terms-of-service/', TemplateView.as_view(template_name='users/legal/terms.html'), name='terms'),
    path('contact-us/', TemplateView.as_view(template_name='users/legal/contact.html'), name='contact'),
    
    # =========================================== App URLs ===============================================
    path('users/', include('users.urls')),
    path('agents/', include('agents.urls')),
    path('agents/chat/', include('chat.urls')),
    path('api/integrations/', include('integrations.urls')),
    path('webhooks/', include('webhooks.urls')),
    path('api/', include('api.urls')),
    path('embed/', include('embed.urls')),
    path('analytics/', include('analytics.urls')),
    path('notifications/', include('notifications.urls')),
    path('security/', include('security.urls')),
    
    # =================================== Health check endpoint ==================================================
    path('health/', TemplateView.as_view(template_name='health.html'), name='health'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
