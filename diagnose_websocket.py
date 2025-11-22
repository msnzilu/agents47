#!/usr/bin/env python
"""
WebSocket Diagnostic Script
Tests Redis, Channel Layers, and WebSocket connectivity
"""
import os
import sys
import django
import asyncio

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiagentplatform.settings')
django.setup()

from django.conf import settings
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from chat.models import Conversation
from agents.models import Agent

User = get_user_model()

def test_redis_connection():
    """Test Redis connectivity"""
    print("\n" + "="*60)
    print("TEST 1: Redis Connection")
    print("="*60)
    
    try:
        import redis
        redis_config = settings.CHANNEL_LAYERS['default']['CONFIG']
        hosts = redis_config.get('hosts', [])
        
        if hosts:
            host, port = hosts[0] if isinstance(hosts[0], tuple) else ('localhost', 6379)
            print(f"Attempting to connect to Redis at {host}:{port}...")
            
            r = redis.Redis(host=host, port=port, decode_responses=True)
            r.ping()
            print("✅ Redis connection successful!")
            
            # Test basic operations
            r.set('test_key', 'test_value')
            value = r.get('test_key')
            r.delete('test_key')
            print(f"✅ Redis read/write test successful (value: {value})")
            
            return True
        else:
            print("❌ No Redis hosts configured")
            return False
            
    except Exception as e:
        print(f"❌ Redis connection failed: {str(e)}")
        print(f"   Error type: {type(e).__name__}")
        return False

async def test_channel_layer():
    """Test Django Channels layer"""
    print("\n" + "="*60)
    print("TEST 2: Django Channels Layer")
    print("="*60)
    
    try:
        channel_layer = get_channel_layer()
        print(f"Channel layer backend: {channel_layer.__class__.__name__}")
        
        # Test sending and receiving
        test_group = "test_group"
        test_message = {"type": "test.message", "data": "Hello World"}
        
        print(f"Sending test message to group '{test_group}'...")
        await channel_layer.group_send(test_group, test_message)
        print("✅ Channel layer group_send successful!")
        
        return True
        
    except Exception as e:
        print(f"❌ Channel layer test failed: {str(e)}")
        print(f"   Error type: {type(e).__name__}")
        return False

def test_database_setup():
    """Test database and conversation setup"""
    print("\n" + "="*60)
    print("TEST 3: Database & Conversation Setup")
    print("="*60)
    
    try:
        # Check for users
        user_count = User.objects.count()
        print(f"Total users in database: {user_count}")
        
        if user_count > 0:
            test_user = User.objects.first()
            print(f"✅ Found test user: {test_user.email}")
        else:
            print("⚠️  No users found in database")
            return False
        
        # Check for agents
        from agents.models import Agent
        agent_count = Agent.objects.count()
        print(f"Total agents in database: {agent_count}")
        
        if agent_count > 0:
            test_agent = Agent.objects.filter(is_active=True).first()
            if test_agent:
                print(f"✅ Found active agent: {test_agent.name}")
            else:
                print("⚠️  No active agents found")
                return False
        else:
            print("⚠️  No agents found in database")
            return False
        
        # Check for conversations
        conv_count = Conversation.objects.count()
        print(f"Total conversations in database: {conv_count}")
        
        if conv_count > 0:
            test_conv = Conversation.objects.first()
            print(f"✅ Found conversation: ID={test_conv.id}, Agent={test_conv.agent.name}")
        else:
            print("⚠️  No conversations found")
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {str(e)}")
        print(f"   Error type: {type(e).__name__}")
        return False

def test_websocket_routing():
    """Test WebSocket URL routing"""
    print("\n" + "="*60)
    print("TEST 4: WebSocket Routing")
    print("="*60)
    
    try:
        from chat.routing import websocket_urlpatterns
        print(f"WebSocket URL patterns configured: {len(websocket_urlpatterns)}")
        
        for pattern in websocket_urlpatterns:
            print(f"  - Pattern: {pattern.pattern}")
            print(f"    Consumer: {pattern.callback.__name__}")
        
        print("✅ WebSocket routing configured")
        return True
        
    except Exception as e:
        print(f"❌ WebSocket routing test failed: {str(e)}")
        return False

def test_asgi_configuration():
    """Test ASGI application configuration"""
    print("\n" + "="*60)
    print("TEST 5: ASGI Configuration")
    print("="*60)
    
    try:
        from aiagentplatform.asgi import application
        print(f"ASGI application type: {type(application).__name__}")
        
        # Check if it's a ProtocolTypeRouter
        if hasattr(application, 'application_mapping'):
            protocols = list(application.application_mapping.keys())
            print(f"Configured protocols: {protocols}")
            
            if 'websocket' in protocols:
                print("✅ WebSocket protocol configured in ASGI")
            else:
                print("❌ WebSocket protocol NOT configured in ASGI")
                return False
        
        print("✅ ASGI configuration looks good")
        return True
        
    except Exception as e:
        print(f"❌ ASGI configuration test failed: {str(e)}")
        return False

def print_configuration_summary():
    """Print current configuration"""
    print("\n" + "="*60)
    print("CONFIGURATION SUMMARY")
    print("="*60)
    
    print(f"DEBUG: {settings.DEBUG}")
    print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    print(f"ASGI_APPLICATION: {settings.ASGI_APPLICATION}")
    
    channel_config = settings.CHANNEL_LAYERS['default']
    print(f"\nChannel Layer Backend: {channel_config['BACKEND']}")
    print(f"Channel Layer Config: {channel_config['CONFIG']}")
    
    print(f"\nCelery Broker: {settings.CELERY_BROKER_URL}")

async def main():
    """Run all diagnostic tests"""
    print("\n" + "="*60)
    print("WebSocket Diagnostic Tool")
    print("="*60)
    
    print_configuration_summary()
    
    results = {
        'redis': test_redis_connection(),
        'channel_layer': await test_channel_layer(),
        'database': test_database_setup(),
        'routing': test_websocket_routing(),
        'asgi': test_asgi_configuration()
    }
    
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.upper()}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ All tests passed! WebSocket should be working.")
        print("\nNext steps:")
        print("1. Check browser console for WebSocket connection errors")
        print("2. Verify the conversation ID exists in the database")
        print("3. Ensure user is authenticated")
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("1. Ensure Redis is running: docker-compose up -d redis")
        print("2. Check CHANNEL_LAYERS configuration in settings.py")
        print("3. Run migrations: python manage.py migrate")
    
    return all_passed

if __name__ == '__main__':
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
