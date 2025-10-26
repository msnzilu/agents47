"""
Streaming Response Tests for Phase 4
Tests streaming token delivery, error handling, and concurrency
"""
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from chat.models import Conversation, Message
from agents.models import Agent
from chat.consumers import ChatConsumer

User = get_user_model()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestStreaming:
    """Test streaming response functionality"""
    
    async def test_agent_streams_response_tokens(self):
        """Test that agent responses are streamed token by token"""
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
            system_prompt='You are helpful.'
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
            'message': 'Count to 5',
            'temp_id': 'temp-123'
        })
        
        # Skip message_sent
        await communicator.receive_json_from()
        
        # Receive stream_start
        stream_start = await communicator.receive_json_from(timeout=5)
        assert stream_start['type'] == 'stream_start'
        message_id = stream_start['message_id']
        
        # Collect tokens
        tokens = []
        accumulated_text = ""
        
        for _ in range(50):  # Max 50 tokens
            try:
                response = await communicator.receive_json_from(timeout=2)
                
                if response['type'] == 'stream_token':
                    tokens.append(response['token'])
                    accumulated_text = response['accumulated']
                    assert response['message_id'] == message_id
                    
                elif response['type'] == 'stream_end':
                    assert response['message_id'] == message_id
                    assert 'final_content' in response
                    break
            except:
                break
        
        # Verify we received tokens
        assert len(tokens) > 0, "Should receive at least one token"
        assert len(accumulated_text) > 0, "Should have accumulated text"
        
        # Cleanup
        await communicator.disconnect()
    
    async def test_streaming_handles_long_responses(self):
        """Test streaming with long responses (multiple tokens)"""
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
            system_prompt='Give detailed explanations.'
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
        
        # Send message asking for long response
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': 'Explain machine learning in detail',
            'temp_id': 'temp-123'
        })
        
        # Skip message_sent
        await communicator.receive_json_from()
        
        # Receive stream_start
        stream_start = await communicator.receive_json_from(timeout=5)
        assert stream_start['type'] == 'stream_start'
        
        # Count tokens
        token_count = 0
        max_tokens = 100
        
        for _ in range(max_tokens):
            try:
                response = await communicator.receive_json_from(timeout=3)
                
                if response['type'] == 'stream_token':
                    token_count += 1
                    # Verify accumulated grows
                    assert len(response['accumulated']) > 0
                    
                elif response['type'] == 'stream_end':
                    break
            except:
                break
        
        # Should have received multiple tokens for long response
        assert token_count > 5, f"Expected multiple tokens, got {token_count}"
        
        # Cleanup
        await communicator.disconnect()
    
    async def test_streaming_error_stops_gracefully(self):
        """Test that streaming errors are handled gracefully"""
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
        
        # Skip connection_established
        await communicator.receive_json_from()
        
        # Mock the streaming to raise an error mid-stream
        with patch('chat.consumers.ChatConsumer.stream_agent_response') as mock_stream:
            # Make it raise an error
            mock_stream.side_effect = Exception("Streaming error")
            
            # Send message
            await communicator.send_json_to({
                'type': 'chat_message',
                'message': 'Test message',
                'temp_id': 'temp-123'
            })
            
            # Should receive error message
            for _ in range(5):
                try:
                    response = await communicator.receive_json_from(timeout=2)
                    if response['type'] == 'error':
                        assert 'error' in response
                        break
                except:
                    pass
        
        # Connection should still be open
        # Try sending another message
        await communicator.send_json_to({
            'type': 'ping'
        })
        
        # Should receive pong
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'pong'
        
        # Cleanup
        await communicator.disconnect()
    
    async def test_concurrent_streams_isolated(self):
        """Test that multiple concurrent streams don't interfere"""
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
        
        # Create two conversations
        conv1 = await database_sync_to_async(Conversation.objects.create)(
            agent=agent,
            user=user,
            title='Chat 1'
        )
        
        conv2 = await database_sync_to_async(Conversation.objects.create)(
            agent=agent,
            user=user,
            title='Chat 2'
        )
        
        # Connect to both
        comm1 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{conv1.id}/"
        )
        comm1.scope['user'] = user
        
        comm2 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{conv2.id}/"
        )
        comm2.scope['user'] = user
        
        # Connect both
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()
        assert connected1 and connected2
        
        # Skip connection_established for both
        await comm1.receive_json_from()
        await comm2.receive_json_from()
        
        # Send messages to both simultaneously
        await asyncio.gather(
            comm1.send_json_to({
                'type': 'chat_message',
                'message': 'Message to conv 1',
                'temp_id': 'temp-1'
            }),
            comm2.send_json_to({
                'type': 'chat_message',
                'message': 'Message to conv 2',
                'temp_id': 'temp-2'
            })
        )
        
        # Receive confirmations
        resp1 = await comm1.receive_json_from()
        resp2 = await comm2.receive_json_from()
        
        # Verify each received its own confirmation
        assert resp1['temp_id'] == 'temp-1'
        assert resp2['temp_id'] == 'temp-2'
        
        # Both should start streaming independently
        stream1 = await comm1.receive_json_from(timeout=5)
        stream2 = await comm2.receive_json_from(timeout=5)
        
        assert stream1['type'] == 'stream_start'
        assert stream2['type'] == 'stream_start'
        assert stream1['message_id'] != stream2['message_id']
        
        # Cleanup
        await comm1.disconnect()
        await comm2.disconnect()
    
    async def test_streaming_can_be_interrupted(self):
        """Test that disconnecting during streaming stops gracefully"""
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
        
        # Skip connection_established
        await communicator.receive_json_from()
        
        # Send message
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': 'Tell me a long story',
            'temp_id': 'temp-123'
        })
        
        # Skip message_sent
        await communicator.receive_json_from()
        
        # Receive stream_start
        await communicator.receive_json_from(timeout=5)
        
        # Receive a few tokens
        for _ in range(3):
            try:
                await communicator.receive_json_from(timeout=1)
            except:
                pass
        
        # Disconnect mid-stream
        await communicator.disconnect()
        
        # Should disconnect cleanly without errors
        # (No assertion needed - just shouldn't raise exception)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestStreamingPerformance:
    """Test streaming performance and reliability"""
    
    async def test_streaming_maintains_order(self):
        """Test that tokens are received in order"""
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
        
        # Skip connection_established
        await communicator.receive_json_from()
        
        # Send message
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': 'Count: 1, 2, 3, 4, 5',
            'temp_id': 'temp-123'
        })
        
        # Skip message_sent
        await communicator.receive_json_from()
        
        # Skip stream_start
        await communicator.receive_json_from(timeout=5)
        
        # Collect accumulated text
        accumulated_texts = []
        
        for _ in range(20):
            try:
                response = await communicator.receive_json_from(timeout=2)
                
                if response['type'] == 'stream_token':
                    accumulated_texts.append(response['accumulated'])
                    
                elif response['type'] == 'stream_end':
                    break
            except:
                break
        
        # Verify accumulated text always grows (never shrinks)
        if len(accumulated_texts) > 1:
            for i in range(1, len(accumulated_texts)):
                assert len(accumulated_texts[i]) >= len(accumulated_texts[i-1]), \
                    "Accumulated text should always grow, never shrink"
        
        # Cleanup
        await communicator.disconnect()
    
    async def test_streaming_completes_within_timeout(self):
        """Test that streaming completes in reasonable time"""
        import time
        
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
        
        # Skip connection_established
        await communicator.receive_json_from()
        
        start_time = time.time()
        
        # Send message
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': 'Say hello',
            'temp_id': 'temp-123'
        })
        
        # Wait for stream to complete
        stream_completed = False
        for _ in range(100):
            try:
                response = await communicator.receive_json_from(timeout=1)
                if response['type'] == 'stream_end':
                    stream_completed = True
                    break
            except:
                break
        
        elapsed_time = time.time() - start_time
        
        # Should complete within 30 seconds
        assert elapsed_time < 30, f"Streaming took too long: {elapsed_time}s"
        assert stream_completed, "Stream should complete"
        
        # Cleanup
        await communicator.disconnect()