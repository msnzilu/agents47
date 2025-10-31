"""
tests/test_sales_tools.py
Phase 6: Sales Use Case Tools Tests
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from agents.models import Agent
from agents.tools.sales_tools import (
    LeadScorer,
    CRMConnector,
    OutreachTemplatePersonalizer,
    FollowUpReminder
)

User = get_user_model()


class TestLeadScorer(TestCase):
    """Test lead scoring algorithm"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Sales Agent',
            use_case='sales'
        )
        self.scorer = LeadScorer(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_lead_scoring_algorithm(self):
        """Test BANT-based lead scoring algorithm"""
        lead_data = {
            'id': 'LEAD123',
            'budget': 75000,
            'timeline_days': 45,
            'authority': 'decision_maker',
            'need': 'critical'
        }
        
        result = await self.scorer._execute(lead_data=lead_data)
        
        assert 'total_score' in result
        assert 'status' in result
        assert 'breakdown' in result
        
        # Verify BANT criteria are in breakdown
        breakdown = result['breakdown']
        assert 'budget' in breakdown
        assert 'timeline' in breakdown
        assert 'authority' in breakdown
        assert 'need' in breakdown
        
        # Score should be high for this qualified lead
        assert result['total_score'] >= 70
        assert result['status'] in ['hot', 'warm']
    
    @pytest.mark.asyncio
    async def test_high_budget_scoring(self):
        """Test that high budget leads score higher"""
        high_budget_lead = {
            'budget': 150000,
            'timeline_days': 90,
            'authority': 'influencer',
            'need': 'high'
        }
        
        low_budget_lead = {
            'budget': 5000,
            'timeline_days': 90,
            'authority': 'influencer',
            'need': 'high'
        }
        
        high_result = await self.scorer._execute(lead_data=high_budget_lead)
        low_result = await self.scorer._execute(lead_data=low_budget_lead)
        
        assert high_result['total_score'] > low_result['total_score']
    
    @pytest.mark.asyncio
    async def test_urgent_timeline_scoring(self):
        """Test that urgent timelines score higher"""
        urgent_lead = {
            'budget': 50000,
            'timeline_days': 15,
            'authority': 'decision_maker',
            'need': 'critical'
        }
        
        delayed_lead = {
            'budget': 50000,
            'timeline_days': 200,
            'authority': 'decision_maker',
            'need': 'critical'
        }
        
        urgent_result = await self.scorer._execute(lead_data=urgent_lead)
        delayed_result = await self.scorer._execute(lead_data=delayed_lead)
        
        assert urgent_result['total_score'] > delayed_result['total_score']
        assert urgent_result['status'] == 'hot'
    
    @pytest.mark.asyncio
    async def test_decision_maker_authority(self):
        """Test that decision makers score higher than users"""
        decision_maker_lead = {
            'budget': 50000,
            'timeline_days': 60,
            'authority': 'decision_maker',
            'need': 'high'
        }
        
        user_lead = {
            'budget': 50000,
            'timeline_days': 60,
            'authority': 'user',
            'need': 'high'
        }
        
        dm_result = await self.scorer._execute(lead_data=decision_maker_lead)
        user_result = await self.scorer._execute(lead_data=user_lead)
        
        assert dm_result['total_score'] > user_result['total_score']
    
    @pytest.mark.asyncio
    async def test_critical_need_scoring(self):
        """Test that critical needs score higher"""
        critical_lead = {
            'budget': 50000,
            'timeline_days': 60,
            'authority': 'influencer',
            'need': 'critical'
        }
        
        low_need_lead = {
            'budget': 50000,
            'timeline_days': 60,
            'authority': 'influencer',
            'need': 'low'
        }
        
        crit_result = await self.scorer._execute(lead_data=critical_lead)
        low_result = await self.scorer._execute(lead_data=low_need_lead)
        
        assert crit_result['total_score'] > low_result['total_score']
    
    @pytest.mark.asyncio
    async def test_lead_status_categories(self):
        """Test lead status categorization (hot/warm/cold)"""
        # Hot lead
        hot_lead = {
            'budget': 100000,
            'timeline_days': 20,
            'authority': 'decision_maker',
            'need': 'critical'
        }
        
        # Cold lead
        cold_lead = {
            'budget': 5000,
            'timeline_days': 300,
            'authority': 'user',
            'need': 'low'
        }
        
        hot_result = await self.scorer._execute(lead_data=hot_lead)
        cold_result = await self.scorer._execute(lead_data=cold_lead)
        
        assert hot_result['status'] == 'hot'
        assert cold_result['status'] == 'cold'


class TestCRMConnector(TestCase):
    """Test CRM integration operations"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Sales Agent',
            use_case='sales'
        )
        self.crm = CRMConnector(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_crm_lookup_returns_contact(self):
        """Test CRM contact lookup by email"""
        result = await self.crm._execute(
            action='lookup',
            email='john.doe@example.com'
        )
        
        assert result['found'] is True
        assert 'contact' in result
        
        contact = result['contact']
        assert contact['email'] == 'john.doe@example.com'
        assert 'id' in contact
        assert 'name' in contact
        assert 'company' in contact
    
    @pytest.mark.asyncio
    async def test_crm_lookup_by_company(self):
        """Test CRM lookup by company name"""
        result = await self.crm._execute(
            action='lookup',
            email='contact@acme.com',
            company='Acme Corp'
        )
        
        if result['found']:
            assert result['contact']['company'] == 'Acme Corp'
    
    @pytest.mark.asyncio
    async def test_crm_lookup_not_found(self):
        """Test CRM lookup when contact doesn't exist"""
        result = await self.crm._execute(
            action='lookup',
            email='nonexistent@example.com'
        )
        
        assert 'found' in result
    
    @pytest.mark.asyncio
    async def test_crm_create_contact(self):
        """Test creating new CRM contact"""
        result = await self.crm._execute(
            action='create',
            email='newlead@example.com',
            name='Jane Smith',
            company='Tech Startup Inc',
            phone='+1-555-0123',
            source='website'
        )
        
        assert result['success'] is True
        assert 'contact_id' in result
        assert 'created_at' in result
    
    @pytest.mark.asyncio
    async def test_crm_update_contact(self):
        """Test updating existing CRM contact"""
        result = await self.crm._execute(
            action='update',
            contact_id='contact_12345',
            deal_stage='negotiation',
            last_contact_date='2024-12-01',
            notes='Follow-up scheduled'
        )
        
        assert result['success'] is True
        assert result['contact_id'] == 'contact_12345'
        assert 'updated_fields' in result
        assert 'deal_stage' in result['updated_fields']


class TestOutreachTemplates(TestCase):
    """Test email outreach template generation"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Sales Agent',
            use_case='sales'
        )
        self.personalizer = OutreachTemplatePersonalizer(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_outreach_template_personalization(self):
        """Test personalized outreach email generation"""
        template = "Hi {name}, I noticed {company} is looking for {solution}. Let's connect!"
        
        result = await self.personalizer._execute(
            template=template,
            contact_data={
                'name': 'John',
                'company': 'Acme Corp',
                'solution': 'data analytics tools'
            }
        )
        
        assert 'personalized_message' in result
        assert 'John' in result['personalized_message']
        assert 'Acme Corp' in result['personalized_message']
        assert 'data analytics tools' in result['personalized_message']
    
    @pytest.mark.asyncio
    async def test_outreach_template_variables(self):
        """Test that all template variables are replaced"""
        template = "Dear {name}, Following up on {topic} for {company}."
        
        result = await self.personalizer._execute(
            template=template,
            contact_data={
                'name': 'Sarah',
                'topic': 'our demo',
                'company': 'Tech Innovations'
            }
        )
        
        message = result['personalized_message']
        
        # Verify personalization
        assert 'Sarah' in message
        assert 'our demo' in message
        assert 'Tech Innovations' in message
        assert 'variables_used' in result
        assert len(result['variables_used']) == 3


class TestFollowUpReminders(TestCase):
    """Test follow-up reminder creation"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Sales Agent',
            use_case='sales'
        )
        self.reminder = FollowUpReminder(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_follow_up_reminder_created(self):
        """Test creation of follow-up reminders for leads"""
        result = await self.reminder._execute(
            contact_id='CONT-123',
            follow_up_date='2024-12-15',
            note='Discuss pricing and timeline'
        )
        
        assert result['success'] is True
        assert 'reminder_id' in result
        assert result['contact_id'] == 'CONT-123'
        assert result['scheduled_for'] == '2024-12-15'
        assert result['note'] == 'Discuss pricing and timeline'
    
    @pytest.mark.asyncio
    async def test_follow_up_reminder_without_note(self):
        """Test creating reminder without note"""
        result = await self.reminder._execute(
            contact_id='CONT-456',
            follow_up_date='2024-12-20'
        )
        
        assert result['success'] is True
        assert result['contact_id'] == 'CONT-456'
        assert 'note' in result