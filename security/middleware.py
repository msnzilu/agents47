"""
security/middleware.py
Complete middleware for Security & Compliance (Phase 9)
"""
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import logout
import time
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# RATE LIMITING
# =============================================================================

class RateLimiter:
    """Rate limiting implementation using in-memory storage"""
    
    def __init__(self, name: str, limit: int, period: int):
        """
        Initialize rate limiter
        
        Args:
            name: Identifier for this rate limiter
            limit: Maximum number of requests
            period: Time period in seconds
        """
        self.name = name
        self.limit = limit
        self.period = period
        self._requests = {}  # In production, use Redis
    
    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """
        Check if request is allowed
        
        Returns:
            (is_allowed, info_dict)
        """
        now = time.time()
        key = f"{self.name}:{identifier}"
        
        # Clean old requests
        if key in self._requests:
            self._requests[key] = [
                req_time for req_time in self._requests[key]
                if now - req_time < self.period
            ]
        else:
            self._requests[key] = []
        
        # Check limit
        current_count = len(self._requests[key])
        
        if current_count >= self.limit:
            oldest_request = min(self._requests[key])
            retry_after = int(self.period - (now - oldest_request))
            
            return False, {
                'limit': self.limit,
                'remaining': 0,
                'reset': int(oldest_request + self.period),
                'retry_after': retry_after
            }
        
        # Allow request
        self._requests[key].append(now)
        
        return True, {
            'limit': self.limit,
            'remaining': self.limit - current_count - 1,
            'reset': int(now + self.period)
        }
    
    def reset(self, identifier: str):
        """Reset rate limit for identifier"""
        key = f"{self.name}:{identifier}"
        if key in self._requests:
            del self._requests[key]


# Rate limiter instances
API_RATE_LIMITER = RateLimiter('api', limit=100, period=3600)  # 100/hour
USER_ACTION_LIMITER = RateLimiter('user_action', limit=50, period=60)  # 50/min
IP_RATE_LIMITER = RateLimiter('ip', limit=1000, period=3600)  # 1000/hour


def rate_limit(limit: int = 100, period: int = 3600):
    """
    Decorator for rate limiting views
    
    Usage:
        @rate_limit(limit=50, period=3600)
        def my_view(request):
            pass
    """
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            # Create rate limiter for this view
            limiter = RateLimiter(
                name=f"view_{view_func.__name__}",
                limit=limit,
                period=period
            )
            
            # Get identifier (user or IP)
            if request.user.is_authenticated:
                identifier = f"user_{request.user.id}"
            else:
                identifier = f"ip_{get_client_ip(request)}"
            
            # Check rate limit
            is_allowed, info = limiter.is_allowed(identifier)
            
            if not is_allowed:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'retry_after': info['retry_after']
                }, status=429)
            
            # Add rate limit headers to response
            response = view_func(request, *args, **kwargs)
            response['X-RateLimit-Limit'] = str(info['limit'])
            response['X-RateLimit-Remaining'] = str(info['remaining'])
            response['X-RateLimit-Reset'] = str(info['reset'])
            
            return response
        
        return wrapped_view
    return decorator


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip


# =============================================================================
# RATE LIMIT MIDDLEWARE
# =============================================================================

class RateLimitMiddleware:
    """Middleware to enforce rate limiting on API endpoints"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to API endpoints
        if request.path.startswith('/api/'):
            # Get identifier
            if request.user.is_authenticated:
                identifier = f"user_{request.user.id}"
                limiter = API_RATE_LIMITER
            else:
                identifier = f"ip_{get_client_ip(request)}"
                limiter = IP_RATE_LIMITER
            
            # Check rate limit
            is_allowed, info = limiter.is_allowed(identifier)
            
            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for {identifier} on {request.path}"
                )
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'retry_after': info['retry_after']
                }, status=429)
            
            # Process request
            response = self.get_response(request)
            
            # Add rate limit headers
            response['X-RateLimit-Limit'] = str(info['limit'])
            response['X-RateLimit-Remaining'] = str(info['remaining'])
            response['X-RateLimit-Reset'] = str(info['reset'])
            
            return response
        
        return self.get_response(request)


# =============================================================================
# SECURITY HEADERS MIDDLEWARE
# =============================================================================

class SecurityHeadersMiddleware:
    """Add security headers to all responses"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Content Security Policy
        csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdn.tailwindcss.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https://cdn.jsdelivr.net; "
        "connect-src 'self' https://api.openai.com https://api.anthropic.com; "
        "frame-ancestors 'none'; "
    )
        response['Content-Security-Policy'] = csp
        
        # Other security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # HSTS (only in production)
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response


# =============================================================================
# SESSION TIMEOUT MIDDLEWARE
# =============================================================================

class SessionTimeoutMiddleware:
    """Enforce session timeout for security"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, 'SESSION_TIMEOUT_MINUTES', 30) * 60
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Check last activity
            last_activity = request.session.get('last_activity')
            
            if last_activity:
                idle_time = timezone.now().timestamp() - last_activity
                
                if idle_time > self.timeout:
                    # Session expired
                    logout(request)
                    
                    # Redirect to login with message
                    from django.contrib import messages
                    from django.shortcuts import redirect
                    messages.warning(
                        request,
                        "Your session has expired due to inactivity. Please log in again."
                    )
                    
                    # For API requests, return JSON
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Session expired',
                            'code': 'session_expired'
                        }, status=401)
            
            # Update last activity
            request.session['last_activity'] = timezone.now().timestamp()
        
        return self.get_response(request)


# =============================================================================
# CSRF TOKEN ROTATION MIDDLEWARE
# =============================================================================

class CSRFTokenRotationMiddleware:
    """Rotate CSRF tokens periodically for security"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rotation_period = 3600  # 1 hour
    
    def __call__(self, request):
        if request.user.is_authenticated:
            last_rotation = request.session.get('csrf_token_rotation')
            
            if not last_rotation or (timezone.now().timestamp() - last_rotation) > self.rotation_period:
                # Rotate CSRF token
                from django.middleware.csrf import rotate_token
                rotate_token(request)
                request.session['csrf_token_rotation'] = timezone.now().timestamp()
        
        return self.get_response(request)


# =============================================================================
# REQUEST LOGGING MIDDLEWARE
# =============================================================================

class RequestLoggingMiddleware:
    """Log all requests for security auditing"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Log request
        logger.info(
            f"{request.method} {request.path} "
            f"from {get_client_ip(request)} "
            f"by {request.user if request.user.is_authenticated else 'anonymous'}"
        )
        
        response = self.get_response(request)
        
        # Log response status
        if response.status_code >= 400:
            logger.warning(
                f"Request failed: {request.method} {request.path} "
                f"returned {response.status_code}"
            )
        
        return response


# =============================================================================
# IP WHITELIST MIDDLEWARE (Optional)
# =============================================================================

class IPWhitelistMiddleware:
    """Restrict access to whitelisted IPs (for admin endpoints)"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.whitelist = getattr(settings, 'IP_WHITELIST', [])
    
    def __call__(self, request):
        # Only check admin endpoints
        if request.path.startswith('/admin/'):
            client_ip = get_client_ip(request)
            
            if self.whitelist and client_ip not in self.whitelist:
                logger.warning(
                    f"Blocked admin access from non-whitelisted IP: {client_ip}"
                )
                return JsonResponse({
                    'error': 'Access denied'
                }, status=403)
        
        return self.get_response(request)