"""
tests/test_knowledge_tools.py
Phase 6: Knowledge Management Use Case Tools Tests
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from agents.models import Agent
from agents.tools.use_case_tools import (
    PolicyQA,
    DocumentSearcher
)

User = get_user_model()


class TestPolicyQA(TestCase):
    """Test policy Q&A functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Knowledge Agent',
            use_case='knowledge'
        )
        self.policy_qa = PolicyQA(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_policy_qa_retrieves_answer(self):
        """Test retrieval of policy answers from knowledge base"""
        result = await self.policy_qa._execute(
            question="What is your refund policy?"
        )
        
        assert 'question' in result
        assert 'answer' in result
        assert 'confidence' in result
        assert 'sources' in result
        
        # Verify answer is relevant to refund policy
        answer_lower = result['answer'].lower()
        assert 'refund' in answer_lower or 'return' in answer_lower or 'policy' in answer_lower
        
        # Confidence should be reasonable for matched policy
        assert result['confidence'] > 0.5
    
    @pytest.mark.asyncio
    async def test_policy_qa_privacy_question(self):
        """Test privacy policy question"""
        result = await self.policy_qa._execute(
            question="How do you protect my data and privacy?"
        )
        
        assert result['confidence'] > 0.5
        answer_lower = result['answer'].lower()
        assert any(word in answer_lower for word in ['privacy', 'data', 'protect', 'gdpr', 'security'])
        
        # Verify source tracking
        assert 'sources' in result
        if result['sources']:
            assert 'privacy' in result['sources']
    
    @pytest.mark.asyncio
    async def test_policy_qa_vacation_policy(self):
        """Test employee vacation policy question"""
        result = await self.policy_qa._execute(
            question="How many vacation days do employees get?"
        )
        
        assert result['answer'] is not None
        answer_lower = result['answer'].lower()
        assert any(word in answer_lower for word in ['vacation', 'days', 'paid'])
    
    @pytest.mark.asyncio
    async def test_policy_qa_no_match(self):
        """Test handling of questions with no policy match"""
        result = await self.policy_qa._execute(
            question="What is the weather like today?"
        )
        
        # Should return low confidence and generic response
        assert result['confidence'] < 0.5
        assert 'could not find' in result['answer'].lower() or 'contact' in result['answer'].lower()
    
    @pytest.mark.asyncio
    async def test_policy_qa_with_knowledge_base_id(self):
        """Test querying specific knowledge base"""
        result = await self.policy_qa._execute(
            question="What is your security policy?",
            knowledge_base_id="kb_security_001"
        )
        
        assert result['knowledge_base'] == "kb_security_001"
        assert 'answer' in result


class TestDocumentSearcher(TestCase):
    """Test document search across knowledge bases"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Knowledge Agent',
            use_case='knowledge'
        )
        self.searcher = DocumentSearcher(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_cross_kb_search(self):
        """Test searching across multiple knowledge bases"""
        result = await self.searcher._execute(
            query="customer support best practices",
            limit=10
        )
        
        assert 'query' in result
        assert 'results' in result
        assert 'total_results' in result
        assert result['total_results'] > 0
        
        # Verify result structure
        for doc in result['results']:
            assert 'document_id' in doc
            assert 'title' in doc
            assert 'snippet' in doc
            assert 'relevance' in doc
            assert 'document_type' in doc
    
    @pytest.mark.asyncio
    async def test_document_search_relevance_ranking(self):
        """Test that search results are ranked by relevance"""
        result = await self.searcher._execute(
            query="employee handbook",
            limit=5
        )
        
        results = result['results']
        assert len(results) > 0
        
        # Verify results are sorted by relevance (descending)
        relevance_scores = [doc['relevance'] for doc in results]
        assert relevance_scores == sorted(relevance_scores, reverse=True)
        
        # Top result should have highest relevance
        assert results[0]['relevance'] >= results[-1]['relevance']
    
    @pytest.mark.asyncio
    async def test_document_search_with_filters(self):
        """Test document search with type filters"""
        result = await self.searcher._execute(
            query="company policies",
            filters={'document_type': 'policy'},
            limit=10
        )
        
        assert result['filters_applied']['document_type'] == 'policy'
        
        # All results should be policy documents
        for doc in result['results']:
            assert doc['document_type'] == 'policy'
    
    @pytest.mark.asyncio
    async def test_document_search_limit(self):
        """Test that search respects result limit"""
        limit = 3
        result = await self.searcher._execute(
            query="training materials",
            limit=limit
        )
        
        assert len(result['results']) <= limit
    
    @pytest.mark.asyncio
    async def test_document_search_performance(self):
        """Test search performance metrics"""
        result = await self.searcher._execute(
            query="security protocols",
            limit=10
        )
        
        assert 'search_time_ms' in result
        assert isinstance(result['search_time_ms'], (int, float))
        assert result['search_time_ms'] > 0
    
    @pytest.mark.asyncio
    async def test_document_search_snippets(self):
        """Test that results include relevant snippets"""
        result = await self.searcher._execute(
            query="data retention policy",
            limit=5
        )
        
        for doc in result['results']:
            assert 'snippet' in doc
            assert len(doc['snippet']) > 0
            
            # Snippet should be reasonably sized
            assert len(doc['snippet']) <= 500


class TestConfidenceScoring(TestCase):
    """Test confidence score calculation for knowledge queries"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Knowledge Agent',
            use_case='knowledge'
        )
        self.policy_qa = PolicyQA(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_confidence_score_calculated(self):
        """Test that confidence scores are calculated for answers"""
        result = await self.policy_qa._execute(
            question="What is your refund policy?"
        )
        
        assert 'confidence' in result
        assert isinstance(result['confidence'], (int, float))
        assert 0.0 <= result['confidence'] <= 1.0
    
    @pytest.mark.asyncio
    async def test_high_confidence_for_exact_match(self):
        """Test high confidence for exact policy matches"""
        result = await self.policy_qa._execute(
            question="What is the refund policy?"
        )
        
        # Should have high confidence for direct policy question
        assert result['confidence'] >= 0.7
        assert len(result['sources']) > 0
    
    @pytest.mark.asyncio
    async def test_low_confidence_for_no_match(self):
        """Test low confidence when no relevant policy found"""
        result = await self.policy_qa._execute(
            question="What should I have for lunch?"
        )
        
        # Should have low confidence for unrelated question
        assert result['confidence'] < 0.5
    
    @pytest.mark.asyncio
    async def test_medium_confidence_for_partial_match(self):
        """Test medium confidence for partial matches"""
        result = await self.policy_qa._execute(
            question="Tell me about payments and billing"
        )
        
        # May have medium confidence if partial match exists
        assert 0.0 <= result['confidence'] <= 1.0


class TestKnowledgeIntegration(TestCase):
    """Test integration between policy Q&A and document search"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Knowledge Agent',
            use_case='knowledge'
        )
        self.policy_qa = PolicyQA(agent=self.agent)
        self.searcher = DocumentSearcher(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_qa_and_search_consistency(self):
        """Test that Q&A and search return consistent results"""
        query = "employee benefits"
        
        # Get Q&A answer
        qa_result = await self.policy_qa._execute(question=query)
        
        # Get search results
        search_result = await self.searcher._execute(query=query, limit=5)
        
        # Both should return relevant content
        assert qa_result['confidence'] > 0
        assert search_result['total_results'] > 0
        
        # If Q&A has high confidence, search should find relevant docs
        if qa_result['confidence'] > 0.7:
            assert len(search_result['results']) > 0
    
    @pytest.mark.asyncio
    async def test_source_citation_accuracy(self):
        """Test that sources cited by Q&A can be found in search"""
        qa_result = await self.policy_qa._execute(
            question="What is the vacation policy?"
        )
        
        if qa_result['sources']:
            # Search for the source document
            source = qa_result['sources'][0]
            search_result = await self.searcher._execute(
                query=source,
                limit=5
            )
            
            # Should find documents related to the source
            assert search_result['total_results'] > 0
    
    @pytest.mark.asyncio
    async def test_fallback_to_search_on_low_qa_confidence(self):
        """Test that low Q&A confidence suggests using search"""
        qa_result = await self.policy_qa._execute(
            question="obscure policy detail"
        )
        
        if qa_result['confidence'] < 0.5:
            # Perform search as fallback
            search_result = await self.searcher._execute(
                query="obscure policy detail",
                limit=10
            )
            
            # Search should still attempt to find relevant content
            assert 'results' in search_result