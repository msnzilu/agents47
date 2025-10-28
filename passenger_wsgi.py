import sys
import os

# ==============================================================================
# STEP 1: Set the Python interpreter path
# ==============================================================================
# Replace 'username' with your actual cPanel username
# Replace '3.9' with your actual Python version from cPanel
INTERP = "/home/agenobhk/virtualenv/public_html/agents47/3.9/bin/python3"

if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)


# ==============================================================================
# STEP 2: Add your project to Python's path
# ==============================================================================
cwd = os.getcwd()
sys.path.insert(0, cwd)
sys.path.insert(0, os.path.join(cwd, 'aiagentplatform'))  # Your Django project folder


# ==============================================================================
# STEP 3: Load environment variables from .env file
# ==============================================================================
# Your project uses django-environ, so we'll load it here
from pathlib import Path
import environ

# Initialize environ
env = environ.Env(DEBUG=(bool, False))

# Read .env file
env_file = Path(cwd) / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))


# ==============================================================================
# STEP 4: Set Django settings module
# ==============================================================================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiagentplatform.settings')


# ==============================================================================
# STEP 5: Get the Django WSGI application
# ==============================================================================
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()