"""
Tests for knowledge base functionality.
"""
import pytest
from django.contrib.auth import get_user_model
from agents.models import Agent, KnowledgeBase, DocumentChunk
from agents.services import DocumentProcessor, ChunkingService, KnowledgeBaseService

User = get_user_model()


@pytest.mark.django_db
class TestKnowledgeBase:
    """Test knowledge base operations."""
    
    def test_document_chunking(self):
        """Test text chunking."""
        text = "This is a test document. " * 100
        chunks = ChunkingService.chunk_text(text, chunk_size=100, chunk_overlap=20)
        
        assert len(chunks) > 0
        assert all('content' in chunk for chunk in chunks)
        assert all('index' in chunk for chunk in chunks)
    
    def test_create_knowledge_base(self):
        """Test creating knowledge base."""
        user = User.objects.create_user(email='test@example.com', password='test123')
        agent = Agent.objects.create(
            user=user,
            name='Test Agent',
            use_case='support'
        )
        
        kb = KnowledgeBase.objects.create(
            agent=agent,
            title='Test KB',
            content='Test content',
            document_type='text'
        )
        
        assert kb.status == 'pending'
        assert kb.agent == agent
    
    @pytest.mark.skip(reason="Requires OpenAI API key")
    def test_embedding_generation(self):
        """Test embedding generation (requires API key)."""
        from agents.services import EmbeddingService
        
        embedder = EmbeddingService(provider='openai')
        embedding = embedder.generate_embedding("Test text")
        
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)