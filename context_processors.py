from django.conf import settings

def site_context(request):
    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_DOMAIN': settings.SITE_DOMAIN
    }