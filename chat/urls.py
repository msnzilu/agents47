"""
URL patterns for chat app.
"""
from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('<int:agent_id>/', views.chat_view, name='chat_view'),
    path('embed/<int:agent_id>/', views.embed_chat, name='embed_chat'),
    path('<int:agent_id>/history/', views.conversation_history, name='history'),
    path('conversation/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
]