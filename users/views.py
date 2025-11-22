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
from django.contrib.auth import login, authenticate
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, 
    CustomPasswordResetForm, UserProfileForm, CustomAuthenticationForm, TwoFactorVerifyForm
)
from django.utils.decorators import method_decorator
from security.models import LoginAttempt
from django.views import View
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


# class CustomLoginView(LoginView):
#     """
#     Custom login view using email.
#     """
#     template_name = 'users/auth/login.html'
#     form_class = CustomAuthenticationForm
#     redirect_authenticated_user = True
    
#     def get_success_url(self):
#         """Redirect to dashboard after login."""
#         return reverse_lazy('users:dashboard')
    
#     def form_valid(self, form):
#         """Handle successful login."""
#         messages.success(self.request, f'Welcome back, {form.get_user().get_display_name()}!')
#         return super().form_valid(form)
    
#     def form_invalid(self, form):
#         """Handle invalid login."""
#         messages.error(self.request, 'Invalid email or password.')
#         return super().form_invalid(form)

class CustomLoginView(LoginView):
    """
    Custom login view with 2FA support and attempt tracking.
    """
    template_name = 'users/auth/login.html'
    form_class = CustomAuthenticationForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        """Redirect to dashboard after login."""
        return reverse_lazy('users:dashboard')
    
    def get_client_ip(self):
        """Get client IP address."""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    def form_valid(self, form):
        """Handle successful login - check if 2FA is enabled."""
        user = form.get_user()
        email = user.email
        ip_address = self.get_client_ip()
        user_agent = self.request.META.get('HTTP_USER_AGENT', '')[:255]
        
        # Check if account is locked
        if LoginAttempt.is_account_locked(email):
            LoginAttempt.record_attempt(
                email=email,
                ip_address=ip_address,
                success=False,
                user_agent=user_agent,
                failure_reason='Account locked'
            )
            messages.error(
                self.request,
                'Account temporarily locked due to multiple failed login attempts. '
                'Please try again later or reset your password.'
            )
            return redirect('users:login')
        
        # Check if user has 2FA enabled
        if hasattr(user, 'two_factor_auth') and user.two_factor_auth.is_enabled:
            # Store user info in session for 2FA verification
            self.request.session['pre_2fa_user_id'] = user.id
            self.request.session['pre_2fa_user_email'] = email
            self.request.session['pre_2fa_backend'] = user.backend
            self.request.session['pre_2fa_ip'] = ip_address
            self.request.session['pre_2fa_user_agent'] = user_agent
            
            # Redirect to 2FA verification page
            return redirect('users:login_2fa_verify')
        
        # No 2FA - record successful login and complete
        LoginAttempt.record_attempt(
            email=email,
            ip_address=ip_address,
            success=True,
            user_agent=user_agent
        )
        
        messages.success(self.request, f'Welcome back, {user.get_display_name()}!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """Handle invalid login."""
        email = form.data.get('username', '')  # username field contains email
        if email:
            ip_address = self.get_client_ip()
            user_agent = self.request.META.get('HTTP_USER_AGENT', '')[:255]
            
            LoginAttempt.record_attempt(
                email=email,
                ip_address=ip_address,
                success=False,
                user_agent=user_agent,
                failure_reason='Invalid credentials'
            )
            
            # Check if account should be locked
            if LoginAttempt.is_account_locked(email):
                messages.error(
                    self.request,
                    'Too many failed login attempts. Your account has been temporarily locked. '
                    'Please try again in 30 minutes or reset your password.'
                )
            else:
                remaining = 5 - LoginAttempt.get_recent_failures(email)
                messages.error(
                    self.request,
                    f'Invalid email or password. {remaining} attempts remaining before lockout.'
                )
        else:
            messages.error(self.request, 'Invalid email or password.')
        
        return super().form_invalid(form)


@method_decorator(never_cache, name='dispatch')
class Login2FAVerifyView(View):
    """
    View to verify 2FA token during login.
    """
    template_name = 'users/auth/login_2fa_verify.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is already authenticated
        if request.user.is_authenticated:
            return redirect('users:dashboard')
        
        # Check if we have a pending 2FA verification
        if 'pre_2fa_user_id' not in request.session:
            messages.error(request, 'Invalid 2FA verification session.')
            return redirect('users:login')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        from .forms import TwoFactorVerifyForm
        form = TwoFactorVerifyForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        from .forms import TwoFactorVerifyForm
        from django.contrib.auth import get_user_model
        
        form = TwoFactorVerifyForm(request.POST)
        
        if not form.is_valid():
            messages.error(request, 'Please enter a valid verification code.')
            return render(request, self.template_name, {'form': form})
        
        # Get the user from session
        User = get_user_model()
        user_id = request.session.get('pre_2fa_user_id')
        email = request.session.get('pre_2fa_user_email')
        ip_address = request.session.get('pre_2fa_ip')
        user_agent = request.session.get('pre_2fa_user_agent', '')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, 'Invalid verification session.')
            return redirect('users:login')
        
        # Verify the token
        token = form.cleaned_data['token']
        use_backup = form.cleaned_data.get('use_backup', False)
        
        if use_backup:
            # Verify backup code
            is_valid = user.two_factor_auth.verify_backup_code(token)
            code_type = 'backup code'
        else:
            # Verify TOTP token
            is_valid = user.two_factor_auth.verify_token(token)
            code_type = '2FA token'
        
        if not is_valid:
            # Record failed 2FA attempt
            LoginAttempt.record_attempt(
                email=email,
                ip_address=ip_address,
                success=False,
                user_agent=user_agent,
                failure_reason=f'Invalid {code_type}'
            )
            
            messages.error(request, 'Invalid verification code. Please try again.')
            return render(request, self.template_name, {'form': form})
        
        # Token is valid - record successful login
        LoginAttempt.record_attempt(
            email=email,
            ip_address=ip_address,
            success=True,
            user_agent=user_agent
        )
        
        # Complete the login
        backend = request.session.get('pre_2fa_backend')
        user.backend = backend
        login(request, user)
        
        # Clean up session
        for key in ['pre_2fa_user_id', 'pre_2fa_user_email', 'pre_2fa_backend', 
                    'pre_2fa_ip', 'pre_2fa_user_agent']:
            request.session.pop(key, None)
        
        if use_backup:
            messages.warning(
                request,
                'Backup code used successfully. You have fewer backup codes remaining.'
            )
        
        messages.success(request, f'Welcome back, {user.get_display_name()}!')
        return redirect('users:dashboard')


@require_POST
def login_2fa_cancel(request):
    """Cancel 2FA verification and return to login."""
    if 'pre_2fa_user_id' in request.session:
        del request.session['pre_2fa_user_id']
    if 'pre_2fa_backend' in request.session:
        del request.session['pre_2fa_backend']
    
    messages.info(request, 'Login cancelled.')
    return redirect('users:login')


@login_required
def custom_logout(request):
    """
    Custom logout view that handles both GET and POST requests.
    """
    if request.user.is_authenticated:
        messages.success(request, 'You have been logged out successfully.')
        logout(request)
    
    return redirect('home') 



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
        show_2fa_alert = not (
            hasattr(self.request.user, 'two_factor_auth') and 
            self.request.user.two_factor_auth.is_enabled
        )
        
        # Get agents by use case
        use_case_breakdown = Agent.objects.filter(user=user).values(
            'use_case'
        ).annotate(count=Count('id')).order_by('-count')
        
        context.update({
            'agents': agents,
            'show_2fa_alert':show_2fa_alert,
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