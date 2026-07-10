from django.core.exceptions import PermissionDenied
from django.db.models import Q

from apps.equipment.models import Equipment
from apps.locations.models import Location
from apps.organizations.models import CostCenter, LegalEntity


EDIT_ACCESS_LEVELS = {'edit', 'admin'}
ADMIN_DIRECTORY_ROLES = {'system_admin', 'company_admin'}
REPAIR_MANAGER_ROLES = {'system_admin', 'company_admin', 'technician', 'service_engineer'}


def user_has_global_access(user):
    return bool(user and (user.is_superuser or getattr(user, 'is_global_access', False)))


def user_can_admin_directories(user):
    return bool(
        user
        and (
            user.is_superuser
            or getattr(user, 'can_view_admin_panel', True)
            or getattr(user, 'role', '') in ADMIN_DIRECTORY_ROLES
        )
    )


def user_can_admin_global_directories(user):
    return bool(user and (user.is_superuser or getattr(user, 'can_manage_directories', True)))


def get_accessible_legal_entity_ids(user):
    if user_has_global_access(user):
        return None

    return user.legal_entity_accesses.filter(
        allow_all_locations=True,
    ).values_list('legal_entity_id', flat=True)


def get_accessible_location_ids(user):
    if user_has_global_access(user):
        return None

    return user.location_accesses.values_list('location_id', flat=True)


def get_accessible_cost_centers(user):
    queryset = CostCenter.objects.select_related('legal_entity', 'location').filter(is_active=True)
    if user_has_global_access(user):
        return queryset

    legal_entity_ids = get_accessible_legal_entity_ids(user)
    location_ids = get_accessible_location_ids(user)

    return queryset.filter(
        Q(legal_entity_id__in=legal_entity_ids) |
        Q(location_id__in=location_ids) |
        Q(legal_entity__isnull=True, location__isnull=True)
    ).distinct()


def get_accessible_legal_entities(user):
    queryset = LegalEntity.objects.filter(is_active=True)
    if user_has_global_access(user):
        return queryset

    legal_entity_ids = get_accessible_legal_entity_ids(user)
    location_ids = get_accessible_location_ids(user)

    return queryset.filter(
        Q(id__in=legal_entity_ids) |
        Q(cost_centers__location_id__in=location_ids)
    ).distinct()


def get_accessible_locations(user):
    queryset = Location.objects.filter(is_active=True)
    if user_has_global_access(user):
        return queryset

    legal_entity_ids = get_accessible_legal_entity_ids(user)
    location_ids = get_accessible_location_ids(user)

    return queryset.filter(
        Q(id__in=location_ids) |
        Q(cost_centers__legal_entity_id__in=legal_entity_ids)
    ).distinct()


def get_editable_legal_entity_ids(user):
    if user_has_global_access(user):
        return None

    return user.legal_entity_accesses.filter(
        access_level__in=EDIT_ACCESS_LEVELS,
        allow_all_locations=True,
    ).values_list('legal_entity_id', flat=True)


def get_editable_location_ids(user):
    if user_has_global_access(user):
        return None

    return user.location_accesses.filter(
        access_level__in=EDIT_ACCESS_LEVELS,
    ).values_list('location_id', flat=True)


def get_editable_cost_centers(user):
    queryset = CostCenter.objects.select_related('legal_entity', 'location').filter(is_active=True)
    if user_has_global_access(user):
        return queryset

    legal_entity_ids = get_editable_legal_entity_ids(user)
    location_ids = get_editable_location_ids(user)

    return queryset.filter(
        Q(legal_entity_id__in=legal_entity_ids) |
        Q(location_id__in=location_ids)
    ).distinct()


def get_editable_legal_entities(user):
    queryset = LegalEntity.objects.filter(is_active=True)
    if user_has_global_access(user):
        return queryset

    legal_entity_ids = get_editable_legal_entity_ids(user)
    location_ids = get_editable_location_ids(user)

    return queryset.filter(
        Q(id__in=legal_entity_ids) |
        Q(cost_centers__location_id__in=location_ids)
    ).distinct()


def get_editable_locations(user):
    queryset = Location.objects.filter(is_active=True)
    if user_has_global_access(user):
        return queryset

    legal_entity_ids = get_editable_legal_entity_ids(user)
    location_ids = get_editable_location_ids(user)

    return queryset.filter(
        Q(id__in=location_ids) |
        Q(cost_centers__legal_entity_id__in=legal_entity_ids)
    ).distinct()


def get_user_equipment_queryset(user):
    queryset = Equipment.objects.select_related(
        'legal_entity',
        'location',
        'category',
        'status',
        'responsible_user',
    ).prefetch_related('tags')

    if not getattr(user, 'can_view_equipment', True):
        return queryset.none()

    if user_has_global_access(user):
        return queryset

    legal_entity_ids = user.legal_entity_accesses.filter(
        allow_all_locations=True,
    ).values_list('legal_entity_id', flat=True)
    location_ids = user.location_accesses.values_list('location_id', flat=True)

    return queryset.filter(
        Q(legal_entity_id__in=legal_entity_ids) |
        Q(location_id__in=location_ids)
    ).distinct()


def user_has_any_edit_access(user):
    if not getattr(user, 'can_edit_equipment', True):
        return False
    if user_has_global_access(user):
        return True

    return (
        user.legal_entity_accesses.filter(access_level__in=EDIT_ACCESS_LEVELS).exists()
        or user.location_accesses.filter(access_level__in=EDIT_ACCESS_LEVELS).exists()
    )


def user_can_edit_equipment(user, equipment):
    return user_can_edit_scope(user, equipment.legal_entity, equipment.location)


def require_equipment_edit_access(user, equipment):
    if not user_can_edit_equipment(user, equipment):
        raise PermissionDenied


def user_can_edit_scope(user, legal_entity, location):
    if not getattr(user, 'can_edit_equipment', True):
        return False
    if user_has_global_access(user):
        return True
    if legal_entity is None and location is None:
        return user_has_any_edit_access(user)

    has_legal_entity_edit = user.legal_entity_accesses.filter(
        legal_entity=legal_entity,
        access_level__in=EDIT_ACCESS_LEVELS,
        allow_all_locations=True,
    ).exists()

    has_location_edit = user.location_accesses.filter(
        location=location,
        access_level__in=EDIT_ACCESS_LEVELS,
    ).exists()

    return has_legal_entity_edit or has_location_edit


def require_scope_edit_access(user, legal_entity, location):
    if not user_can_edit_scope(user, legal_entity, location):
        raise PermissionDenied


def user_can_manage_repairs(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, 'is_global_access', False)
            or getattr(user, 'role', '') in REPAIR_MANAGER_ROLES
        )
    )


def require_repair_manage_access(user):
    if not user_can_manage_repairs(user):
        raise PermissionDenied
