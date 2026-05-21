from django import forms
from django.forms import ModelChoiceField

from apps.equipment.models import (
    Equipment,
    EquipmentCategory,
    EquipmentFile,
    EquipmentNote,
    EquipmentPhoto,
    EquipmentRequisite,
    EquipmentStatus,
)
from apps.inventory.models import EquipmentInventory, EquipmentRepair, InventoryItem, InventorySession
from apps.locations.models import Location
from apps.organizations.models import LegalEntity, CostCenter
from apps.users.models import User
from apps.warehouses.models import Warehouse

from .access import (
    get_editable_cost_centers,
    get_editable_legal_entities,
    get_editable_locations,
    get_user_equipment_queryset,
)


class EquipmentInventoryChoiceField(ModelChoiceField):
    def label_from_instance(self, obj):
        parts = [obj.name]
        if obj.inventory_number:
            parts.append(f'инв. {obj.inventory_number}')
        if obj.legal_entity:
            parts.append(str(obj.legal_entity))
        if obj.warehouse:
            parts.append(str(obj.warehouse))
        return ' · '.join(parts)


def _get_warehouse_name_choices():
    names = (
        Warehouse.objects
        .order_by('name')
        .values_list('name', flat=True)
        .distinct()
    )
    return [('', 'Выберите склад')] + [(name, name) for name in names]


class EquipmentCreateForm(forms.ModelForm):
    warehouse = forms.ChoiceField(label='Склад')

    class Meta:
        model = Equipment
        fields = [
            'legal_entity',
            'location',
            'cost_center',
            'warehouse',
            'category',
            'status',
            'name',
            'brand',
            'model',
            'serial_number',
            'inventory_number',
            'purchase_date',
            'warranty_until',
            'price',
            'estimated_current_value',
            'placement_zone',
            'last_inventory_date',
            'last_repair_date',
            'responsible_user',
            'comment',
            'is_active',
        ]
        labels = {
            'legal_entity': 'Юридическое лицо',
            'location': 'Локация',
            'cost_center': 'ЦФО',
            'warehouse': 'Склад',
            'category': 'Категория',
            'status': 'Статус',
            'name': 'Наименование',
            'brand': 'Бренд',
            'model': 'Модель',
            'serial_number': 'Серийный номер',
            'inventory_number': 'Инвентарный номер',
            'purchase_date': 'Дата покупки',
            'warranty_until': 'Гарантия до',
            'price': 'Цена приобретения',
            'estimated_current_value': 'Оценочная текущая стоимость',
            'placement_zone': 'Зона размещения',
            'last_inventory_date': 'Дата последней инвентаризации',
            'last_repair_date': 'Дата последнего ремонта',
            'responsible_user': 'Ответственный',
            'comment': 'Комментарий',
            'is_active': 'Активно',
        }
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'warranty_until': forms.DateInput(attrs={'type': 'date'}),
            'last_inventory_date': forms.DateInput(attrs={'type': 'date'}),
            'last_repair_date': forms.DateInput(attrs={'type': 'date'}),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['legal_entity'].queryset = get_editable_legal_entities(self.user).order_by('name')
        self.fields['location'].queryset = get_editable_locations(self.user).order_by('name')
        self.fields['cost_center'].queryset = get_editable_cost_centers(self.user).order_by('name')
        self.fields['warehouse'].choices = _get_warehouse_name_choices()
        self.fields['category'].queryset = EquipmentCategory.objects.all().order_by('name')
        self.fields['status'].queryset = EquipmentStatus.objects.all().order_by('name')
        self.fields['responsible_user'].queryset = User.objects.filter(is_active=True).order_by('username')

        self.fields['legal_entity'].empty_label = 'Выберите юридическое лицо'
        self.fields['location'].empty_label = 'Выберите локацию'
        self.fields['cost_center'].empty_label = 'Выберите ЦФО'
        self.fields['category'].empty_label = 'Выберите категорию'
        self.fields['status'].empty_label = 'Выберите статус'
        self.fields['responsible_user'].empty_label = 'Выберите пользователя'

        if self.instance and self.instance.pk and self.instance.warehouse_id:
            self.fields['warehouse'].initial = self.instance.warehouse.name

        for field_name, field in self.fields.items():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()

    def clean(self):
        cleaned_data = super().clean()
        legal_entity = cleaned_data.get('legal_entity')
        location = cleaned_data.get('location')
        cost_center = cleaned_data.get('cost_center')

        if legal_entity and location and cost_center:
            if cost_center.legal_entity_id != legal_entity.id:
                self.add_error('cost_center', 'ЦФО относится к другому юридическому лицу.')
            if cost_center.location_id != location.id:
                self.add_error('cost_center', 'ЦФО относится к другой локации.')

        return cleaned_data

    def clean_warehouse(self):
        warehouse_name = self.cleaned_data.get('warehouse')
        cost_center = self.cleaned_data.get('cost_center')

        if not warehouse_name or not cost_center:
            return None

        try:
            return Warehouse.objects.get(cost_center=cost_center, name=warehouse_name)
        except Warehouse.DoesNotExist as exc:
            raise forms.ValidationError('Для выбранного ЦФО нет такого склада.') from exc


class EquipmentMoveForm(forms.Form):
    legal_entity = forms.ModelChoiceField(
        queryset=LegalEntity.objects.all().order_by('name'),
        label='Юридическое лицо'
    )
    to_location = forms.ModelChoiceField(
        queryset=Location.objects.all().order_by('name'),
        label='Новая локация'
    )
    to_cost_center = forms.ModelChoiceField(
        queryset=CostCenter.objects.all().order_by('name'),
        label='Новый ЦФО'
    )
    to_warehouse = forms.ChoiceField(
        label='Новый склад'
    )
    comment = forms.CharField(
        required=False,
        label='Комментарий',
        widget=forms.Textarea(attrs={'rows': 3})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        equipment = kwargs.pop('equipment', None)
        super().__init__(*args, **kwargs)

        self.fields['legal_entity'].queryset = get_editable_legal_entities(self.user).order_by('name')
        self.fields['to_location'].queryset = get_editable_locations(self.user).order_by('name')
        self.fields['to_cost_center'].queryset = get_editable_cost_centers(self.user).order_by('name')

        self.fields['legal_entity'].empty_label = 'Выберите юридическое лицо'
        self.fields['to_location'].empty_label = 'Выберите локацию'
        self.fields['to_cost_center'].empty_label = 'Выберите ЦФО'
        self.fields['to_warehouse'].choices = _get_warehouse_name_choices()

        if equipment is not None and not self.is_bound:
            self.fields['legal_entity'].initial = equipment.legal_entity
            self.fields['to_location'].initial = equipment.location
            self.fields['to_cost_center'].initial = equipment.cost_center
            self.fields['to_warehouse'].initial = equipment.warehouse.name

        for field_name, field in self.fields.items():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()

    def clean(self):
        cleaned_data = super().clean()
        legal_entity = cleaned_data.get('legal_entity')
        to_location = cleaned_data.get('to_location')
        to_cost_center = cleaned_data.get('to_cost_center')
        to_warehouse_name = cleaned_data.get('to_warehouse')

        if legal_entity and to_location and to_cost_center:
            if to_cost_center.legal_entity_id != legal_entity.id:
                self.add_error('to_cost_center', 'ЦФО относится к другому юридическому лицу.')
            if to_cost_center.location_id != to_location.id:
                self.add_error('to_cost_center', 'ЦФО относится к другой локации.')

        if to_cost_center and to_warehouse_name:
            try:
                cleaned_data['to_warehouse'] = Warehouse.objects.get(
                    cost_center=to_cost_center,
                    name=to_warehouse_name,
                )
            except Warehouse.DoesNotExist:
                self.add_error('to_warehouse', 'Для выбранного ЦФО нет такого склада.')

        return cleaned_data


class EquipmentNoteForm(forms.ModelForm):
    class Meta:
        model = EquipmentNote
        fields = ['text']
        labels = {
            'text': 'Заметка',
        }
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class EquipmentRequisiteForm(forms.ModelForm):
    class Meta:
        model = EquipmentRequisite
        fields = ['requisite_type', 'name', 'value', 'comment']
        labels = {
            'requisite_type': 'Тип',
            'name': 'Название',
            'value': 'Значение',
            'comment': 'Комментарий',
        }
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class EquipmentFileForm(forms.ModelForm):
    class Meta:
        model = EquipmentFile
        fields = ['title', 'file', 'comment']
        labels = {
            'title': 'Название документа',
            'file': 'Документ',
            'comment': 'Комментарий',
        }
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class EquipmentPhotoForm(forms.ModelForm):
    class Meta:
        model = EquipmentPhoto
        fields = ['image', 'caption', 'is_primary']
        labels = {
            'image': 'Фото',
            'caption': 'Подпись',
            'is_primary': 'Основное фото',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            current_class = field.widget.attrs.get('class', '')
            if field_name == 'is_primary':
                field.widget.attrs['class'] = current_class.strip()
            else:
                field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class EquipmentRepairForm(forms.ModelForm):
    class Meta:
        model = EquipmentRepair
        fields = ['description', 'priority']
        labels = {
            'description': 'Описание проблемы',
            'priority': 'Приоритет',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['priority'].required = False
        self.fields['priority'].initial = EquipmentRepair.PRIORITY_NORMAL
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()

    def clean_priority(self):
        return self.cleaned_data.get('priority') or EquipmentRepair.PRIORITY_NORMAL


class EquipmentRepairStatusForm(forms.ModelForm):
    class Meta:
        model = EquipmentRepair
        fields = ['status', 'assigned_to', 'repair_date', 'contractor', 'cost', 'resolution', 'status_comment']
        labels = {
            'status': 'Статус',
            'assigned_to': 'Техник',
            'repair_date': 'Дата ремонта',
            'contractor': 'Исполнитель',
            'cost': 'Стоимость ремонта',
            'resolution': 'Что сделано',
            'status_comment': 'Комментарий по статусу',
        }
        widgets = {
            'repair_date': forms.DateInput(attrs={'type': 'date'}),
            'resolution': forms.Textarea(attrs={'rows': 3}),
            'status_comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(
            is_active=True,
            role__in=['technician', 'service_engineer'],
        ).order_by('username')
        self.fields['assigned_to'].empty_label = 'Выберите техника'
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class EquipmentInventoryForm(forms.ModelForm):
    class Meta:
        model = EquipmentInventory
        fields = ['inventory_date', 'condition_status', 'estimated_value', 'comment']
        labels = {
            'inventory_date': 'Дата инвентаризации',
            'condition_status': 'Статус состояния',
            'estimated_value': 'Оценочная текущая стоимость',
            'comment': 'Комментарий',
        }
        widgets = {
            'inventory_date': forms.DateInput(attrs={'type': 'date'}),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class InventorySessionForm(forms.ModelForm):
    class Meta:
        model = InventorySession
        fields = ['name', 'act_number', 'legal_entity', 'location', 'period_start', 'period_end', 'comment']
        labels = {
            'name': 'Название инвентаризации',
            'act_number': 'Номер акта',
            'legal_entity': 'Юридическое лицо',
            'location': 'Локация',
            'period_start': 'Дата начала',
            'period_end': 'Дата окончания',
            'comment': 'Комментарий',
        }
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['legal_entity'].queryset = get_editable_legal_entities(self.user).order_by('name')
        self.fields['location'].queryset = get_editable_locations(self.user).order_by('name')
        self.fields['legal_entity'].empty_label = 'Выберите юридическое лицо'
        self.fields['location'].empty_label = 'Выберите локацию'
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()

    def clean(self):
        cleaned_data = super().clean()
        period_start = cleaned_data.get('period_start')
        period_end = cleaned_data.get('period_end')
        if period_start and period_end and period_end < period_start:
            self.add_error('period_end', 'Дата окончания не может быть раньше даты начала.')
        return cleaned_data


class InventoryAddEquipmentForm(forms.Form):
    equipment = EquipmentInventoryChoiceField(
        queryset=Equipment.objects.none(),
        label='Оборудование',
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.session = kwargs.pop('session', None)
        super().__init__(*args, **kwargs)
        if self.user is None:
            queryset = Equipment.objects.none()
        else:
            queryset = get_user_equipment_queryset(self.user).filter(is_active=True)
        queryset = queryset.select_related(
            'legal_entity',
            'location',
            'warehouse',
        )
        if self.session is not None:
            queryset = queryset.filter(
                location=self.session.location,
            ).exclude(
                inventory_items__session=self.session,
            )
        self.fields['equipment'].queryset = queryset.order_by('name')
        self.fields['equipment'].empty_label = 'Выберите оборудование'
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class InventoryScanEquipmentForm(forms.Form):
    qr_value = forms.CharField(
        label='QR/NFC метка оборудования',
        max_length=1000,
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'autofocus': 'autofocus',
            'placeholder': 'Отсканируйте QR/NFC или вставьте ссылку',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control inventory-scan-input'.strip()


class InventoryItemCheckForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ['found', 'actual_location', 'actual_warehouse', 'condition_status', 'estimated_value', 'comment']
        labels = {
            'found': 'Найдено',
            'actual_location': 'Фактическая локация',
            'actual_warehouse': 'Фактическая зона/склад',
            'condition_status': 'Состояние',
            'estimated_value': 'Оценочная стоимость',
            'comment': 'Комментарий',
        }
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop('session', None)
        super().__init__(*args, **kwargs)
        if self.session is not None:
            self.fields['actual_location'].queryset = Location.objects.filter(is_active=True).order_by('name')
            self.fields['actual_warehouse'].queryset = Warehouse.objects.filter(
                cost_center__legal_entity=self.session.legal_entity,
                cost_center__location=self.session.location,
                is_active=True,
            ).order_by('name')
        self.fields['actual_location'].empty_label = 'Выберите локацию'
        self.fields['actual_warehouse'].empty_label = 'Выберите зону/склад'
        for field_name, field in self.fields.items():
            current_class = field.widget.attrs.get('class', '')
            if field_name == 'found':
                field.widget.attrs['class'] = current_class.strip()
            else:
                field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class EquipmentInventorySessionSelectForm(forms.Form):
    session = forms.ModelChoiceField(
        queryset=InventorySession.objects.none(),
        label='Акт инвентаризации',
    )

    def __init__(self, *args, **kwargs):
        self.equipment = kwargs.pop('equipment', None)
        super().__init__(*args, **kwargs)
        queryset = InventorySession.objects.filter(
            status__in=[InventorySession.STATUS_ACTIVE, InventorySession.STATUS_APPROVAL],
        )
        if self.equipment is not None:
            queryset = queryset.filter(
                legal_entity=self.equipment.legal_entity,
                location=self.equipment.location,
            )
        self.fields['session'].queryset = queryset.order_by('-period_start', '-started_at', 'name')
        self.fields['session'].empty_label = 'Выберите акт'
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()
