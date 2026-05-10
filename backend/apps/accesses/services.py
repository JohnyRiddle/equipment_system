from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.utils import timezone

from cryptography.fernet import Fernet, MultiFernet

from .models import AccessChangeLog, AccessSecretViewLog


def _get_fernet():
    keys = getattr(settings, 'ACCESS_SECRET_KEYS', [])
    if not keys:
        raise ImproperlyConfigured('ACCESS_SECRET_KEYS is required to manage access secrets.')
    return MultiFernet([Fernet(key.encode()) for key in keys])


def encrypt_secret(raw_value):
    if raw_value is None or raw_value == '':
        raise ValueError('Secret value cannot be empty.')
    return _get_fernet().encrypt(raw_value.encode('utf-8')).decode('utf-8')


def decrypt_secret(encrypted_value):
    return _get_fernet().decrypt(encrypted_value.encode('utf-8')).decode('utf-8')


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_secret_view(secret, user, request, result, reason=''):
    return AccessSecretViewLog.objects.create(
        access=secret.access,
        secret=secret,
        user=user if getattr(user, 'is_authenticated', False) else None,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        result=result,
        reason=reason,
    )


def log_access_change(access, user, action, secret=None, metadata=None):
    return AccessChangeLog.objects.create(
        access=access,
        secret=secret,
        user=user if getattr(user, 'is_authenticated', False) else None,
        action=action,
        metadata=metadata or {},
    )


def reveal_access_secret(secret, user, request, allowed):
    if not allowed:
        log_secret_view(secret, user, request, 'denied', 'User has no secret access permission.')
        raise PermissionDenied

    value = decrypt_secret(secret.encrypted_value)
    log_secret_view(secret, user, request, 'allowed')
    secret.access.last_secret_viewed_at = timezone.now()
    secret.access.save(update_fields=['last_secret_viewed_at', 'updated_at'])
    return value
