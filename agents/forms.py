"""
Agent forms for creation and editing.
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Agent


class AgentBasicForm(forms.ModelForm):
    """
    Step 1: Basic agent information (name, description, use case).
    """
    
    class Meta:
        model = Agent
        fields = ['name', 'description', 'use_case']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'e.g., Customer Support Bot',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Describe what this agent does...',
                'rows': 4,
            }),
            'use_case': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            }),
        }
    
    def clean_name(self):
        """Validate agent name."""
        name = self.cleaned_data.get('name')
        if len(name) < 3:
            raise ValidationError('Agent name must be at least 3 characters long.')
        return name


class AgentConfigForm(forms.ModelForm):
    """
    Step 2: AI configuration (prompt, model settings).
    """
    
    # Add custom fields for easier configuration
    provider = forms.ChoiceField(
        choices=[
            ('openai', 'OpenAI'),
            ('anthropic', 'Anthropic (Claude)'),
        ],
        initial='openai',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        })
    )
    
    model = forms.ChoiceField(
        choices=[
            ('gpt-4o-mini', 'GPT-4o Mini (Fast & Cheap)'),
            ('gpt-4o', 'GPT-4o (Most Capable)'),
            ('claude-3.5-sonnet', 'Claude 3.5 Sonnet'),
        ],
        initial='gpt-4o-mini',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        })
    )
    
    temperature = forms.FloatField(
        min_value=0.0,
        max_value=2.0,
        initial=0.7,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'step': '0.1',
        }),
        help_text='Lower = more focused, Higher = more creative (0.0 - 2.0)'
    )
    
    max_tokens = forms.IntegerField(
        min_value=100,
        max_value=4000,
        initial=1000,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        }),
        help_text='Maximum length of response'
    )
    
    class Meta:
        model = Agent
        fields = ['prompt_template']
        widgets = {
            'prompt_template': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm',
                'placeholder': 'You are a helpful assistant that...',
                'rows': 8,
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load existing config if editing
        if self.instance and self.instance.pk:
            config = self.instance.config_json or {}
            self.fields['provider'].initial = config.get('provider', 'openai')
            self.fields['model'].initial = config.get('model', 'gpt-4o-mini')
            self.fields['temperature'].initial = config.get('temperature', 0.7)
            self.fields['max_tokens'].initial = config.get('max_tokens', 1000)
    
    def save(self, commit=True):
        """Save config fields to config_json."""
        instance = super().save(commit=False)
        
        # Build config_json from form fields
        instance.config_json = {
            'provider': self.cleaned_data['provider'],
            'model': self.cleaned_data['model'],
            'temperature': self.cleaned_data['temperature'],
            'max_tokens': self.cleaned_data['max_tokens'],
            'tools_enabled': True,
        }
        
        if commit:
            instance.save()
        
        return instance


class AgentCreateForm(forms.ModelForm):
    """
    Single-page form for quick agent creation.
    Combines basic info and simple config.
    """
    
    class Meta:
        model = Agent
        fields = ['name', 'description', 'use_case', 'prompt_template']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'e.g., Customer Support Bot',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Describe what this agent does...',
                'rows': 3,
            }),
            'use_case': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            }),
            'prompt_template': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm',
                'placeholder': 'You are a helpful assistant that...',
                'rows': 6,
            }),
        }
    
    def clean_name(self):
        """Validate agent name."""
        name = self.cleaned_data.get('name')
        if len(name) < 3:
            raise ValidationError('Agent name must be at least 3 characters long.')
        return name
    
    def save(self, commit=True):
        """Set default config on creation."""
        instance = super().save(commit=False)
        
        # Set default config based on use case
        if not instance.config_json:
            instance.config_json = {
                'provider': 'openai',
                'model': 'gpt-4o-mini',
                'temperature': 0.7,
                'max_tokens': 1000,
                'tools_enabled': True,
            }
        
        if commit:
            instance.save()
        
        return instance


class AgentUpdateForm(forms.ModelForm):
    """
    Form for updating existing agents.
    """
    
    class Meta:
        model = Agent
        fields = ['name', 'description', 'use_case', 'prompt_template', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'rows': 4,
            }),
            'use_case': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            }),
            'prompt_template': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm',
                'rows': 8,
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded',
            }),
        }


class AgentCloneForm(forms.Form):
    """
    Form for cloning an agent with a new name.
    """
    new_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter new agent name',
        })
    )
    
    include_knowledge = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded',
        }),
        label='Clone knowledge base as well',
        help_text='Copy all documents and embeddings to the new agent'
    )