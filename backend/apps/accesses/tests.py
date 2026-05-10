from cryptography.fernet import Fernet

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accesses.models import AccessChangeLog, AccessGrant, AccessSecret, AccessSecretViewLog, AccessType, EquipmentAccess
from apps.accesses.services import decrypt_secret, encrypt_secret
from apps.equipment.models import Equipment, EquipmentCategory, EquipmentStatus
from apps.locations.models import Location
from apps.organizations.models import CostCenter, LegalEntity, UserLegalEntityAccess, UserLocationAccess
from apps.users.models import User
from apps.warehouses.models import Warehouse


class EquipmentAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            username='admin-user',
            password='password',
            is_global_access=True,
            role='system_admin',
        )
        cls.viewer_user = User.objects.create_user(
            username='viewer-user',
            password='password',
        )
        cls.editor_user = User.objects.create_user(
            username='editor-user',
            password='password',
        )
        cls.service_user = User.objects.create_user(
            username='service-user',
            password='password',
            role='service_engineer',
        )

        cls.legal_entity = LegalEntity.objects.create(name='ООО Грелка', short_name='Грелка')
        cls.other_legal_entity = LegalEntity.objects.create(name='ООО Трансавангард', short_name='ТА')
        cls.location = Location.objects.create(name='Шерегеш')
        cls.other_location = Location.objects.create(name='Сочи')
        cls.cost_center = CostCenter.objects.create(
            legal_entity=cls.legal_entity,
            location=cls.location,
            name='Грелка',
        )
        cls.other_cost_center = CostCenter.objects.create(
            legal_entity=cls.other_legal_entity,
            location=cls.other_location,
            name='Варя',
        )
        cls.warehouse = Warehouse.objects.create(cost_center=cls.cost_center, name='Кухня')
        cls.other_warehouse = Warehouse.objects.create(cost_center=cls.other_cost_center, name='Бар')
        cls.category = EquipmentCategory.objects.create(name='POS')
        cls.status = EquipmentStatus.objects.create(name='В работе', code='WORKING')
        cls.equipment = Equipment.objects.create(
            legal_entity=cls.legal_entity,
            location=cls.location,
            cost_center=cls.cost_center,
            warehouse=cls.warehouse,
            category=cls.category,
            status=cls.status,
            name='POS terminal',
            serial_number='POS-001',
        )
        cls.other_equipment = Equipment.objects.create(
            legal_entity=cls.other_legal_entity,
            location=cls.other_location,
            cost_center=cls.other_cost_center,
            warehouse=cls.other_warehouse,
            category=cls.category,
            status=cls.status,
            name='Other POS',
            serial_number='POS-002',
        )
        cls.access_type = AccessType.objects.create(code='ssh', name='SSH', sort_order=10)

        UserLegalEntityAccess.objects.create(
            user=cls.viewer_user,
            legal_entity=cls.legal_entity,
            access_level='view',
        )
        UserLocationAccess.objects.create(
            user=cls.editor_user,
            location=cls.location,
            access_level='edit',
        )
        UserLocationAccess.objects.create(
            user=cls.service_user,
            location=cls.location,
            access_level='edit',
        )

    def test_access_list_is_limited_to_user_scope(self):
        allowed_access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Allowed SSH',
            host='10.0.0.10',
        )
        hidden_access = EquipmentAccess.objects.create(
            equipment=self.other_equipment,
            legal_entity=self.other_legal_entity,
            location=self.other_location,
            cost_center=self.other_cost_center,
            access_type=self.access_type,
            title='Hidden SSH',
            host='10.0.0.20',
        )
        self.client.force_login(self.viewer_user)

        response = self.client.get(reverse('equipment_access_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, allowed_access.title)
        self.assertNotContains(response, hidden_access.title)

    def test_editor_can_create_access_in_editable_scope(self):
        self.client.force_login(self.editor_user)

        response = self.client.post(
            reverse('equipment_access_create'),
            {
                'equipment': self.equipment.pk,
                'legal_entity': self.legal_entity.pk,
                'location': self.location.pk,
                'cost_center': self.cost_center.pk,
                'access_type': self.access_type.pk,
                'title': 'Kitchen SSH',
                'host': '10.0.0.30',
                'port': '22',
                'url': '',
                'username': 'admin',
                'description': 'No secrets here',
                'expires_at': '',
                'is_active': 'on',
            },
        )

        access = EquipmentAccess.objects.get(title='Kitchen SSH')

        self.assertRedirects(response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertEqual(access.created_by, self.editor_user)
        self.assertEqual(access.updated_by, self.editor_user)

    @override_settings(ACCESS_SECRET_KEYS=[Fernet.generate_key().decode()])
    def test_editor_can_create_access_with_password_field(self):
        self.client.force_login(self.editor_user)

        response = self.client.post(
            reverse('equipment_access_create'),
            {
                'equipment': self.equipment.pk,
                'legal_entity': self.legal_entity.pk,
                'location': self.location.pk,
                'cost_center': self.cost_center.pk,
                'access_type': self.access_type.pk,
                'title': 'Kitchen SSH with password',
                'host': '10.0.0.31',
                'port': '22',
                'url': '',
                'username': 'admin',
                'password': 'form-password',
                'description': '',
                'expires_at': '',
                'is_active': 'on',
            },
        )

        access = EquipmentAccess.objects.get(title='Kitchen SSH with password')
        secret = AccessSecret.objects.get(access=access, secret_type='password')
        detail_response = self.client.get(reverse('equipment_access_detail', kwargs={'pk': access.pk}))

        self.assertRedirects(response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertEqual(secret.label, 'Пароль')
        self.assertEqual(decrypt_secret(secret.encrypted_value), 'form-password')
        self.assertNotContains(detail_response, 'form-password')

    @override_settings(ACCESS_SECRET_KEYS=[Fernet.generate_key().decode()])
    def test_editor_can_update_access_password_field(self):
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Update password SSH',
            host='10.0.0.32',
        )
        secret = AccessSecret.objects.create(
            access=access,
            secret_type='password',
            label='Пароль',
            encrypted_value=encrypt_secret('old-form-password'),
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        self.client.force_login(self.editor_user)

        response = self.client.post(
            reverse('equipment_access_update', kwargs={'pk': access.pk}),
            {
                'equipment': self.equipment.pk,
                'legal_entity': self.legal_entity.pk,
                'location': self.location.pk,
                'cost_center': self.cost_center.pk,
                'access_type': self.access_type.pk,
                'title': 'Update password SSH',
                'host': '10.0.0.32',
                'port': '',
                'url': '',
                'username': 'admin',
                'password': 'new-form-password',
                'description': '',
                'expires_at': '',
                'is_active': 'on',
            },
        )

        secret.refresh_from_db()

        self.assertRedirects(response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertEqual(decrypt_secret(secret.encrypted_value), 'new-form-password')
        self.assertIsNotNone(secret.rotated_at)
        self.assertTrue(AccessChangeLog.objects.filter(access=access, secret=secret, action='secret_rotated').exists())

    def test_editor_cannot_create_access_outside_editable_scope(self):
        self.client.force_login(self.editor_user)

        response = self.client.post(
            reverse('equipment_access_create'),
            {
                'equipment': self.other_equipment.pk,
                'legal_entity': self.other_legal_entity.pk,
                'location': self.other_location.pk,
                'cost_center': self.other_cost_center.pk,
                'access_type': self.access_type.pk,
                'title': 'Unauthorized SSH',
                'host': '10.0.0.40',
                'port': '22',
                'url': '',
                'username': 'admin',
                'description': '',
                'expires_at': '',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EquipmentAccess.objects.filter(title='Unauthorized SSH').exists())
        self.assertContains(response, 'Select a valid choice')

    def test_viewer_cannot_edit_access(self):
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Readonly SSH',
            host='10.0.0.50',
        )
        self.client.force_login(self.viewer_user)

        edit_response = self.client.get(reverse('equipment_access_update', kwargs={'pk': access.pk}))
        archive_response = self.client.post(reverse('equipment_access_archive', kwargs={'pk': access.pk}))

        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(archive_response.status_code, 403)

    @override_settings(ACCESS_SECRET_KEYS=[Fernet.generate_key().decode()])
    def test_editor_can_add_encrypted_secret_without_plaintext_in_detail(self):
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Secret SSH',
            host='10.0.0.60',
        )
        self.client.force_login(self.editor_user)

        response = self.client.post(
            reverse('access_secret_create', kwargs={'pk': access.pk}),
            {
                'secret_type': 'password',
                'label': 'root password',
                'raw_value': 'plain-secret-value',
                'is_active': 'on',
            },
        )

        secret = AccessSecret.objects.get(access=access)
        detail_response = self.client.get(reverse('equipment_access_detail', kwargs={'pk': access.pk}))

        self.assertRedirects(response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertNotEqual(secret.encrypted_value, 'plain-secret-value')
        self.assertEqual(decrypt_secret(secret.encrypted_value), 'plain-secret-value')
        self.assertContains(detail_response, 'root password')
        self.assertNotContains(detail_response, 'plain-secret-value')

    @override_settings(ACCESS_SECRET_KEYS=[Fernet.generate_key().decode()])
    def test_service_engineer_can_reveal_secret_and_audit_log_is_written(self):
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Reveal SSH',
            host='10.0.0.70',
        )
        secret = AccessSecret.objects.create(
            access=access,
            secret_type='password',
            label='admin password',
            encrypted_value=encrypt_secret('service-secret'),
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        self.client.force_login(self.service_user)

        response = self.client.post(reverse('access_secret_reveal', kwargs={'pk': access.pk, 'secret_pk': secret.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'service-secret')
        self.assertTrue(AccessSecretViewLog.objects.filter(secret=secret, user=self.service_user, result='allowed').exists())
        access.refresh_from_db()
        self.assertIsNotNone(access.last_secret_viewed_at)

    @override_settings(ACCESS_SECRET_KEYS=[Fernet.generate_key().decode()])
    def test_viewer_cannot_reveal_secret_and_denied_log_is_written(self):
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Denied SSH',
            host='10.0.0.80',
        )
        secret = AccessSecret.objects.create(
            access=access,
            secret_type='password',
            label='admin password',
            encrypted_value=encrypt_secret('blocked-secret'),
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        self.client.force_login(self.viewer_user)

        response = self.client.post(reverse('access_secret_reveal', kwargs={'pk': access.pk, 'secret_pk': secret.pk}))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(AccessSecretViewLog.objects.filter(secret=secret, user=self.viewer_user, result='denied').exists())

    @override_settings(ACCESS_SECRET_KEYS=[Fernet.generate_key().decode()])
    def test_editor_can_rotate_secret_and_change_log_is_written(self):
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Rotate SSH',
            host='10.0.0.90',
        )
        secret = AccessSecret.objects.create(
            access=access,
            secret_type='password',
            label='admin password',
            encrypted_value=encrypt_secret('old-secret'),
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        self.client.force_login(self.editor_user)

        response = self.client.post(
            reverse('access_secret_rotate', kwargs={'pk': access.pk, 'secret_pk': secret.pk}),
            {
                'secret_type': 'password',
                'label': 'admin password',
                'raw_value': 'new-secret',
                'is_active': 'on',
            },
        )

        secret.refresh_from_db()

        self.assertRedirects(response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertEqual(decrypt_secret(secret.encrypted_value), 'new-secret')
        self.assertIsNotNone(secret.rotated_at)
        self.assertTrue(AccessChangeLog.objects.filter(
            access=access,
            secret=secret,
            user=self.editor_user,
            action='secret_rotated',
        ).exists())

    @override_settings(ACCESS_SECRET_KEYS=[Fernet.generate_key().decode()])
    def test_editor_can_archive_secret_and_hide_it_from_detail(self):
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Archive Secret SSH',
            host='10.0.0.91',
        )
        secret = AccessSecret.objects.create(
            access=access,
            secret_type='password',
            label='temporary password',
            encrypted_value=encrypt_secret('temporary-secret'),
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        self.client.force_login(self.editor_user)

        response = self.client.post(reverse('access_secret_archive', kwargs={'pk': access.pk, 'secret_pk': secret.pk}))
        detail_response = self.client.get(reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        secret.refresh_from_db()

        self.assertRedirects(response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertFalse(secret.is_active)
        self.assertNotContains(detail_response, 'temporary-secret')
        self.assertContains(detail_response, 'Secret archived')
        self.assertTrue(AccessChangeLog.objects.filter(
            access=access,
            secret=secret,
            user=self.editor_user,
            action='secret_archived',
        ).exists())

    def test_personal_grant_allows_out_of_scope_user_to_view_single_access(self):
        access = EquipmentAccess.objects.create(
            equipment=self.other_equipment,
            legal_entity=self.other_legal_entity,
            location=self.other_location,
            cost_center=self.other_cost_center,
            access_type=self.access_type,
            title='Granted SSH',
            host='10.0.1.10',
        )
        AccessGrant.objects.create(
            access=access,
            user=self.viewer_user,
            level='view_meta',
            granted_by=self.admin_user,
        )
        self.client.force_login(self.viewer_user)

        list_response = self.client.get(reverse('equipment_access_list'))
        detail_response = self.client.get(reverse('equipment_access_detail', kwargs={'pk': access.pk}))

        self.assertContains(list_response, 'Granted SSH')
        self.assertEqual(detail_response.status_code, 200)

    @override_settings(ACCESS_SECRET_KEYS=[Fernet.generate_key().decode()])
    def test_view_secret_grant_allows_secret_reveal_without_location_access(self):
        access = EquipmentAccess.objects.create(
            equipment=self.other_equipment,
            legal_entity=self.other_legal_entity,
            location=self.other_location,
            cost_center=self.other_cost_center,
            access_type=self.access_type,
            title='Granted Secret SSH',
            host='10.0.1.20',
        )
        secret = AccessSecret.objects.create(
            access=access,
            secret_type='password',
            label='granted password',
            encrypted_value=encrypt_secret('grant-secret'),
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        AccessGrant.objects.create(
            access=access,
            user=self.viewer_user,
            level='view_secret',
            granted_by=self.admin_user,
        )
        self.client.force_login(self.viewer_user)

        response = self.client.post(reverse('access_secret_reveal', kwargs={'pk': access.pk, 'secret_pk': secret.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'grant-secret')
        self.assertTrue(AccessSecretViewLog.objects.filter(secret=secret, user=self.viewer_user, result='allowed').exists())

    def test_editor_can_grant_and_archive_personal_access(self):
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Grant Managed SSH',
            host='10.0.1.30',
        )
        self.client.force_login(self.editor_user)

        create_response = self.client.post(
            reverse('access_grant_create', kwargs={'pk': access.pk}),
            {
                'user': self.viewer_user.pk,
                'level': 'view_meta',
                'expires_at': '',
                'is_active': 'on',
            },
        )
        grant = AccessGrant.objects.get(access=access, user=self.viewer_user)
        archive_response = self.client.post(reverse('access_grant_archive', kwargs={'pk': access.pk, 'grant_pk': grant.pk}))
        grant.refresh_from_db()

        self.assertRedirects(create_response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertRedirects(archive_response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertFalse(grant.is_active)
        self.assertTrue(AccessChangeLog.objects.filter(access=access, action='grant_added').exists())
        self.assertTrue(AccessChangeLog.objects.filter(access=access, action='grant_archived').exists())

    @override_settings(ACCESS_SECRET_KEYS=[Fernet.generate_key().decode()])
    def test_access_export_csv_contains_metadata_without_secret_values(self):
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Export SSH',
            host='10.0.2.10',
            username='export-user',
        )
        AccessSecret.objects.create(
            access=access,
            secret_type='password',
            label='export password',
            encrypted_value=encrypt_secret('export-secret-value'),
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        self.client.force_login(self.viewer_user)

        response = self.client.get(reverse('equipment_access_export_csv'), {'q': 'Export SSH'})
        content = response.content.decode('utf-8-sig')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8-sig')
        self.assertIn('accesses_export.csv', response['Content-Disposition'])
        self.assertIn('Export SSH', content)
        self.assertIn('export-user', content)
        self.assertIn('True', content)
        self.assertNotIn('export-secret-value', content)
        self.assertNotIn('export password', content)

    def test_access_user_report_lists_accessible_grants_only(self):
        allowed_access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=self.access_type,
            title='Allowed Grant Report SSH',
            host='10.0.2.20',
        )
        hidden_access = EquipmentAccess.objects.create(
            equipment=self.other_equipment,
            legal_entity=self.other_legal_entity,
            location=self.other_location,
            cost_center=self.other_cost_center,
            access_type=self.access_type,
            title='Hidden Grant Report SSH',
            host='10.0.2.30',
        )
        AccessGrant.objects.create(
            access=allowed_access,
            user=self.viewer_user,
            level='view_meta',
            granted_by=self.admin_user,
        )
        AccessGrant.objects.create(
            access=hidden_access,
            user=self.viewer_user,
            level='view_meta',
            granted_by=self.admin_user,
        )
        self.client.force_login(self.editor_user)

        response = self.client.get(reverse('access_user_report'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Allowed Grant Report SSH')
        self.assertNotContains(response, 'Hidden Grant Report SSH')
