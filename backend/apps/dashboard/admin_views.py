from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.models import ActionLog
from apps.core.services import log_action
from apps.equipment.models import EquipmentCategory, EquipmentStatus
from apps.locations.models import Location
from apps.organizations.models import CostCenter, LegalEntity
from apps.users.models import User
from apps.warehouses.models import Warehouse

from .access import (
    get_accessible_cost_centers,
    get_accessible_legal_entities,
    get_accessible_locations,
    user_can_admin_directories,
    user_can_admin_global_directories,
)
from .admin_forms import (
    CostCenterAdminForm,
    EquipmentCategoryAdminForm,
    EquipmentStatusAdminForm,
    LegalEntityAdminForm,
    LocationAdminForm,
    UserManagementForm,
    WarehouseAdminForm,
)


ADMIN_SECTIONS = {
    'legal-entities': {
        'title': 'Юридические лица',
        'model': LegalEntity,
        'form': LegalEntityAdminForm,
        'columns': [('Название', 'name'), ('Короткое имя', 'short_name'), ('ИНН', 'tax_id'), ('Активно', 'is_active')],
        'search': ['name', 'short_name', 'tax_id'],
    },
    'locations': {
        'title': 'Локации',
        'model': Location,
        'form': LocationAdminForm,
        'columns': [('Название', 'name'), ('Активно', 'is_active')],
        'search': ['name'],
    },
    'cost-centers': {
        'title': 'ЦФО',
        'model': CostCenter,
        'form': CostCenterAdminForm,
        'columns': [('Название', 'name'), ('Юрлицо', 'legal_entity'), ('Локация', 'location'), ('Активно', 'is_active')],
        'search': ['name', 'legal_entity__name', 'location__name'],
        'select_related': ['legal_entity', 'location'],
    },
    'warehouses': {
        'title': 'Склады',
        'model': Warehouse,
        'form': WarehouseAdminForm,
        'columns': [('Название', 'name'), ('ЦФО', 'cost_center'), ('Активно', 'is_active')],
        'search': ['name', 'cost_center__name'],
        'select_related': ['cost_center'],
    },
    'equipment-categories': {
        'title': 'Категории оборудования',
        'model': EquipmentCategory,
        'form': EquipmentCategoryAdminForm,
        'columns': [('Название', 'name')],
        'search': ['name'],
    },
    'equipment-statuses': {
        'title': 'Статусы оборудования',
        'model': EquipmentStatus,
        'form': EquipmentStatusAdminForm,
        'columns': [('Название', 'name'), ('Код', 'code')],
        'search': ['name', 'code'],
    },
    'users': {
        'title': 'Пользователи',
        'model': User,
        'form': UserManagementForm,
        'columns': [('Логин', 'username'), ('Почта', 'email'), ('Роль', 'role'), ('Глобальный доступ', 'is_global_access'), ('Активен', 'is_active')],
        'search': ['username', 'email', 'first_name', 'last_name', 'phone'],
    },
}


COMPANY_ADMIN_SECTIONS = set(ADMIN_SECTIONS.keys())
COMPANY_ADMIN_CREATE_SECTIONS = set(ADMIN_SECTIONS.keys())
COMPANY_ADMIN_DELETE_SECTIONS = set(ADMIN_SECTIONS.keys())


def is_admin_user(user):
    return user.is_authenticated and user_can_admin_directories(user)


def admin_required(view_func):
    @login_required
    def wrapped(request, *args, **kwargs):
        if not is_admin_user(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


def get_available_sections(user):
    if getattr(user, 'can_manage_users', True) and getattr(user, 'can_manage_directories', True):
        return ADMIN_SECTIONS
    if getattr(user, 'can_manage_users', True):
        return {'users': ADMIN_SECTIONS['users']}
    if getattr(user, 'can_manage_directories', True):
        return {
            key: config
            for key, config in ADMIN_SECTIONS.items()
            if key != 'users'
        }

    return {}


def get_section(user, section):
    sections = get_available_sections(user)
    if section not in sections:
        raise PermissionDenied
    return sections[section]


def can_create_in_section(user, section):
    if section == 'users':
        return getattr(user, 'can_manage_users', True)
    return getattr(user, 'can_manage_directories', True)


def can_delete_in_section(user, section):
    if section == 'users':
        return getattr(user, 'can_manage_users', True)
    return getattr(user, 'can_manage_directories', True)


def get_queryset(config, user):
    queryset = config['model'].objects.all()
    select_related = config.get('select_related', [])
    if select_related:
        queryset = queryset.select_related(*select_related)
    if not user_can_admin_global_directories(user):
        if config['model'] is LegalEntity:
            queryset = get_accessible_legal_entities(user)
        elif config['model'] is Location:
            queryset = get_accessible_locations(user)
        elif config['model'] is CostCenter:
            queryset = get_accessible_cost_centers(user)
        elif config['model'] is Warehouse:
            queryset = queryset.filter(cost_center__in=get_accessible_cost_centers(user))
    return queryset.order_by(*get_ordering(config['model']))


def get_ordering(model):
    if hasattr(model, 'name'):
        return ['name']
    if hasattr(model, 'username'):
        return ['username']
    return ['id']


def get_attr_value(obj, attr):
    value = obj
    for part in attr.split('__'):
        value = getattr(value, part)
    if isinstance(value, bool):
        return 'Да' if value else 'Нет'
    if value in (None, ''):
        return '—'
    return value


def build_admin_form_context(section, config, form, form_title, obj=None):
    context = {
        'section': section,
        'title': config['title'],
        'form': form,
        'object': obj,
        'form_title': form_title,
    }
    if isinstance(form, UserManagementForm):
        context['profile_fields'] = [
            form[field_name]
            for field_name in form.PROFILE_FIELDS
            if field_name in form.fields
        ]
        context['access_fieldsets'] = [
            {
                'title': title,
                'fields': [
                    form[field_name]
                    for field_name in field_names
                    if field_name in form.fields
                ],
            }
            for title, field_names in form.ACCESS_FIELDSETS.items()
        ]
    return context


def build_rows(page_obj, columns):
    rows = []
    for obj in page_obj.object_list:
        rows.append({
            'object': obj,
            'values': [get_attr_value(obj, attr) for _, attr in columns],
        })
    return rows


@admin_required
def admin_panel_home(request):
    cards = []
    for key, config in get_available_sections(request.user).items():
        cards.append({
            'key': key,
            'title': config['title'],
            'count': get_queryset(config, request.user).count(),
        })
    return render(request, 'dashboard/admin_panel/home.html', {'cards': cards})


@admin_required
def audit_log_view(request):
    queryset = ActionLog.objects.select_related('actor', 'content_type').order_by('-created_at')
    query = request.GET.get('q', '').strip()
    action = request.GET.get('action', '').strip()
    actor_id = request.GET.get('actor', '').strip()

    if query:
        queryset = queryset.filter(
            Q(actor__username__icontains=query) |
            Q(object_repr__icontains=query) |
            Q(object_id__icontains=query) |
            Q(message__icontains=query)
        )
    if action:
        queryset = queryset.filter(action=action)
    if actor_id:
        queryset = queryset.filter(actor_id=actor_id)

    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    filter_query_params = request.GET.copy()
    filter_query_params.pop('page', None)

    return render(
        request,
        'dashboard/admin_panel/audit_log.html',
        {
            'logs': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'filter_querystring': filter_query_params.urlencode(),
            'query': query,
            'selected_action': action,
            'selected_actor': actor_id,
            'actions': ActionLog.ACTION_CHOICES,
            'actors': User.objects.filter(action_logs__isnull=False).distinct().order_by('username'),
        },
    )


@admin_required
def admin_section_list(request, section):
    config = get_section(request.user, section)
    queryset = get_queryset(config, request.user)
    query = request.GET.get('q', '').strip()

    if query:
        search_query = Q()
        for field in config.get('search', []):
            search_query |= Q(**{f'{field}__icontains': query})
        queryset = queryset.filter(search_query)

    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    rows = build_rows(page_obj, config['columns'])

    return render(
        request,
        'dashboard/admin_panel/list.html',
        {
            'section': section,
            'title': config['title'],
            'columns': [label for label, _ in config['columns']],
            'rows': rows,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'query': query,
            'can_create': can_create_in_section(request.user, section),
            'can_delete': can_delete_in_section(request.user, section),
        },
    )


@admin_required
def admin_section_create(request, section):
    config = get_section(request.user, section)
    if not can_create_in_section(request.user, section):
        raise PermissionDenied
    form_class = config['form']

    if request.method == 'POST':
        form = form_class(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save()
            log_action(
                request,
                ActionLog.ACTION_CREATE,
                obj,
                message=f'Создана запись раздела {config["title"]}.',
                metadata={'section': section},
            )
            messages.success(request, 'Запись создана.')
            return redirect('admin_section_list', section=section)
    else:
        form = form_class(user=request.user)

    return render(
        request,
        'dashboard/admin_panel/form.html',
        {
            'section': section,
            'title': config['title'],
            'form': form,
            'form_title': 'Новая запись',
        },
    )


@admin_required
def admin_section_update(request, section, pk):
    config = get_section(request.user, section)
    obj = get_object_or_404(get_queryset(config, request.user), pk=pk)
    form_class = config['form']

    if request.method == 'POST':
        form = form_class(request.POST, instance=obj, user=request.user)
        if form.is_valid():
            obj = form.save()
            log_action(
                request,
                ActionLog.ACTION_UPDATE,
                obj,
                message=f'Обновлена запись раздела {config["title"]}.',
                metadata={'section': section},
            )
            messages.success(request, 'Запись обновлена.')
            return redirect('admin_section_list', section=section)
    else:
        form = form_class(instance=obj, user=request.user)

    return render(
        request,
        'dashboard/admin_panel/form.html',
        {
            'section': section,
            'title': config['title'],
            'form': form,
            'object': obj,
            'form_title': 'Редактирование',
        },
    )


@admin_required
def admin_section_delete(request, section, pk):
    config = get_section(request.user, section)
    if not can_delete_in_section(request.user, section):
        raise PermissionDenied
    obj = get_object_or_404(get_queryset(config, request.user), pk=pk)

    if request.method != 'POST':
        return render(
            request,
            'dashboard/admin_panel/confirm_delete.html',
            {
                'section': section,
                'title': config['title'],
                'object': obj,
            },
        )

    if isinstance(obj, User) and obj.pk == request.user.pk:
        messages.error(request, 'Нельзя удалить текущего пользователя.')
        return redirect('admin_section_list', section=section)

    try:
        object_repr = str(obj)
        object_id = str(obj.pk)
        model_label = obj._meta.label_lower
        obj.delete()
        log_action(
            request,
            ActionLog.ACTION_DELETE,
            message=f'Удалена запись раздела {config["title"]}: {object_repr}.',
            metadata={'section': section, 'object_id': object_id, 'model': model_label},
        )
        messages.success(request, 'Запись удалена.')
    except ProtectedError:
        messages.error(request, 'Запись используется в оборудовании или связанных данных и не может быть удалена.')

    return redirect('admin_section_list', section=section)
