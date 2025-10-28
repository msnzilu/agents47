"""
User views for authentication and profile management.
Phase 1: Foundation & Authentication
"""
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordResetView, 
    PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
)
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, TemplateView
from django.db.models import Count, Q
from django.utils import timezone
from django.conf import settings
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, 
    CustomPasswordResetForm, UserProfileForm
)

User = get_user_model()

def contact_view(request):
    """Display the contact page"""
    return render(request, 'users/legal/contact.html')

@require_POST
def contact_submit(request):
    """Handle contact form submission"""
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    subject = request.POST.get('subject', '').strip()
    message = request.POST.get('message', '').strip()
    
    # Validation
    if not all([name, email, subject, message]):
        html = '''
            <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                <p class="font-medium">✗ All fields are required</p>
            </div>
        '''
        return JsonResponse({'success': False, 'html': html}, status=400)
    
    if len(message) < 10:
        html = '''
            <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                <p class="font-medium">✗ Message must be at least 10 characters</p>
            </div>
        '''
        return JsonResponse({'success': False, 'html': html}, status=400)
    
    # Send email
    try:
        email_subject = f"Contact Form: {subject} - {name}"
        email_body = f"""
New Contact Form Submission

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}
        """
        
        send_mail(
            email_subject,
            email_body,
            settings.DEFAULT_FROM_EMAIL,
            ['support@yourplatform.com'],  # Replace with your email
            fail_silently=False,
        )
        
        # Return success message
        html = '''
            <div class="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
                <p class="font-medium">✓ Message sent successfully!</p>
                <p class="text-sm mt-1">We'll get back to you within 24 hours.</p>
            </div>
        '''
        return JsonResponse({'success': True, 'html': html})
        
    except Exception as e:
        html = '''
            <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                <p class="font-medium">✗ Error sending message</p>
                <p class="text-sm mt-1">Please try again or email us directly at support@yourplatform.com</p>
            </div>
        '''
        return JsonResponse({'success': False, 'html': html}, status=500)


class RegisterView(CreateView):
    """
    User registration view.
    """
    template_name = 'users/auth/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('users:login')
    
    def dispatch(self, request, *args, **kwargs):
        # Redirect authenticated users to dashboard
        if request.user.is_authenticated:
            return redirect('users:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Save user and log them in."""
        response = super().form_valid(form)
        # Auto-login after registration
        email = form.cleaned_data.get('email')
        password = form.cleaned_data.get('password1')
        user = authenticate(username=email, password=password)
        if user:
            login(self.request, user)
            messages.success(self.request, f'Account created successfully! Welcome to {settings.SITE_NAME}.')
            return redirect('users:dashboard')
        return response
    
    def form_invalid(self, form):
        """Handle invalid form submission."""
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class CustomLoginView(LoginView):
    """
    Custom login view using email.
    """
    template_name = 'users/auth/login.html'
    form_class = CustomAuthenticationForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        """Redirect to dashboard after login."""
        return reverse_lazy('users:dashboard')
    
    def form_valid(self, form):
        """Handle successful login."""
        messages.success(self.request, f'Welcome back, {form.get_user().get_display_name()}!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """Handle invalid login."""
        messages.error(self.request, 'Invalid email or password.')
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.success(request, 'You have been logged out successfully.')
        return super().dispatch(request, *args, **kwargs)



class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard view showing user's agents and statistics.
    """
    template_name = 'users/users/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user's agents with annotations
        from agents.models import Agent
        from chat.models import Conversation
        
        agents = Agent.objects.filter(user=user).annotate(
            conversation_count=Count('conversations', distinct=True)
        ).order_by('-created_at')[:5]  # Latest 5 agents
        
        # Get recent conversations
        recent_conversations = Conversation.objects.filter(
            agent__user=user
        ).select_related('agent').order_by('-updated_at')[:10]
        
        # Calculate statistics
        total_agents = Agent.objects.filter(user=user).count()
        total_conversations = Conversation.objects.filter(agent__user=user).count()
        
        # Get agents by use case
        use_case_breakdown = Agent.objects.filter(user=user).values(
            'use_case'
        ).annotate(count=Count('id')).order_by('-count')
        
        context.update({
            'agents': agents,
            'recent_conversations': recent_conversations,
            'total_agents': total_agents,
            'total_conversations': total_conversations,
            'use_case_breakdown': use_case_breakdown,
        })
        
        return context


class ProfileView(LoginRequiredMixin, UpdateView):
    """
    User profile view for updating account information.
    """
    template_name = 'users/users/profile.html'
    form_class = UserProfileForm
    success_url = reverse_lazy('users:profile')
    
    def get_object(self, queryset=None):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)


class CustomPasswordResetView(PasswordResetView):
    """
    Custom password reset view.
    """
    template_name = 'users/auth/password_reset.html'
    form_class = CustomPasswordResetForm
    success_url = reverse_lazy('users:password_reset_done')
    email_template_name = 'users/auth/password_reset_email.html'
    subject_template_name = 'users/auth/password_reset_subject.txt'
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            'Password reset email sent! Please check your inbox.'
        )
        return super().form_valid(form)


class CustomPasswordResetDoneView(PasswordResetDoneView):
    """
    Password reset done view.
    """
    template_name = 'users/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    Password reset confirm view.
    """
    template_name = 'users/auth/password_reset_confirm.html'
    success_url = reverse_lazy('users:password_reset_complete')
    
    def form_valid(self, form):
        messages.success(self.request, 'Your password has been reset successfully!')
        return super().form_valid(form)


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    """
    Password reset complete view.
    """
    template_name = 'users/auth/password_reset_complete.html'


@login_required
def delete_account(request):
    """
    View to handle account deletion.
    """
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, 'Your account has been deleted successfully.')
        return redirect('home')
    
    return render(request, 'users/users/delete_account_confirm.html')