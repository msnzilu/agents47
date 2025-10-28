import imaplib
import email
from email.header import decode_header
from django.conf import settings
from chat.models import Conversation, Message
from agents.models import Agent
import logging

logger = logging.getLogger(__name__)

class EmailHandler:
    """Handle incoming emails via IMAP"""
    
    def __init__(self, agent: Agent):
        self.agent = agent
        self.integration = agent.integrations.filter(
            integration_type='email',
            is_active=True
        ).first()
        
        if not self.integration:
            raise ValueError("No active email integration found")
    
    def connect(self):
        """Connect to IMAP server"""
        settings = self.integration.settings
        
        imap = imaplib.IMAP4_SSL(
            settings['imap_server'],
            settings.get('imap_port', 993)
        )
        
        imap.login(
            settings['email'],
            settings['password']
        )
        
        return imap
    
    def fetch_new_messages(self):
        """Fetch unread messages from inbox"""
        imap = self.connect()
        
        try:
            imap.select('INBOX')
            
            # Search for unread messages
            _, message_numbers = imap.search(None, 'UNSEEN')
            
            for num in message_numbers[0].split():
                _, msg_data = imap.fetch(num, '(RFC822)')
                
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Process email
                self.process_email(email_message)
                
                # Mark as read
                imap.store(num, '+FLAGS', '\\Seen')
        
        finally:
            imap.close()
            imap.logout()
    
    def process_email(self, email_message):
        """Process incoming email and create conversation"""
        from_email = email_message['From']
        subject = email_message['Subject']
        
        # Get email body
        body = self.get_email_body(email_message)
        
        # Get or create conversation
        conversation, created = Conversation.objects.get_or_create(
            agent=self.agent,
            channel='email',
            channel_identifier=from_email,
            defaults={'title': subject or 'Email conversation'}
        )
        
        # Create message
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=body,
            metadata={
                'from': from_email,
                'subject': subject
            }
        )
        
        # Trigger agent response
        from chat.tasks import trigger_agent_response
        trigger_agent_response.delay(conversation.id, body)
        
        logger.info(f"Processed email from {from_email}")
    
    def get_email_body(self, email_message):
        """Extract body from email message"""
        body = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = email_message.get_payload(decode=True).decode()
        
        return body