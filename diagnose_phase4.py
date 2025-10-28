#!/usr/bin/env python
"""Simple Phase 4 Diagnostic for Docker"""
import os
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiagentplatform.settings')
import django
django.setup()

print("\n" + "="*60)
print("PHASE 4 DIAGNOSTIC CHECK")
print("="*60 + "\n")

issues = []

# Check 1: Channels
print("✓ Check 1: Channels")
try:
    import channels
    print("  ✅ Channels is installed")
except ImportError:
    print("  ❌ Channels NOT installed")
    issues.append("Install channels: pip install channels")

# Check 2: Channels Redis
print("\n✓ Check 2: Channels Redis")
try:
    import channels_redis
    print("  ✅ Channels Redis is installed")
except ImportError:
    print("  ❌ Channels Redis NOT installed")
    issues.append("Install channels-redis: pip install channels-redis")

# Check 3: Redis Connection
print("\n✓ Check 3: Redis Connection")
try:
    import redis
    # Try Docker hostname first
    try:
        r = redis.Redis(host='redis', port=6379, socket_connect_timeout=2)
        r.ping()
        print("  ✅ Redis connected at redis:6379")
    except:
        # Try localhost
        try:
            r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
            r.ping()
            print("  ✅ Redis connected at localhost:6379")
            print("  ⚠️  Using localhost - should use 'redis' in Docker")
        except Exception as e:
            print(f"  ❌ Redis not accessible: {e}")
            issues.append("Start Redis or check docker-compose.yml")
except ImportError:
    print("  ❌ Redis package not installed")
    issues.append("Install redis: pip install redis")

# Check 4: Django Settings
print("\n✓ Check 4: Django Settings")
from django.conf import settings

if 'channels' in settings.INSTALLED_APPS:
    print("  ✅ 'channels' in INSTALLED_APPS")
else:
    print("  ❌ 'channels' NOT in INSTALLED_APPS")
    issues.append("Add 'channels' to INSTALLED_APPS")

if hasattr(settings, 'ASGI_APPLICATION'):
    print(f"  ✅ ASGI_APPLICATION: {settings.ASGI_APPLICATION}")
else:
    print("  ❌ ASGI_APPLICATION not set")
    issues.append("Set ASGI_APPLICATION = 'aiagentplatform.asgi.application'")

if hasattr(settings, 'CHANNEL_LAYERS'):
    print("  ✅ CHANNEL_LAYERS configured")
    config = settings.CHANNEL_LAYERS.get('default', {}).get('CONFIG', {})
    hosts = config.get('hosts', [])
    if hosts:
        print(f"     Hosts: {hosts}")
        if 'localhost' in str(hosts):
            print("     ⚠️  Using 'localhost' - change to 'redis' for Docker")
            issues.append("Change CHANNEL_LAYERS hosts to ('redis', 6379)")
else:
    print("  ❌ CHANNEL_LAYERS not configured")
    issues.append("Configure CHANNEL_LAYERS in settings.py")

# Check 5: Required Files
print("\n✓ Check 5: Required Files")

files = {
    'aiagentplatform/asgi.py': 'ASGI configuration',
    'chat/routing.py': 'WebSocket routing',
    'chat/consumers.py': 'WebSocket consumer'
}

for filepath, description in files.items():
    if os.path.exists(filepath):
        print(f"  ✅ {filepath}")
    else:
        print(f"  ❌ {filepath} missing")
        issues.append(f"Create {filepath}")

# Check 6: Channel Layer Object
print("\n✓ Check 6: Channel Layer")
try:
    from channels.layers import get_channel_layer
    layer = get_channel_layer()
    if layer:
        print(f"  ✅ Channel layer: {layer.__class__.__name__}")
    else:
        print("  ❌ Channel layer is None")
        issues.append("Channel layer not configured properly")
except Exception as e:
    print(f"  ❌ Error: {e}")
    issues.append("Fix channel layer configuration")

# Summary
print("\n" + "="*60)
print("SUMMARY")
print("="*60 + "\n")

if issues:
    print("⚠️  Issues Found:\n")
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue}")
    print("\n" + "="*60)
    print("\n📌 MOST IMPORTANT:")
    print("   Update docker-compose.yml web service to use Daphne:")
    print("   command: daphne -b 0.0.0.0 -p 8000 aiagentplatform.asgi:application\n")
else:
    print("✅ All checks passed!\n")
    print("Next steps:")
    print("1. Ensure docker-compose.yml uses Daphne (not runserver)")
    print("2. Run: docker-compose down && docker-compose up -d")
    print("3. Test: http://localhost:8000/chat/<agent_id>/\n")

print("="*60 + "\n")

