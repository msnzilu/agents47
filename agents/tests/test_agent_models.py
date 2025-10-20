"""
Phase 2: Agent Model Tests
Test agent creation, validation, and relationships.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from agents.models import Agent, KnowledgeBase

User = get_user_model()


@pytest.mark.django_db
class TestAgentCreation:
    """Test agent creation with valid data."""
    
    def test_agent_creation_with_valid_data(self):
        """Test creating an agent with all required fields."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = Agent.objects.create(
            user=user,
            name='Test Agent',
            description='A test agent for customer support',
            use_case=Agent.UseCase.SUPPORT,
            prompt_template='You are a helpful assistant.',
            config_json={
                'provider': 'openai',
                'model': 'gpt-4o-mini',
                'temperature': 0.7,
                'max_tokens': 1000,
            }
        )
        
        assert agent.id is not None
        assert agent.name == 'Test Agent'
        assert agent.user == user
        assert agent.use_case == Agent.UseCase.SUPPORT
        assert agent.is_active is True
        assert agent.config_json['provider'] == 'openai'
    
    def test_agent_use_case_validation(self):
        """Test that use_case field validates against defined choices."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Valid use cases
        valid_cases = [
            Agent.UseCase.SUPPORT,
            Agent.UseCase.RESEARCH,
            Agent.UseCase.AUTOMATION,
            Agent.UseCase.SCHEDULING,
            Agent.UseCase.KNOWLEDGE,
            Agent.UseCase.SALES,
        ]
        
        for use_case in valid_cases:
            agent = Agent.objects.create(
                user=user,
                name=f'Agent {use_case}',
                use_case=use_case
            )
            assert agent.use_case == use_case
        
        # Invalid use case should be caught at database level
        agent = Agent(
            user=user,
            name='Invalid Agent',
            use_case='invalid_case'
        )
        
        with pytest.raises(ValidationError):
            agent.full_clean()
    
    def test_agent_config_json_structure(self):
        """Test that config_json stores and retrieves data correctly."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        config_data = {
            'provider': 'anthropic',
            'model': 'claude-3.5-sonnet',
            'temperature': 0.5,
            'max_tokens': 2000,
            'tools_enabled': True,
            'custom_setting': 'value'
        }
        
        agent = Agent.objects.create(
            user=user,
            name='Config Test Agent',
            config_json=config_data
        )
        
        # Retrieve from database
        retrieved_agent = Agent.objects.get(pk=agent.pk)
        
        assert retrieved_agent.config_json == config_data
        assert retrieved_agent.config_json['provider'] == 'anthropic'
        assert retrieved_agent.config_json['temperature'] == 0.5
        assert retrieved_agent.config_json['custom_setting'] == 'value'
    
    def test_agent_belongs_to_user(self):
        """Test that agents are correctly associated with users."""
        user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        
        agent1 = Agent.objects.create(
            user=user1,
            name='User 1 Agent',
            use_case=Agent.UseCase.SUPPORT
        )
        
        agent2 = Agent.objects.create(
            user=user2,
            name='User 2 Agent',
            use_case=Agent.UseCase.RESEARCH
        )
        
        # Test relationship
        assert agent1.user == user1
        assert agent2.user == user2
        
        # Test reverse relationship
        assert agent1 in user1.agents.all()
        assert agent1 not in user2.agents.all()
        assert agent2 in user2.agents.all()
        assert agent2 not in user1.agents.all()
        
        # Test filtering
        user1_agents = Agent.objects.filter(user=user1)
        assert user1_agents.count() == 1
        assert agent1 in user1_agents


@pytest.mark.django_db
class TestAgentDeletion:
    """Test agent deletion behavior."""
    
    def test_agent_hard_delete(self):
        """Test that agents can be deleted (hard delete for now)."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = Agent.objects.create(
            user=user,
            name='Test Agent',
            use_case=Agent.UseCase.SUPPORT
        )
        
        agent_id = agent.id
        agent.delete()
        
        # Verify agent is deleted
        assert not Agent.objects.filter(pk=agent_id).exists()
    
    def test_agent_soft_delete(self):
        """Test soft delete using is_active flag."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = Agent.objects.create(
            user=user,
            name='Test Agent',
            use_case=Agent.UseCase.SUPPORT,
            is_active=True
        )
        
        # Soft delete by setting is_active to False
        agent.is_active = False
        agent.save()
        
        # Agent still exists but is inactive
        retrieved_agent = Agent.objects.get(pk=agent.pk)
        assert retrieved_agent.is_active is False
        
        # Can filter for active agents only
        active_agents = Agent.objects.filter(user=user, is_active=True)
        assert agent not in active_agents


@pytest.mark.django_db
class TestAgentMethods:
    """Test agent model methods."""
    
    def test_get_default_config(self):
        """Test get_default_config method."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Agent with no config
        agent1 = Agent.objects.create(
            user=user,
            name='Agent 1',
        )
        config1 = agent1.get_default_config()
        assert config1['provider'] == 'openai'
        assert config1['model'] == 'gpt-4o-mini'
        
        # Agent with partial config
        agent2 = Agent.objects.create(
            user=user,
            name='Agent 2',
            config_json={'temperature': 0.9}
        )
        config2 = agent2.get_default_config()
        assert config2['temperature'] == 0.9
        assert config2['provider'] == 'openai'  # Default filled in
    
    def test_get_conversation_count(self):
        """Test get_conversation_count method."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = Agent.objects.create(
            user=user,
            name='Test Agent',
        )
        
        # No conversations yet
        assert agent.get_conversation_count() == 0
        
        # Create conversations
        from chat.models import Conversation
        Conversation.objects.create(agent=agent, title='Conv 1')
        Conversation.objects.create(agent=agent, title='Conv 2')
        
        assert agent.get_conversation_count() == 2
    
    def test_agent_str_representation(self):
        """Test __str__ method."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = Agent.objects.create(
            user=user,
            name='Support Bot',
            use_case=Agent.UseCase.SUPPORT
        )
        
        assert str(agent) == 'Support Bot (Customer Support)'


@pytest.mark.django_db
class TestKnowledgeBase:
    """Test KnowledgeBase model."""
    
    def test_knowledge_base_creation(self):
        """Test creating knowledge base entries."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = Agent.objects.create(
            user=user,
            name='Test Agent',
        )
        
        kb = KnowledgeBase.objects.create(
            agent=agent,
            title='FAQ Document',
            content='Q: What is this? A: This is a test.'
        )
        
        assert kb.agent == agent
        assert kb.title == 'FAQ Document'
        assert kb in agent.knowledge_bases.all()