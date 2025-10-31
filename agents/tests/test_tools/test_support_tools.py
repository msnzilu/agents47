"""
tests/test_support_tools.py
Phase 6: Support Use Case Tools Tests
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from agents.models import Agent
from agents.tools.support_tools import (
    SentimentAnalyzer,
    EscalationDetector,
    TicketCreator,
    CannedResponseSuggester
)

User = get_user_model()


class SentimentAnalysisTestCase(TestCase):
    """Test sentiment analysis tool"""
    
    def setUp(self):
        """Create test user and agent"""
        self.user = User.objects.create_user(
            email='support@example.com',
            username='supportagent',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Support Bot',
            use_case='support',
            is_active=True
        )
        self.tool = SentimentAnalyzer(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis_detects_negative(self):
        """Test detection of negative sentiment in customer messages"""
        negative_text = (
            "I'm extremely frustrated! This product is terrible and completely "
            "broken. This is the worst experience I've ever had. Absolutely "
            "unacceptable service!"
        )
        
        result = await self.tool._execute(text=negative_text)
        
        # Check sentiment score is negative
        assert result['sentiment_score'] < 0
        
        # Check sentiment is negative
        assert result['sentiment'] == 'negative'
        
        # Check confidence
        assert 'confidence' in result
    
    @pytest.mark.asyncio
    async def test_sentiment_positive_message(self):
        """Test positive sentiment detection"""
        positive_text = (
            "Thank you so much! This is absolutely wonderful and works perfectly. "
            "I really appreciate your excellent service. You're the best!"
        )
        
        result = await self.tool._execute(text=positive_text)
        
        # Positive score
        assert result['sentiment_score'] > 0
        assert result['sentiment'] == 'positive'
    
    @pytest.mark.asyncio
    async def test_sentiment_neutral_query(self):
        """Test neutral sentiment for simple questions"""
        neutral_text = "What are your business hours? How do I reset my password?"
        
        result = await self.tool._execute(text=neutral_text)
        
        assert result['sentiment'] == 'neutral'
        assert abs(result['sentiment_score']) <= 0.3


class EscalationDetectorTestCase(TestCase):
    """Test escalation detection tool"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='support@example.com',
            username='supportagent',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Support Bot',
            use_case='support'
        )
        self.tool = EscalationDetector(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_escalation_threshold_triggers(self):
        """Test escalation trigger on negative sentiment and keywords"""
        conversation = [
            {
                'role': 'user',
                'content': 'I have a problem with my account'
            },
            {
                'role': 'assistant',
                'content': 'I can help you with that'
            },
            {
                'role': 'user',
                'content': 'This is not working! I want my money back immediately!'
            },
            {
                'role': 'assistant',
                'content': 'Let me look into that for you'
            },
            {
                'role': 'user',
                'content': 'I will contact my lawyer and sue your company if this is not resolved!'
            }
        ]
        
        result = await self.tool._execute(
            conversation_history=conversation,
            sentiment_score=-0.8
        )
        
        # Should trigger escalation
        assert result['should_escalate'] is True
        assert result['priority'] == 'high'
        assert 'reason' in result
    
    @pytest.mark.asyncio
    async def test_escalation_executive_request(self):
        """Test escalation on executive contact request"""
        conversation = [
            {
                'role': 'user',
                'content': 'I need to speak to the manager about this issue'
            }
        ]
        
        result = await self.tool._execute(conversation_history=conversation)
        
        assert result['should_escalate'] is True
        assert 'manager' in result['reason'].lower() or 'keywords' in result['reason'].lower()
    
    @pytest.mark.asyncio
    async def test_escalation_refund_request(self):
        """Test escalation on refund request"""
        conversation = [
            {
                'role': 'user',
                'content': 'I demand a refund immediately'
            }
        ]
        
        result = await self.tool._execute(conversation_history=conversation)
        
        assert result['should_escalate'] is True
    
    @pytest.mark.asyncio
    async def test_no_escalation_normal_conversation(self):
        """Test no escalation for normal support conversation"""
        conversation = [
            {'role': 'user', 'content': 'Hello, how can I update my profile?'},
            {'role': 'assistant', 'content': 'Go to Settings > Profile'},
            {'role': 'user', 'content': 'Thank you, that worked!'}
        ]
        
        result = await self.tool._execute(
            conversation_history=conversation,
            sentiment_score=0.5
        )
        
        assert result['should_escalate'] is False
        assert result['priority'] == 'normal'


class TicketCreatorTestCase(TestCase):
    """Test ticket creation tool"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='support@example.com',
            username='supportagent',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Support Bot',
            use_case='support'
        )
        self.tool = TicketCreator(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_ticket_creation_payload_correct(self):
        """Test ticket creation with complete payload"""
        result = await self.tool._execute(
            customer_id='CUST-12345',
            issue_summary='Unable to access account after password reset',
            priority='high',
            category='technical'
        )
        
        assert result['success'] is True
        
        ticket = result['ticket']
        
        # Verify all fields are present
        assert 'id' in ticket
        assert ticket['customer_id'] == 'CUST-12345'
        assert ticket['summary'] == 'Unable to access account after password reset'
        assert ticket['priority'] == 'high'
        assert ticket['category'] == 'technical'
        assert ticket['status'] == 'open'
        
        # Verify ticket ID format
        assert 'TKT-' in ticket['id']
        
        # Verify timestamps
        assert 'created_at' in ticket
    
    @pytest.mark.asyncio
    async def test_ticket_default_values(self):
        """Test ticket creation with default priority and category"""
        result = await self.tool._execute(
            customer_id='CUST-999',
            issue_summary='General inquiry'
        )
        
        assert result['success'] is True
        ticket = result['ticket']
        
        # Default priority should be normal
        assert ticket['priority'] == 'normal'
        
        # Default category should be general
        assert ticket['category'] == 'general'
    
    @pytest.mark.asyncio
    async def test_ticket_unique_ids(self):
        """Test that each ticket gets a unique ID"""
        result1 = await self.tool._execute(
            customer_id='CUST-1',
            issue_summary='Issue 1'
        )
        result2 = await self.tool._execute(
            customer_id='CUST-2',
            issue_summary='Issue 2'
        )
        result3 = await self.tool._execute(
            customer_id='CUST-3',
            issue_summary='Issue 3'
        )
        
        ticket1 = result1['ticket']['id']
        ticket2 = result2['ticket']['id']
        ticket3 = result3['ticket']['id']
        
        # All IDs should be unique
        assert ticket1 != ticket2
        assert ticket2 != ticket3
        assert ticket1 != ticket3


class CannedResponseSuggesterTestCase(TestCase):
    """Test canned response suggestion tool"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='support@example.com',
            username='supportagent',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Support Bot',
            use_case='support'
        )
        self.tool = CannedResponseSuggester(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_canned_response_retrieval(self):
        """Test retrieval of appropriate canned response"""
        result = await self.tool._execute(issue_category='technical')
        
        assert 'suggested_response' in result
        assert 'category' in result
        assert result['category'] == 'technical'
        assert 'technical' in result['suggested_response'].lower() or 'troubleshoot' in result['suggested_response'].lower()
    
    @pytest.mark.asyncio
    async def test_canned_response_billing_inquiry(self):
        """Test billing inquiry response"""
        result = await self.tool._execute(issue_category='billing')
        
        assert result['category'] == 'billing'
        assert 'billing' in result['suggested_response'].lower()
    
    @pytest.mark.asyncio
    async def test_canned_response_with_alternatives(self):
        """Test that alternatives are provided"""
        result = await self.tool._execute(issue_category='shipping')
        
        assert 'alternatives' in result
        assert len(result['alternatives']) > 0
        # Alternatives should not include the selected category
        assert all('shipping' not in alt.lower() for alt in result['alternatives'][:1])
    
    @pytest.mark.asyncio
    async def test_canned_response_default_fallback(self):
        """Test behavior with unknown category"""
        result = await self.tool._execute(issue_category='unknown_category')
        
        # Should fall back to general response
        assert 'suggested_response' in result
        assert result['category'] == 'unknown_category'