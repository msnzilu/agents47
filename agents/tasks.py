"""
Celery tasks for async knowledge base processing.
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_knowledge_base_task(self, knowledge_base_id: int):
    """
    Async task to process knowledge base document.
    """
    from .services import KnowledgeBaseService
    
    try:
        KnowledgeBaseService.process_document(knowledge_base_id)
        return {'status': 'success', 'knowledge_base_id': knowledge_base_id}
    except Exception as e:
        logger.error(f"Task failed for KB {knowledge_base_id}: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))