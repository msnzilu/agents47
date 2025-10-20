"""
URL patterns for chat app.
"""
from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('<int:agent_id>/', views.chat_view, name='chat_view'),
    path('embed/<int:agent_id>/', views.embed_chat, name='embed_chat'),
]