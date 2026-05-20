import csv
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import ActionLog
from apps.core.services import log_action
from apps.equipment.models import (
    Equipment,
    EquipmentCategory,
    EquipmentFile,
    EquipmentPhoto,
    EquipmentRequisite,
    EquipmentStatus,
)
from apps.accesses.access import (
    get_user_access_queryset,
    require_access_edit_permission,
    user_can_edit_access,
    user_can_reveal_access_secret,
    user_has_any_access_edit_permission,
)
from apps.accesses.forms import AccessGrantForm, AccessSecretForm, EquipmentAccessForm
from apps.accesses.models import AccessGrant, AccessSecret, AccessType, EquipmentAccess
from apps.accesses.services import encrypt_secret, log_access_change, reveal_access_secret
from apps.inventory.models import EquipmentInventory, EquipmentMovement, EquipmentRepair, InventoryItem, InventorySession
from apps.locations.models import Location
from apps.organizations.models import CostCenter, LegalEntity
from apps.tags.models import EquipmentTag
from apps.tags.services import create_qr_tag_for_equipment, regenerate_qr_tag_for_equipment
from apps.warehouses.models import Warehouse

from .access import (
    get_editable_cost_centers,
    get_user_equipment_queryset,
    require_equipment_edit_access,
    require_repair_manage_access,
    require_scope_edit_access,
    user_can_admin_directories,
    user_can_edit_equipment,
    user_can_edit_scope,
    user_has_global_access,
    user_can_manage_repairs,
    user_has_any_edit_access,
)
from .forms import (
    EquipmentCreateForm,
    EquipmentFileForm,
    EquipmentInventoryForm,
    EquipmentInventorySessionSelectForm,
    EquipmentMoveForm,
    EquipmentNoteForm,
    EquipmentPhotoForm,
    EquipmentRepairForm,
    EquipmentRepairStatusForm,
    EquipmentRequisiteForm,
    InventoryAddEquipmentForm,
    InventoryItemCheckForm,
    InventorySessionForm,
)
from .pdf import build_qr_labels_pdf
from .report_exports import build_csv_response, build_pdf_response, build_xlsx_response


PATCH_NOTES = [
    {
        'version': '0.1.8',
        'date': '2026-05-20',
        'title': 'Исправление поля "Склад"',
        'summary': 'Убрана битая кодировка в подсказке выпадающего списка склада.',
        'items': [
            'В форме оборудования placeholder склада снова отображается по-русски: "Выберите склад".',
            'Причина была в статическом JavaScript-файле, данные в базе остались корректными.',
        ],
    },
    {
        'version': '0.1.7',
        'date': '2026-05-20',
        'title': 'Проверка backup и актов инвентаризации',
        'summary': 'Проверены серверные backup-логи и исправлено открытие пустого акта инвентаризации после создания.',
        'items': [
            'Локальный backup на сервере успешно создает XML базы и зашифрованный архив.',
            'Google Drive и GitHub backup требуют заполнения внешних настроек и пока выключены.',
            'Администратор теперь может открыть новый акт инвентаризации даже до добавления оборудования.',
        ],
    },
    {
        'version': '0.1.6',
        'date': '2026-05-15',
        'title': 'Backup раз в 10 дней и ручной запуск',
        'summary': 'Автоматический backup теперь запускается раз в 10 дней, а ручной режим описан отдельной командой.',
        'items': [
            'Cron-расписание по умолчанию изменено на запуск в 03:00 раз в 10 дней.',
            'Ручной backup можно запустить командой scripts/production_backup.sh.',
            'Документация backup обновлена под новый режим работы.',
        ],
    },
    {
        'version': '0.1.5',
        'date': '2026-05-15',
        'title': 'Автоматический backup в три резерва',
        'summary': 'Добавлена серверная логика регулярного backup: локальная копия, Google Drive и отдельный GitHub-репозиторий.',
        'items': [
            'Backup создает XML базы, архив media, manifest и общий архив сборки.',
            'Для Google Drive и GitHub используется только зашифрованный архив.',
            'Добавлен установщик cron, чтобы backup запускался автоматически по расписанию.',
        ],
    },
    {
        'version': '0.1.4',
        'date': '2026-05-15',
        'title': 'Backup базы в XML',
        'summary': 'Полный backup базы теперь создается в общепринятом XML-формате фикстур Django.',
        'items': [
            'Добавлена команда backup_database_xml для создания полного XML backup базы.',
            'Скрипт backup сохраняет базу в файл database.xml рядом с архивом media.',
            'Скрипт restore восстанавливает данные из database.xml через штатный механизм loaddata.',
        ],
    },
    {
        'version': '0.1.3',
        'date': '2026-05-15',
        'title': 'Создание пользователей без ошибки 500',
        'summary': 'Исправлено падение формы при создании нового пользователя во внутренней админ-панели.',
        'items': [
            'Новый пользователь больше не считается существующим только из-за заранее созданного UUID.',
            'Пароль нового пользователя сохраняется корректно.',
            'Выбранные юрлица и локации назначаются сразу после создания.',
        ],
    },
    {
        'version': '0.1.2',
        'date': '2026-05-15',
        'title': 'Русский интерфейс без лишнего английского',
        'summary': 'Формы и основные подписи интерфейса приведены к русскому языку.',
        'items': [
            'Роли пользователей и уровни доступа отображаются на русском языке.',
            'Подписи форм доступа, секретов и выдачи прав заменены на понятные русские названия.',
            'Английские названия в меню, таблицах и странице входа убраны из пользовательского интерфейса.',
        ],
    },
    {
        'version': '0.1.1',
        'date': '2026-05-15',
        'title': 'Удобная выдача прав пользователям',
        'summary': 'Права на юрлица и локации теперь настраиваются прямо в карточке пользователя, без создания отдельных записей для каждой области.',
        'items': [
            'Во вкладке "Права доступа" появился выбор нескольких юридических лиц и локаций галочками.',
            'Один уровень доступа применяется сразу ко всем выбранным юрлицам и локациям.',
            'Исправлено сохранение пользователя: если поле нового пароля пустое, старый пароль больше не сбрасывается.',
        ],
    },
    {
        'version': '0.1.0',
        'date': '2026-05-14',
        'title': 'Первая серверная сборка',
        'summary': 'Система подготовлена к запуску на сервере и дальнейшей выкладке небольшими патчами.',
        'items': [
            'Добавлен production-запуск через Docker, Gunicorn и Nginx.',
            'Подготовлены настройки безопасности для серверного режима.',
            'QR-ссылки стали гибкими: они могут работать с локальным адресом, IP или будущим доменом.',
            'В интерфейсе отображается версия приложения.',
        ],
    },
]


@login_required
def dashboard_home(request):
    equipment_qs = get_user_equipment_queryset(request.user)
    notifications = build_attention_notifications(request.user, limit_per_group=3)

    context = {
        'equipment_count': equipment_qs.count(),
        'active_equipment_count': equipment_qs.filter(is_active=True).count(),
        'repair_count': equipment_qs.filter(status__code='REPAIR').count(),
        'storage_count': equipment_qs.filter(status__code='STORAGE').count(),
        'notification_groups': notifications['groups'],
        'notification_total': notifications['total'],
    }
    return render(request, 'dashboard/home.html', context)


@login_required
def patch_notes_view(request):
    return render(
        request,
        'dashboard/patch_notes.html',
        {
            'current_version': settings.APP_VERSION,
            'patches': PATCH_NOTES,
        },
    )


def _notification_item(title, subtitle, url, severity='warning'):
    return {
        'title': title,
        'subtitle': subtitle,
        'url': url,
        'severity': severity,
    }


def _limited_items(items, limit):
    return items if limit is None else items[:limit]


def build_attention_notifications(user, limit_per_group=None):
    today = timezone.localdate()
    soon = today + timedelta(days=30)
    stale_inventory_before = today - timedelta(days=180)
    stale_repair_before = timezone.now() - timedelta(days=7)

    equipment_queryset = get_user_equipment_queryset(user).select_related(
        'legal_entity',
        'location',
        'warehouse',
        'status',
    )
    repair_queryset = get_user_repair_queryset(user)
    inventory_queryset = get_user_inventory_queryset(user)
    access_queryset = get_user_access_queryset(user).select_related('access_type', 'equipment', 'location')

    open_repair_statuses = [
        EquipmentRepair.STATUS_REQUESTED,
        EquipmentRepair.STATUS_ACCEPTED,
        EquipmentRepair.STATUS_IN_PROGRESS,
        EquipmentRepair.STATUS_WAITING_PARTS,
    ]
    open_repairs = repair_queryset.filter(status__in=open_repair_statuses).order_by('created_at')
    stale_repairs = open_repairs.filter(created_at__lte=stale_repair_before)
    unfinished_inventory = inventory_queryset.filter(status__in=['draft', 'in_progress']).order_by('started_at', 'period_start')
    stale_equipment = equipment_queryset.filter(is_active=True).filter(
        Q(last_inventory_date__isnull=True) |
        Q(last_inventory_date__lt=stale_inventory_before)
    ).order_by('last_inventory_date', 'name')
    expiring_accesses = access_queryset.filter(is_active=True, expires_at__isnull=False, expires_at__lte=soon).order_by('expires_at')
    accesses_without_secrets = access_queryset.filter(is_active=True).exclude(
        secrets__is_active=True
    ).distinct().order_by('title')
    warranty_issues = equipment_queryset.filter(
        is_active=True,
        warranty_until__isnull=False,
        warranty_until__lte=soon,
    ).order_by('warranty_until', 'name')
    active_repair_equipment_ids = open_repairs.values('equipment_id')
    repair_status_without_request = equipment_queryset.filter(
        status__code='REPAIR',
    ).exclude(
        id__in=active_repair_equipment_ids,
    ).order_by('name')

    groups = []

    stale_repair_items = [
        _notification_item(
            repair.equipment.name,
            f'{repair.get_status_display()} · создано {repair.created_at:%d.%m.%Y} · {repair.description[:100]}',
            reverse('equipment_detail', kwargs={'pk': repair.equipment.pk}),
            'critical',
        )
        for repair in _limited_items(list(stale_repairs[:50]), limit_per_group)
    ]
    groups.append({
        'key': 'stale_repairs',
        'title': 'Ремонты долго в работе',
        'count': stale_repairs.count(),
        'items': stale_repair_items,
    })

    unfinished_inventory_items = [
        _notification_item(
            session.act_number or session.name,
            f'{session.location} · {session.get_status_display()} · {session.period_start or session.started_at or "-"}',
            reverse('inventory_session_detail', kwargs={'pk': session.pk}),
            'warning',
        )
        for session in _limited_items(list(unfinished_inventory[:50]), limit_per_group)
    ]
    groups.append({
        'key': 'unfinished_inventory',
        'title': 'Незавершенная инвентаризация',
        'count': unfinished_inventory.count(),
        'items': unfinished_inventory_items,
    })

    stale_equipment_items = [
        _notification_item(
            equipment.name,
            f'{equipment.location} · последняя инвентаризация: {equipment.last_inventory_date or "не проводилась"}',
            reverse('equipment_detail', kwargs={'pk': equipment.pk}),
            'warning',
        )
        for equipment in _limited_items(list(stale_equipment[:50]), limit_per_group)
    ]
    groups.append({
        'key': 'stale_equipment',
        'title': 'Оборудование давно не инвентаризировалось',
        'count': stale_equipment.count(),
        'items': stale_equipment_items,
    })

    expiring_access_items = [
        _notification_item(
            access.title,
            f'{access.access_type} · истекает {access.expires_at:%d.%m.%Y}',
            reverse('equipment_access_detail', kwargs={'pk': access.pk}),
            'critical' if access.expires_at < today else 'warning',
        )
        for access in _limited_items(list(expiring_accesses[:50]), limit_per_group)
    ]
    groups.append({
        'key': 'expiring_accesses',
        'title': 'Истекающие доступы',
        'count': expiring_accesses.count(),
        'items': expiring_access_items,
    })

    accesses_without_secrets_items = [
        _notification_item(
            access.title,
            f'{access.access_type} · {access.host or access.url or access.location}',
            reverse('equipment_access_detail', kwargs={'pk': access.pk}),
            'warning',
        )
        for access in _limited_items(list(accesses_without_secrets[:50]), limit_per_group)
    ]
    groups.append({
        'key': 'accesses_without_secrets',
        'title': 'Доступы без активного секрета',
        'count': accesses_without_secrets.count(),
        'items': accesses_without_secrets_items,
    })

    warranty_items = [
        _notification_item(
            equipment.name,
            f'{equipment.location} · гарантия до {equipment.warranty_until:%d.%m.%Y}',
            reverse('equipment_detail', kwargs={'pk': equipment.pk}),
            'critical' if equipment.warranty_until < today else 'warning',
        )
        for equipment in _limited_items(list(warranty_issues[:50]), limit_per_group)
    ]
    groups.append({
        'key': 'warranty_issues',
        'title': 'Истекает гарантия',
        'count': warranty_issues.count(),
        'items': warranty_items,
    })

    repair_status_items = [
        _notification_item(
            equipment.name,
            f'{equipment.location} · статус {equipment.status}',
            reverse('equipment_detail', kwargs={'pk': equipment.pk}),
            'critical',
        )
        for equipment in _limited_items(list(repair_status_without_request[:50]), limit_per_group)
    ]
    groups.append({
        'key': 'repair_status_without_request',
        'title': 'Статус "На ремонте" без активной заявки',
        'count': repair_status_without_request.count(),
        'items': repair_status_items,
    })

    groups = [group for group in groups if group['count']]
    return {
        'groups': groups,
        'total': sum(group['count'] for group in groups),
    }


@login_required
def notifications_view(request):
    notifications = build_attention_notifications(request.user)
    return render(
        request,
        'dashboard/notifications.html',
        {
            'notification_groups': notifications['groups'],
            'notification_total': notifications['total'],
        },
    )


@login_required
def cost_centers_by_location_view(request):
    location_id = request.GET.get('location', '').strip()
    legal_entity_id = request.GET.get('legal_entity', '').strip()

    if user_can_admin_directories(request.user):
        cost_centers = CostCenter.objects.filter(is_active=True)
    else:
        cost_centers = get_editable_cost_centers(request.user)

    if location_id:
        cost_centers = cost_centers.filter(location_id=location_id)
    if legal_entity_id:
        cost_centers = cost_centers.filter(legal_entity_id=legal_entity_id)
    cost_centers = cost_centers.order_by('name')

    return JsonResponse({
        'items': [
            {
                'id': str(cost_center.id),
                'name': cost_center.name,
            }
            for cost_center in cost_centers
        ]
    })


@login_required
def warehouses_by_cost_center_view(request):
    cost_center_id = request.GET.get('cost_center', '').strip()

    if not cost_center_id:
        warehouses = Warehouse.objects.none()
    else:
        editable_cost_centers = (
            CostCenter.objects.filter(is_active=True)
            if user_can_admin_directories(request.user)
            else get_editable_cost_centers(request.user)
        )
        warehouses = Warehouse.objects.filter(
            is_active=True,
            cost_center_id__in=editable_cost_centers.filter(id=cost_center_id),
        ).order_by('name')

    return JsonResponse({
        'items': [
            {
                'id': warehouse.name,
                'name': warehouse.name,
            }
            for warehouse in warehouses
        ]
    })


@login_required
def global_search_view(request):
    query = request.GET.get('q', '').strip()
    min_query_length = 2
    results = {
        'equipment': [],
        'tags': [],
        'accesses': [],
        'repairs': [],
        'inventory': [],
        'movements': [],
    }
    total_count = 0

    if len(query) >= min_query_length:
        equipment_queryset = get_user_equipment_queryset(request.user).select_related(
            'legal_entity',
            'location',
            'warehouse',
            'category',
            'status',
        )
        equipment_results = equipment_queryset.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(model__icontains=query) |
            Q(serial_number__icontains=query) |
            Q(inventory_number__icontains=query) |
            Q(comment__icontains=query) |
            Q(category__name__icontains=query) |
            Q(status__name__icontains=query) |
            Q(warehouse__name__icontains=query)
        ).distinct().order_by('name')[:10]
        results['equipment'] = [
            {
                'title': equipment.name,
                'subtitle': f'{equipment.serial_number or "Без серийного номера"} · {equipment.location} · {equipment.status}',
                'url': reverse('equipment_detail', kwargs={'pk': equipment.pk}),
            }
            for equipment in equipment_results
        ]

        tag_results = EquipmentTag.objects.filter(
            equipment__in=equipment_queryset,
            is_active=True,
        ).filter(
            Q(code__icontains=query) |
            Q(payload__icontains=query) |
            Q(tag_type__icontains=query)
        ).select_related('equipment').order_by('tag_type', 'code')[:10]
        results['tags'] = [
            {
                'title': f'{tag.get_tag_type_display()} {tag.code}',
                'subtitle': f'{tag.equipment.name} · {tag.payload}',
                'url': reverse('equipment_detail', kwargs={'pk': tag.equipment.pk}),
            }
            for tag in tag_results
        ]

        access_results = get_user_access_queryset(request.user).select_related(
            'access_type',
            'equipment',
            'legal_entity',
            'location',
        ).filter(
            Q(title__icontains=query) |
            Q(host__icontains=query) |
            Q(url__icontains=query) |
            Q(username__icontains=query) |
            Q(description__icontains=query) |
            Q(equipment__name__icontains=query) |
            Q(equipment__serial_number__icontains=query) |
            Q(access_type__name__icontains=query)
        ).distinct().order_by('title')[:10]
        results['accesses'] = [
            {
                'title': access.title,
                'subtitle': f'{access.access_type} · {access.host or access.url or access.username or access.location}',
                'url': reverse('equipment_access_detail', kwargs={'pk': access.pk}),
            }
            for access in access_results
        ]

        repair_results = get_user_repair_queryset(request.user).filter(
            Q(equipment__name__icontains=query) |
            Q(equipment__serial_number__icontains=query) |
            Q(description__icontains=query) |
            Q(resolution__icontains=query) |
            Q(contractor__icontains=query) |
            Q(status_comment__icontains=query)
        ).distinct().order_by('-created_at')[:10]
        results['repairs'] = [
            {
                'title': repair.equipment.name,
                'subtitle': f'{repair.get_status_display()} · {repair.description[:120]}',
                'url': reverse('equipment_detail', kwargs={'pk': repair.equipment.pk}),
            }
            for repair in repair_results
        ]

        inventory_results = get_user_inventory_queryset(request.user).filter(
            Q(name__icontains=query) |
            Q(act_number__icontains=query) |
            Q(comment__icontains=query) |
            Q(items__equipment__name__icontains=query) |
            Q(items__equipment__serial_number__icontains=query) |
            Q(items__comment__icontains=query)
        ).distinct().order_by('-period_start', '-started_at')[:10]
        results['inventory'] = [
            {
                'title': session.act_number or session.name,
                'subtitle': f'{session.name} · {session.location} · {session.get_status_display()}',
                'url': reverse('inventory_session_detail', kwargs={'pk': session.pk}),
            }
            for session in inventory_results
        ]

        movement_results = EquipmentMovement.objects.filter(
            equipment__in=equipment_queryset
        ).select_related(
            'equipment',
            'from_location',
            'to_location',
            'from_warehouse',
            'to_warehouse',
            'moved_by',
        ).filter(
            Q(equipment__name__icontains=query) |
            Q(equipment__serial_number__icontains=query) |
            Q(equipment__inventory_number__icontains=query) |
            Q(from_location__name__icontains=query) |
            Q(to_location__name__icontains=query) |
            Q(from_warehouse__name__icontains=query) |
            Q(to_warehouse__name__icontains=query) |
            Q(comment__icontains=query) |
            Q(moved_by__username__icontains=query)
        ).distinct().order_by('-moved_at')[:10]
        results['movements'] = [
            {
                'title': movement.equipment.name,
                'subtitle': f'{movement.from_location or "-"} -> {movement.to_location or "-"} · {movement.comment or movement.moved_at}',
                'url': f'{reverse("movement_journal")}?q={movement.equipment.serial_number or movement.equipment.name}',
            }
            for movement in movement_results
        ]

        total_count = sum(len(items) for items in results.values())

    return render(
        request,
        'dashboard/search_results.html',
        {
            'query': query,
            'min_query_length': min_query_length,
            'results': results,
            'total_count': total_count,
        },
    )


def _apply_equipment_filters(request, equipment_queryset):
    q = request.GET.get('q', '').strip()
    activity = request.GET.get('activity', 'active').strip()
    legal_entity_id = request.GET.get('legal_entity', '').strip()
    location_id = request.GET.get('location', '').strip()
    cost_center_id = request.GET.get('cost_center', '').strip()
    warehouse_id = request.GET.get('warehouse', '').strip()
    category_id = request.GET.get('category', '').strip()
    status_id = request.GET.get('status', '').strip()

    if q:
        equipment_queryset = equipment_queryset.filter(
            Q(name__icontains=q) |
            Q(serial_number__icontains=q) |
            Q(inventory_number__icontains=q) |
            Q(brand__icontains=q) |
            Q(model__icontains=q) |
            Q(category__name__icontains=q) |
            Q(status__name__icontains=q) |
            Q(warehouse__name__icontains=q) |
            Q(tags__code__icontains=q) |
            Q(tags__payload__icontains=q)
        ).distinct()

    if activity == 'archived':
        equipment_queryset = equipment_queryset.filter(is_active=False)
    elif activity != 'all':
        equipment_queryset = equipment_queryset.filter(is_active=True)

    if legal_entity_id:
        equipment_queryset = equipment_queryset.filter(legal_entity_id=legal_entity_id)
    if location_id:
        equipment_queryset = equipment_queryset.filter(location_id=location_id)
    if cost_center_id:
        equipment_queryset = equipment_queryset.filter(cost_center_id=cost_center_id)
    if warehouse_id:
        equipment_queryset = equipment_queryset.filter(warehouse_id=warehouse_id)
    if category_id:
        equipment_queryset = equipment_queryset.filter(category_id=category_id)
    if status_id:
        equipment_queryset = equipment_queryset.filter(status_id=status_id)

    return equipment_queryset


def _get_equipment_filter_options(equipment_queryset):
    return {
        'legal_entities': LegalEntity.objects.filter(
            equipment_items__in=equipment_queryset,
        ).distinct().order_by('name'),
        'locations': Location.objects.filter(
            equipment_items__in=equipment_queryset,
        ).distinct().order_by('name'),
        'cost_centers': CostCenter.objects.select_related('legal_entity', 'location').filter(
            equipment_items__in=equipment_queryset,
        ).distinct().order_by('name'),
        'warehouses': Warehouse.objects.select_related('cost_center').filter(
            equipment_items__in=equipment_queryset,
        ).distinct().order_by('name'),
        'categories': EquipmentCategory.objects.filter(
            equipment_items__in=equipment_queryset,
        ).distinct().order_by('name'),
        'statuses': EquipmentStatus.objects.filter(
            equipment_items__in=equipment_queryset,
        ).distinct().order_by('name'),
    }


@login_required
def equipment_list_view(request):
    base_equipment_queryset = (
        get_user_equipment_queryset(request.user).select_related(
            'legal_entity',
            'location',
            'cost_center',
            'warehouse',
            'category',
            'status',
            'responsible_user',
        )
        .order_by('name')
    )

    equipment_queryset = _apply_equipment_filters(request, base_equipment_queryset)

    paginator = Paginator(equipment_queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    for equipment in page_obj.object_list:
        equipment.can_edit = user_can_edit_equipment(request.user, equipment)
    filter_query_params = request.GET.copy()
    filter_query_params.pop('page', None)

    context = {
        'equipment_list': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'can_create_equipment': user_has_any_edit_access(request.user),
        'filter_querystring': filter_query_params.urlencode(),
    }
    context.update(_get_equipment_filter_options(base_equipment_queryset))

    return render(request, 'dashboard/equipment_list.html', context)


@login_required
def movement_journal_view(request):
    allowed_equipment = get_user_equipment_queryset(request.user)
    base_movements_queryset = EquipmentMovement.objects.filter(equipment__in=allowed_equipment)
    movements_queryset = (
        base_movements_queryset
        .select_related(
            'equipment',
            'legal_entity',
            'from_location',
            'to_location',
            'from_cost_center',
            'to_cost_center',
            'from_warehouse',
            'to_warehouse',
            'moved_by',
        )
        .order_by('-moved_at')
    )
    movements_queryset = _apply_movement_filters(request, movements_queryset)

    paginator = Paginator(movements_queryset, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    filter_query_params = request.GET.copy()
    filter_query_params.pop('page', None)

    context = {
        'movements': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'filter_querystring': filter_query_params.urlencode(),
        'legal_entities': LegalEntity.objects.filter(
            equipment_movements__in=base_movements_queryset,
        ).distinct().order_by('name'),
        'locations': Location.objects.filter(
            Q(outgoing_movements__in=base_movements_queryset) |
            Q(incoming_movements__in=base_movements_queryset),
        ).distinct().order_by('name'),
    }

    return render(request, 'dashboard/movement_journal.html', context)


def _apply_movement_filters(request, movements_queryset):
    q = request.GET.get('q', '').strip()
    legal_entity_id = request.GET.get('legal_entity', '').strip()
    location_id = request.GET.get('location', '').strip()

    if q:
        movements_queryset = movements_queryset.filter(
            Q(equipment__name__icontains=q) |
            Q(equipment__serial_number__icontains=q) |
            Q(equipment__inventory_number__icontains=q) |
            Q(from_location__name__icontains=q) |
            Q(to_location__name__icontains=q) |
            Q(from_warehouse__name__icontains=q) |
            Q(to_warehouse__name__icontains=q) |
            Q(moved_by__username__icontains=q) |
            Q(comment__icontains=q)
        ).distinct()

    if legal_entity_id:
        movements_queryset = movements_queryset.filter(legal_entity_id=legal_entity_id)
    if location_id:
        movements_queryset = movements_queryset.filter(
            Q(from_location_id=location_id) |
            Q(to_location_id=location_id)
        )
    return movements_queryset


@login_required
def reports_home_view(request):
    equipment_queryset = get_user_equipment_queryset(request.user)
    repair_queryset = get_user_repair_queryset(request.user)
    inventory_queryset = get_user_inventory_queryset(request.user)

    equipment_by_status = (
        equipment_queryset
        .values('status__name')
        .annotate(total=Count('id'))
        .order_by('status__name')
    )
    equipment_by_location = (
        equipment_queryset
        .values('location__name')
        .annotate(total=Count('id'))
        .order_by('location__name')
    )
    movement_queryset = EquipmentMovement.objects.filter(equipment__in=equipment_queryset)
    repair_cost_total = repair_queryset.aggregate(total=Sum('cost'))['total'] or 0
    inventory_item_count = InventoryItem.objects.filter(session__in=inventory_queryset).count()
    inventory_found_count = InventoryItem.objects.filter(session__in=inventory_queryset, found=True).count()

    return render(
        request,
        'dashboard/reports_home.html',
        {
            'equipment_total': equipment_queryset.count(),
            'equipment_active': equipment_queryset.filter(is_active=True).count(),
            'equipment_repair': equipment_queryset.filter(status__code='REPAIR').count(),
            'equipment_by_status': equipment_by_status,
            'equipment_by_location': equipment_by_location,
            'repair_total': repair_queryset.count(),
            'repair_open': repair_queryset.exclude(
                status__in=[EquipmentRepair.STATUS_COMPLETED, EquipmentRepair.STATUS_CANCELLED]
            ).count(),
            'repair_cost_total': repair_cost_total,
            'movement_total': movement_queryset.count(),
            'inventory_total': inventory_queryset.count(),
            'inventory_completed': inventory_queryset.filter(status='completed').count(),
            'inventory_item_count': inventory_item_count,
            'inventory_found_count': inventory_found_count,
            'repair_status_choices': EquipmentRepair.STATUS_CHOICES,
            'inventory_status_choices': InventorySession.STATUS_CHOICES,
        },
    )


def get_user_inventory_queryset(user):
    if user_has_global_access(user):
        return InventorySession.objects.select_related(
            'legal_entity',
            'location',
            'created_by',
            'confirmed_by',
        )

    allowed_equipment = get_user_equipment_queryset(user)
    return InventorySession.objects.filter(
        Q(legal_entity__equipment_items__in=allowed_equipment) |
        Q(location__equipment_items__in=allowed_equipment)
    ).select_related(
        'legal_entity',
        'location',
        'created_by',
        'confirmed_by',
    ).distinct()


def get_user_repair_queryset(user):
    allowed_equipment = get_user_equipment_queryset(user)
    return EquipmentRepair.objects.filter(
        equipment__in=allowed_equipment
    ).select_related(
        'equipment',
        'equipment__location',
        'equipment__warehouse',
        'legal_entity',
        'created_by',
        'accepted_by',
        'assigned_to',
    ).distinct()


def _apply_repair_report_filters(request, repair_queryset):
    status = request.GET.get('status', '').strip()
    date_from = parse_date(request.GET.get('date_from', '').strip())
    date_to = parse_date(request.GET.get('date_to', '').strip())

    if status:
        repair_queryset = repair_queryset.filter(status=status)
    if date_from:
        repair_queryset = repair_queryset.filter(created_at__date__gte=date_from)
    if date_to:
        repair_queryset = repair_queryset.filter(created_at__date__lte=date_to)
    return repair_queryset


def _apply_inventory_report_filters(request, inventory_queryset):
    status = request.GET.get('status', '').strip()
    date_from = parse_date(request.GET.get('date_from', '').strip())
    date_to = parse_date(request.GET.get('date_to', '').strip())

    if status:
        inventory_queryset = inventory_queryset.filter(status=status)
    if date_from:
        inventory_queryset = inventory_queryset.filter(period_start__gte=date_from)
    if date_to:
        inventory_queryset = inventory_queryset.filter(period_end__lte=date_to)
    return inventory_queryset


def _report_response(request, filename, title, headers, rows, report_format=None):
    report_format = (report_format or request.GET.get('format', 'csv')).strip().lower()
    if report_format == 'xlsx':
        return build_xlsx_response(filename, title[:31], headers, rows)
    if report_format == 'pdf':
        return build_pdf_response(filename, title, headers, rows)
    return build_csv_response(filename, headers, rows)


def _equipment_report_rows(equipment_queryset):
    headers = [
        'ID',
        'Название',
        'Юрлицо',
        'Локация',
        'ЦФО',
        'Склад/зона',
        'Категория',
        'Статус',
        'Бренд',
        'Модель',
        'Серийный номер',
        'Инвентарный номер',
        'Цена приобретения',
        'Оценочная стоимость',
        'Дата покупки',
        'Последняя инвентаризация',
        'Последний ремонт',
        'Активно',
    ]
    rows = [[
        equipment.id,
        equipment.name,
        equipment.legal_entity.name,
        equipment.location.name,
        equipment.cost_center.name if equipment.cost_center else '',
        equipment.warehouse.name if equipment.warehouse else '',
        equipment.category.name if equipment.category else '',
        equipment.status.name if equipment.status else '',
        equipment.brand,
        equipment.model,
        equipment.serial_number,
        equipment.inventory_number,
        equipment.price or '',
        equipment.estimated_current_value or '',
        equipment.purchase_date or '',
        equipment.last_inventory_date or '',
        equipment.last_repair_date or '',
        'Да' if equipment.is_active else 'Нет',
    ] for equipment in equipment_queryset]
    return headers, rows


def _repair_report_rows(repair_queryset):
    headers = [
        'ID',
        'Оборудование',
        'Серийный номер',
        'Юрлицо',
        'Локация',
        'Склад/зона',
        'Статус',
        'Приоритет',
        'Проблема',
        'Что сделано',
        'Стоимость',
        'Исполнитель',
        'Создал',
        'Техник',
        'Создано',
        'Завершено',
    ]
    rows = [[
        repair.id,
        repair.equipment.name,
        repair.equipment.serial_number,
        repair.legal_entity.name,
        repair.equipment.location.name if repair.equipment.location else '',
        repair.equipment.warehouse.name if repair.equipment.warehouse else '',
        repair.get_status_display(),
        repair.get_priority_display(),
        repair.description,
        repair.resolution,
        repair.cost or '',
        repair.contractor,
        repair.created_by.username if repair.created_by else '',
        repair.assigned_to.username if repair.assigned_to else '',
        repair.created_at,
        repair.completed_at or '',
    ] for repair in repair_queryset]
    return headers, rows


def _movement_report_rows(movements_queryset):
    headers = [
        'ID',
        'Оборудование',
        'Серийный номер',
        'Юрлицо',
        'Откуда локация',
        'Куда локация',
        'Откуда ЦФО',
        'Куда ЦФО',
        'Откуда склад/зона',
        'Куда склад/зона',
        'Кто переместил',
        'Дата перемещения',
        'Комментарий',
    ]
    rows = [[
        movement.id,
        movement.equipment.name,
        movement.equipment.serial_number,
        movement.legal_entity.name,
        movement.from_location.name if movement.from_location else '',
        movement.to_location.name if movement.to_location else '',
        movement.from_cost_center.name if movement.from_cost_center else '',
        movement.to_cost_center.name if movement.to_cost_center else '',
        movement.from_warehouse.name if movement.from_warehouse else '',
        movement.to_warehouse.name if movement.to_warehouse else '',
        movement.moved_by.username if movement.moved_by else '',
        movement.moved_at,
        movement.comment,
    ] for movement in movements_queryset]
    return headers, rows


def _inventory_report_rows(inventory_queryset):
    headers = [
        'ID акта',
        'Номер акта',
        'Название',
        'Юрлицо',
        'Локация',
        'Статус',
        'Дата начала',
        'Дата окончания',
        'Оборудование',
        'Серийный номер',
        'Найдено',
        'Фактическая локация',
        'Фактический склад/зона',
        'Состояние',
        'Оценочная стоимость',
        'Проверил',
        'Комментарий',
    ]
    rows = []
    for session in inventory_queryset:
        items = list(session.items.select_related(
            'equipment',
            'actual_location',
            'actual_warehouse',
            'checked_by',
        ).order_by('equipment__name'))
        if not items:
            rows.append([
                session.id,
                session.act_number,
                session.name,
                session.legal_entity.name,
                session.location.name,
                session.get_status_display(),
                session.period_start or '',
                session.period_end or '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                session.comment,
            ])
        for item in items:
            rows.append([
                session.id,
                session.act_number,
                session.name,
                session.legal_entity.name,
                session.location.name,
                session.get_status_display(),
                session.period_start or '',
                session.period_end or '',
                item.equipment.name,
                item.equipment.serial_number,
                'Да' if item.found else 'Нет',
                item.actual_location.name if item.actual_location else '',
                item.actual_warehouse.name if item.actual_warehouse else '',
                item.get_condition_status_display(),
                item.estimated_value or '',
                item.checked_by.username if item.checked_by else '',
                item.comment,
            ])
    return headers, rows


def update_equipment_status_by_code(equipment, code):
    default_names = {
        'WORKING': 'В работе',
        'REPAIR': 'На ремонте',
        'STORAGE': 'На складе',
        'WRITTEN_OFF': 'Списано',
    }
    status, _ = EquipmentStatus.objects.get_or_create(
        code=code,
        defaults={'name': default_names.get(code, code)},
    )
    if equipment.status_id != status.id:
        equipment.status = status
        equipment.save(update_fields=['status', 'updated_at'])


@login_required
def inventory_session_list_view(request):
    queryset = get_user_inventory_queryset(request.user).order_by('-period_start', '-started_at', '-id')
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(act_number__icontains=query) |
            Q(comment__icontains=query)
        )
    if status:
        queryset = queryset.filter(status=status)

    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    filter_query_params = request.GET.copy()
    filter_query_params.pop('page', None)

    return render(
        request,
        'dashboard/inventory_session_list.html',
        {
            'sessions': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'filter_querystring': filter_query_params.urlencode(),
            'query': query,
            'selected_status': status,
            'statuses': InventorySession.STATUS_CHOICES,
            'can_create_inventory': user_has_any_edit_access(request.user),
        },
    )


@login_required
def inventory_session_create_view(request):
    if not user_has_any_edit_access(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        form = InventorySessionForm(request.POST, user=request.user)
        if form.is_valid():
            session = form.save(commit=False)
            require_scope_edit_access(request.user, session.legal_entity, session.location)
            session.created_by = request.user
            session.status = 'in_progress'
            session.started_at = timezone.now()
            session.save()
            log_action(request, ActionLog.ACTION_CREATE, session, message='Создан акт инвентаризации.')
            messages.success(request, 'Инвентаризация создана.')
            return redirect('inventory_session_detail', pk=session.pk)
    else:
        form = InventorySessionForm(user=request.user)

    return render(
        request,
        'dashboard/inventory_session_form.html',
        {
            'form': form,
            'page_title': 'Создание инвентаризации',
        },
    )


@login_required
def inventory_session_detail_view(request, pk):
    session = get_object_or_404(get_user_inventory_queryset(request.user), pk=pk)
    items = session.items.select_related(
        'equipment',
        'equipment__legal_entity',
        'equipment__location',
        'equipment__warehouse',
        'actual_location',
        'actual_warehouse',
        'checked_by',
        'scanned_tag',
    ).order_by('equipment__name')

    return render(
        request,
        'dashboard/inventory_session_detail.html',
        {
            'session': session,
            'items': items,
            'add_form': InventoryAddEquipmentForm(user=request.user, session=session),
            'can_edit_inventory': user_can_edit_scope(request.user, session.legal_entity, session.location),
        },
    )


@login_required
@require_POST
def inventory_session_add_item_view(request, pk):
    session = get_object_or_404(get_user_inventory_queryset(request.user), pk=pk)
    require_scope_edit_access(request.user, session.legal_entity, session.location)
    if session.status in ['completed', 'cancelled']:
        raise PermissionDenied

    form = InventoryAddEquipmentForm(request.POST, user=request.user, session=session)
    if form.is_valid():
        equipment = form.cleaned_data['equipment']
        InventoryItem.objects.get_or_create(
            session=session,
            equipment=equipment,
            defaults={
                'actual_location': equipment.location,
                'actual_warehouse': equipment.warehouse,
                'estimated_value': equipment.estimated_current_value,
            },
        )
        messages.success(request, 'Позиция добавлена в акт.')
    else:
        messages.error(request, 'Не удалось добавить позицию.')
    return redirect('inventory_session_detail', pk=session.pk)


@login_required
def inventory_item_check_view(request, pk, item_pk):
    session = get_object_or_404(get_user_inventory_queryset(request.user), pk=pk)
    require_scope_edit_access(request.user, session.legal_entity, session.location)
    item = get_object_or_404(InventoryItem.objects.select_related('equipment'), pk=item_pk, session=session)

    if request.method == 'POST':
        form = InventoryItemCheckForm(request.POST, instance=item, session=session)
        if form.is_valid():
            item = form.save(commit=False)
            item.checked_by = request.user
            item.checked_at = timezone.now()
            item.save()
            inventory_date = session.period_end or session.period_start or timezone.localdate()
            EquipmentInventory.objects.create(
                equipment=item.equipment,
                legal_entity=item.equipment.legal_entity,
                location=item.actual_location or item.equipment.location,
                warehouse=item.actual_warehouse or item.equipment.warehouse,
                inventory_date=inventory_date,
                condition_status=item.condition_status,
                estimated_value=item.estimated_value,
                comment=item.comment,
                checked_by=request.user,
            )
            log_action(request, ActionLog.ACTION_UPDATE, item, message='Позиция инвентаризации проверена.')
            messages.success(request, 'Позиция инвентаризирована.')
            return redirect('inventory_session_detail', pk=session.pk)
    else:
        form = InventoryItemCheckForm(instance=item, session=session)

    return render(
        request,
        'dashboard/inventory_item_check_form.html',
        {
            'session': session,
            'item': item,
            'form': form,
        },
    )


@login_required
@require_POST
def inventory_session_confirm_view(request, pk):
    session = get_object_or_404(get_user_inventory_queryset(request.user), pk=pk)
    require_scope_edit_access(request.user, session.legal_entity, session.location)
    session.status = 'completed'
    session.completed_at = timezone.now()
    session.confirmed_at = timezone.now()
    session.confirmed_by = request.user
    session.save(update_fields=['status', 'completed_at', 'confirmed_at', 'confirmed_by'])
    log_action(request, ActionLog.ACTION_UPDATE, session, message='Акт инвентаризации подтвержден.')
    messages.success(request, 'Акт инвентаризации подтвержден.')
    return redirect('inventory_session_detail', pk=session.pk)


@login_required
def inventory_session_print_view(request, pk):
    session = get_object_or_404(get_user_inventory_queryset(request.user), pk=pk)
    items = session.items.select_related(
        'equipment',
        'equipment__warehouse',
        'actual_location',
        'actual_warehouse',
        'checked_by',
    ).order_by('equipment__name')
    return render(
        request,
        'dashboard/inventory_session_print.html',
        {
            'session': session,
            'items': items,
        },
    )


@login_required
def equipment_export_csv_view(request):
    equipment_queryset = (
        get_user_equipment_queryset(request.user).select_related(
            'legal_entity',
            'location',
            'cost_center',
            'warehouse',
            'category',
            'status',
            'responsible_user',
        )
        .order_by('name')
    )
    equipment_queryset = _apply_equipment_filters(request, equipment_queryset)
    headers, rows = _equipment_report_rows(equipment_queryset)

    log_action(
        request,
        ActionLog.ACTION_EXPORT,
        message='Экспортирован CSV оборудования.',
        metadata={'rows': equipment_queryset.count()},
    )
    return build_csv_response('equipment_export', headers, rows)


@login_required
def equipment_report_export_view(request, report_format='csv'):
    equipment_queryset = (
        get_user_equipment_queryset(request.user).select_related(
            'legal_entity',
            'location',
            'cost_center',
            'warehouse',
            'category',
            'status',
            'responsible_user',
        )
        .order_by('name')
    )
    equipment_queryset = _apply_equipment_filters(request, equipment_queryset)
    headers, rows = _equipment_report_rows(equipment_queryset)
    log_action(
        request,
        ActionLog.ACTION_EXPORT,
        message='Сформирован отчет по оборудованию.',
        metadata={'rows': equipment_queryset.count(), 'format': report_format},
    )
    return _report_response(request, 'equipment_report', 'Отчет по оборудованию', headers, rows, report_format)


@login_required
def repair_report_export_view(request, report_format='csv'):
    repair_queryset = _apply_repair_report_filters(
        request,
        get_user_repair_queryset(request.user).order_by('-created_at', '-repair_date'),
    )
    headers, rows = _repair_report_rows(repair_queryset)

    log_action(
        request,
        ActionLog.ACTION_EXPORT,
        message='Сформирован отчет по ремонтам.',
        metadata={'rows': repair_queryset.count(), 'format': report_format},
    )
    return _report_response(request, 'repair_report', 'Отчет по ремонтам', headers, rows, report_format)


def repair_report_export_csv_view(request):
    return repair_report_export_view(request, 'csv')


@login_required
def inventory_report_export_view(request, report_format='csv'):
    inventory_queryset = _apply_inventory_report_filters(
        request,
        get_user_inventory_queryset(request.user).order_by('-period_start', '-started_at'),
    )
    headers, rows = _inventory_report_rows(inventory_queryset)

    log_action(
        request,
        ActionLog.ACTION_EXPORT,
        message='Сформирован отчет по инвентаризациям.',
        metadata={'rows': inventory_queryset.count(), 'format': report_format},
    )
    return _report_response(request, 'inventory_report', 'Отчет по инвентаризации', headers, rows, report_format)


def inventory_report_export_csv_view(request):
    return inventory_report_export_view(request, 'csv')


@login_required
def movement_report_export_view(request, report_format='csv'):
    allowed_equipment = get_user_equipment_queryset(request.user)
    movements_queryset = (
        EquipmentMovement.objects.filter(equipment__in=allowed_equipment)
        .select_related(
            'equipment',
            'legal_entity',
            'from_location',
            'to_location',
            'from_cost_center',
            'to_cost_center',
            'from_warehouse',
            'to_warehouse',
            'moved_by',
        )
        .order_by('-moved_at')
    )
    movements_queryset = _apply_movement_filters(request, movements_queryset)
    headers, rows = _movement_report_rows(movements_queryset)
    log_action(
        request,
        ActionLog.ACTION_EXPORT,
        message='Сформирован отчет по перемещениям.',
        metadata={'rows': movements_queryset.count(), 'format': report_format},
    )
    return _report_response(request, 'movement_report', 'Отчет по перемещениям', headers, rows, report_format)


def _apply_equipment_access_filters(request, access_queryset):
    q = request.GET.get('q', '').strip()
    activity = request.GET.get('activity', 'active').strip()
    access_type_id = request.GET.get('access_type', '').strip()
    legal_entity_id = request.GET.get('legal_entity', '').strip()
    location_id = request.GET.get('location', '').strip()
    equipment_id = request.GET.get('equipment', '').strip()

    if q:
        access_queryset = access_queryset.filter(
            Q(title__icontains=q) |
            Q(host__icontains=q) |
            Q(url__icontains=q) |
            Q(username__icontains=q) |
            Q(description__icontains=q) |
            Q(equipment__name__icontains=q) |
            Q(equipment__serial_number__icontains=q)
        ).distinct()

    if activity == 'archived':
        access_queryset = access_queryset.filter(is_active=False)
    elif activity != 'all':
        access_queryset = access_queryset.filter(is_active=True)

    if access_type_id:
        access_queryset = access_queryset.filter(access_type_id=access_type_id)
    if legal_entity_id:
        access_queryset = access_queryset.filter(legal_entity_id=legal_entity_id)
    if location_id:
        access_queryset = access_queryset.filter(location_id=location_id)
    if equipment_id:
        access_queryset = access_queryset.filter(equipment_id=equipment_id)

    return access_queryset


def _get_equipment_access_filter_options(access_queryset):
    return {
        'access_types': AccessType.objects.filter(
            equipment_accesses__in=access_queryset,
        ).distinct().order_by('sort_order', 'name'),
        'legal_entities': LegalEntity.objects.filter(
            equipment_accesses__in=access_queryset,
        ).distinct().order_by('name'),
        'locations': Location.objects.filter(
            equipment_accesses__in=access_queryset,
        ).distinct().order_by('name'),
        'equipment_items': EquipmentAccess.objects.filter(
            id__in=access_queryset.values('id'),
            equipment__isnull=False,
        ).values(
            'equipment_id',
            'equipment__name',
        ).distinct().order_by('equipment__name'),
    }


@login_required
def equipment_access_list_view(request):
    base_access_queryset = get_user_access_queryset(request.user).order_by('title')
    access_queryset = _apply_equipment_access_filters(request, base_access_queryset)

    paginator = Paginator(access_queryset, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    for access in page_obj.object_list:
        access.can_edit = user_can_edit_access(request.user, access)

    filter_query_params = request.GET.copy()
    filter_query_params.pop('page', None)

    context = {
        'access_list': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'can_create_access': user_has_any_access_edit_permission(request.user),
        'filter_querystring': filter_query_params.urlencode(),
    }
    context.update(_get_equipment_access_filter_options(base_access_queryset))

    return render(request, 'dashboard/access_list.html', context)


@login_required
def equipment_access_export_csv_view(request):
    access_queryset = get_user_access_queryset(request.user).order_by('title')
    access_queryset = _apply_equipment_access_filters(request, access_queryset)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="accesses_export.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'ID',
        'Название',
        'Тип',
        'Оборудование',
        'Юридическое лицо',
        'Локация',
        'ЦФО',
        'Хост',
        'Порт',
        'URL',
        'Логин',
        'Есть активные секреты',
        'Активные персональные права',
        'Истекает',
        'Активен',
        'Создал',
        'Обновил',
        'Создано',
        'Обновлено',
    ])

    for access in access_queryset.prefetch_related('secrets', 'grants'):
        writer.writerow([
            access.id,
            access.title,
            access.access_type,
            access.equipment or '',
            access.legal_entity,
            access.location,
            access.cost_center or '',
            access.host,
            access.port or '',
            access.url,
            access.username,
            access.secrets.filter(is_active=True).exists(),
            access.grants.filter(is_active=True).count(),
            access.expires_at or '',
            access.is_active,
            access.created_by or '',
            access.updated_by or '',
            access.created_at,
            access.updated_at,
        ])

    log_action(
        request,
        ActionLog.ACTION_EXPORT,
        message='Экспортирован CSV доступов.',
        metadata={'rows': access_queryset.count()},
    )
    return response


@login_required
def access_user_report_view(request):
    accessible_accesses = get_user_access_queryset(request.user)
    grants = (
        AccessGrant.objects.filter(access__in=accessible_accesses, is_active=True)
        .select_related(
            'user',
            'access',
            'access__access_type',
            'access__equipment',
            'access__legal_entity',
            'access__location',
            'granted_by',
        )
        .order_by('user__username', 'access__title')
    )

    query = request.GET.get('q', '').strip()
    if query:
        grants = grants.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(access__title__icontains=query) |
            Q(access__equipment__name__icontains=query)
        ).distinct()

    paginator = Paginator(grants, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    filter_query_params = request.GET.copy()
    filter_query_params.pop('page', None)

    return render(
        request,
        'dashboard/access_user_report.html',
        {
            'grants': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'filter_querystring': filter_query_params.urlencode(),
            'query': query,
        },
    )


@login_required
def equipment_access_detail_view(request, pk):
    access = get_object_or_404(get_user_access_queryset(request.user), pk=pk)
    secrets = access.secrets.filter(is_active=True).order_by('secret_type', 'label')
    can_reveal_secret = user_can_reveal_access_secret(request.user, access)
    for secret in secrets:
        secret.can_reveal = can_reveal_secret
    return render(
        request,
        'dashboard/access_detail.html',
        {
            'access': access,
            'can_edit_access': user_can_edit_access(request.user, access),
            'can_reveal_secret': can_reveal_secret,
            'secrets': secrets,
            'secret_view_logs': access.secret_view_logs.select_related('secret', 'user')[:10],
            'change_logs': access.change_logs.select_related('secret', 'user')[:20],
            'grants': access.grants.select_related('user', 'granted_by').filter(is_active=True),
        },
    )


@login_required
def equipment_access_create_view(request):
    if not user_has_any_access_edit_permission(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        form = EquipmentAccessForm(request.POST, user=request.user)
        if form.is_valid():
            require_scope_edit_access(
                request.user,
                form.cleaned_data['legal_entity'],
                form.cleaned_data['location'],
            )
            access = form.save(commit=False)
            access.created_by = request.user
            access.updated_by = request.user
            access.save()
            log_access_change(access, request.user, 'created')
            log_action(
                request,
                ActionLog.ACTION_CREATE,
                access,
                message='Создан технический доступ.',
                metadata={'has_initial_password': bool(form.cleaned_data.get('password'))},
            )
            password = form.cleaned_data.get('password')
            if password:
                try:
                    encrypted_password = encrypt_secret(password)
                except ImproperlyConfigured as exc:
                    form.add_error('password', str(exc))
                    access.delete()
                    return render(
                        request,
                        'dashboard/access_form.html',
                        {
                            'form': form,
                            'page_title': 'Добавление доступа',
                            'submit_label': 'Сохранить',
                            'cancel_url': 'equipment_access_list',
                        },
                    )
                secret = AccessSecret.objects.create(
                    access=access,
                    secret_type='password',
                    label='Пароль',
                    encrypted_value=encrypted_password,
                    created_by=request.user,
                    updated_by=request.user,
                )
                log_access_change(access, request.user, 'secret_added', secret=secret, metadata={
                    'secret_type': secret.secret_type,
                    'label': secret.label,
                })
            messages.success(request, 'Доступ успешно добавлен.')
            return redirect('equipment_access_detail', pk=access.pk)
    else:
        form = EquipmentAccessForm(user=request.user)

    return render(
        request,
        'dashboard/access_form.html',
        {
            'form': form,
            'page_title': 'Добавление доступа',
            'submit_label': 'Сохранить',
            'cancel_url': 'equipment_access_list',
        },
    )


@login_required
def equipment_access_update_view(request, pk):
    access = get_object_or_404(get_user_access_queryset(request.user), pk=pk)
    require_access_edit_permission(request.user, access)

    if request.method == 'POST':
        form = EquipmentAccessForm(request.POST, instance=access, user=request.user)
        if form.is_valid():
            require_scope_edit_access(
                request.user,
                form.cleaned_data['legal_entity'],
                form.cleaned_data['location'],
            )
            access = form.save(commit=False)
            access.updated_by = request.user
            access.save()
            log_access_change(access, request.user, 'updated')
            log_action(request, ActionLog.ACTION_UPDATE, access, message='Обновлен технический доступ.')
            password = form.cleaned_data.get('password')
            if password:
                try:
                    encrypted_password = encrypt_secret(password)
                except ImproperlyConfigured as exc:
                    form.add_error('password', str(exc))
                    return render(
                        request,
                        'dashboard/access_form.html',
                        {
                            'form': form,
                            'access': access,
                            'page_title': 'Редактирование доступа',
                            'submit_label': 'Сохранить изменения',
                            'cancel_url': 'equipment_access_detail',
                        },
                    )
                secret = access.secrets.filter(secret_type='password', is_active=True).order_by('created_at').first()
                if secret:
                    secret.encrypted_value = encrypted_password
                    secret.label = secret.label or 'Пароль'
                    secret.updated_by = request.user
                    secret.rotated_at = timezone.now()
                    secret.save()
                    action = 'secret_rotated'
                else:
                    secret = AccessSecret.objects.create(
                        access=access,
                        secret_type='password',
                        label='Пароль',
                        encrypted_value=encrypted_password,
                        created_by=request.user,
                        updated_by=request.user,
                    )
                    action = 'secret_added'
                log_access_change(access, request.user, action, secret=secret, metadata={
                    'secret_type': secret.secret_type,
                    'label': secret.label,
                })
            messages.success(request, 'Доступ успешно обновлен.')
            return redirect('equipment_access_detail', pk=access.pk)
    else:
        form = EquipmentAccessForm(instance=access, user=request.user)

    return render(
        request,
        'dashboard/access_form.html',
        {
            'form': form,
            'access': access,
            'page_title': 'Редактирование доступа',
            'submit_label': 'Сохранить изменения',
            'cancel_url': 'equipment_access_detail',
        },
    )


@login_required
def access_secret_create_view(request, pk):
    access = get_object_or_404(get_user_access_queryset(request.user), pk=pk)
    require_access_edit_permission(request.user, access)

    if request.method == 'POST':
        form = AccessSecretForm(request.POST)
        if form.is_valid():
            secret = form.save(commit=False)
            secret.access = access
            try:
                secret.encrypted_value = encrypt_secret(form.cleaned_data['raw_value'])
            except ImproperlyConfigured as exc:
                form.add_error(None, str(exc))
                return render(
                    request,
                    'dashboard/access_secret_form.html',
                    {
                        'access': access,
                        'form': form,
                    },
                )
            secret.created_by = request.user
            secret.updated_by = request.user
            secret.save()
            log_access_change(access, request.user, 'secret_added', secret=secret, metadata={
                'secret_type': secret.secret_type,
                'label': secret.label,
            })
            log_action(
                request,
                ActionLog.ACTION_CREATE,
                access,
                message='Добавлен секрет доступа.',
                metadata={'secret_type': secret.secret_type, 'label': secret.label},
            )
            messages.success(request, 'Секрет добавлен.')
            return redirect('equipment_access_detail', pk=access.pk)
    else:
        form = AccessSecretForm()

    return render(
        request,
        'dashboard/access_secret_form.html',
        {
            'access': access,
            'form': form,
        },
    )


@login_required
def access_secret_rotate_view(request, pk, secret_pk):
    access = get_object_or_404(get_user_access_queryset(request.user), pk=pk)
    require_access_edit_permission(request.user, access)
    secret = get_object_or_404(AccessSecret, pk=secret_pk, access=access, is_active=True)

    if request.method == 'POST':
        form = AccessSecretForm(request.POST, instance=secret)
        if form.is_valid():
            secret = form.save(commit=False)
            try:
                secret.encrypted_value = encrypt_secret(form.cleaned_data['raw_value'])
            except ImproperlyConfigured as exc:
                form.add_error(None, str(exc))
                return render(
                    request,
                    'dashboard/access_secret_form.html',
                    {
                        'access': access,
                        'secret': secret,
                        'form': form,
                        'page_title': 'Ротация секрета',
                        'submit_label': 'Сохранить новый секрет',
                    },
                )
            secret.updated_by = request.user
            secret.rotated_at = timezone.now()
            secret.save()
            log_access_change(access, request.user, 'secret_rotated', secret=secret, metadata={
                'secret_type': secret.secret_type,
                'label': secret.label,
            })
            log_action(
                request,
                ActionLog.ACTION_UPDATE,
                access,
                message='Секрет доступа обновлен.',
                metadata={'secret_type': secret.secret_type, 'label': secret.label},
            )
            messages.success(request, 'Секрет обновлен.')
            return redirect('equipment_access_detail', pk=access.pk)
    else:
        form = AccessSecretForm(instance=secret)

    return render(
        request,
        'dashboard/access_secret_form.html',
        {
            'access': access,
            'secret': secret,
            'form': form,
            'page_title': 'Ротация секрета',
            'submit_label': 'Сохранить новый секрет',
        },
    )


@login_required
@require_POST
def access_secret_archive_view(request, pk, secret_pk):
    access = get_object_or_404(get_user_access_queryset(request.user), pk=pk)
    require_access_edit_permission(request.user, access)
    secret = get_object_or_404(AccessSecret, pk=secret_pk, access=access, is_active=True)
    secret.is_active = False
    secret.updated_by = request.user
    secret.save(update_fields=['is_active', 'updated_by', 'updated_at'])
    log_access_change(access, request.user, 'secret_archived', secret=secret, metadata={
        'secret_type': secret.secret_type,
        'label': secret.label,
    })
    log_action(
        request,
        ActionLog.ACTION_ARCHIVE,
        access,
        message='Секрет доступа архивирован.',
        metadata={'secret_type': secret.secret_type, 'label': secret.label},
    )
    messages.success(request, 'Секрет отправлен в архив.')
    return redirect('equipment_access_detail', pk=access.pk)


@login_required
def access_grant_create_view(request, pk):
    access = get_object_or_404(get_user_access_queryset(request.user), pk=pk)
    require_access_edit_permission(request.user, access)

    if request.method == 'POST':
        form = AccessGrantForm(request.POST)
        if form.is_valid():
            grant, _ = AccessGrant.objects.update_or_create(
                access=access,
                user=form.cleaned_data['user'],
                defaults={
                    'level': form.cleaned_data['level'],
                    'expires_at': form.cleaned_data['expires_at'],
                    'is_active': form.cleaned_data['is_active'],
                    'granted_by': request.user,
                },
            )
            log_access_change(access, request.user, 'grant_added', metadata={
                'user': grant.user.username,
                'level': grant.level,
                'expires_at': grant.expires_at.isoformat() if grant.expires_at else None,
            })
            log_action(
                request,
                ActionLog.ACTION_CREATE,
                access,
                message='Добавлен персональный грант доступа.',
                metadata={'user': grant.user.username, 'level': grant.level},
            )
            messages.success(request, 'Грант добавлен.')
            return redirect('equipment_access_detail', pk=access.pk)
    else:
        form = AccessGrantForm()

    return render(
        request,
        'dashboard/access_grant_form.html',
        {
            'access': access,
            'form': form,
        },
    )


@login_required
@require_POST
def access_grant_archive_view(request, pk, grant_pk):
    access = get_object_or_404(get_user_access_queryset(request.user), pk=pk)
    require_access_edit_permission(request.user, access)
    grant = get_object_or_404(AccessGrant, pk=grant_pk, access=access, is_active=True)
    grant.is_active = False
    grant.save(update_fields=['is_active'])
    log_access_change(access, request.user, 'grant_archived', metadata={
        'user': grant.user.username,
        'level': grant.level,
    })
    log_action(
        request,
        ActionLog.ACTION_ARCHIVE,
        access,
        message='Персональный грант доступа архивирован.',
        metadata={'user': grant.user.username, 'level': grant.level},
    )
    messages.success(request, 'Грант отправлен в архив.')
    return redirect('equipment_access_detail', pk=access.pk)


@login_required
@require_POST
def access_secret_reveal_view(request, pk, secret_pk):
    access = get_object_or_404(get_user_access_queryset(request.user), pk=pk)
    secret = get_object_or_404(AccessSecret.objects.select_related('access'), pk=secret_pk, access=access, is_active=True)
    revealed_value = reveal_access_secret(
        secret,
        request.user,
        request,
        user_can_reveal_access_secret(request.user, access),
    )
    log_action(
        request,
        ActionLog.ACTION_REVEAL,
        access,
        message='Запрошено раскрытие секрета доступа.',
        metadata={'secret_type': secret.secret_type, 'label': secret.label},
    )
    secrets = access.secrets.filter(is_active=True).order_by('secret_type', 'label')
    can_reveal_secret = user_can_reveal_access_secret(request.user, access)
    for item in secrets:
        item.can_reveal = can_reveal_secret

    return render(
        request,
        'dashboard/access_detail.html',
        {
            'access': access,
            'can_edit_access': user_can_edit_access(request.user, access),
            'can_reveal_secret': can_reveal_secret,
            'secrets': secrets,
            'secret_view_logs': access.secret_view_logs.select_related('secret', 'user')[:10],
            'change_logs': access.change_logs.select_related('secret', 'user')[:20],
            'grants': access.grants.select_related('user', 'granted_by').filter(is_active=True),
            'revealed_secret': {
                'id': secret.id,
                'label': secret.label,
                'value': revealed_value,
            },
        },
    )


@login_required
@require_POST
def equipment_access_archive_view(request, pk):
    access = get_object_or_404(get_user_access_queryset(request.user), pk=pk)
    require_access_edit_permission(request.user, access)
    access.is_active = False
    access.updated_by = request.user
    access.save(update_fields=['is_active', 'updated_by', 'updated_at'])
    log_access_change(access, request.user, 'archived')
    log_action(request, ActionLog.ACTION_ARCHIVE, access, message='Технический доступ архивирован.')
    messages.success(request, 'Доступ отправлен в архив.')
    return redirect('equipment_access_detail', pk=access.pk)


@login_required
def qr_print_pdf_view(request):
    equipment_queryset = (
        get_user_equipment_queryset(request.user).select_related(
            'legal_entity',
            'location',
            'cost_center',
            'warehouse',
            'category',
            'status',
        )
        .order_by('name')
    )
    equipment_queryset = _apply_equipment_filters(request, equipment_queryset)

    selected_ids = request.GET.getlist('ids')
    if selected_ids:
        equipment_queryset = equipment_queryset.filter(id__in=selected_ids)

    equipment_items = list(equipment_queryset[:200])
    for equipment in equipment_items:
        create_qr_tag_for_equipment(equipment, assigned_by=request.user, request=request)

    response = HttpResponse(
        build_qr_labels_pdf(equipment_items),
        content_type='application/pdf',
    )
    response['Content-Disposition'] = 'attachment; filename="equipment_qr_labels.pdf"'
    log_action(
        request,
        ActionLog.ACTION_EXPORT,
        message='Сформирован PDF QR-этикеток.',
        metadata={'rows': len(equipment_items)},
    )
    return response


@login_required
def equipment_detail_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )

    context = {
        'equipment': equipment,
        'can_edit_equipment': user_can_edit_equipment(request.user, equipment),
        'tags': equipment.tags.filter(is_active=True).order_by('tag_type', 'code'),
        'movements': equipment.movements.select_related(
            'from_location',
            'to_location',
            'from_cost_center',
            'to_cost_center',
            'from_warehouse',
            'to_warehouse',
            'moved_by'
        ).order_by('-moved_at')[:20],
        'maintenance_logs': equipment.maintenance_logs.order_by('-performed_at')[:20],
        'repairs': equipment.repairs.select_related(
            'created_by',
            'accepted_by',
            'assigned_to',
        ).order_by('-created_at', '-repair_date')[:20],
        'can_manage_repairs': user_can_manage_repairs(request.user),
        'inventory_checks': equipment.inventory_checks.select_related(
            'location',
            'warehouse',
            'checked_by',
        ).order_by('-inventory_date', '-created_at')[:20],
        'notes': equipment.notes.select_related('created_by').order_by('-created_at')[:20],
        'requisites': equipment.requisites.filter(is_active=True).select_related(
            'created_by',
            'updated_by',
        ).order_by('requisite_type', 'name', 'value'),
        'files': equipment.files.filter(is_active=True).select_related('uploaded_by').order_by('-uploaded_at'),
        'photos': equipment.photos.filter(is_active=True).select_related('uploaded_by').order_by(
            '-is_primary',
            '-uploaded_at',
        ),
        'active_inventory_sessions': InventorySession.objects.filter(
            status__in=['draft', 'in_progress'],
            legal_entity=equipment.legal_entity,
            location=equipment.location,
        ).order_by('-period_start', '-started_at', 'name'),
        'note_form': EquipmentNoteForm(),
    }
    return render(request, 'dashboard/equipment_detail.html', context)


@login_required
@require_POST
def equipment_note_create_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    form = EquipmentNoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.equipment = equipment
        note.created_by = request.user
        note.save()
        log_action(request, ActionLog.ACTION_CREATE, note, message='Добавлена заметка к оборудованию.')
        messages.success(request, 'Заметка добавлена.')
    else:
        messages.error(request, 'Не удалось добавить заметку.')

    return redirect('equipment_detail', pk=equipment.pk)


@login_required
def equipment_requisite_create_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    if request.method == 'POST':
        form = EquipmentRequisiteForm(request.POST)
        if form.is_valid():
            requisite = form.save(commit=False)
            requisite.equipment = equipment
            requisite.created_by = request.user
            requisite.updated_by = request.user
            requisite.save()
            log_action(request, ActionLog.ACTION_CREATE, requisite, message='Добавлен реквизит оборудования.')
            messages.success(request, 'Реквизит добавлен.')
            return redirect('equipment_detail', pk=equipment.pk)
    else:
        form = EquipmentRequisiteForm()

    return render(
        request,
        'dashboard/equipment_requisite_form.html',
        {
            'equipment': equipment,
            'form': form,
        }
    )


@login_required
@require_POST
def equipment_requisite_archive_view(request, pk, requisite_pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    requisite = get_object_or_404(
        EquipmentRequisite,
        pk=requisite_pk,
        equipment=equipment,
        is_active=True,
    )
    requisite.is_active = False
    requisite.updated_by = request.user
    requisite.save(update_fields=['is_active', 'updated_by', 'updated_at'])
    log_action(request, ActionLog.ACTION_ARCHIVE, requisite, message='Реквизит оборудования архивирован.')
    messages.success(request, 'Реквизит архивирован.')
    return redirect('equipment_detail', pk=equipment.pk)


@login_required
def equipment_file_create_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    if request.method == 'POST':
        form = EquipmentFileForm(request.POST, request.FILES)
        if form.is_valid():
            equipment_file = form.save(commit=False)
            equipment_file.equipment = equipment
            equipment_file.uploaded_by = request.user
            equipment_file.save()
            log_action(request, ActionLog.ACTION_CREATE, equipment_file, message='Добавлен файл оборудования.')
            messages.success(request, 'Файл добавлен.')
            return redirect('equipment_detail', pk=equipment.pk)
    else:
        form = EquipmentFileForm()

    return render(
        request,
        'dashboard/equipment_file_form.html',
        {
            'equipment': equipment,
            'form': form,
        }
    )


@login_required
@require_POST
def equipment_file_archive_view(request, pk, file_pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    equipment_file = get_object_or_404(
        EquipmentFile,
        pk=file_pk,
        equipment=equipment,
        is_active=True,
    )
    equipment_file.is_active = False
    equipment_file.save(update_fields=['is_active'])
    log_action(request, ActionLog.ACTION_ARCHIVE, equipment_file, message='Файл оборудования архивирован.')
    messages.success(request, 'Файл архивирован.')
    return redirect('equipment_detail', pk=equipment.pk)


@login_required
def equipment_photo_create_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    if request.method == 'POST':
        form = EquipmentPhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.equipment = equipment
            photo.uploaded_by = request.user
            photo.save()
            log_action(request, ActionLog.ACTION_CREATE, photo, message='Добавлено фото оборудования.')
            messages.success(request, 'Фото добавлено.')
            return redirect('equipment_detail', pk=equipment.pk)
    else:
        form = EquipmentPhotoForm()

    return render(
        request,
        'dashboard/equipment_photo_form.html',
        {
            'equipment': equipment,
            'form': form,
        }
    )


@login_required
@require_POST
def equipment_photo_archive_view(request, pk, photo_pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    photo = get_object_or_404(
        EquipmentPhoto,
        pk=photo_pk,
        equipment=equipment,
        is_active=True,
    )
    photo.is_active = False
    photo.save(update_fields=['is_active'])
    log_action(request, ActionLog.ACTION_ARCHIVE, photo, message='Фото оборудования архивировано.')
    messages.success(request, 'Фото архивировано.')
    return redirect('equipment_detail', pk=equipment.pk)


@login_required
@require_POST
def equipment_photo_make_primary_view(request, pk, photo_pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    photo = get_object_or_404(
        EquipmentPhoto,
        pk=photo_pk,
        equipment=equipment,
        is_active=True,
    )
    photo.is_primary = True
    photo.save(update_fields=['is_primary'])
    log_action(request, ActionLog.ACTION_UPDATE, photo, message='Фото оборудования назначено основным.')
    messages.success(request, 'Основное фото обновлено.')
    return redirect('equipment_detail', pk=equipment.pk)


@login_required
def repair_request_list_view(request):
    queryset = get_user_repair_queryset(request.user).order_by('-created_at', '-repair_date')
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        queryset = queryset.filter(
            Q(equipment__name__icontains=query) |
            Q(equipment__serial_number__icontains=query) |
            Q(equipment__inventory_number__icontains=query) |
            Q(description__icontains=query) |
            Q(resolution__icontains=query)
        )
    if status:
        queryset = queryset.filter(status=status)

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    filter_query_params = request.GET.copy()
    filter_query_params.pop('page', None)

    return render(
        request,
        'dashboard/repair_request_list.html',
        {
            'repairs': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'filter_query': filter_query_params.urlencode(),
            'query': query,
            'selected_status': status,
            'status_choices': EquipmentRepair.STATUS_CHOICES,
            'can_manage_repairs': user_can_manage_repairs(request.user),
        },
    )


@login_required
def equipment_repair_create_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    if request.method == 'POST':
        form = EquipmentRepairForm(request.POST)
        if form.is_valid():
            repair = form.save(commit=False)
            repair.equipment = equipment
            repair.legal_entity = equipment.legal_entity
            repair.repair_date = timezone.localdate()
            repair.status = EquipmentRepair.STATUS_REQUESTED
            repair.created_by = request.user
            if any(request.POST.get(field) for field in ['repair_date', 'cost', 'contractor']):
                repair.status = EquipmentRepair.STATUS_COMPLETED
                repair.repair_date = parse_date(request.POST.get('repair_date', '')) or repair.repair_date
                repair.cost = request.POST.get('cost') or None
                repair.contractor = request.POST.get('contractor', '')
                repair.completed_at = timezone.now()
                repair.accepted_by = request.user
                repair.accepted_at = repair.completed_at
            repair.save()
            update_equipment_status_by_code(equipment, 'REPAIR')
            log_action(request, ActionLog.ACTION_CREATE, repair, message='Добавлена запись ремонта оборудования.')
            messages.success(request, 'Ремонт добавлен.')
            return redirect('equipment_detail', pk=equipment.pk)
    else:
        form = EquipmentRepairForm()

    return render(
        request,
        'dashboard/equipment_repair_form.html',
        {
            'equipment': equipment,
            'form': form,
        }
    )


@login_required
def equipment_repair_update_view(request, pk):
    repair = get_object_or_404(get_user_repair_queryset(request.user), pk=pk)
    require_repair_manage_access(request.user)

    previous_status = repair.status
    if request.method == 'POST':
        form = EquipmentRepairStatusForm(request.POST, instance=repair)
        if form.is_valid():
            repair = form.save(commit=False)
            now = timezone.now()
            if repair.status != previous_status:
                repair.status_changed_at = now
            if repair.status in [EquipmentRepair.STATUS_ACCEPTED, EquipmentRepair.STATUS_IN_PROGRESS] and not repair.accepted_by:
                repair.accepted_by = request.user
                repair.accepted_at = now
            if repair.status == EquipmentRepair.STATUS_IN_PROGRESS and not repair.started_at:
                repair.started_at = now
            if repair.status == EquipmentRepair.STATUS_COMPLETED:
                if not repair.completed_at:
                    repair.completed_at = now
                if not repair.repair_date:
                    repair.repair_date = timezone.localdate()
            repair.save()

            if repair.status in [
                EquipmentRepair.STATUS_REQUESTED,
                EquipmentRepair.STATUS_ACCEPTED,
                EquipmentRepair.STATUS_IN_PROGRESS,
                EquipmentRepair.STATUS_WAITING_PARTS,
            ]:
                update_equipment_status_by_code(repair.equipment, 'REPAIR')
            elif repair.status in [EquipmentRepair.STATUS_COMPLETED, EquipmentRepair.STATUS_CANCELLED]:
                update_equipment_status_by_code(repair.equipment, 'WORKING')

            log_action(request, ActionLog.ACTION_UPDATE, repair, message='Обновлен статус заявки на ремонт.')
            messages.success(request, 'Статус ремонта обновлен.')
            return redirect('equipment_detail', pk=repair.equipment.pk)
    else:
        form = EquipmentRepairStatusForm(instance=repair)

    return render(
        request,
        'dashboard/equipment_repair_status_form.html',
        {
            'repair': repair,
            'equipment': repair.equipment,
            'form': form,
        },
    )


@login_required
def equipment_inventory_create_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    if request.method == 'POST':
        form = EquipmentInventoryForm(request.POST)
        if form.is_valid():
            inventory = form.save(commit=False)
            inventory.equipment = equipment
            inventory.legal_entity = equipment.legal_entity
            inventory.location = equipment.location
            inventory.warehouse = equipment.warehouse
            inventory.checked_by = request.user
            inventory.save()
            log_action(request, ActionLog.ACTION_CREATE, inventory, message='Добавлена запись инвентаризации оборудования.')
            messages.success(request, 'Инвентаризация добавлена.')
            return redirect('equipment_detail', pk=equipment.pk)
    else:
        form = EquipmentInventoryForm(initial={
            'estimated_value': equipment.estimated_current_value,
        })

    return render(
        request,
        'dashboard/equipment_inventory_form.html',
        {
            'equipment': equipment,
            'form': form,
        }
    )


@login_required
def equipment_add_to_inventory_session_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    if request.method == 'POST':
        form = EquipmentInventorySessionSelectForm(request.POST, equipment=equipment)
        if form.is_valid():
            session = form.cleaned_data['session']
            require_scope_edit_access(request.user, session.legal_entity, session.location)
            item, _ = InventoryItem.objects.get_or_create(
                session=session,
                equipment=equipment,
                defaults={
                    'actual_location': equipment.location,
                    'actual_warehouse': equipment.warehouse,
                    'estimated_value': equipment.estimated_current_value,
                },
            )
            item.found = True
            item.checked_by = request.user
            item.checked_at = timezone.now()
            item.save(update_fields=['found', 'checked_by', 'checked_at'])
            messages.success(request, 'Оборудование добавлено в инвентаризацию.')
            return redirect('inventory_session_detail', pk=session.pk)
    else:
        form = EquipmentInventorySessionSelectForm(equipment=equipment)

    return render(
        request,
        'dashboard/equipment_inventory_session_select.html',
        {
            'equipment': equipment,
            'form': form,
        },
    )


@login_required
def tag_redirect_view(request, code):
    tag = get_object_or_404(
        EquipmentTag.objects.select_related('equipment', 'legal_entity'),
        code=code,
        is_active=True
    )

    equipment = tag.equipment

    allowed_qs = get_user_equipment_queryset(request.user)
    if not allowed_qs.filter(pk=equipment.pk).exists():
        return render(request, 'dashboard/access_denied.html', status=403)

    # 👇 добавляем mobile режим
    mobile = request.GET.get('mobile')

    if mobile == '1':
        return redirect(f'/app/equipment/{equipment.pk}/?mobile=1')

    return redirect('equipment_detail', pk=equipment.pk)

@login_required
def qr_print_view(request):
    equipment_qs = get_user_equipment_queryset(request.user)

    selected_ids = request.GET.getlist('ids')

    if selected_ids:
        equipment_qs = equipment_qs.filter(id__in=selected_ids)

    tags = []
    for eq in equipment_qs.prefetch_related('tags'):
        for tag in eq.tags.filter(tag_type='QR', is_active=True):
            tags.append({
                'equipment': eq,
                'tag': tag
            })

    context = {
        'items': tags
    }

    return render(request, 'dashboard/qr_print.html', context)

@login_required
def equipment_move_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    if request.method == 'POST':
        form = EquipmentMoveForm(request.POST, user=request.user, equipment=equipment)
        if form.is_valid():
            legal_entity = form.cleaned_data['legal_entity']
            to_location = form.cleaned_data['to_location']
            to_cost_center = form.cleaned_data['to_cost_center']
            to_warehouse = form.cleaned_data['to_warehouse']
            comment = form.cleaned_data['comment']
            require_scope_edit_access(request.user, legal_entity, to_location)
            from_location = equipment.location
            from_cost_center = equipment.cost_center
            from_warehouse = equipment.warehouse

            with transaction.atomic():
                movement = EquipmentMovement.objects.create(
                    equipment=equipment,
                    legal_entity=legal_entity,
                    from_location=from_location,
                    to_location=to_location,
                    from_cost_center=from_cost_center,
                    to_cost_center=to_cost_center,
                    from_warehouse=from_warehouse,
                    to_warehouse=to_warehouse,
                    moved_by=request.user,
                    comment=comment,
                )

                equipment.legal_entity = legal_entity
                equipment.location = to_location
                equipment.cost_center = to_cost_center
                equipment.warehouse = to_warehouse
                equipment.save(update_fields=[
                    'legal_entity',
                    'location',
                    'cost_center',
                    'warehouse',
                    'updated_at',
                ])
                log_action(
                    request,
                    ActionLog.ACTION_MOVE,
                    equipment,
                    message='Оборудование перемещено.',
                    metadata={
                        'movement_id': str(movement.pk),
                        'from_location': str(from_location) if from_location else '',
                        'to_location': str(to_location) if to_location else '',
                        'from_warehouse': str(from_warehouse) if from_warehouse else '',
                        'to_warehouse': str(to_warehouse) if to_warehouse else '',
                    },
                )

            messages.success(request, 'Оборудование успешно перемещено.')
            return redirect('equipment_detail', pk=equipment.pk)
    else:
        form = EquipmentMoveForm(user=request.user, equipment=equipment)

    context = {
        'equipment': equipment,
        'form': form,
    }
    return render(request, 'dashboard/equipment_move.html', context)

@login_required
def equipment_create_view(request):
    if not user_has_any_edit_access(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        form = EquipmentCreateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            require_scope_edit_access(
                request.user,
                form.cleaned_data['legal_entity'],
                form.cleaned_data['location'],
            )
            equipment = form.save()
            create_qr_tag_for_equipment(equipment, assigned_by=request.user, request=request)
            log_action(request, ActionLog.ACTION_CREATE, equipment, message='Создана карточка оборудования.')
            messages.success(request, 'Оборудование успешно добавлено.')
            return redirect('equipment_detail', pk=equipment.pk)
    else:
        form = EquipmentCreateForm(user=request.user)

    return render(
        request,
        'dashboard/equipment_create.html',
        {
            'form': form,
            'page_title': 'Добавление оборудования',
            'submit_label': 'Сохранить',
            'cancel_url': 'equipment_list',
        }
    )


@login_required
def equipment_update_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)

    if request.method == 'POST':
        form = EquipmentCreateForm(request.POST, request.FILES, instance=equipment, user=request.user)
        if form.is_valid():
            require_scope_edit_access(
                request.user,
                form.cleaned_data['legal_entity'],
                form.cleaned_data['location'],
            )
            equipment = form.save()
            log_action(request, ActionLog.ACTION_UPDATE, equipment, message='Обновлена карточка оборудования.')
            messages.success(request, 'Оборудование успешно обновлено.')
            return redirect('equipment_detail', pk=equipment.pk)
    else:
        form = EquipmentCreateForm(instance=equipment, user=request.user)

    return render(
        request,
        'dashboard/equipment_create.html',
        {
            'form': form,
            'equipment': equipment,
            'page_title': 'Редактирование оборудования',
            'submit_label': 'Сохранить изменения',
            'cancel_url': 'equipment_detail',
        }
    )


@login_required
@require_POST
def equipment_archive_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)
    equipment.is_active = False
    equipment.save(update_fields=['is_active', 'updated_at'])
    log_action(request, ActionLog.ACTION_ARCHIVE, equipment, message='Оборудование отправлено в архив.')
    messages.success(request, 'Оборудование отправлено в архив.')
    return redirect('equipment_detail', pk=equipment.pk)


@login_required
@require_POST
def equipment_regenerate_qr_view(request, pk):
    equipment = get_object_or_404(
        get_user_equipment_queryset(request.user),
        pk=pk
    )
    require_equipment_edit_access(request.user, equipment)
    regenerate_qr_tag_for_equipment(equipment, assigned_by=request.user, request=request)
    log_action(request, ActionLog.ACTION_UPDATE, equipment, message='QR-код оборудования обновлен.')
    messages.success(request, 'QR-код успешно обновлен.')
    return redirect('equipment_detail', pk=equipment.pk)
