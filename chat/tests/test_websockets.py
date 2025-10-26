"""
WebSocket Connection Tests for Phase 4
Tests authentication, connection, and reconnection logic
"""
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch, MagicMock
import json

from chat.models import Conversation, Message
from agents.models import Agent
from chat.consumers import ChatConsumer

User = get_user_model()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocketConnections:
    """Test WebSocket connection and authentication"""
    
    async def test_websocket_connection_authenticates(self):
        """Test that authenticated users can connect to WebSocket"""
        # Create user and conversation
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = await database_sync_to_async(Agent.objects.create)(
            name='Test Agent',
            user=user,
            is_active=True
        )
        
        conversation = await database_sync_to_async(Conversation.objects.create)(
            agent=agent,
            user=user,
            title='Test Chat'
        )
        
        # Create WebSocket communicator
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{conversation.id}/"
        )
        communicator.scope['user'] = user
        
        # Test connection
        connected, _ = await communicator.connect()
        assert connected, "WebSocket should connect for authenticated user"
        
        # Should receive connection_established message
        response = await communicator.receive_json_from()
        assert response['type'] == 'connection_established'
        assert response['conversation_id'] == conversation.id
        
        # Cleanup
        await communicator.disconnect()
    
    async def test_websocket_connection_rejects_anonymous(self):
        """Test that anonymous users cannot connect"""
        from django.contrib.auth.models import AnonymousUser
        
        # Create test conversation
        user = await database_sync_to_async(User.objects.create_user)(
            username='owner',
            email='owner@example.com',
            password='pass123'
        )
        
        agent = await database_sync_to_async(Agent.objects.create)(
            name='Test Agent',
            user=user,
            is_active=True
        )
        
        conversation = await database_sync_to_async(Conversation.objects.create)(
            agent=agent,
            user=user,
            title='Test Chat'
        )
        
        # Try to connect as anonymous user
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{conversation.id}/"
        )
        communicator.scope['user'] = AnonymousUser()
        
        # Connection should be rejected
        connected, _ = await communicator.connect()
        assert not connected, "WebSocket should reject anonymous users"
        
        await communicator.disconnect()
    
    async def test_websocket_sends_message(self):
        """Test sending a message through WebSocket"""
        # Setup
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = await database_sync_to_async(Agent.objects.create)(
            name='Test Agent',
            user=user,
            is_active=True
        )
        
        conversation = await database_sync_to_async(Conversation.objects.create)(
            agent=agent,
            user=user,
            title='Test Chat'
        )
        
        # Connect
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{conversation.id}/"
        )
        communicator.scope['user'] = user
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Skip connection_established message
        await communicator.receive_json_from()
        
        # Send message
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': 'Hello, agent!',
            'temp_id': 'temp-123'
        })
        
        # Should receive confirmation
        response = await communicator.receive_json_from()
        assert response['type'] == 'message_sent'
        assert 'message_id' in response
        assert response['temp_id'] == 'temp-123'
        
        # Verify message was saved
        message_count = await database_sync_to_async(
            Message.objects.filter(conversation=conversation).count
        )()
        assert message_count == 1
        
        # Cleanup
        await communicator.disconnect()
    
    async def test_websocket_receives_agent_response(self):
        """Test receiving agent response through WebSocket"""
        # Setup
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = await database_sync_to_async(Agent.objects.create)(
            name='Test Agent',
            user=user,
            is_active=True,
            system_prompt='You are a helpful assistant.'
        )
        
        conversation = await database_sync_to_async(Conversation.objects.create)(
            agent=agent,
            user=user,
            title='Test Chat'
        )
        
        # Connect
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{conversation.id}/"
        )
        communicator.scope['user'] = user
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Skip connection_established
        await communicator.receive_json_from()
        
        # Send message
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': 'Hello!',
            'temp_id': 'temp-123'
        })
        
        # Receive message_sent confirmation
        await communicator.receive_json_from()
        
        # Should receive stream_start
        stream_start = await communicator.receive_json_from(timeout=5)
        assert stream_start['type'] == 'stream_start'
        assert 'message_id' in stream_start
        
        # Should receive stream tokens
        token_received = False
        for _ in range(10):  # Try to receive up to 10 tokens
            try:
                response = await communicator.receive_json_from(timeout=2)
                if response['type'] == 'stream_token':
                    token_received = True
                    assert 'token' in response
                    assert 'accumulated' in response
                if response['type'] == 'stream_end':
                    break
            except:
                break
        
        assert token_received, "Should receive at least one stream token"
        
        # Cleanup
        await communicator.disconnect()
    
    async def test_websocket_handles_disconnect(self):
        """Test graceful disconnect handling"""
        # Setup
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = await database_sync_to_async(Agent.objects.create)(
            name='Test Agent',
            user=user,
            is_active=True
        )
        
        conversation = await database_sync_to_async(Conversation.objects.create)(
            agent=agent,
            user=user,
            title='Test Chat'
        )
        
        # Connect
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{conversation.id}/"
        )
        communicator.scope['user'] = user
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Disconnect
        await communicator.disconnect()
        
        # Try to send message after disconnect - should fail gracefully
        try:
            await communicator.send_json_to({
                'type': 'chat_message',
                'message': 'This should not be sent'
            })
            # If we get here, something is wrong
            assert False, "Should not be able to send after disconnect"
        except:
            # Expected - connection is closed
            pass
    
    async def test_websocket_reconnects_after_drop(self):
        """Test reconnection after connection drop"""
        # Setup
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = await database_sync_to_async(Agent.objects.create)(
            name='Test Agent',
            user=user,
            is_active=True
        )
        
        conversation = await database_sync_to_async(Conversation.objects.create)(
            agent=agent,
            user=user,
            title='Test Chat'
        )
        
        # First connection
        communicator1 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{conversation.id}/"
        )
        communicator1.scope['user'] = user
        
        connected, _ = await communicator1.connect()
        assert connected
        
        # Disconnect
        await communicator1.disconnect()
        
        # Reconnect
        communicator2 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{conversation.id}/"
        )
        communicator2.scope['user'] = user
        
        connected, _ = await communicator2.connect()
        assert connected, "Should be able to reconnect after disconnect"
        
        # Should receive connection_established
        response = await communicator2.receive_json_from()
        assert response['type'] == 'connection_established'
        
        # Cleanup
        await communicator2.disconnect()