from django.contrib.contenttypes.models import ContentType

from .models import ActionLog


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_action(request, action, obj=None, message='', metadata=None):
    actor = None
    if request is not None and getattr(request, 'user', None) and request.user.is_authenticated:
        actor = request.user

    content_type = None
    object_id = ''
    object_repr = ''
    if obj is not None:
        content_type = ContentType.objects.get_for_model(obj, for_concrete_model=False)
        object_id = str(getattr(obj, 'pk', '') or '')
        object_repr = str(obj)[:500]

    return ActionLog.objects.create(
        actor=actor,
        action=action,
        content_type=content_type,
        object_id=object_id,
        object_repr=object_repr,
        message=message,
        metadata=metadata or {},
        ip_address=get_client_ip(request) if request is not None else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request is not None else '',
    )
