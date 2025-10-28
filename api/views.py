"""
REST API Views
Phase 7: Integration Layer
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions, viewsets, status
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from agents.models import Agent
from chat.models import Conversation

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def api_root(request):
    """API root endpoint"""
    return Response({
        'version': '1.0',
        'endpoints': {
            'agents': request.build_absolute_uri('/api/agents/'),
            'conversations': request.build_absolute_uri('/api/conversations/'),
            'health': request.build_absolute_uri('/api/health/'),
            'docs': request.build_absolute_uri('/api/docs/'),
        }
    })

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat()
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_api_key(request):
    """Generate API key - placeholder"""
    return Response({
        'message': 'API key generation - coming soon'
    }, status=status.HTTP_501_NOT_IMPLEMENTED)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20

class AgentViewSet(viewsets.ReadOnlyModelViewSet):
    """Agent API ViewSet - read only for now"""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        return Agent.objects.filter(user=self.request.user)
    
    def list(self, request):
        agents = self.get_queryset()
        return Response({
            'count': agents.count(),
            'results': [
                {
                    'id': agent.id,
                    'name': agent.name,
                    'description': agent.description,
                    'use_case': agent.use_case,
                    'is_active': agent.is_active,
                }
                for agent in agents[:20]
            ]
        })
    
    def retrieve(self, request, pk=None):
        try:
            agent = self.get_queryset().get(pk=pk)
            return Response({
                'id': agent.id,
                'name': agent.name,
                'description': agent.description,
                'use_case': agent.use_case,
                'is_active': agent.is_active,
                'created_at': agent.created_at,
            })
        except Agent.DoesNotExist:
            return Response({'error': 'Agent not found'}, status=404)

class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    """Conversation API ViewSet - read only for now"""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        return Conversation.objects.filter(agent__user=self.request.user)
    
    def list(self, request):
        conversations = self.get_queryset()
        return Response({
            'count': conversations.count(),
            'results': [
                {
                    'id': conv.id,
                    'title': conv.title,
                    'agent_id': conv.agent_id,
                    'created_at': conv.created_at,
                }
                for conv in conversations[:20]
            ]
        })