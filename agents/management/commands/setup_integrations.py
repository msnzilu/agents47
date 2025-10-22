# agents/management/commands/setup_integrations.py
from django.core.management.base import BaseCommand
from agents.models import Agent
from integrations.models import Integration

class Command(BaseCommand):
    help = 'Set up LLM integrations for agents'

    def add_arguments(self, parser):
        parser.add_argument('--agent-id', type=int, help='ID of the agent to set up integrations for')
        parser.add_argument('--openai-key', type=str, help='OpenAI API key')
        parser.add_argument('--anthropic-key', type=str, help='Anthropic API key')

    def handle(self, *args, **options):
        agent_id = options.get('agent_id')
        openai_key = options.get('openai_key')
        anthropic_key = options.get('anthropic_key')

        if not (openai_key and anthropic_key):
            self.stdout.write(self.style.ERROR('Both --openai-key and --anthropic-key are required'))
            return

        try:
            if agent_id:
                agents = [Agent.objects.get(id=agent_id)]
            else:
                agents = Agent.objects.all()

            for agent in agents:
                # Create OpenAI integration
                Integration.objects.create(
                    agent=agent,
                    name="OpenAI GPT-4o-mini",
                    integration_type="openai",
                    config={"api_key": openai_key},
                    status="active"
                )
                self.stdout.write(self.style.SUCCESS(f'Created OpenAI integration for agent {agent.name}'))

                # Create Anthropic integration
                Integration.objects.create(
                    agent=agent,
                    name="Anthropic Claude",
                    integration_type="anthropic",
                    config={"api_key": anthropic_key},
                    status="active"
                )
                self.stdout.write(self.style.SUCCESS(f'Created Anthropic integration for agent {agent.name}'))

        except Agent.DoesNotExist:
            self.stdout.write(self.style.ERROR('Agent not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error setting up integrations: {str(e)}'))