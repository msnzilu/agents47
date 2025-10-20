from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
import json

class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive_json(self, content):
        message_type = content.get('type')
        
        if message_type == 'chat_message':
            # Save message to database
            message = await self.save_message(content['message'])
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'user': self.scope['user'].username,
                    'timestamp': message.created_at.isoformat()
                }
            )
    
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send_json(event)
    
    @database_sync_to_async
    def save_message(self, content):
        # Save message to database
        return Message.objects.create(
            conversation_id=self.conversation_id,
            user=self.scope['user'],
            content=content,
            role='user'
        )