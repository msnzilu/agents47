# Project Overview: Agents47

## 1. Project Purpose
Agents47 is a web-based platform for creating and managing intelligent AI agents designed to automate business tasks. It allows users to build customizable agents for customer support, research, automation, and more, with capabilities for RAG (Retrieval-Augmented Generation) and multi-agent orchestration.

## 2. Technology Stack
- **Backend Framework**: Django 5.2.7
- **API Framework**: Django REST Framework (DRF)
- **Database**: PostgreSQL with `pgvector` extension (for vector embeddings)
- **Asynchronous Tasks**: Celery + Redis
- **AI/ML**: 
  - OpenAI, Anthropic (LLM Providers)
  - LangChain (Orchestration framework)
  - `pgvector` (Vector storage)
- **Frontend**: Server-side rendered Django Templates (HTML/CSS/JS)
- **Documentation**: `drf-spectacular` (Swagger/Redoc)

## 3. Architecture

### Directory Structure
- **`aiagentplatform/`**: Main project configuration (`settings.py`, `urls.py`).
- **`agents/`**: Core logic for Agent definition, configuration, and RAG (`Agent`, `KnowledgeBase`, `DocumentChunk` models).
- **`chat/`**: Handling conversations and messaging.
- **`api/`**: REST API endpoints (`/api/agents/`, `/api/conversations/`).
- **`users/`**: User management and authentication.
- **`integrations/`, `webhooks/`**: External connectivity.
- **`templates/`**: HTML templates for the UI.
- **`static/`**: Static assets (CSS, JS, Images).

### Key Components
1.  **Agent Engine**:
    -   Supports multiple use cases (Support, Research, Automation).
    -   Configurable prompts and LLM settings.
    -   **RAG**: `KnowledgeBase` model handles document ingestion, chunking, and embedding.
    -   **Orchestration**: `AgentOrchestration` allows defining multi-agent workflows (Sequential, Parallel, etc.).

2.  **API Layer**:
    -   Exposes endpoints for managing agents and conversations.
    -   Includes auto-generated documentation at `/api/docs/` and `/api/redoc/`.

3.  **Background Processing**:
    -   Celery is used for long-running tasks, likely including document processing (embedding generation) and agent execution.

4.  **Frontend**:
    -   Traditional Django Template-based UI.
    -   `users/home.html` serves as the landing page.

## 4. Configuration
-   **Environment Variables**: Managed via `.env` (using `django-environ`).
-   **Settings**: `aiagentplatform/settings.py` configures installed apps, middleware, database, and API keys.

## 5. Observations
-   The project is well-structured with a clear separation of concerns (apps).
-   It uses modern Django features and best practices (e.g., `pathlib`, `environ`).
-   The inclusion of `pgvector` indicates a native approach to vector search within Postgres, avoiding external vector DBs.
-   The `AgentOrchestration` model suggests advanced capabilities for complex workflows beyond simple chat.
