"""
Notification URLs
"""
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('api/', views.notification_api, name='api'),
    path('<int:notification_id>/read/', views.mark_as_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_read'),
    path('<int:notification_id>/archive/', views.archive_notification, name='archive'),
]