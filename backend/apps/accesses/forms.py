from django import forms

from apps.dashboard.access import get_editable_cost_centers, get_editable_legal_entities, get_editable_locations
from apps.users.models import User

from .access import get_editable_equipment_for_accesses
from .models import AccessGrant, AccessSecret, AccessType, EquipmentAccess


class EquipmentAccessForm(forms.ModelForm):
    password = forms.CharField(
        label='Пароль',
        required=False,
        widget=forms.PasswordInput(render_value=False),
        strip=False,
        help_text='Если заполнить, пароль будет сохранен как зашифрованный секрет.',
    )

    class Meta:
        model = EquipmentAccess
        fields = [
            'equipment',
            'legal_entity',
            'location',
            'cost_center',
            'access_type',
            'title',
            'host',
            'port',
            'url',
            'username',
            'password',
            'description',
            'expires_at',
            'is_active',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'expires_at': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'equipment': 'Оборудование',
            'legal_entity': 'Юридическое лицо',
            'location': 'Локация',
            'cost_center': 'ЦФО',
            'access_type': 'Тип доступа',
            'title': 'Название',
            'host': 'Хост',
            'port': 'Порт',
            'url': 'URL',
            'username': 'Логин',
            'description': 'Описание',
            'expires_at': 'Истекает',
            'is_active': 'Активен',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['equipment'].queryset = get_editable_equipment_for_accesses(self.user).order_by('name')
        self.fields['legal_entity'].queryset = get_editable_legal_entities(self.user).order_by('name')
        self.fields['location'].queryset = get_editable_locations(self.user).order_by('name')
        self.fields['cost_center'].queryset = get_editable_cost_centers(self.user).order_by('name')
        self.fields['access_type'].queryset = AccessType.objects.filter(is_active=True).order_by('sort_order', 'name')

        self.fields['equipment'].required = False
        self.fields['cost_center'].required = False
        self.fields['port'].required = False
        self.fields['expires_at'].required = False

        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()

    def clean(self):
        cleaned_data = super().clean()
        equipment = cleaned_data.get('equipment')
        legal_entity = cleaned_data.get('legal_entity')
        location = cleaned_data.get('location')
        cost_center = cleaned_data.get('cost_center')

        if equipment:
            if legal_entity and equipment.legal_entity_id != legal_entity.id:
                self.add_error('legal_entity', 'Юрлицо должно совпадать с карточкой оборудования.')
            if location and equipment.location_id != location.id:
                self.add_error('location', 'Локация должна совпадать с карточкой оборудования.')
            if cost_center and equipment.cost_center_id != cost_center.id:
                self.add_error('cost_center', 'ЦФО должен совпадать с карточкой оборудования.')

        if cost_center:
            if legal_entity and cost_center.legal_entity_id != legal_entity.id:
                self.add_error('cost_center', 'ЦФО относится к другому юрлицу.')
            if location and cost_center.location_id != location.id:
                self.add_error('cost_center', 'ЦФО относится к другой локации.')

        return cleaned_data


class AccessSecretForm(forms.ModelForm):
    raw_value = forms.CharField(
        label='Значение секрета',
        widget=forms.Textarea(attrs={'rows': 4}),
        strip=False,
    )

    class Meta:
        model = AccessSecret
        fields = [
            'secret_type',
            'label',
            'raw_value',
            'is_active',
        ]
        labels = {
            'secret_type': 'Тип секрета',
            'label': 'Подпись',
            'is_active': 'Активен',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class AccessGrantForm(forms.ModelForm):
    class Meta:
        model = AccessGrant
        fields = [
            'user',
            'level',
            'expires_at',
            'is_active',
        ]
        widgets = {
            'expires_at': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'user': 'Пользователь',
            'level': 'Уровень',
            'expires_at': 'Истекает',
            'is_active': 'Активен',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['expires_at'].required = False
        for field in self.fields.values():
            current_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current_class} form-control'.strip()
