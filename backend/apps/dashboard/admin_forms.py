from django import forms

from apps.equipment.models import EquipmentCategory, EquipmentStatus
from apps.locations.models import Location
from apps.organizations.models import CostCenter, LegalEntity, UserLegalEntityAccess, UserLocationAccess
from apps.users.models import User
from apps.warehouses.models import Warehouse

from .access import (
    get_accessible_cost_centers,
    get_accessible_legal_entities,
    get_accessible_locations,
    user_can_admin_global_directories,
)


class AdminFormMixin:
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class LegalEntityAdminForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = LegalEntity
        fields = ['name', 'short_name', 'tax_id', 'is_active']
        labels = {
            'name': 'Название',
            'short_name': 'Краткое название',
            'tax_id': 'ИНН',
            'is_active': 'Активно',
        }


class LocationAdminForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'is_active']


class CostCenterAdminForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = CostCenter
        fields = ['legal_entity', 'location', 'name', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not user_can_admin_global_directories(self.user):
            self.fields['legal_entity'].queryset = get_accessible_legal_entities(self.user).order_by('name')
            self.fields['location'].queryset = get_accessible_locations(self.user).order_by('name')


class WarehouseAdminForm(AdminFormMixin, forms.ModelForm):
    legal_entity = forms.ModelChoiceField(
        queryset=LegalEntity.objects.filter(is_active=True).order_by('name'),
        label='Юридическое лицо',
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True).order_by('name'),
        label='Локация',
    )

    class Meta:
        model = Warehouse
        fields = ['legal_entity', 'location', 'cost_center', 'name', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not user_can_admin_global_directories(self.user):
            self.fields['legal_entity'].queryset = get_accessible_legal_entities(self.user).order_by('name')
            self.fields['location'].queryset = get_accessible_locations(self.user).order_by('name')
        self.fields['cost_center'].queryset = CostCenter.objects.select_related(
            'legal_entity',
            'location',
        ).filter(is_active=True).order_by('name')
        if not user_can_admin_global_directories(self.user):
            self.fields['cost_center'].queryset = get_accessible_cost_centers(self.user).order_by('name')

        if self.instance and self.instance.pk and self.instance.cost_center_id:
            self.fields['legal_entity'].initial = self.instance.cost_center.legal_entity
            self.fields['location'].initial = self.instance.cost_center.location

    def clean(self):
        cleaned_data = super().clean()
        legal_entity = cleaned_data.get('legal_entity')
        location = cleaned_data.get('location')
        cost_center = cleaned_data.get('cost_center')

        if legal_entity and cost_center and cost_center.legal_entity_id != legal_entity.id:
            self.add_error('cost_center', 'ЦФО относится к другому юридическому лицу.')
        if location and cost_center and cost_center.location_id != location.id:
            self.add_error('cost_center', 'ЦФО относится к другой локации.')

        return cleaned_data


class EquipmentCategoryAdminForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = EquipmentCategory
        fields = ['name']


class EquipmentStatusAdminForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = EquipmentStatus
        fields = ['name', 'code']


class UserManagementForm(AdminFormMixin, forms.ModelForm):
    ACCESS_FIELDSETS = {
        'Основные разделы': [
            'can_view_equipment',
            'can_edit_equipment',
            'can_view_movements',
            'can_export_data',
        ],
        'Доступы и секреты': [
            'can_view_accesses',
            'can_edit_accesses',
            'can_reveal_access_secrets',
        ],
        'Администрирование': [
            'can_view_admin_panel',
            'can_manage_directories',
            'can_manage_users',
            'can_view_audit_log',
        ],
    }
    PROFILE_FIELDS = [
        'username',
        'first_name',
        'last_name',
        'email',
        'phone',
        'job_title',
        'role',
        'is_active',
        'is_staff',
        'is_global_access',
        'password',
    ]
    password = forms.CharField(
        label='Новый пароль',
        required=False,
        widget=forms.PasswordInput,
        help_text='Оставьте пустым, чтобы не менять пароль.',
    )
    scope_access_level = forms.ChoiceField(
        label='Уровень доступа к области',
        required=False,
        choices=UserLegalEntityAccess.ACCESS_LEVEL_CHOICES,
        initial='view',
        help_text='Применяется к выбранным юрлицам и локациям.',
    )
    legal_entities = forms.ModelMultipleChoiceField(
        label='Юридические лица',
        required=False,
        queryset=LegalEntity.objects.filter(is_active=True).order_by('name'),
        widget=forms.CheckboxSelectMultiple,
    )
    locations = forms.ModelMultipleChoiceField(
        label='Локации',
        required=False,
        queryset=Location.objects.filter(is_active=True).order_by('name'),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'phone',
            'job_title',
            'role',
            'is_active',
            'is_staff',
            'is_global_access',
            'password',
            'can_view_equipment',
            'can_edit_equipment',
            'can_view_movements',
            'can_view_accesses',
            'can_edit_accesses',
            'can_reveal_access_secrets',
            'can_export_data',
            'can_view_admin_panel',
            'can_manage_directories',
            'can_manage_users',
            'can_view_audit_log',
            'scope_access_level',
            'legal_entities',
            'locations',
        ]
        labels = {
            'username': 'Логин',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'email': 'Электронная почта',
            'phone': 'Телефон',
            'job_title': 'Должность',
            'role': 'Роль',
            'is_active': 'Активен',
            'is_staff': 'Доступ к Django-админке',
            'is_global_access': 'Глобальный доступ',
            'can_view_equipment': 'Просмотр оборудования',
            'can_edit_equipment': 'Создание и редактирование оборудования',
            'can_view_movements': 'Просмотр перемещений',
            'can_view_accesses': 'Просмотр раздела доступов',
            'can_edit_accesses': 'Создание и редактирование доступов',
            'can_reveal_access_secrets': 'Раскрытие секретов доступов',
            'can_export_data': 'Экспорт CSV/PDF',
            'can_view_admin_panel': 'Доступ к внутренней админ-панели',
            'can_manage_directories': 'Управление справочниками',
            'can_manage_users': 'Управление пользователями и правами',
            'can_view_audit_log': 'Просмотр журнала действий',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and not self.instance._state.adding:
            self.fields['legal_entities'].initial = self.instance.legal_entity_accesses.filter(
                allow_all_locations=True,
            ).values_list('legal_entity_id', flat=True)
            self.fields['locations'].initial = self.instance.location_accesses.values_list('location_id', flat=True)
            self.fields['scope_access_level'].initial = self._get_initial_scope_access_level()

    def _get_initial_scope_access_level(self):
        levels = set(
            self.instance.legal_entity_accesses.filter(
                allow_all_locations=True,
            ).values_list('access_level', flat=True)
        )
        levels.update(self.instance.location_accesses.values_list('access_level', flat=True))
        for level in ('admin', 'edit', 'view'):
            if level in levels:
                return level
        return 'view'

    def save(self, commit=True):
        old_password = None
        if self.instance and self.instance.pk and not self.instance._state.adding:
            old_password = User.objects.only('password').get(pk=self.instance.pk).password

        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        elif old_password is not None:
            user.password = old_password
        else:
            user.set_unusable_password()

        if commit:
            user.save()
            self.save_m2m()
            self._sync_scope_access(user)
        return user

    def _sync_scope_access(self, user):
        access_level = self.cleaned_data.get('scope_access_level') or 'view'
        legal_entities = list(self.cleaned_data.get('legal_entities') or [])
        locations = list(self.cleaned_data.get('locations') or [])
        legal_entity_ids = [item.pk for item in legal_entities]
        location_ids = [item.pk for item in locations]

        user.legal_entity_accesses.filter(allow_all_locations=True).exclude(
            legal_entity_id__in=legal_entity_ids,
        ).delete()
        user.location_accesses.exclude(location_id__in=location_ids).delete()

        for legal_entity in legal_entities:
            UserLegalEntityAccess.objects.update_or_create(
                user=user,
                legal_entity=legal_entity,
                defaults={
                    'access_level': access_level,
                    'allow_all_locations': True,
                },
            )
        for location in locations:
            UserLocationAccess.objects.update_or_create(
                user=user,
                location=location,
                defaults={'access_level': access_level},
            )


class UserLegalEntityAccessAdminForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = UserLegalEntityAccess
        fields = ['user', 'legal_entity', 'access_level', 'allow_all_locations']


class UserLocationAccessAdminForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = UserLocationAccess
        fields = ['user', 'location', 'access_level']
