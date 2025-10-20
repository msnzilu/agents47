"""
Phase 2: Agent Views Tests
Test CRUD operations, permissions, and filtering.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from agents.models import Agent

User = get_user_model()


@pytest.mark.django_db
class TestAgentListView:
    """Test agent list/dashboard view."""
    
    def test_dashboard_displays_user_agents_only(self, client):
        """Test that users only see their own agents."""
        # Create two users
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
        
        # Create agents for each user
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
        
        # Login as user1
        client.login(username='user1@example.com', password='pass123')
        
        url = reverse('agents:agent_list')
        response = client.get(url)
        
        assert response.status_code == 200
        assert agent1 in response.context['agents']
        assert agent2 not in response.context['agents']
    
    def test_filter_agents_by_use_case(self, client):
        """Test filtering agents by use case."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create agents with different use cases
        support_agent = Agent.objects.create(
            user=user,
            name='Support Agent',
            use_case=Agent.UseCase.SUPPORT
        )
        research_agent = Agent.objects.create(
            user=user,
            name='Research Agent',
            use_case=Agent.UseCase.RESEARCH
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        # Filter by support
        url = reverse('agents:agent_list') + '?use_case=support'
        response = client.get(url)
        
        assert response.status_code == 200
        assert support_agent in response.context['agents']
        assert research_agent not in response.context['agents']


@pytest.mark.django_db
class TestAgentCreateView:
    """Test agent creation."""
    
    def test_create_agent_form_renders(self, client):
        """Test that create agent form renders correctly."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_create')
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'form' in response.context
        assert 'Create' in response.content.decode()
    
    def test_create_agent_post_success(self, client):
        """Test successful agent creation via POST."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_create')
        data = {
            'name': 'New Test Agent',
            'description': 'A brand new agent',
            'use_case': Agent.UseCase.SUPPORT,
            'prompt_template': 'You are helpful.',
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 302  # Redirect on success
        assert Agent.objects.filter(name='New Test Agent').exists()
        
        agent = Agent.objects.get(name='New Test Agent')
        assert agent.user == user
        assert agent.use_case == Agent.UseCase.SUPPORT
    
    def test_create_agent_invalid_data(self, client):
        """Test agent creation with invalid data."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_create')
        data = {
            'name': 'AB',  # Too short (< 3 chars)
            'use_case': Agent.UseCase.SUPPORT,
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200  # Form re-rendered with errors
        assert not Agent.objects.filter(name='AB').exists()
        assert 'form' in response.context
        assert response.context['form'].errors


@pytest.mark.django_db
class TestAgentUpdateView:
    """Test agent update functionality."""
    
    def test_update_agent_permissions(self, client):
        """Test that users can only update their own agents."""
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
        
        agent = Agent.objects.create(
            user=user1,
            name='User 1 Agent',
            use_case=Agent.UseCase.SUPPORT
        )
        
        # User2 tries to update user1's agent
        client.login(username='user2@example.com', password='pass123')
        
        url = reverse('agents:agent_update', kwargs={'pk': agent.pk})
        response = client.get(url)
        
        # Should return 404 (not found) to prevent information disclosure
        assert response.status_code == 404
    
    def test_update_agent_success(self, client):
        """Test successful agent update."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = Agent.objects.create(
            user=user,
            name='Original Name',
            description='Original description',
            use_case=Agent.UseCase.SUPPORT
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_update', kwargs={'pk': agent.pk})
        data = {
            'name': 'Updated Name',
            'description': 'Updated description',
            'use_case': Agent.UseCase.RESEARCH,
            'prompt_template': 'New prompt',
            'is_active': True,
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 302  # Redirect on success
        
        agent.refresh_from_db()
        assert agent.name == 'Updated Name'
        assert agent.description == 'Updated description'
        assert agent.use_case == Agent.UseCase.RESEARCH


@pytest.mark.django_db
class TestAgentDeleteView:
    """Test agent deletion."""
    
    def test_delete_agent_confirmation(self, client):
        """Test that delete requires confirmation."""
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
        
        client.login(username='test@example.com', password='testpass123')
        
        # GET request shows confirmation page
        url = reverse('agents:agent_delete', kwargs={'pk': agent.pk})
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'agent' in response.context
        assert agent.name in response.content.decode()
        
        # Agent still exists after GET
        assert Agent.objects.filter(pk=agent.pk).exists()
    
    def test_delete_agent_post(self, client):
        """Test actual agent deletion via POST."""
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
        
        agent_id = agent.pk
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_delete', kwargs={'pk': agent.pk})
        response = client.post(url)
        
        assert response.status_code == 302  # Redirect after delete
        assert not Agent.objects.filter(pk=agent_id).exists()


@pytest.mark.django_db
class TestAgentCloneView:
    """Test agent cloning functionality."""
    
    def test_clone_agent_creates_copy(self, client):
        """Test that cloning creates a new agent with copied data."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        original_agent = Agent.objects.create(
            user=user,
            name='Original Agent',
            description='Original description',
            use_case=Agent.UseCase.SUPPORT,
            prompt_template='Original prompt',
            config_json={'temperature': 0.8}
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_clone', kwargs={'pk': original_agent.pk})
        data = {
            'new_name': 'Cloned Agent',
            'include_knowledge': False,
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 302  # Redirect on success
        assert Agent.objects.filter(name='Cloned Agent').exists()
        
        cloned_agent = Agent.objects.get(name='Cloned Agent')
        assert cloned_agent.description == original_agent.description
        assert cloned_agent.use_case == original_agent.use_case
        assert cloned_agent.prompt_template == original_agent.prompt_template
        assert cloned_agent.config_json == original_agent.config_json
        assert cloned_agent.pk != original_agent.pk  # Different agent


@pytest.mark.django_db
class TestAgentDetailView:
    """Test agent detail view."""
    
    def test_agent_detail_view(self, client):
        """Test agent detail page displays correctly."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        agent = Agent.objects.create(
            user=user,
            name='Test Agent',
            description='Test description',
            use_case=Agent.UseCase.SUPPORT
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_detail', kwargs={'pk': agent.pk})
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'agent' in response.context
        assert response.context['agent'] == agent
        assert agent.name in response.content.decode()