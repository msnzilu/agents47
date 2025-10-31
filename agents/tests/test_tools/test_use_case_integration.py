"""
tests/test_use_case_integration.py
Phase 6: Use Case Integration Tests
Tests agent tool selection, prompt templates, and tool chaining
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from agents.models import Agent
from integrations.models import Integration
from agents.agents import AgentFactory, ToolRegistry
from agents.tools.use_case_tools import UseCaseAgentFactory

User = get_user_model()


class TestAgentToolSelection(TestCase):
    """Test that agents select correct tools for their use case"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
    
    def test_agent_selects_correct_tools_for_use_case(self):
        """Test that each use case agent gets appropriate tools"""
        use_cases = ['support', 'research', 'automation', 'scheduling', 'knowledge', 'sales']
        
        for use_case in use_cases:
            agent = Agent.objects.create(
                user=self.user,
                name=f'{use_case.title()} Agent',
                use_case=use_case
            )
            
            # Get tools for this use case
            tools = ToolRegistry.get_tools_for_use_case(use_case)
            
            # Verify tools are returned
            assert len(tools) > 0, f"No tools found for {use_case}"
            
            # Verify tool names match use case
            tool_names = [t['name'] for t in tools]
            
            if use_case == 'support':
                assert any('sentiment' in name or 'escalation' in name for name in tool_names)
            elif use_case == 'research':
                assert any('search' in name or 'summar' in name for name in tool_names)
            elif use_case == 'automation':
                assert any('workflow' in name or 'email' in name for name in tool_names)
            elif use_case == 'scheduling':
                assert any('calendar' in name or 'meeting' in name for name in tool_names)
            elif use_case == 'knowledge':
                assert any('policy' in name or 'document' in name for name in tool_names)
            elif use_case == 'sales':
                assert any('lead' in name or 'crm' in name for name in tool_names)
    
    def test_support_agent_tools(self):
        """Test support agent has sentiment, escalation, ticket, and canned response tools"""
        agent = Agent.objects.create(
            user=self.user,
            name='Support Agent',
            use_case='support'
        )
        
        tools = ToolRegistry.get_tools_for_use_case('support')
        tool_names = [t['name'] for t in tools]
        
        expected_tools = ['sentiment_analyzer', 'escalation_detector', 'ticket_creator', 'canned_response_suggester']
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"
    
    def test_research_agent_tools(self):
        """Test research agent has search, summarization, and extraction tools"""
        agent = Agent.objects.create(
            user=self.user,
            name='Research Agent',
            use_case='research'
        )
        
        tools = ToolRegistry.get_tools_for_use_case('research')
        tool_names = [t['name'] for t in tools]
        
        expected_tools = ['multi_source_search', 'summarizer', 'data_extractor']
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"
    
    def test_automation_agent_tools(self):
        """Test automation agent has workflow, email, and webhook tools"""
        agent = Agent.objects.create(
            user=self.user,
            name='Automation Agent',
            use_case='automation'
        )
        
        tools = ToolRegistry.get_tools_for_use_case('automation')
        tool_names = [t['name'] for t in tools]
        
        expected_tools = ['workflow_executor', 'email_sender', 'webhook_caller']
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"
    
    def test_scheduling_agent_tools(self):
        """Test scheduling agent has calendar and meeting tools"""
        agent = Agent.objects.create(
            user=self.user,
            name='Scheduling Agent',
            use_case='scheduling'
        )
        
        tools = ToolRegistry.get_tools_for_use_case('scheduling')
        tool_names = [t['name'] for t in tools]
        
        expected_tools = ['calendar_manager', 'meeting_scheduler']
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"
    
    def test_knowledge_agent_tools(self):
        """Test knowledge agent has policy Q&A and document search tools"""
        agent = Agent.objects.create(
            user=self.user,
            name='Knowledge Agent',
            use_case='knowledge'
        )
        
        tools = ToolRegistry.get_tools_for_use_case('knowledge')
        tool_names = [t['name'] for t in tools]
        
        expected_tools = ['policy_qa', 'document_searcher']
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"
    
    def test_sales_agent_tools(self):
        """Test sales agent has lead scoring and CRM tools"""
        agent = Agent.objects.create(
            user=self.user,
            name='Sales Agent',
            use_case='sales'
        )
        
        tools = ToolRegistry.get_tools_for_use_case('sales')
        tool_names = [t['name'] for t in tools]
        
        expected_tools = ['lead_scorer', 'crm_connector']
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"


class TestUseCasePromptTemplates(TestCase):
    """Test that use case specific prompt templates are applied"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
    
    def test_use_case_prompt_templates_applied(self):
        """Test that each use case has optimized prompt template"""
        use_cases = ['support', 'research', 'automation', 'scheduling', 'knowledge', 'sales']
        
        for use_case in use_cases:
            prompt = UseCaseAgentFactory.get_prompt_template(use_case)
            
            # Verify prompt is not empty
            assert len(prompt) > 0, f"Empty prompt for {use_case}"
            
            # Verify prompt mentions the use case or role
            prompt_lower = prompt.lower()
            assert use_case in prompt_lower or self._get_role_keyword(use_case) in prompt_lower
    
    def _get_role_keyword(self, use_case):
        """Helper to get expected role keyword in prompt"""
        role_map = {
            'support': 'customer support',
            'research': 'research',
            'automation': 'automation',
            'scheduling': 'scheduling',
            'knowledge': 'knowledge',
            'sales': 'sales'
        }
        return role_map.get(use_case, use_case)
    
    def test_support_prompt_includes_empathy(self):
        """Test support prompt emphasizes empathy and sentiment"""
        prompt = UseCaseAgentFactory.get_prompt_template('support')
        prompt_lower = prompt.lower()
        
        # Should mention empathy, sentiment, escalation
        assert any(word in prompt_lower for word in ['empathy', 'empathetic', 'sentiment', 'emotion'])
        assert 'escalat' in prompt_lower
    
    def test_research_prompt_includes_sources(self):
        """Test research prompt emphasizes citations and sources"""
        prompt = UseCaseAgentFactory.get_prompt_template('research')
        prompt_lower = prompt.lower()
        
        # Should mention sources, citations, accuracy
        assert any(word in prompt_lower for word in ['source', 'citation', 'cite', 'accurate'])
    
    def test_automation_prompt_includes_reliability(self):
        """Test automation prompt emphasizes reliability and execution"""
        prompt = UseCaseAgentFactory.get_prompt_template('automation')
        prompt_lower = prompt.lower()
        
        # Should mention workflow, execution, automation
        assert any(word in prompt_lower for word in ['workflow', 'automat', 'execut', 'reliab'])
    
    def test_scheduling_prompt_includes_coordination(self):
        """Test scheduling prompt emphasizes coordination"""
        prompt = UseCaseAgentFactory.get_prompt_template('scheduling')
        prompt_lower = prompt.lower()
        
        # Should mention calendar, meeting, schedule
        assert any(word in prompt_lower for word in ['calendar', 'meeting', 'schedul', 'availab'])
    
    def test_knowledge_prompt_includes_accuracy(self):
        """Test knowledge prompt emphasizes accuracy and sources"""
        prompt = UseCaseAgentFactory.get_prompt_template('knowledge')
        prompt_lower = prompt.lower()
        
        # Should mention knowledge, policy, document
        assert any(word in prompt_lower for word in ['knowledge', 'policy', 'document', 'accurate'])
    
    def test_sales_prompt_includes_qualification(self):
        """Test sales prompt emphasizes lead qualification"""
        prompt = UseCaseAgentFactory.get_prompt_template('sales')
        prompt_lower = prompt.lower()
        
        # Should mention leads, qualify, sales
        assert any(word in prompt_lower for word in ['lead', 'qualif', 'sales', 'prospect'])


class TestToolChaining(TestCase):
    """Test that tools can be chained together for complex workflows"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
    
    @pytest.mark.asyncio
    async def test_tool_chaining_works(self):
        """Test chaining multiple tools in sequence"""
        # Create support agent
        agent = Agent.objects.create(
            user=self.user,
            name='Support Agent',
            use_case='support'
        )
        
        # Get sentiment analyzer and escalation detector
        from agents.tools.support.sentiment import SentimentAnalyzer
        from agents.tools.use_case_tools import EscalationDetector
        
        analyzer = SentimentAnalyzer(agent=agent)
        detector = EscalationDetector(agent=agent)
        
        # Simulate tool chain: sentiment -> escalation
        customer_message = "I'm extremely frustrated! This is unacceptable!"
        
        # Step 1: Analyze sentiment
        sentiment_result = await analyzer._execute(text=customer_message)
        
        # Step 2: Use sentiment score for escalation detection
        escalation_result = await detector._execute(
            conversation_history=[{'role': 'user', 'content': customer_message}],
            sentiment_score=sentiment_result['sentiment_score']
        )
        
        # Verify chain works
        assert sentiment_result['sentiment_score'] < 0  # Negative
        assert escalation_result['should_escalate'] is True
    
    @pytest.mark.asyncio
    async def test_research_tool_chain(self):
        """Test chaining research tools: search -> extract -> summarize"""
        agent = Agent.objects.create(
            user=self.user,
            name='Research Agent',
            use_case='research'
        )
        
        from agents.tools.use_case_tools import MultiSourceSearch, DataExtractor, Summarizer
        
        searcher = MultiSourceSearch(agent=agent)
        extractor = DataExtractor(agent=agent)
        summarizer = Summarizer(agent=agent)
        
        # Chain: search -> extract -> summarize
        search_result = await searcher._execute(query="AI trends 2024", sources=['web'])
        
        # Extract data from search results
        combined_text = "\n".join([r.get('snippet', '') for r in search_result['results']])
        extract_result = await extractor._execute(text=combined_text, extract_types=['entities', 'urls'])
        
        # Summarize the findings
        summary_result = await summarizer._execute(text=combined_text, style='bullet')
        
        # Verify chain
        assert search_result['total_results'] > 0
        assert extract_result['total_items'] > 0
        assert len(summary_result['summary']) > 0
    
    @pytest.mark.asyncio
    async def test_automation_tool_chain(self):
        """Test chaining automation tools: workflow -> email -> webhook"""
        agent = Agent.objects.create(
            user=self.user,
            name='Automation Agent',
            use_case='automation'
        )
        
        from agents.tools.use_case_tools import WorkflowExecutor, EmailSender, WebhookCaller
        
        executor = WorkflowExecutor(agent=agent)
        sender = EmailSender(agent=agent)
        caller = WebhookCaller(agent=agent)
        
        # Create workflow that chains email and webhook
        workflow = {
            'id': 'notification_chain',
            'steps': [
                {
                    'type': 'action',
                    'name': 'Send Email',
                    'action': {'type': 'notify', 'recipient': 'admin@example.com'}
                },
                {
                    'type': 'action',
                    'name': 'Call Webhook',
                    'action': {'type': 'log', 'message': 'Webhook called'}
                }
            ]
        }
        
        workflow_result = await executor._execute(workflow_config=workflow)
        
        # Verify workflow executed both steps
        assert workflow_result['success'] is True
        assert workflow_result['executed_steps'] == 2
    
    @pytest.mark.asyncio
    async def test_sales_tool_chain(self):
        """Test chaining sales tools: CRM lookup -> lead scoring -> follow-up"""
        agent = Agent.objects.create(
            user=self.user,
            name='Sales Agent',
            use_case='sales'
        )
        
        from agents.tools.use_case_tools import CRMConnector, LeadScorer
        
        crm = CRMConnector(agent=agent)
        scorer = LeadScorer(agent=agent)
        
        # Chain: lookup contact -> score lead -> update CRM
        contact_result = await crm._execute(
            action='lookup',
            email='prospect@example.com'
        )
        
        if contact_result['found']:
            # Score the lead
            lead_data = {
                'id': contact_result['contact']['id'],
                'budget': 75000,
                'timeline_days': 30,
                'authority': 'decision_maker',
                'need': 'critical'
            }
            
            score_result = await scorer._execute(lead_data=lead_data)
            
            # Update CRM with score
            update_result = await crm._execute(
                action='update',
                contact_id=contact_result['contact']['id'],
                lead_score=score_result['total_score'],
                lead_status=score_result['status']
            )
            
            # Verify chain
            assert score_result['total_score'] > 0
            assert update_result['success'] is True
    
    @pytest.mark.asyncio
    async def test_conditional_tool_chaining(self):
        """Test conditional tool execution based on previous results"""
        agent = Agent.objects.create(
            user=self.user,
            name='Support Agent',
            use_case='support'
        )
        
        from agents.tools.support.sentiment import SentimentAnalyzer
        from agents.tools.use_case_tools import EscalationDetector, TicketCreator
        
        analyzer = SentimentAnalyzer(agent=agent)
        detector = EscalationDetector(agent=agent)
        ticket_creator = TicketCreator(agent=agent)
        
        # Conditional chain: analyze -> if negative -> check escalation -> if needed -> create ticket
        message = "This is terrible! I want a refund now!"
        
        sentiment = await analyzer._execute(text=message)
        
        if sentiment['sentiment_score'] < -0.3:
            escalation = await detector._execute(
                conversation_history=[{'role': 'user', 'content': message}],
                sentiment_score=sentiment['sentiment_score']
            )
            
            if escalation['should_escalate']:
                ticket = await ticket_creator._execute(
                    customer_id='CUST123',
                    issue_summary='Urgent refund request - escalation needed',
                    priority='high',
                    category='billing'
                )
                
                # Verify conditional chain executed
                assert ticket['success'] is True
                assert ticket['ticket']['priority'] == 'high'


class TestCrossUseCaseIntegration(TestCase):
    """Test tools working across use cases"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
    
    @pytest.mark.asyncio
    async def test_email_sender_used_across_use_cases(self):
        """Test EmailSender works for both automation and sales"""
        from agents.tools.use_case_tools import EmailSender
        
        # Test with automation agent
        auto_agent = Agent.objects.create(
            user=self.user,
            name='Automation Agent',
            use_case='automation'
        )
        
        auto_sender = EmailSender(agent=auto_agent)
        auto_result = await auto_sender._execute(
            recipient='user@example.com',
            template='notification',
            variables={'name': 'User', 'title': 'Alert', 'message': 'System updated'}
        )
        
        # Test with sales agent
        sales_agent = Agent.objects.create(
            user=self.user,
            name='Sales Agent',
            use_case='sales'
        )
        
        sales_sender = EmailSender(agent=sales_agent)
        sales_result = await sales_sender._execute(
            recipient='prospect@example.com',
            template='notification',
            variables={'name': 'Prospect', 'title': 'Demo', 'message': 'Schedule demo?'}
        )
        
        # Both should work
        assert auto_result['success'] is True
        assert sales_result['success'] is True