from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from agents.models import Agent

User = get_user_model()

class APIIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.agent = Agent.objects.create(
            user=self.user,
            name='Test Agent',
            description='Test',
            use_case='support'
        )
    
    def test_list_agents(self):
        """Test listing agents"""
        response = self.client.get('/api/agents/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_agent(self):
        """Test creating agent via API"""
        data = {
            'name': 'New Agent',
            'description': 'Created via API',
            'use_case': 'research'
        }
        response = self.client.post('/api/agents/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_chat_endpoint(self):
        """Test chat API endpoint"""
        data = {'message': 'Hello'}
        response = self.client.post(
            f'/api/agents/{self.agent.id}/chat/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('response', response.data)