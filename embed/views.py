"""
Embeddable Widget Views
Phase 7: Integration Layer
"""
from django.shortcuts import render, get_object_or_404
from django.views.decorators.clickjacking import xframe_options_exempt
from django.http import HttpResponse
from django.template.loader import render_to_string
from agents.models import Agent


@xframe_options_exempt
def chat_widget(request, agent_id):
    """
    Embeddable chat widget iframe page
    
    Query parameters:
    - theme: 'light' or 'dark' (default: 'light')
    - color: Primary color hex code (default: '#4F46E5')
    """
    agent = get_object_or_404(Agent, id=agent_id, is_active=True)
    
    context = {
        'agent': agent,
        'theme': request.GET.get('theme', 'light'),
        'primary_color': request.GET.get('color', '#4F46E5'),
    }
    
    return render(request, 'users/embed/chat_widget.html', context)


def widget_loader(request, agent_id):
    """
    Widget loader JavaScript file
    
    This generates a JavaScript file that can be embedded on any website
    to load the chat widget.
    
    Usage:
    <script src="https://yourdomain.com/embed/loader/{agent_id}/" async></script>
    <script>
      window.AIAgentWidget = {
        agentId: '{agent_id}',
        theme: 'light',
        primaryColor: '#4F46E5',
        position: 'right',
        greeting: 'Hi! Need help?'
      };
    </script>
    """
    agent = get_object_or_404(Agent, id=agent_id, is_active=True)
    
    context = {
        'agent': agent,
        'request': request,
    }
    
    js_content = render_to_string('users/embed/widget_loader.js', context)
    
    response = HttpResponse(js_content, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
    return response


def widget_demo(request, agent_id):
    """
    Demo page showing how to embed the widget
    """
    agent = get_object_or_404(Agent, id=agent_id, is_active=True)
    
    # Generate embed code
    base_url = f"{request.scheme}://{request.get_host()}"
    
    basic_embed = f'''<script src="{base_url}/embed/loader/{agent_id}/" async></script>'''
    
    custom_embed = f'''<script src="{base_url}/embed/loader/{agent_id}/" async></script>
<script>
  window.AIAgentWidget = {{
    agentId: '{agent_id}',
    theme: 'light',              // 'light' or 'dark'
    primaryColor: '#4F46E5',     // Any hex color
    position: 'right',           // 'left' or 'right'
    greeting: 'Hi! Need help?'   // Custom greeting message
  }};
</script>'''
    
    context = {
        'agent': agent,
        'basic_embed': basic_embed,
        'custom_embed': custom_embed,
        'base_url': base_url,
    }
    
    return render(request, 'users/embed/widget_demo.html', context)