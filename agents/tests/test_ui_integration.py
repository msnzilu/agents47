"""
Phase 2: UI Integration Tests
Test HTMX, responsive layout, and navigation.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from agents.models import Agent

User = get_user_model()


@pytest.mark.django_db
class TestHTMXIntegration:
    """Test HTMX functionality."""
    
    def test_htmx_form_submission(self, client):
        """Test that forms work with and without HTMX."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_create')
        data = {
            'name': 'HTMX Test Agent',
            'description': 'Testing HTMX submission',
            'use_case': Agent.UseCase.SUPPORT,
            'prompt_template': 'Test prompt',
        }
        
        # Regular form submission
        response = client.post(url, data)
        assert response.status_code == 302
        assert Agent.objects.filter(name='HTMX Test Agent').exists()
        
        # HTMX header form submission
        response_htmx = client.post(
            url, 
            data, 
            HTTP_HX_REQUEST='true'
        )
        # Should still work (same behavior for now)
        assert response_htmx.status_code in [200, 302]


@pytest.mark.django_db
class TestResponsiveLayout:
    """Test responsive layout and mobile compatibility."""
    
    def test_responsive_layout_mobile(self, client):
        """Test that pages render with mobile user agent."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        Agent.objects.create(
            user=user,
            name='Test Agent',
            use_case=Agent.UseCase.SUPPORT
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        # Simulate mobile user agent
        mobile_user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        
        urls = [
            reverse('agents:agent_list'),
            reverse('agents:agent_create'),
        ]
        
        for url in urls:
            response = client.get(url, HTTP_USER_AGENT=mobile_user_agent)
            assert response.status_code == 200
            
            # Check for Tailwind responsive classes
            content = response.content.decode()
        
        # Check for filter elements
        assert 'select' in content.lower()
        assert 'Use Case' in content or 'use case' in content
        assert 'Status' in content or 'status' in content


@pytest.mark.django_db
class TestPageLoadPerformance:
    """Test page load and rendering."""
    
    def test_agent_list_loads_with_many_agents(self, client):
        """Test that agent list loads efficiently with many agents."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create 50 agents
        for i in range(50):
            Agent.objects.create(
                user=user,
                name=f'Agent {i}',
                use_case=Agent.UseCase.SUPPORT
            )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_list')
        response = client.get(url)
        
        assert response.status_code == 200
        # Should be paginated (12 per page)
        assert len(response.context['agents']) == 12
    
    def test_pagination_controls_present(self, client):
        """Test that pagination controls appear when needed."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create 20 agents (more than one page)
        for i in range(20):
            Agent.objects.create(
                user=user,
                name=f'Agent {i}',
                use_case=Agent.UseCase.SUPPORT
            )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_list')
        response = client.get(url)
        
        content = response.content.decode()
        assert 'Page' in content or 'page' in content
        assert 'Next' in content or 'next' in content


@pytest.mark.django_db
class TestFormValidationUI:
    """Test form validation feedback."""
    
    def test_form_errors_displayed(self, client):
        """Test that form validation errors are displayed to user."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_create')
        data = {
            'name': 'AB',  # Too short
            'use_case': Agent.UseCase.SUPPORT,
        }
        
        response = client.post(url, data)
        
        content = response.content.decode()
        
        # Check for error message display
        assert 'error' in content.lower() or 'invalid' in content.lower()
        assert response.status_code == 200  # Form re-rendered
    
    def test_success_message_displayed(self, client):
        """Test that success messages are displayed."""
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
        
        # Update agent
        url = reverse('agents:agent_update', kwargs={'pk': agent.pk})
        data = {
            'name': 'Updated Agent',
            'description': 'Updated',
            'use_case': Agent.UseCase.SUPPORT,
            'prompt_template': 'Test',
            'is_active': True,
        }
        
        response = client.post(url, data, follow=True)
        
        # Check for success message
        messages_list = list(response.context['messages'])
        assert len(messages_list) > 0
        assert 'success' in str(messages_list[0]).lower() or 'updated' in str(messages_list[0]).lower()


@pytest.mark.django_db
class TestAccessibility:
    """Test basic accessibility features."""
    
    def test_form_labels_present(self, client):
        """Test that form fields have labels."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_create')
        response = client.get(url)
        
        content = response.content.decode()
        
        # Check for label tags
        assert '<label' in content
        assert 'for=' in content
    
    def test_semantic_html(self, client):
        """Test that semantic HTML elements are used."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_list')
        response = client.get(url)
        
        content = response.content.decode()
        
        # Check for semantic elements
        assert '<nav' in content or '<header' in content
        assert '<main' in content or 'role="main"' in content.decode()
        assert 'md:' in content or 'lg:' in content or 'sm:' in content
    
    def test_responsive_grid_classes(self, client):
        """Test that responsive grid classes are present."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create multiple agents
        for i in range(5):
            Agent.objects.create(
                user=user,
                name=f'Agent {i}',
                use_case=Agent.UseCase.SUPPORT
            )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_list')
        response = client.get(url)
        
        content = response.content.decode()
        
        # Check for responsive grid classes
        assert 'grid' in content
        assert 'md:grid-cols-2' in content or 'lg:grid-cols-3' in content


@pytest.mark.django_db
class TestNavigation:
    """Test navigation links and flow."""
    
    def test_navigation_links(self, client):
        """Test that navigation links are present and functional."""
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
        
        # Test dashboard link
        response = client.get(reverse('users:dashboard'))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'agents' in content.lower()
        
        # Test agent list has create link
        response = client.get(reverse('agents:agent_list'))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Create' in content or 'create' in content
        
        # Test agent detail has edit link
        response = client.get(reverse('agents:agent_detail', kwargs={'pk': agent.pk}))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Edit' in content or 'edit' in content
    
    def test_breadcrumb_navigation(self, client):
        """Test breadcrumb/back navigation."""
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
        
        # Agent detail should have back link
        response = client.get(reverse('agents:agent_detail', kwargs={'pk': agent.pk}))
        content = response.content.decode()
        assert 'Back' in content or 'back' in content
        assert reverse('agents:agent_list') in content
    
    def test_navbar_present(self, client):
        """Test that navigation bar is present on all pages."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        urls = [
            reverse('users:dashboard'),
            reverse('agents:agent_list'),
            reverse('agents:agent_create'),
        ]
        
        for url in urls:
            response = client.get(url)
            content = response.content.decode()
            
            # Check for navbar elements
            assert 'Dashboard' in content or 'dashboard' in content
            assert 'Agent' in content or 'agent' in content
            assert user.email in content  # User email in navbar


@pytest.mark.django_db
class TestSearchAndFilter:
    """Test search and filter UI."""
    
    def test_search_box_present(self, client):
        """Test that search box is present on agent list."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_list')
        response = client.get(url)
        
        content = response.content.decode()
        assert 'search' in content.lower()
        assert 'input' in content.lower()
    
    def test_filter_dropdowns_present(self, client):
        """Test that filter dropdowns are present."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        client.login(username='test@example.com', password='testpass123')
        
        url = reverse('agents:agent_list')
        response = client.get(url)
        
        content = response.content