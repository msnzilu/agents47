"""
Management command to seed database with sample data for development.
Usage: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from agents.models import Agent
from chat.models import Conversation, Message

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds database with sample data for development'
    
    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')
        
        # Create test users
        self.stdout.write('Creating users...')
        
        # Create superuser if doesn't exist
        if not User.objects.filter(email='admin@example.com').exists():
            admin = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123',
                first_name='Admin',
                last_name='User'
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Created admin user: admin@example.com'))
        else:
            admin = User.objects.get(email='admin@example.com')
            self.stdout.write('✓ Admin user already exists')
        
        # Create regular test user
        if not User.objects.filter(email='test@example.com').exists():
            test_user = User.objects.create_user(
                username='testuser',
                email='test@example.com',
                password='test123',
                first_name='Test',
                last_name='User',
                company='Test Company',
                terms_accepted=True
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Created test user: test@example.com'))
        else:
            test_user = User.objects.get(email='test@example.com')
            self.stdout.write('✓ Test user already exists')
        
        # Create sample agents
        self.stdout.write('\nCreating sample agents...')
        
        sample_agents = [
            {
                'name': 'Customer Support Bot',
                'description': 'Handles customer inquiries and support tickets with contextual responses.',
                'use_case': Agent.UseCase.SUPPORT,
                'prompt_template': 'You are a helpful customer support agent. Respond professionally and empathetically to customer inquiries.',
            },
            {
                'name': 'Research Assistant',
                'description': 'Helps with web research, data analysis, and report generation.',
                'use_case': Agent.UseCase.RESEARCH,
                'prompt_template': 'You are a research assistant. Provide thorough, well-sourced information and insights.',
            },
            {
                'name': 'Task Automation Agent',
                'description': 'Automates workflows, sends emails, and manages integrations.',
                'use_case': Agent.UseCase.AUTOMATION,
                'prompt_template': 'You are an automation assistant. Help users streamline their workflows efficiently.',
            },
            {
                'name': 'Meeting Scheduler',
                'description': 'Manages calendar, schedules meetings, and sends reminders.',
                'use_case': Agent.UseCase.SCHEDULING,
                'prompt_template': 'You are a scheduling assistant. Help manage calendars and coordinate meetings.',
            },
            {
                'name': 'Knowledge Base Expert',
                'description': 'Answers questions from internal documentation and policies.',
                'use_case': Agent.UseCase.KNOWLEDGE,
                'prompt_template': 'You are a knowledge management assistant. Provide accurate answers from the knowledge base.',
            },
        ]
        
        for agent_data in sample_agents:
            agent, created = Agent.objects.get_or_create(
                user=test_user,
                name=agent_data['name'],
                defaults=agent_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created agent: {agent.name}'))
            else:
                self.stdout.write(f'  ✓ Agent already exists: {agent.name}')
        
        # Create sample conversations
        self.stdout.write('\nCreating sample conversations...')
        
        support_agent = Agent.objects.filter(
            user=test_user,
            use_case=Agent.UseCase.SUPPORT
        ).first()
        
        if support_agent:
            conversation, created = Conversation.objects.get_or_create(
                agent=support_agent,
                title='Sample Support Conversation',
                defaults={'channel': 'web'}
            )
            
            if created:
                # Add sample messages
                Message.objects.create(
                    conversation=conversation,
                    role=Message.Role.USER,
                    content='Hi, I need help with my account.'
                )
                Message.objects.create(
                    conversation=conversation,
                    role=Message.Role.ASSISTANT,
                    content='Hello! I\'d be happy to help you with your account. What specific issue are you experiencing?'
                )
                Message.objects.create(
                    conversation=conversation,
                    role=Message.Role.USER,
                    content='I can\'t reset my password.'
                )
                Message.objects.create(
                    conversation=conversation,
                    role=Message.Role.ASSISTANT,
                    content='I can help you reset your password. Please check your email for a password reset link. If you don\'t receive it within a few minutes, let me know!'
                )
                
                self.stdout.write(self.style.SUCCESS('  ✓ Created sample conversation with messages'))
            else:
                self.stdout.write('  ✓ Sample conversation already exists')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Database seeded successfully!'))
        self.stdout.write('\nTest credentials:')
        self.stdout.write('  Admin: admin@example.com / admin123')
        self.stdout.write('  User:  test@example.com / test123')