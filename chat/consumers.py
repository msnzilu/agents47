"""
Enhanced WebSocket Consumer for Real-Time Chat with Streaming
"""
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
import json
import logging
import asyncio
from datetime import datetime
from agents.agents import AgentFactory
from agents.models import Agent

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
                await self.handle_ping()
            
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            await self.send_error(f"Error processing message: {str(e)}")
    
    async def handle_chat_message(self, content):
        """Handle incoming chat message from user"""
        message_content = content.get('message', '').strip()
        temp_id = content.get('temp_id')
        
        if not message_content:
            await self.send_error("Empty message", temp_id)
            return
        
        try:
            # Save user message to database
            saved_message = await self.save_message(message_content)
            
            if not saved_message:
                await self.send_error("Failed to save message", temp_id)
                return
            
            # Broadcast user message to all clients in the room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': saved_message['id'],
                        'temp_id': temp_id,
                        'role': 'user',
                        'content': message_content,
                        'user_id': str(self.user.id),
                        'username': self.user.username,
                        'timestamp': saved_message['created_at']
                    }
                }
            )
            
            # Get agent info and generate response
            await self.generate_agent_response(message_content)
            
        except Exception as e:
            logger.error(f"Error handling chat message: {str(e)}", exc_info=True)
            await self.send_error(f"Failed to process message: {str(e)}", temp_id)
    
    async def generate_agent_response(self, user_message: str):
        """
        Generate and stream agent response using AgentFactory.
        
        This method:
        1. Retrieves the Agent model
        2. Creates a LangChain agent using AgentFactory
        3. Executes the agent to get a real LLM response
        4. Simulates streaming by sending the response token-by-token
        """
        agent_dict = None
        
        try:
            # Get agent info from database
            agent_model = await self.get_agent_model()
            if not agent_model:
                await self.send_error("Agent not found")
                return
            
            if not agent_model.is_active:
                await self.send_error("Agent is not active")
                return
            
            # Create placeholder assistant message
            assistant_message = await self.create_assistant_message()
            if not assistant_message:
                await self.send_error("Failed to create assistant message")
                return
            
            message_id = assistant_message['id']
            
            # Notify clients that streaming is starting
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_stream_start',
                    'message_id': message_id,
                    'timestamp': assistant_message['created_at']
                }
            )
            
            # Send agent typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'agent_typing',
                    'is_typing': True
                }
            )
            
            try:
                # Create LangChain agent using AgentFactory
                logger.info(f"Creating agent instance for {agent_model.name}")
                agent_dict = await self.run_sync(
                    AgentFactory.create_agent,
                    agent_model
                )
                
                # Execute agent to get response
                logger.info(f"Executing agent for message: {user_message[:50]}...")
                result = await AgentFactory.execute_agent_async(agent_dict, user_message)
                
                if not result.get('success', False):
                    error_msg = result.get('error', 'Unknown error occurred')
                    logger.error(f"Agent execution failed: {error_msg}")
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'agent_error',
                            'error': f"Failed to generate response: {error_msg}"
                        }
                    )
                    return
                
                # Extract response and metadata
                response_text = result.get('response', '')
                sources = result.get('sources', [])
                phase6_results = result.get('phase6_results', {})
                
                logger.info(f"Agent response received: {len(response_text)} characters")
                
                # Simulate streaming by sending tokens
                accumulated_content = ""
                token_index = 0
                
                # Split response into tokens (words + punctuation)
                # This simulates streaming since AgentFactory returns complete response
                words = response_text.split()
                
                for word in words:
                    token = word + " "
                    accumulated_content += token
                    token_index += 1
                    
                    # Send token to all clients
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'message_stream_token',
                            'message_id': message_id,
                            'token': token,
                            'accumulated': accumulated_content.strip(),
                            'index': token_index
                        }
                    )
                    
                    # Small delay to simulate streaming
                    await asyncio.sleep(0.05)
                
                # Update database with final content and metadata
                metadata = {
                    'streaming': False,
                    'sources': sources,
                    'phase6_results': phase6_results
                }
                await self.update_assistant_message(
                    message_id, 
                    accumulated_content.strip(),
                    metadata
                )
                
                logger.info(f"Agent response complete. Sources: {len(sources)}, "
                          f"Phase6 results: {list(phase6_results.keys())}")
                
            except ValueError as ve:
                # Handle configuration errors (missing API keys, etc.)
                error_msg = str(ve)
                logger.error(f"Agent configuration error: {error_msg}")
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'agent_error',
                        'error': f"Configuration error: {error_msg}. Please check your agent's LLM integration settings."
                    }
                )
                return
                
            except Exception as e:
                logger.error(f"Error executing agent: {str(e)}", exc_info=True)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'agent_error',
                        'error': f"Agent execution error: {str(e)}"
                    }
                )
                return
            
        except Exception as e:
            logger.error(f"Error in generate_agent_response: {str(e)}", exc_info=True)
            await self.send_error(f"Failed to generate response: {str(e)}")
            
        finally:
            # Always stop agent typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'agent_typing',
                    'is_typing': False
                }
            )
            
            # Notify clients that streaming ended
            if assistant_message:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'message_stream_end',
                        'message_id': assistant_message['id'],
                        'timestamp': datetime.utcnow().isoformat()
                    }
                )
    
    async def run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in a thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    
    async def handle_typing(self, content):
        """Handle typing indicator from user"""
        is_typing = content.get('is_typing', False)
        
        # Broadcast typing indicator to other users
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
        """Handle message deletion request"""
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
    
    async def handle_ping(self):
        """Handle ping request for keep-alive"""
        await self.send_json({
            'type': 'pong',
            'timestamp': datetime.utcnow().isoformat()
        })
    
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
    def get_agent_model(self):
        """Get the Agent model instance for this conversation"""
        from chat.models import Conversation
        
        try:
            conversation = Conversation.objects.select_related('agent').get(
                id=self.conversation_id,
                user=self.user
            )
            return conversation.agent
        except Conversation.DoesNotExist:
            logger.error(f"Conversation {self.conversation_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting agent model: {str(e)}", exc_info=True)
            return None
    
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
    def update_assistant_message(self, message_id: int, content: str, metadata: dict = None) -> bool:
        """Update assistant message with full content and metadata"""
        from chat.models import Message
        
        try:
            message = Message.objects.get(id=message_id)
            message.content = content
            
            # Update metadata
            if metadata:
                message.metadata.update(metadata)
            else:
                message.metadata['streaming'] = False
            
            message.save(update_fields=['content', 'metadata'])
            return True
        except Exception as e:
            logger.error(f"Error updating assistant message: {str(e)}", exc_info=True)
            return False
    
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