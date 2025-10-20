"""
Phase 1: Authentication Tests
Test coverage for user registration, login, and password management.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client

User = get_user_model()


@pytest.mark.django_db
class TestUserRegistration:
    """Test user registration functionality."""
    
    def test_user_registration_success(self, client):
        """Test successful user registration."""
        url = reverse('users:register')
        data = {
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'terms_accepted': True,
        }
        
        response = client.post(url, data)
        
        # Should redirect to dashboard after auto-login
        assert response.status_code == 302
        assert User.objects.filter(email='newuser@example.com').exists()
        
        user = User.objects.get(email='newuser@example.com')
        assert user.first_name == 'New'
        assert user.terms_accepted is True
    
    def test_user_registration_duplicate_email(self, client):
        """Test registration with duplicate email fails."""
        User.objects.create_user(
            username='existing',
            email='existing@example.com',
            password='password123'
        )
        
        url = reverse('users:register')
        data = {
            'email': 'existing@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'terms_accepted': True,
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200  # Form re-rendered with errors
        assert 'email' in response.context['form'].errors
    
    def test_user_registration_password_mismatch(self, client):
        """Test registration with mismatched passwords fails."""
        url = reverse('users:register')
        data = {
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'DifferentPass456!',
            'terms_accepted': True,
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        assert not User.objects.filter(email='newuser@example.com').exists()
    
    def test_user_registration_requires_terms(self, client):
        """Test registration requires terms acceptance."""
        url = reverse('users:register')
        data = {
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'terms_accepted': False,
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        assert 'terms_accepted' in response.context['form'].errors


@pytest.mark.django_db
class TestUserLogin:
    """Test user login functionality."""
    
    def test_login_valid_credentials(self, client):
        """Test login with valid credentials."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        url = reverse('users:login')
        data = {
            'username': 'test@example.com',  # Email used as username
            'password': 'password123',
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 302  # Redirect to dashboard
        assert response.wsgi_request.user.is_authenticated
        assert response.wsgi_request.user == user
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials fails."""
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        url = reverse('users:login')
        data = {
            'username': 'test@example.com',
            'password': 'wrongpassword',
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200  # Form re-rendered
        assert not response.wsgi_request.user.is_authenticated
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user fails."""
        url = reverse('users:login')
        data = {
            'username': 'nonexistent@example.com',
            'password': 'password123',
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        assert not response.wsgi_request.user.is_authenticated


@pytest.mark.django_db
class TestPasswordReset:
    """Test password reset functionality."""
    
    def test_password_reset_flow(self, client, mailoutbox):
        """Test complete password reset flow."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='oldpassword123'
        )
        
        # Request password reset
        url = reverse('users:password_reset')
        data = {'email': 'test@example.com'}
        response = client.post(url, data)
        
        assert response.status_code == 302
        assert len(mailoutbox) == 1
        assert 'test@example.com' in mailoutbox[0].to
    
    def test_password_reset_invalid_email(self, client, mailoutbox):
        """Test password reset with invalid email."""
        url = reverse('users:password_reset')
        data = {'email': 'nonexistent@example.com'}
        response = client.post(url, data)
        
        # Should still redirect (security: don't reveal if email exists)
        assert response.status_code == 302
        assert len(mailoutbox) == 0


@pytest.mark.django_db
class TestSessionManagement:
    """Test session persistence and logout."""
    
    def test_session_persistence(self, client):
        """Test that session persists across requests."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        client.login(username='test@example.com', password='password123')
        
        # Make another request
        response = client.get(reverse('users:dashboard'))
        assert response.status_code == 200
        assert response.wsgi_request.user.is_authenticated
    
    def test_logout(self, client):
        """Test user logout."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        client.login(username='test@example.com', password='password123')
        
        # Logout
        response = client.post(reverse('users:logout'))
        assert response.status_code == 302
        
        # Verify logged out
        response = client.get(reverse('users:dashboard'))
        assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
class TestUnauthorizedAccess:
    """Test unauthorized access redirects."""
    
    def test_unauthorized_access_redirects(self, client):
        """Test that unauthorized access to protected pages redirects to login."""
        protected_urls = [
            reverse('users:dashboard'),
            reverse('users:profile'),
        ]
        
        for url in protected_urls:
            response = client.get(url)
            assert response.status_code == 302
            assert '/users/login/' in response.url