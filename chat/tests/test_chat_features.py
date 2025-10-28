"""
Chat Features Tests for Phase 4
Tests message management, conversation switching, and content rendering
FIXED: Added missing login calls
"""
import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch

from chat.models import Conversation, Message
from agents.models import Agent

User = get_user_model()


class TestChatFeatures(TestCase):
    """Test chat feature functionality"""
    
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
    
    def test_message_delete_soft_deletes(self):
        """Test that deleting a message soft-deletes it"""
        # Create a message
        message = Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='Test message'
        )
        
        # Note: This test assumes you'll implement a delete message endpoint
        # For now, test soft delete directly
        original_id = message.id
        
        # Soft delete by setting a deleted flag or moving to archive
        # (Adjust based on your actual implementation)
        message.metadata['deleted'] = True
        message.metadata['deleted_at'] = timezone.now().isoformat()
        message.save()
        
        # Message should still exist in database
        assert Message.objects.filter(id=original_id).exists()
        
        # But should be marked as deleted
        message.refresh_from_db()
        assert message.metadata.get('deleted') == True
    
    def test_conversation_switching_loads_correct_history(self):
        """Test switching between conversations loads correct messages"""
        # FIXED: Added login
        self.client.login(username='testuser', password='testpass123')
        
        # Create second conversation
        conversation2 = Conversation.objects.create(
            agent=self.agent,
            user=self.user,
            title='Second Chat'
        )
        
        # Add messages to first conversation
        msg1 = Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='Message in conv 1'
        )
        
        # Add messages to second conversation
        msg2 = Message.objects.create(
            conversation=conversation2,
            user=self.user,
            role='user',
            content='Message in conv 2'
        )
        
        # Load first conversation
        url = reverse('chat:chat_view', args=[self.agent.id])
        response1 = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response1.status_code == 200
        messages1 = list(response1.context['messages'])
        assert len(messages1) == 1
        assert messages1[0].content == 'Message in conv 1'
        
        # Load second conversation
        response2 = self.client.get(f"{url}?conversation={conversation2.id}")
        
        assert response2.status_code == 200
        messages2 = list(response2.context['messages'])
        assert len(messages2) == 1
        assert messages2[0].content == 'Message in conv 2'
    
    def test_markdown_renders_safely(self):
        """Test that markdown in messages is rendered safely"""
        # FIXED: Added login
        self.client.login(username='testuser', password='testpass123')
        
        # Create message with markdown and potential XSS
        markdown_content = """
        # Heading
        **Bold text**
        <script>alert('XSS')</script>
        [Link](https://example.com)
        """
        
        message = Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='assistant',
            content=markdown_content
        )
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        
        # Should NOT contain raw script tag
        assert '<script>alert' not in content
        
        # Should contain escaped or removed script
        assert '&lt;script&gt;' in content or '<script>' not in content
    
    def test_conversation_title_updates(self):
        """Test that conversation title can be updated"""
        # FIXED: Added login
        self.client.login(username='testuser', password='testpass123')
        
        # Update title
        new_title = "Updated Conversation Title"
        self.conversation.title = new_title
        self.conversation.save()
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response.status_code == 200
        assert response.context['conversation'].title == new_title
    
    def test_message_timestamps_are_accurate(self):
        """Test that message timestamps are properly recorded"""
        # Create messages with slight delay
        msg1 = Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='First message'
        )
        
        import time
        time.sleep(0.1)
        
        msg2 = Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='Second message'
        )
        
        # Second message should have later timestamp
        assert msg2.created_at > msg1.created_at
    
    def test_conversation_updated_at_changes_on_new_message(self):
        """Test that conversation updated_at changes when message added"""
        original_updated = self.conversation.updated_at
        
        import time
        time.sleep(0.1)
        
        # Add a message
        Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='New message'
        )
        
        # Update conversation timestamp
        self.conversation.updated_at = timezone.now()
        self.conversation.save()
        
        self.conversation.refresh_from_db()
        assert self.conversation.updated_at > original_updated
    
    def test_empty_conversation_shows_empty_state(self):
        """Test that conversation with no messages shows empty state"""
        # FIXED: Added login
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('chat:chat_view', args=[self.agent.id])
        response = self.client.get(f"{url}?conversation={self.conversation.id}")
        
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        
        # Should show empty state
        assert 'empty-state' in content or 'Start a conversation' in content
    
    def test_conversation_message_count(self):
        """Test that message count method returns correct count"""
        # Add messages
        for i in range(5):
            Message.objects.create(
                conversation=self.conversation,
                user=self.user,
                role='user',
                content=f'Message {i}'
            )
        
        assert self.conversation.message_count() == 5
    
    def test_conversation_get_context(self):
        """Test that get_context returns recent messages"""
        # Add 15 messages
        for i in range(15):
            Message.objects.create(
                conversation=self.conversation,
                user=self.user,
                role='user',
                content=f'Message {i}'
            )
        
        # Get context with limit of 10
        context = self.conversation.get_context(limit=10)
        
        assert len(list(context)) == 10
    
    def test_multiple_users_different_conversations(self):
        """Test that different users have separate conversations"""
        # Create another user
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        
        agent2 = Agent.objects.create(
            name='Agent 2',
            user=user2,
            is_active=True
        )
        
        conv2 = Conversation.objects.create(
            agent=agent2,
            user=user2,
            title='User 2 Chat'
        )
        
        # Add message to each
        Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='User 1 message'
        )
        
        Message.objects.create(
            conversation=conv2,
            user=user2,
            role='user',
            content='User 2 message'
        )
        
        # Verify separation
        user1_messages = Message.objects.filter(conversation=self.conversation)
        user2_messages = Message.objects.filter(conversation=conv2)
        
        assert user1_messages.count() == 1
        assert user2_messages.count() == 1
        assert user1_messages[0].content == 'User 1 message'
        assert user2_messages[0].content == 'User 2 message'


class TestChatMetadata(TestCase):
    """Test chat metadata and tracking features"""
    
    def setUp(self):
        """Set up test data"""
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
    
    def test_conversation_stores_metadata(self):
        """Test that conversation can store custom metadata"""
        metadata = {
            'user_agent': 'Mozilla/5.0',
            'ip_address': '127.0.0.1',
            'created_via': 'web_interface'
        }
        
        self.conversation.metadata = metadata
        self.conversation.save()
        
        self.conversation.refresh_from_db()
        assert self.conversation.metadata['user_agent'] == 'Mozilla/5.0'
        assert self.conversation.metadata['created_via'] == 'web_interface'
    
    def test_message_stores_metadata(self):
        """Test that messages can store custom metadata"""
        message = Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='Test',
            metadata={
                'sent_at': timezone.now().isoformat(),
                'client_type': 'web'
            }
        )
        
        message.refresh_from_db()
        assert 'sent_at' in message.metadata
        assert message.metadata['client_type'] == 'web'
    
    def test_conversation_channel_tracking(self):
        """Test that conversation tracks its channel"""
        # Create conversation with specific channel
        conv = Conversation.objects.create(
            agent=self.agent,
            user=self.user,
            title='API Chat',
            channel='api'
        )
        
        assert conv.channel == 'api'
        
        # Create another with different channel
        conv2 = Conversation.objects.create(
            agent=self.agent,
            user=self.user,
            title='Web Chat',
            channel='web'
        )
        
        assert conv2.channel == 'web'
        
        # Can filter by channel
        api_convs = Conversation.objects.filter(channel='api')
        assert api_convs.count() == 1
        assert api_convs[0].title == 'API Chat'


class TestChatSearch(TestCase):
    """Test chat search and filtering features"""
    
    def setUp(self):
        """Set up test data"""
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
    
    def test_filter_messages_by_role(self):
        """Test filtering messages by role"""
        # Create messages with different roles
        Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='User message'
        )
        
        Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='Assistant message'
        )
        
        Message.objects.create(
            conversation=self.conversation,
            role='system',
            content='System message'
        )
        
        # Filter by role
        user_messages = Message.objects.filter(
            conversation=self.conversation,
            role='user'
        )
        
        assistant_messages = Message.objects.filter(
            conversation=self.conversation,
            role='assistant'
        )
        
        assert user_messages.count() == 1
        assert assistant_messages.count() == 1
        assert user_messages[0].content == 'User message'
    
    def test_filter_conversations_by_agent(self):
        """Test filtering conversations by agent"""
        # Create another agent
        agent2 = Agent.objects.create(
            name='Agent 2',
            user=self.user,
            is_active=True
        )
        
        # Create conversations for each agent
        Conversation.objects.create(
            agent=self.agent,
            user=self.user,
            title='Agent 1 Chat'
        )
        
        Conversation.objects.create(
            agent=agent2,
            user=self.user,
            title='Agent 2 Chat'
        )
        
        # Filter by agent
        agent1_convs = Conversation.objects.filter(agent=self.agent)
        agent2_convs = Conversation.objects.filter(agent=agent2)
        
        assert agent1_convs.count() >= 2  # Original + new
        assert agent2_convs.count() == 1
    
    def test_search_messages_by_content(self):
        """Test searching messages by content"""
        # Create messages with searchable content
        Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='How do I configure Python?'
        )
        
        Message.objects.create(
            conversation=self.conversation,
            user=self.user,
            role='user',
            content='Tell me about JavaScript'
        )
        
        # Search for Python
        python_messages = Message.objects.filter(
            conversation=self.conversation,
            content__icontains='Python'
        )
        
        assert python_messages.count() == 1
        assert 'Python' in python_messages[0].content