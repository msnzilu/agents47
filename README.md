# Agents 47 MVP

A web-based platform for creating, customizing, and deploying intelligent AI agents for business use cases including customer support, research, automation, scheduling, knowledge management, and sales.

## 🚀 Phase 1: Foundation & Authentication - COMPLETE

Phase 1 establishes the project infrastructure, authentication system, and basic data models.

### ✅ Deliverables Completed

- ✅ Project setup with Django 5.x
- ✅ PostgreSQL 16+ with pgvector extension
- ✅ Docker Compose for local development
- ✅ Custom User model with email-based authentication
- ✅ Registration, login, logout, password reset
- ✅ Dashboard with user statistics
- ✅ Profile management
- ✅ Core models (User, Agent, Conversation, Message)
- ✅ Comprehensive test suite
- ✅ Django Admin customization

## 📋 Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Docker & Docker Compose (recommended)

## 🛠️ Local Setup

### Option 1: Docker (Recommended)

1. **Clone the repository**
```bash
git clone <repository-url>
cd ai_agent_platform
```

2. **Create environment file**
```bash
cp .env.example .env
```

3. **Edit `.env` file** with your configuration:
```bash
# Required for AI features (Phase 3+)
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

4. **Start services with Docker Compose**
```bash
docker-compose up -d
```

5. **Run migrations**
```bash
docker-compose exec web python manage.py migrate
```

6. **Create superuser**
```bash
docker-compose exec web python manage.py createsuperuser
```

7. **Seed sample data** (optional)
```bash
docker-compose exec web python manage.py seed_data
```

8. **Access the application**
- Web Interface: http://localhost:8000
- Admin Panel: http://localhost:8000/admin
- Test credentials (if seeded):
  - Admin: `admin@example.com` / `admin123`
  - User: `test@example.com` / `test123`

### Option 2: Manual Setup

1. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Setup PostgreSQL**
```bash
# Create database
createdb ai_agent_platform

# Enable pgvector extension
psql ai_agent_platform -c "CREATE EXTENSION vector;"
```

4. **Setup Redis**
```bash
# Start Redis server
redis-server
```

5. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

6. **Run migrations**
```bash
python manage.py migrate
```

7. **Create superuser**
```bash
python manage.py createsuperuser
```

8. **Collect static files**
```bash
python manage.py collectstatic --noinput
```

9. **Run development server**
```bash
python manage.py runserver
```

10. **In separate terminals, start Celery and Channels**
```bash
# Terminal 2: Celery worker
celery -A ai_agent_platform worker -l info

# Terminal 3: Daphne (ASGI server for WebSockets)
daphne -b 0.0.0.0 -p 8000 ai_agent_platform.asgi:application
```

## 🧪 Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=. --cov-report=html
```

### Run specific test file
```bash
pytest users/tests/test_authentication.py
```

### Run specific test class
```bash
pytest users/tests/test_authentication.py::TestUserRegistration
```

### Run tests in Docker
```bash
docker-compose exec web pytest
```

## 📊 Project Structure

```
ai_agent_platform/
├── ai_agent_platform/          # Main project settings
│   ├── settings.py             # Django settings
│   ├── urls.py                 # URL configuration
│   ├── asgi.py                 # ASGI config for WebSockets
│   ├── celery.py               # Celery configuration
│   └── wsgi.py                 # WSGI config
├── users/                      # User authentication & profiles
│   ├── models.py               # CustomUser model
│   ├── forms.py                # Authentication forms
│   ├── views.py                # Auth & dashboard views
│   ├── admin.py                # Admin customization
│   ├── management/commands/    # Management commands
│   └── tests/                  # User tests
├── agents/                     # Agent management (Phase 2+)
│   ├── models.py               # Agent, KnowledgeBase models
│   └── admin.py
├── chat/                       # Chat & conversations (Phase 3-4)
│   ├── models.py               # Conversation, Message models
│   ├── consumers.py            # WebSocket consumers
│   └── routing.py              # WebSocket routing
├── integrations/               # External integrations (Phase 7)
│   └── models.py
├── analytics/                  # Usage analytics (Phase 8)
│   └── models.py
├── templates/                  # Shared templates
│   ├── base.html               # Base template
│   ├── home.html               # Landing page
│   └── users/                  # User templates
│       ├── register.html
│       ├── login.html
│       └── dashboard.html
├── static/                     # Static files
│   └── js/
│       └── widget.js           # Chat widget (Phase 7)
├── tests/                      # Integration tests
│   └── test_setup.py
├── docker-compose.yml          # Docker services
├── Dockerfile                  # Docker image
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
└── README.md                   # This file
```

## 🎯 Phase 1 Success Criteria

- [x] All authentication tests pass (100% coverage)
- [x] Docker containers start without errors
- [x] Can create/login users via UI and Admin
- [x] Database migrations are reversible
- [x] pgvector extension loaded successfully

## 📝 Environment Variables

### Required
- `SECRET_KEY`: Django secret key (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string

### Optional (for later phases