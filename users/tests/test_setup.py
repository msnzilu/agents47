"""
Phase 1: Setup and Infrastructure Tests
Test database connection, pgvector, environment, and static files.
"""
import pytest
import os
from django.conf import settings
from django.db import connection
from django.core.management import call_command


@pytest.mark.django_db
class TestDatabaseConnection:
    """Test database connectivity and configuration."""
    
    def test_database_connection(self):
        """Test that database connection works."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
    
    def test_database_name(self):
        """Test correct database is configured."""
        db_name = connection.settings_dict['NAME']
        assert 'ai_agent_platform' in db_name or 'test' in db_name


@pytest.mark.django_db
class TestPgVector:
    """Test pgvector extension setup."""
    
    def test_pgvector_extension_loaded(self):
        """Test that pgvector extension is installed."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM pg_extension WHERE extname = 'vector'"
            )
            result = cursor.fetchone()
            assert result is not None, "pgvector extension not installed"


class TestStaticFiles:
    """Test static file configuration."""
    
    def test_static_files_collected(self):
        """Test static files can be collected."""
        # This will fail if configuration is wrong
        try:
            call_command('collectstatic', '--noinput', '--clear', verbosity=0)
            assert True
        except Exception as e:
            pytest.fail(f"Static files collection failed: {e}")
    
    def test_static_root_configured(self):
        """Test STATIC_ROOT is properly configured."""
        assert settings.STATIC_ROOT is not None
        assert settings.STATIC_URL is not None


class TestEnvironmentVariables:
    """Test environment variable loading."""
    
    def test_environment_variables_loaded(self):
        """Test that critical environment variables are accessible."""
        # These should be set even with defaults
        assert settings.SECRET_KEY is not None
        assert settings.DEBUG is not None
        assert settings.ALLOWED_HOSTS is not None
    
    def test_database_url_configured(self):
        """Test DATABASE_URL is properly configured."""
        db_config = settings.DATABASES['default']
        assert db_config['ENGINE'] is not None
        assert db_config['NAME'] is not None
    
    def test_redis_url_configured(self):
        """Test REDIS_URL is configured for Celery and Channels."""
        assert hasattr(settings, 'CELERY_BROKER_URL')
        assert 'redis' in settings.CELERY_BROKER_URL.lower()


class TestMigrations:
    """Test database migrations."""
    
    @pytest.mark.django_db
    def test_migrations_applied(self):
        """Test that all migrations are applied."""
        from django.db.migrations.executor import MigrationExecutor
        
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        
        # If plan is empty, all migrations are applied
        assert len(plan) == 0, f"Unapplied migrations found: {plan}"


class TestInstalledApps:
    """Test required apps are installed."""
    
    def test_required_apps_installed(self):
        """Test all required apps are in INSTALLED_APPS."""
        required_apps = [
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'rest_framework',
            'channels',
            'users',
            'agents',
            'chat',
            'integrations',
            'analytics',
        ]
        
        for app in required_apps:
            assert app in settings.INSTALLED_APPS, f"{app} not in INSTALLED_APPS"


class TestMiddleware:
    """Test middleware configuration."""
    
    def test_security_middleware_configured(self):
        """Test security middleware is properly configured."""
        required_middleware = [
            'django.middleware.security.SecurityMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
        ]
        
        for middleware in required_middleware:
            assert middleware in settings.MIDDLEWARE, \
                f"{middleware} not in MIDDLEWARE"