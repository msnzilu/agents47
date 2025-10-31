"""
REST API Views
Phase 7: Integration Layer
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions, viewsets, status, serializers
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from agents.models import Agent
from chat.models import Conversation

# Try to import drf-spectacular for better API docs
try:
    from drf_spectacular.utils import extend_schema, OpenApiResponse
    DRF_SPECTACULAR_AVAILABLE = True
except ImportError:
    # Fallback decorator that does nothing
    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    DRF_SPECTACULAR_AVAILABLE = False


# Serializers
class AgentSerializer(serializers.ModelSerializer):
    """Serializer for Agent model"""
    class Meta:
        model = Agent
        fields = ['id', 'name', 'description', 'use_case', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class AgentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for Agent list view"""
    class Meta:
        model = Agent
        fields = ['id', 'name', 'description', 'use_case', 'is_active']


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for Conversation model"""
    agent_name = serializers.CharField(source='agent.name', read_only=True)
    
    class Meta:
        model = Conversation
        fields = ['id', 'title', 'agent_id', 'agent_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ConversationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for Conversation list view"""
    class Meta:
        model = Conversation
        fields = ['id', 'title', 'agent_id', 'created_at']


# Response Serializers for documentation
class ApiRootResponseSerializer(serializers.Serializer):
    """Serializer for API root response"""
    version = serializers.CharField()
    endpoints = serializers.DictField()


class HealthCheckResponseSerializer(serializers.Serializer):
    """Serializer for health check response"""
    status = serializers.CharField()
    timestamp = serializers.DateTimeField()


class ApiKeyResponseSerializer(serializers.Serializer):
    """Serializer for API key response"""
    message = serializers.CharField()


# API Root and utility views (class-based to avoid schema warnings)
from rest_framework.views import APIView

class ApiRootView(APIView):
    """API root endpoint"""
    permission_classes = [permissions.AllowAny]
    serializer_class = ApiRootResponseSerializer
    
    @extend_schema(
        responses={200: ApiRootResponseSerializer},
        description="API root endpoint - lists all available endpoints"
    )
    def get(self, request):
        return Response({
            'version': '1.0',
            'endpoints': {
                'agents': request.build_absolute_uri('/api/agents/'),
                'conversations': request.build_absolute_uri('/api/conversations/'),
                'health': request.build_absolute_uri('/api/health/'),
                'docs': request.build_absolute_uri('/api/docs/'),
            }
        })


class HealthCheckView(APIView):
    """Health check endpoint"""
    permission_classes = [permissions.AllowAny]
    serializer_class = HealthCheckResponseSerializer
    
    @extend_schema(
        responses={200: HealthCheckResponseSerializer},
        description="Health check endpoint - returns service status"
    )
    def get(self, request):
        return Response({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat()
        })


class GenerateApiKeyView(APIView):
    """Generate API key endpoint"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ApiKeyResponseSerializer
    
    @extend_schema(
        responses={501: ApiKeyResponseSerializer},
        description="Generate API key for authenticated user (not yet implemented)"
    )
    def post(self, request):
        return Response({
            'message': 'API key generation - coming soon'
        }, status=status.HTTP_501_NOT_IMPLEMENTED)


# Keep function aliases for backward compatibility
api_root = ApiRootView.as_view()
health_check = HealthCheckView.as_view()
generate_api_key = GenerateApiKeyView.as_view()


# Pagination
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ViewSets
class AgentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Agent API ViewSet - read only for now
    
    list:
    Return a list of all agents for the authenticated user.
    
    retrieve:
    Return details of a specific agent.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    serializer_class = AgentSerializer
    
    def get_queryset(self):
        """Filter agents by authenticated user"""
        if not self.request.user.is_authenticated:
            return Agent.objects.none()
        return Agent.objects.filter(user=self.request.user).order_by('-created_at')
    
    def get_serializer_class(self):
        """Use different serializers for list and detail views"""
        if self.action == 'list':
            return AgentListSerializer
        return AgentSerializer


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Conversation API ViewSet - read only for now
    
    list:
    Return a list of all conversations for the authenticated user.
    
    retrieve:
    Return details of a specific conversation.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    serializer_class = ConversationSerializer
    
    def get_queryset(self):
        """Filter conversations by authenticated user's agents"""
        if not self.request.user.is_authenticated:
            return Conversation.objects.none()
        return Conversation.objects.filter(
            agent__user=self.request.user
        ).select_related('agent').order_by('-created_at')
    
    def get_serializer_class(self):
        """Use different serializers for list and detail views"""
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer