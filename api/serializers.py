"""
API Serializers for REST API
Phase 7: Integration Layer
"""
from rest_framework import serializers
from agents.models import Agent, ToolExecution
from chat.models import Conversation, Message
from users.models import CustomUser
from django.contrib.auth import authenticate


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user data"""
    
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'company', 
                  'created_at', 'agent_count']
        read_only_fields = ['id', 'created_at', 'agent_count']


class AgentListSerializer(serializers.ModelSerializer):
    """Serializer for agent list view"""
    
    use_case_display = serializers.CharField(source='get_use_case_display', read_only=True)
    conversation_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Agent
        fields = ['id', 'name', 'description', 'use_case', 'use_case_display',
                  'is_active', 'created_at', 'updated_at', 'conversation_count']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_conversation_count(self, obj):
        return obj.conversations.count()


class AgentDetailSerializer(serializers.ModelSerializer):
    """Serializer for agent detail view"""
    
    use_case_display = serializers.CharField(source='get_use_case_display', read_only=True)
    knowledge_base_count = serializers.SerializerMethodField()
    recent_conversations = serializers.SerializerMethodField()
    
    class Meta:
        model = Agent
        fields = ['id', 'name', 'description', 'use_case', 'use_case_display',
                  'prompt_template', 'is_active', 'config', 'created_at', 
                  'updated_at', 'knowledge_base_count', 'recent_conversations']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_knowledge_base_count(self, obj):
        return obj.knowledge_bases.filter(is_active=True).count()
    
    def get_recent_conversations(self, obj):
        conversations = obj.conversations.order_by('-created_at')[:5]
        return ConversationListSerializer(conversations, many=True).data


class AgentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating agents"""
    
    class Meta:
        model = Agent
        fields = ['name', 'description', 'use_case', 'prompt_template', 
                  'is_active', 'config']
    
    def validate_name(self, value):
        """Ensure agent name is not empty"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Agent name must be at least 3 characters")
        return value
    
    def validate_use_case(self, value):
        """Validate use case"""
        valid_cases = ['support', 'research', 'automation', 'scheduling', 
                       'knowledge', 'sales']
        if value not in valid_cases:
            raise serializers.ValidationError(f"Invalid use case. Must be one of: {', '.join(valid_cases)}")
        return value


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages"""
    
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'role', 'role_display', 'content', 'metadata', 
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ConversationListSerializer(serializers.ModelSerializer):
    """Serializer for conversation list"""
    
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = ['id', 'title', 'channel', 'channel_identifier', 
                  'created_at', 'updated_at', 'message_count', 'last_message']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                'content': last_msg.content[:100],
                'role': last_msg.role,
                'created_at': last_msg.created_at
            }
        return None


class ConversationDetailSerializer(serializers.ModelSerializer):
    """Serializer for conversation detail with messages"""
    
    messages = MessageSerializer(many=True, read_only=True)
    agent_name = serializers.CharField(source='agent.name', read_only=True)
    
    class Meta:
        model = Conversation
        fields = ['id', 'title', 'agent', 'agent_name', 'channel', 
                  'channel_identifier', 'created_at', 'updated_at', 'messages']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatMessageSerializer(serializers.Serializer):
    """Serializer for sending chat messages"""
    
    message = serializers.CharField(required=True, min_length=1, max_length=10000)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    stream = serializers.BooleanField(default=False)
    
    def validate_message(self, value):
        """Validate message content"""
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty")
        return value


class EscalationSerializer(serializers.Serializer):
    """Serializer for escalation requests"""
    
    conversation_id = serializers.IntegerField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    priority = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'critical'],
        default='medium'
    )
    assign_to = serializers.EmailField(required=False, allow_null=True)


class APIKeySerializer(serializers.Serializer):
    """Serializer for API key generation"""
    
    name = serializers.CharField(max_length=100)
    expires_in_days = serializers.IntegerField(min_value=1, max_value=365, default=90)