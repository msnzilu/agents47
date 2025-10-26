"""
Pytest configuration and shared fixtures for Phase 3 tests
"""
import pytest
from django.contrib.auth import get_user_model
from agents.models import Agent
from integrations.models import Integration
from chat.models import Conversation, Message

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def other_user(db):
    """Create another test user"""
    return User.objects.create_user(
        username='otheruser',
        email='other@example.com',
        password='testpass123'
    )


@pytest.fixture
def agent(user):
    """Create a test agent"""
    return Agent.objects.create(
        user=user,
        name='Test Agent',
        use_case='support',
        config_json={
            'temperature': 0.7,
            'max_tokens': 1000,
            'tools_enabled': False
        }
    )


@pytest.fixture
def agent_with_tools(user):
    """Create an agent with tools enabled"""
    return Agent.objects.create(
        user=user,
        name='Tool Agent',
        use_case='support',
        config_json={
            'temperature': 0.7,
            'max_tokens': 1000,
            'tools_enabled': True
        }
    )


@pytest.fixture
def openai_integration(agent):
    """Create OpenAI integration"""
    return Integration.objects.create(
        agent=agent,
        name='OpenAI API',
        integration_type='openai',
        status=Integration.Status.ACTIVE,
        is_active=True,
        config={'api_key': 'sk-test-key'}
    )


@pytest.fixture
def anthropic_integration(agent):
    """Create Anthropic integration"""
    return Integration.objects.create(
        agent=agent,
        name='Anthropic API',
        integration_type='anthropic',
        status=Integration.Status.ACTIVE,
        is_active=True,
        config={'api_key': 'sk-ant-test-key'}
    )


@pytest.fixture
def conversation(agent):
    """Create a conversation"""
    return Conversation.objects.create(
        agent=agent,
        is_active=True
    )


@pytest.fixture
def conversation_with_history(conversation):
    """Create conversation with message history"""
    messages = []
    for i in range(10):
        msg = Message.objects.create(
            conversation=conversation,
            role='user' if i % 2 == 0 else 'assistant',
            content=f'Message {i}'
        )
        messages.append(msg)
    return conversation


@pytest.fixture
def authenticated_client(client, user):
    """Return an authenticated Django test client"""
    client.force_login(user)
    return client


# Pytest marks for organizing tests
def pytest_configure(config):
    """Configure custom pytest marks"""
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: Performance tests"
    )
    config.addinivalue_line(
        "markers", "security: Security tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests"
    )