# Utility functions
def generate_session_id():
    """Generate unique session ID for anonymous users"""
    import uuid
    return str(uuid.uuid4())


def trigger_agent_response(message_id):
    """
    Celery task to trigger agent response
    This would be in tasks.py
    """
    pass  # Implement based on your agent system