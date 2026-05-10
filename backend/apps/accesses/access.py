from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from apps.dashboard.access import (
    EDIT_ACCESS_LEVELS,
    get_editable_legal_entity_ids,
    get_editable_location_ids,
    get_user_equipment_queryset,
    user_can_edit_scope,
    user_has_global_access,
)

from .models import EquipmentAccess


def get_user_access_queryset(user):
    queryset = EquipmentAccess.objects.select_related(
        'equipment',
        'legal_entity',
        'location',
        'cost_center',
        'access_type',
        'created_by',
        'updated_by',
    )
    if not getattr(user, 'can_view_accesses', True):
        return queryset.none()
    if user_has_global_access(user):
        return queryset

    allowed_equipment = get_user_equipment_queryset(user).values_list('id', flat=True)
    legal_entity_ids = user.legal_entity_accesses.filter(
        allow_all_locations=True,
    ).values_list('legal_entity_id', flat=True)
    location_ids = user.location_accesses.values_list('location_id', flat=True)
    grant_access_ids = user.access_grants.filter(
        is_active=True,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.localdate())
    ).values_list('access_id', flat=True)

    return queryset.filter(
        Q(equipment_id__in=allowed_equipment) |
        Q(legal_entity_id__in=legal_entity_ids) |
        Q(location_id__in=location_ids) |
        Q(id__in=grant_access_ids)
    ).distinct()


def user_can_edit_access(user, access):
    if not getattr(user, 'can_edit_accesses', True):
        return False
    if user_can_edit_scope(user, access.legal_entity, access.location):
        return True
    return user.access_grants.filter(
        access=access,
        is_active=True,
        level__in=['edit', 'admin'],
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.localdate())
    ).exists()


def require_access_edit_permission(user, access):
    if not user_can_edit_access(user, access):
        raise PermissionDenied


def user_can_reveal_access_secret(user, access):
    if not user or not user.is_authenticated:
        return False
    if not getattr(user, 'can_reveal_access_secrets', True):
        return False
    if user.is_superuser or getattr(user, 'role', '') == 'system_admin':
        return True
    if getattr(user, 'role', '') == 'service_engineer' and user_can_edit_access(user, access):
        return True
    if user.access_grants.filter(
        access=access,
        is_active=True,
        level__in=['view_secret', 'admin'],
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.localdate())
    ).exists():
        return True
    return False


def user_has_any_access_edit_permission(user):
    if not getattr(user, 'can_edit_accesses', True):
        return False
    if user_has_global_access(user):
        return True

    return (
        user.legal_entity_accesses.filter(access_level__in=EDIT_ACCESS_LEVELS).exists()
        or user.location_accesses.filter(access_level__in=EDIT_ACCESS_LEVELS).exists()
    )


def get_editable_equipment_for_accesses(user):
    queryset = get_user_equipment_queryset(user).filter(is_active=True)
    if not getattr(user, 'can_edit_accesses', True):
        return queryset.none()
    if user_has_global_access(user):
        return queryset

    legal_entity_ids = get_editable_legal_entity_ids(user)
    location_ids = get_editable_location_ids(user)

    return queryset.filter(
        Q(legal_entity_id__in=legal_entity_ids) |
        Q(location_id__in=location_ids)
    ).distinct()
