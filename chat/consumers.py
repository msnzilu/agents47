"""
Enhanced WebSocket Consumer for Real-Time Chat with Streaming
Phase 4: Real-Time Chat & WebSockets
"""
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    Enhanced WebSocket consumer with streaming support.
    
    Handles:
    - Real-time messaging
    - Streaming LLM responses (token-by-token)
    - Typing indicators
    - Message editing/deletion
    - Connection management
    """
    
    async def connect(self):
        """Handle WebSocket connection with authentication"""
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        self.user = self.scope.get('user')
        
        # Reject anonymous users
        if isinstance(self.user, AnonymousUser):
            logger.warning(f"Anonymous user attempted to connect to conversation {self.conversation_id}")
            await self.close(code=4001)
            return
        
        # Verify user has access to this conversation
        has_access = await self.verify_conversation_access()
        if not has_access:
            logger.warning(f"User {self.user.id} denied access to conversation {self.conversation_id}")
            await self.close(code=4003)
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send_json({
            'type': 'connection_established',
            'conversation_id': self.conversation_id,
            'user_id': str(self.user.id),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.info(f"User {self.user.id} connected to conversation {self.conversation_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnect"""
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        
        logger.info(f"User {self.user.id if hasattr(self, 'user') else 'unknown'} "
                   f"disconnected from conversation {self.conversation_id} (code: {close_code})")
    
    async def receive_json(self, content):
        """
        Handle incoming WebSocket messages
        
        Supported message types:
        - chat_message: User sends a message
        - typing: User typing indicator
        - edit_message: Edit existing message
        - delete_message: Delete message
        - ping: Keep-alive ping
        """
        try:
            message_type = content.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(content)
            
            elif message_type == 'typing':
                await self.handle_typing(content)
            
            elif message_type == 'edit_message':
                await self.handle_edit_message(content)
            
            elif message_type == 'delete_message':
                await self.handle_delete_message(content)
            
            elif message_type == 'ping':
                await self.send_json({'type': 'pong'})
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send_error(f"Unknown message type: {message_type}")
        
        except Exception as e:
            logger.error(f"Error in receive_json: {str(e)}", exc_info=True)
            await self.send_error("Internal server error")
    
    async def handle_chat_message(self, content):
        """Handle user chat message"""
        message_content = content.get('message', '').strip()
        temp_id = content.get('temp_id')
        
        if not message_content:
            await self.send_error("Message content is required", temp_id=temp_id)
            return
        
        if len(message_content) > 5000:
            await self.send_error("Message too long (max 5000 characters)", temp_id=temp_id)
            return
        
        try:
            # Save user message to database
            message = await self.save_message(message_content)
            
            if not message:
                await self.send_error("Failed to save message", temp_id=temp_id)
                return
            
            # Send confirmation to sender
            await self.send_json({
                'type': 'message_sent',
                'temp_id': temp_id,
                'message_id': message['id'],
                'timestamp': message['created_at']
            })
            
            # Broadcast message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': message['id'],
                        'content': message_content,
                        'role': 'user',
                        'user_id': str(self.user.id),
                        'username': self.user.username,
                        'created_at': message['created_at']
                    }
                }
            )
            
            # Trigger agent response with streaming
            asyncio.create_task(self.generate_agent_response(message['id']))
        
        except Exception as e:
            logger.error(f"Error handling chat message: {str(e)}", exc_info=True)
            await self.send_error("Failed to process message", temp_id=temp_id)
    
    async def generate_agent_response(self, user_message_id: int):
        """
        Generate streaming agent response
        
        This integrates with your Phase 3 LangChain agents for real streaming.
        For now, it includes a simulation that you can replace with actual LLM calls.
        """
        try:
            # Notify that agent is typing
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'agent_typing',
                    'is_typing': True
                }
            )
            
            # Get agent and conversation context
            agent_info = await self.get_agent_info()
            
            if not agent_info or not agent_info.get('is_active'):
                logger.warning(f"Agent not active for conversation {self.conversation_id}")
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'agent_typing',
                        'is_typing': False
                    }
                )
                return
            
            conversation_history = await self.get_conversation_history()
            
            # Create assistant message placeholder
            assistant_message = await self.create_assistant_message()
            
            # Notify streaming started
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_stream_start',
                    'message_id': assistant_message['id'],
                    'timestamp': assistant_message['created_at']
                }
            )
            
            # Call LLM with streaming
            # TODO: Replace this with your Phase 3 LangChain streaming integration
            full_response = await self.call_llm_streaming(
                agent_info,
                conversation_history,
                assistant_message['id']
            )
            
            # Update message with full content
            await self.update_assistant_message(assistant_message['id'], full_response)
            
            # Notify streaming complete
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_stream_end',
                    'message_id': assistant_message['id'],
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            # Stop typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'agent_typing',
                    'is_typing': False
                }
            )
        
        except Exception as e:
            logger.error(f"Error generating agent response: {str(e)}", exc_info=True)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'agent_error',
                    'error': 'Failed to generate response'
                }
            )
            # Stop typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'agent_typing',
                    'is_typing': False
                }
            )
    
    async def call_llm_streaming(self, agent_info: dict, history: list, message_id: int) -> str:
        """
        Call LLM with streaming support.
        
        TODO: Replace this simulation with actual LangChain streaming from Phase 3.
        
        For real integration, use:
        from agents.agents import execute_agent_streaming
        
        return await execute_agent_streaming(
            agent=agent,
            user_message=last_message,
            conversation_history=history,
            channel_layer=self.channel_layer,
            room_group_name=self.room_group_name,
            message_id=message_id
        )
        """
        # Simulated streaming response for demonstration
        response_text = (
            f"Hello! I'm {agent_info['name']}, your AI assistant. "
            "I understand your message and I'm here to help you. "
            "This is a streaming response that demonstrates real-time token delivery. "
            "In production, this would be powered by your Phase 3 LangChain agents."
        )
        
        # Stream tokens word by word
        words = response_text.split()
        accumulated_text = ""
        
        for i, word in enumerate(words):
            accumulated_text += word + " "
            
            # Send token to all clients in the room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_stream_token',
                    'message_id': message_id,
                    'token': word + " ",
                    'accumulated': accumulated_text.strip(),
                    'index': i
                }
            )
            
            # Simulate network delay
            await asyncio.sleep(0.05)
        
        return accumulated_text.strip()
    
    async def handle_typing(self, content):
        """Handle typing indicator"""
        is_typing = content.get('is_typing', False)
        
        # Broadcast typing indicator to room (other users will filter themselves out)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_typing',
                'user_id': str(self.user.id),
                'username': self.user.username,
                'is_typing': is_typing
            }
        )
    
    async def handle_edit_message(self, content):
        """Handle message edit request"""
        message_id = content.get('message_id')
        new_content = content.get('content', '').strip()
        
        if not message_id or not new_content:
            await self.send_error("Invalid edit request")
            return
        
        success = await self.update_message(message_id, new_content)
        
        if success:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'new_content': new_content,
                    'edited_at': datetime.utcnow().isoformat()
                }
            )
        else:
            await self.send_error("Failed to edit message")
    
    async def handle_delete_message(self, content):
        """Handle message deletion"""
        message_id = content.get('message_id')
        
        if not message_id:
            await self.send_error("Invalid delete request")
            return
        
        success = await self.delete_message(message_id)
        
        if success:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_deleted',
                    'message_id': message_id,
                    'deleted_at': datetime.utcnow().isoformat()
                }
            )
        else:
            await self.send_error("Failed to delete message")
    
    # Group message handlers (called by channel_layer.group_send)
    
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send_json({
            'type': 'message',
            'message': event['message']
        })
    
    async def message_stream_start(self, event):
        """Notify client that streaming started"""
        await self.send_json({
            'type': 'stream_start',
            'message_id': event['message_id'],
            'timestamp': event['timestamp']
        })
    
    async def message_stream_token(self, event):
        """Send streaming token to client"""
        await self.send_json({
            'type': 'stream_token',
            'message_id': event['message_id'],
            'token': event['token'],
            'accumulated': event['accumulated'],
            'index': event.get('index', 0)
        })
    
    async def message_stream_end(self, event):
        """Notify client that streaming ended"""
        await self.send_json({
            'type': 'stream_end',
            'message_id': event['message_id'],
            'timestamp': event['timestamp']
        })
    
    async def agent_typing(self, event):
        """Send agent typing indicator"""
        await self.send_json({
            'type': 'agent_typing',
            'is_typing': event['is_typing']
        })
    
    async def user_typing(self, event):
        """Send user typing indicator"""
        # Don't send typing indicator to the user who is typing
        if str(event['user_id']) != str(self.user.id):
            await self.send_json({
                'type': 'user_typing',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing']
            })
    
    async def message_edited(self, event):
        """Send message edit notification"""
        await self.send_json({
            'type': 'message_edited',
            'message_id': event['message_id'],
            'new_content': event['new_content'],
            'edited_at': event['edited_at']
        })
    
    async def message_deleted(self, event):
        """Send message deletion notification"""
        await self.send_json({
            'type': 'message_deleted',
            'message_id': event['message_id'],
            'deleted_at': event['deleted_at']
        })
    
    async def agent_error(self, event):
        """Send agent error notification"""
        await self.send_json({
            'type': 'error',
            'error': event['error'],
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def send_error(self, error: str, temp_id: str = None):
        """Send error message to client"""
        await self.send_json({
            'type': 'error',
            'error': error,
            'temp_id': temp_id,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    # Database operations (wrapped with database_sync_to_async)
    
    @database_sync_to_async
    def verify_conversation_access(self) -> bool:
        """Verify user has access to this conversation"""
        from chat.models import Conversation
        try:
            conversation = Conversation.objects.get(
                id=self.conversation_id,
                user=self.user
            )
            return conversation.is_active
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_message(self, content: str):
        """Save user message to database"""
        from chat.models import Message, Conversation
        
        try:
            conversation = Conversation.objects.get(
                id=self.conversation_id,
                user=self.user
            )
            
            message = Message.objects.create(
                conversation=conversation,
                user=self.user,
                role='user',
                content=content,
                metadata={
                    'sent_via': 'websocket',
                    'client_type': 'web'
                }
            )
            
            # Update conversation timestamp
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=['updated_at'])
            
            return {
                'id': message.id,
                'created_at': message.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}", exc_info=True)
            return None
    
    @database_sync_to_async
    def create_assistant_message(self):
        """Create placeholder assistant message"""
        from chat.models import Message, Conversation
        
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            
            message = Message.objects.create(
                conversation=conversation,
                user=None,  # Assistant has no user
                role='assistant',
                content="",  # Will be populated by streaming
                metadata={
                    'streaming': True
                }
            )
            
            return {
                'id': message.id,
                'created_at': message.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error creating assistant message: {str(e)}", exc_info=True)
            return None
    
    @database_sync_to_async
    def update_assistant_message(self, message_id: int, content: str) -> bool:
        """Update assistant message with full content"""
        from chat.models import Message
        
        try:
            message = Message.objects.get(id=message_id)
            message.content = content
            message.metadata['streaming'] = False
            message.save(update_fields=['content', 'metadata'])
            return True
        except Exception as e:
            logger.error(f"Error updating assistant message: {str(e)}", exc_info=True)
            return False
    
    @database_sync_to_async
    def get_agent_info(self):
        """Get agent information"""
        from chat.models import Conversation
        
        try:
            conversation = Conversation.objects.select_related('agent').get(id=self.conversation_id)
            agent = conversation.agent
            
            return {
                'id': agent.id,
                'name': agent.name,
                'use_case': agent.use_case,
                'is_active': agent.is_active
            }
        except Exception as e:
            logger.error(f"Error getting agent info: {str(e)}", exc_info=True)
            return None
    
    @database_sync_to_async
    def get_conversation_history(self, limit: int = 10):
        """Get recent conversation history"""
        from chat.models import Message
        
        try:
            messages = Message.objects.filter(
                conversation_id=self.conversation_id
            ).order_by('-created_at')[:limit]
            
            return [
                {
                    'role': msg.role,
                    'content': msg.content
                }
                for msg in reversed(messages)
            ]
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}", exc_info=True)
            return []
    
    @database_sync_to_async
    def update_message(self, message_id: int, new_content: str) -> bool:
        """Update message content"""
        from chat.models import Message
        
        try:
            message = Message.objects.get(
                id=message_id,
                conversation_id=self.conversation_id,
                user=self.user
            )
            message.content = new_content
            message.save(update_fields=['content'])
            return True
        except Exception as e:
            logger.error(f"Error updating message: {str(e)}", exc_info=True)
            return False
    
    @database_sync_to_async
    def delete_message(self, message_id: int) -> bool:
        """Soft delete message"""
        from chat.models import Message
        
        try:
            message = Message.objects.get(
                id=message_id,
                conversation_id=self.conversation_id,
                user=self.user
            )
            # Soft delete by marking in metadata
            message.metadata['deleted'] = True
            message.metadata['deleted_at'] = datetime.utcnow().isoformat()
            message.save(update_fields=['metadata'])
            return True
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}", exc_info=True)
            return False