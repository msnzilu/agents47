"""
Chat Views Tests for Phase 4
Tests view rendering, permissions, and conversation management
FIXED: Removed system_prompt field (doesn't exist in Agent model)
"""
import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from chat.models import Conversation, Message
from agents.models import Agent

User = get_user_model()


class TestChatViews(TestCase):
    """Test chat view functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # FIXED: Removed system_prompt parameter
        self.agent = Agent.objects.create(
            name='Test Agent',
            user=self.user,
            is_active=True
        )
        self.conversation = Conversation.objects.create(
            agent=self.agent,
            user=self.user,
            title='Test Chat'
        )
    
    def test_chat_view_renders_conversation(self):
        """Test that chat view renders successfully with conversation"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response.status_code == 200
        assert 'conversation' in response.context
        assert response.context['conversation'].id == self.conversation.id
        assert 'agent' in response.context
        assert response.context['agent'].id == self.agent.id
    
    def test_chat_view_loads_history(self):
        """Test that chat view loads message history"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create some messages
        for i in range(5):
            Message.objects.create(
                conversation=self.conversation,
                user=self.user,
                role='user',
                content=f'Test message {i}'
            )
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response.status_code == 200
        assert 'messages' in response.context
        assert len(response.context['messages']) == 5
    
    def test_chat_view_requires_agent_ownership(self):
        """Test that users can only access their own agent's chats"""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='pass123'
        )
        
        # Create agent for other user
        other_agent = Agent.objects.create(
            name='Other Agent',
            user=other_user,
            is_active=True
        )
        
        other_conversation = Conversation.objects.create(
            agent=other_agent,
            user=other_user,
            title='Other Chat'
        )
        
        # Try to access other user's conversation
        self.client.login(username='testuser', password='testpass123')
        url = reverse('chat:chat_view', args=[other_agent.id])
        response = self.client.get(f"{url}?conversation={other_conversation.id}")
        
        # Should redirect or return 404
        assert response.status_code in [302, 404]
    
    def test_chat_view_displays_streaming_indicator(self):
        """Test that template includes streaming indicator elements"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        
        # Check for streaming-related elements
        assert 'typing-indicator' in content or 'streaming' in content
        assert 'messages-container' in content
    
    def test_chat_view_creates_new_conversation_on_demand(self):
        """Test that requesting ?conversation=new creates new conversation"""
        self.client.login(username='testuser', password='testpass123')
        
        initial_count = Conversation.objects.count()
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation=new")
        
        # Should redirect to new conversation
        assert response.status_code == 302
        assert Conversation.objects.count() == initial_count + 1
    
    def test_chat_view_requires_authentication(self):
        """Test that chat view requires user to be logged in"""
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/login' in response.url or 'login' in response.url
    
    def test_chat_view_handles_inactive_agent(self):
        """Test chat view behavior with inactive agent"""
        self.agent.is_active = False
        self.agent.save()
        
        self.client.login(username='testuser', password='testpass123')
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        # Should still render but with can_send_messages = False
        assert response.status_code == 200
        assert response.context['can_send_messages'] == False
    
    def test_chat_view_post_creates_message(self):
        """Test POST request creates a message"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.post(
            f"{url}?conversation={self.conversation.id}",
            {'content': 'Hello, agent!'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Should return JSON success
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'message_id' in data
        
        # Verify message was created
        assert Message.objects.filter(
            conversation=self.conversation,
            content='Hello, agent!'
        ).exists()
    
    def test_chat_view_post_rejects_empty_message(self):
        """Test POST with empty message is rejected"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.post(
            f"{url}?conversation={self.conversation.id}",
            {'content': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Should return error
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
    
    def test_chat_view_pagination(self):
        """Test message pagination works correctly"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create 60 messages (more than default page size of 50)
        for i in range(60):
            Message.objects.create(
                conversation=self.conversation,
                user=self.user,
                role='user',
                content=f'Message {i}'
            )
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response.status_code == 200
        assert response.context['messages'].has_other_pages()
        assert len(response.context['messages']) == 50
    
    def test_conversation_history_view(self):
        """Test conversation history view"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create multiple conversations
        for i in range(3):
            Conversation.objects.create(
                agent=self.agent,
                user=self.user,
                title=f'Chat {i}'
            )
        
        url = reverse('chat:history', args=[self.agent.id])
        response = self.client.get(url)
        
        assert response.status_code == 200
        assert 'conversations' in response.context
        assert response.context['conversations'].object_list.count() >= 3
    
    def test_delete_conversation_archives(self):
        """Test deleting conversation sets is_active to False"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('chat:delete_conversation', args=[self.conversation.id])
        response = self.client.post(url)
        
        # Should redirect
        assert response.status_code == 302
        
        # Conversation should be inactive
        self.conversation.refresh_from_db()
        assert self.conversation.is_active == False


class TestChatViewsWithWebSocket(TestCase):
    """Test chat views WebSocket integration"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            name='Test Agent',
            user=self.user,
            is_active=True
        )
        self.conversation = Conversation.objects.create(
            agent=self.agent,
            user=self.user,
            title='Test Chat'
        )
    
    def test_chat_view_includes_websocket_url(self):
        """Test that view context includes WebSocket URL"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response.status_code == 200
        assert 'ws_url' in response.context
        assert f'/ws/chat/{self.conversation.id}/' in response.context['ws_url']
    
    def test_chat_view_template_has_websocket_script(self):
        """Test that template includes WebSocket JavaScript"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        
        # Check for WebSocket-related JavaScript
        assert 'WebSocket' in content or 'websocket' in content.lower()
        assert 'ws://' in content or 'wss://' in content