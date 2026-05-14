import shutil
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accesses.models import AccessSecret, AccessType, EquipmentAccess
from apps.accesses.services import reveal_access_secret
from apps.dashboard.access import require_scope_edit_access
from apps.core.models import ActionLog
from apps.equipment.models import (
    Equipment,
    EquipmentCategory,
    EquipmentFile,
    EquipmentNote,
    EquipmentPhoto,
    EquipmentRequisite,
    EquipmentStatus,
)
from apps.inventory.models import EquipmentInventory, EquipmentMovement, EquipmentRepair, InventoryItem, InventorySession
from apps.locations.models import Location
from apps.organizations.models import CostCenter, LegalEntity, UserLegalEntityAccess, UserLocationAccess
from apps.tags.models import EquipmentTag
from apps.users.models import User
from apps.warehouses.models import Warehouse


class DashboardEquipmentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(dir=settings.BASE_DIR)
        cls._override_settings = override_settings(MEDIA_ROOT=cls._media_root)
        cls._override_settings.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override_settings.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            username='admin-user',
            password='password',
            is_global_access=True,
            role='system_admin',
        )
        cls.limited_user = User.objects.create_user(
            username='limited-user',
            password='password',
        )

        cls.legal_entity = LegalEntity.objects.create(name='ООО «Грелка»', short_name='Грелка')
        cls.other_legal_entity = LegalEntity.objects.create(name='ООО «Трансавангард»', short_name='Трансавангард')

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

        cls.category = EquipmentCategory.objects.create(name='POS-оборудование')
        cls.status = EquipmentStatus.objects.create(name='В работе', code='WORKING')

        cls.equipment = Equipment.objects.create(
            legal_entity=cls.legal_entity,
            location=cls.location,
            cost_center=cls.cost_center,
            warehouse=cls.warehouse,
            category=cls.category,
            status=cls.status,
            name='Тестовый терминал',
            serial_number='SER-001',
            inventory_number='INV-001',
        )
        cls.other_equipment = Equipment.objects.create(
            legal_entity=cls.other_legal_entity,
            location=cls.other_location,
            cost_center=cls.other_cost_center,
            warehouse=cls.other_warehouse,
            category=cls.category,
            status=cls.status,
            name='Чужой холодильник',
            serial_number='SER-002',
            inventory_number='INV-002',
        )

        UserLegalEntityAccess.objects.create(
            user=cls.limited_user,
            legal_entity=cls.legal_entity,
            access_level='view',
        )

    def test_dashboard_shows_application_version(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('dashboard_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Версия {settings.APP_VERSION}')

    def test_equipment_create_generates_qr_tag(self):
        self.client.force_login(self.admin_user)

        with patch.object(
            EquipmentTag,
            'generate_qr_image',
            lambda tag: setattr(tag.qr_image, 'name', f'qr_codes/qr_{tag.code}.png'),
        ):
            response = self.client.post(
                reverse('equipment_create'),
                {
                    'legal_entity': self.legal_entity.id,
                    'location': self.location.id,
                    'cost_center': self.cost_center.id,
                    'warehouse': self.warehouse.name,
                    'category': self.category.id,
                    'status': self.status.id,
                    'name': 'Новый принтер',
                    'brand': 'Epson',
                    'model': 'TM-T88',
                    'serial_number': 'SER-003',
                    'inventory_number': 'INV-003',
                    'purchase_date': '',
                    'warranty_until': '',
                    'price': '',
                    'responsible_user': '',
                    'comment': '',
                    'is_active': 'on',
                },
            )

        created_equipment = Equipment.objects.get(serial_number='SER-003')
        tag = EquipmentTag.objects.get(equipment=created_equipment, tag_type='QR', is_active=True)

        self.assertRedirects(response, reverse('equipment_detail', kwargs={'pk': created_equipment.pk}))
        self.assertEqual(tag.payload, f'http://testserver/equipment/{created_equipment.id}/')
        self.assertTrue(tag.qr_image)
        self.assertTrue(
            ActionLog.objects.filter(
                actor=self.admin_user,
                action=ActionLog.ACTION_CREATE,
                object_id=str(created_equipment.pk),
            ).exists()
        )

    def test_equipment_movement_updates_current_position_and_logs_history(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('equipment_move', kwargs={'pk': self.equipment.pk}),
            {
                'legal_entity': self.other_legal_entity.id,
                'to_location': self.other_location.id,
                'to_cost_center': self.other_cost_center.id,
                'to_warehouse': self.other_warehouse.name,
                'comment': 'Перевезли на другой объект',
            },
        )

        self.equipment.refresh_from_db()
        movement = EquipmentMovement.objects.get(equipment=self.equipment)

        self.assertRedirects(response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertEqual(self.equipment.legal_entity, self.other_legal_entity)
        self.assertEqual(self.equipment.location, self.other_location)
        self.assertEqual(self.equipment.cost_center, self.other_cost_center)
        self.assertEqual(self.equipment.warehouse, self.other_warehouse)
        self.assertEqual(movement.from_location, self.location)
        self.assertEqual(movement.to_location, self.other_location)
        self.assertEqual(movement.from_cost_center, self.cost_center)
        self.assertEqual(movement.to_cost_center, self.other_cost_center)
        self.assertEqual(movement.from_warehouse, self.warehouse)
        self.assertEqual(movement.to_warehouse, self.other_warehouse)

    def test_movement_journal_lists_only_accessible_movements(self):
        EquipmentMovement.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            from_location=self.location,
            to_location=self.location,
            from_cost_center=self.cost_center,
            to_cost_center=self.cost_center,
            from_warehouse=self.warehouse,
            to_warehouse=self.warehouse,
            moved_by=self.admin_user,
            comment='Allowed movement',
        )
        EquipmentMovement.objects.create(
            equipment=self.other_equipment,
            legal_entity=self.other_legal_entity,
            from_location=self.other_location,
            to_location=self.other_location,
            from_cost_center=self.other_cost_center,
            to_cost_center=self.other_cost_center,
            from_warehouse=self.other_warehouse,
            to_warehouse=self.other_warehouse,
            moved_by=self.admin_user,
            comment='Hidden movement',
        )
        self.client.force_login(self.limited_user)

        response = self.client.get(reverse('movement_journal'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Allowed movement')
        self.assertNotContains(response, 'Hidden movement')

    def test_movement_journal_searches_by_comment(self):
        EquipmentMovement.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            from_location=self.location,
            to_location=self.location,
            from_cost_center=self.cost_center,
            to_cost_center=self.cost_center,
            from_warehouse=self.warehouse,
            to_warehouse=self.warehouse,
            moved_by=self.admin_user,
            comment='Coffee station transfer',
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('movement_journal'), {'q': 'Coffee station'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.equipment.name)
        self.assertContains(response, 'Coffee station transfer')

    def test_limited_user_cannot_access_unrelated_equipment(self):
        self.client.force_login(self.limited_user)

        allowed_response = self.client.get(reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        denied_response = self.client.get(reverse('equipment_detail', kwargs={'pk': self.other_equipment.pk}))
        list_response = self.client.get(reverse('equipment_list'))

        self.assertEqual(allowed_response.status_code, 200)
        self.assertEqual(denied_response.status_code, 404)
        self.assertContains(list_response, self.equipment.name)
        self.assertNotContains(list_response, self.other_equipment.name)
        self.assertContains(list_response, self.legal_entity.name)
        self.assertContains(list_response, self.location.name)
        self.assertNotContains(list_response, self.other_legal_entity.name)
        self.assertNotContains(list_response, self.other_location.name)
        self.assertNotContains(list_response, 'Добавить оборудование')
        self.assertNotContains(list_response, 'Переместить')
        self.assertNotContains(allowed_response, 'Редактировать')
        self.assertNotContains(allowed_response, 'Обновить QR')

    def test_legal_entity_access_without_all_locations_requires_location_access(self):
        restricted_user = User.objects.create_user(
            username='restricted-user',
            password='password',
        )
        UserLegalEntityAccess.objects.create(
            user=restricted_user,
            legal_entity=self.legal_entity,
            access_level='view',
            allow_all_locations=False,
        )
        self.client.force_login(restricted_user)

        denied_response = self.client.get(reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        denied_list_response = self.client.get(reverse('equipment_list'))

        UserLocationAccess.objects.create(
            user=restricted_user,
            location=self.location,
            access_level='view',
        )
        allowed_response = self.client.get(reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        allowed_list_response = self.client.get(reverse('equipment_list'))

        self.assertEqual(denied_response.status_code, 404)
        self.assertNotContains(denied_list_response, self.equipment.name)
        self.assertEqual(allowed_response.status_code, 200)
        self.assertContains(allowed_list_response, self.equipment.name)

    def test_view_only_user_cannot_modify_equipment(self):
        self.client.force_login(self.limited_user)

        move_response = self.client.get(reverse('equipment_move', kwargs={'pk': self.equipment.pk}))
        edit_response = self.client.get(reverse('equipment_update', kwargs={'pk': self.equipment.pk}))
        archive_response = self.client.post(reverse('equipment_archive', kwargs={'pk': self.equipment.pk}))
        create_response = self.client.get(reverse('equipment_create'))

        self.assertEqual(move_response.status_code, 403)
        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(archive_response.status_code, 403)
        self.assertEqual(create_response.status_code, 403)

    def test_equipment_detail_supports_notes_requisites_and_files(self):
        self.client.force_login(self.admin_user)

        note_response = self.client.post(
            reverse('equipment_note_create', kwargs={'pk': self.equipment.pk}),
            {'text': 'Проверить кассовый модуль'},
        )
        requisite_response = self.client.post(
            reverse('equipment_requisite_create', kwargs={'pk': self.equipment.pk}),
            {
                'requisite_type': EquipmentRequisite.TYPE_IP,
                'name': 'LAN',
                'value': '10.10.10.15',
                'comment': 'Основная сеть',
            },
        )
        file_response = self.client.post(
            reverse('equipment_file_create', kwargs={'pk': self.equipment.pk}),
            {
                'title': 'Инструкция',
                'file': SimpleUploadedFile('manual.txt', b'hello', content_type='text/plain'),
                'comment': 'Документ поставщика',
            },
        )
        detail_response = self.client.get(reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))

        self.assertRedirects(note_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertRedirects(requisite_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertRedirects(file_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertEqual(EquipmentNote.objects.filter(equipment=self.equipment).count(), 1)
        self.assertEqual(EquipmentRequisite.objects.filter(equipment=self.equipment, is_active=True).count(), 1)
        self.assertEqual(EquipmentFile.objects.filter(equipment=self.equipment, is_active=True).count(), 1)
        self.assertContains(detail_response, '10.10.10.15')
        self.assertContains(detail_response, 'Инструкция')

    def test_view_only_user_cannot_manage_equipment_documents(self):
        self.client.force_login(self.limited_user)

        note_response = self.client.post(
            reverse('equipment_note_create', kwargs={'pk': self.equipment.pk}),
            {'text': 'Недоступно'},
        )
        requisite_response = self.client.get(
            reverse('equipment_requisite_create', kwargs={'pk': self.equipment.pk})
        )
        file_response = self.client.get(
            reverse('equipment_file_create', kwargs={'pk': self.equipment.pk})
        )

        self.assertEqual(note_response.status_code, 403)
        self.assertEqual(requisite_response.status_code, 403)
        self.assertEqual(file_response.status_code, 403)

    def test_equipment_requisite_and_file_archive_hide_items(self):
        self.client.force_login(self.admin_user)
        requisite = EquipmentRequisite.objects.create(
            equipment=self.equipment,
            requisite_type=EquipmentRequisite.TYPE_DOMAIN,
            value='terminal.local',
        )
        equipment_file = EquipmentFile.objects.create(
            equipment=self.equipment,
            title='Схема',
            file=SimpleUploadedFile('scheme.txt', b'scheme', content_type='text/plain'),
        )

        requisite_response = self.client.post(reverse(
            'equipment_requisite_archive',
            kwargs={'pk': self.equipment.pk, 'requisite_pk': requisite.pk},
        ))
        file_response = self.client.post(reverse(
            'equipment_file_archive',
            kwargs={'pk': self.equipment.pk, 'file_pk': equipment_file.pk},
        ))
        detail_response = self.client.get(reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))

        requisite.refresh_from_db()
        equipment_file.refresh_from_db()

        self.assertRedirects(requisite_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertRedirects(file_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertFalse(requisite.is_active)
        self.assertFalse(equipment_file.is_active)
        self.assertNotContains(detail_response, 'terminal.local')
        self.assertNotContains(detail_response, 'Схема')

    def test_equipment_photo_upload_primary_and_archive(self):
        self.client.force_login(self.admin_user)
        image_bytes = (
            b'GIF87a\x01\x00\x01\x00\x80\x00\x00'
            b'\x00\x00\x00\xff\xff\xff,\x00\x00\x00'
            b'\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )

        create_response = self.client.post(
            reverse('equipment_photo_create', kwargs={'pk': self.equipment.pk}),
            {
                'image': SimpleUploadedFile('photo.gif', image_bytes, content_type='image/gif'),
                'caption': 'Передняя панель',
                'is_primary': 'on',
            },
        )
        photo = EquipmentPhoto.objects.get(equipment=self.equipment)
        detail_response = self.client.get(reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))

        self.assertRedirects(create_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertTrue(photo.is_primary)
        self.assertContains(detail_response, 'Передняя панель')

        second_photo = EquipmentPhoto.objects.create(
            equipment=self.equipment,
            image=SimpleUploadedFile('photo2.gif', image_bytes, content_type='image/gif'),
            caption='Задняя панель',
        )
        primary_response = self.client.post(reverse(
            'equipment_photo_make_primary',
            kwargs={'pk': self.equipment.pk, 'photo_pk': second_photo.pk},
        ))
        archive_response = self.client.post(reverse(
            'equipment_photo_archive',
            kwargs={'pk': self.equipment.pk, 'photo_pk': second_photo.pk},
        ))

        photo.refresh_from_db()
        second_photo.refresh_from_db()

        self.assertRedirects(primary_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertRedirects(archive_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertFalse(photo.is_primary)
        self.assertTrue(second_photo.is_primary)
        self.assertFalse(second_photo.is_active)

    def test_view_only_user_cannot_manage_equipment_photos(self):
        self.client.force_login(self.limited_user)

        response = self.client.get(reverse('equipment_photo_create', kwargs={'pk': self.equipment.pk}))

        self.assertEqual(response.status_code, 403)

    def test_equipment_repair_and_inventory_update_summary_fields(self):
        self.client.force_login(self.admin_user)

        repair_response = self.client.post(
            reverse('equipment_repair_create', kwargs={'pk': self.equipment.pk}),
            {
                'repair_date': '2026-05-01',
                'description': 'Замена блока питания',
                'cost': '1500.00',
                'contractor': 'Service',
            },
        )
        inventory_response = self.client.post(
            reverse('equipment_inventory_create', kwargs={'pk': self.equipment.pk}),
            {
                'inventory_date': '2026-05-02',
                'condition_status': EquipmentInventory.CONDITION_OK,
                'estimated_value': '12000.00',
                'comment': 'На месте',
            },
        )
        detail_response = self.client.get(reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))

        self.equipment.refresh_from_db()

        self.assertRedirects(repair_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertRedirects(inventory_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertEqual(EquipmentRepair.objects.filter(equipment=self.equipment).count(), 1)
        self.assertEqual(EquipmentInventory.objects.filter(equipment=self.equipment).count(), 1)
        self.assertEqual(str(self.equipment.last_repair_date), '2026-05-01')
        self.assertEqual(str(self.equipment.last_inventory_date), '2026-05-02')
        self.assertEqual(str(self.equipment.estimated_current_value), '12000.00')
        self.assertContains(detail_response, 'Замена блока питания')
        self.assertContains(detail_response, 'На месте')

    def test_repair_request_workflow_is_managed_by_technician(self):
        technician = User.objects.create_user(
            username='technician-user',
            password='password',
            role='technician',
            is_global_access=True,
        )
        self.client.force_login(self.admin_user)

        create_response = self.client.post(
            reverse('equipment_repair_create', kwargs={'pk': self.equipment.pk}),
            {
                'description': 'Power module does not start',
                'priority': EquipmentRepair.PRIORITY_CRITICAL,
            },
        )
        repair = EquipmentRepair.objects.get(equipment=self.equipment, description='Power module does not start')
        self.equipment.refresh_from_db()

        self.assertRedirects(create_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertEqual(repair.status, EquipmentRepair.STATUS_REQUESTED)
        self.assertEqual(self.equipment.status.code, 'REPAIR')

        self.client.force_login(technician)
        update_response = self.client.post(
            reverse('equipment_repair_update', kwargs={'pk': repair.pk}),
            {
                'status': EquipmentRepair.STATUS_IN_PROGRESS,
                'assigned_to': technician.pk,
                'repair_date': '2026-05-03',
                'contractor': '',
                'cost': '',
                'resolution': '',
                'status_comment': 'Accepted',
            },
        )
        repair.refresh_from_db()

        self.assertRedirects(update_response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertEqual(repair.status, EquipmentRepair.STATUS_IN_PROGRESS)
        self.assertEqual(repair.accepted_by, technician)
        self.assertEqual(repair.assigned_to, technician)
        self.assertIsNotNone(repair.started_at)

    def test_reports_home_and_csv_exports(self):
        repair = EquipmentRepair.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            repair_date='2026-05-04',
            status=EquipmentRepair.STATUS_COMPLETED,
            priority=EquipmentRepair.PRIORITY_HIGH,
            description='Report repair issue',
            resolution='Report repair done',
            cost='2500.00',
            contractor='Service',
            created_by=self.admin_user,
        )
        session = InventorySession.objects.create(
            name='Report inventory',
            act_number='REP-INV-001',
            legal_entity=self.legal_entity,
            location=self.location,
            status='completed',
            created_by=self.admin_user,
            confirmed_by=self.admin_user,
        )
        InventoryItem.objects.create(
            session=session,
            equipment=self.equipment,
            found=True,
            actual_location=self.location,
            actual_warehouse=self.warehouse,
            condition_status=EquipmentInventory.CONDITION_OK,
            estimated_value='9000.00',
            checked_by=self.admin_user,
            comment='Report inventory item',
        )
        movement = EquipmentMovement.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            from_location=self.location,
            to_location=self.other_location,
            from_cost_center=self.cost_center,
            to_cost_center=self.other_cost_center,
            from_warehouse=self.warehouse,
            to_warehouse=self.other_warehouse,
            moved_by=self.admin_user,
            comment='Report movement item',
        )
        self.client.force_login(self.admin_user)

        home_response = self.client.get(reverse('reports_home'))
        repair_csv_response = self.client.get(reverse('repair_report_export_csv'))
        repair_xlsx_response = self.client.get(reverse('repair_report_export_xlsx'))
        repair_pdf_response = self.client.get(reverse('repair_report_export_pdf'))
        inventory_csv_response = self.client.get(reverse('inventory_report_export_csv'))
        movement_csv_response = self.client.get(reverse('movement_report_export_csv'))
        movement_xlsx_response = self.client.get(reverse('movement_report_export_xlsx'))
        movement_pdf_response = self.client.get(reverse('movement_report_export_pdf'))

        repair_csv = repair_csv_response.content.decode('utf-8-sig')
        inventory_csv = inventory_csv_response.content.decode('utf-8-sig')
        movement_csv = movement_csv_response.content.decode('utf-8-sig')

        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, reverse('repair_report_export_csv'))
        self.assertContains(home_response, reverse('movement_report_export_csv'))
        self.assertEqual(repair_csv_response.status_code, 200)
        self.assertIn('repair_report.csv', repair_csv_response['Content-Disposition'])
        self.assertIn('Оборудование', repair_csv)
        self.assertIn(str(repair.id), repair_csv)
        self.assertIn('Report repair issue', repair_csv)
        self.assertEqual(repair_xlsx_response.status_code, 200)
        self.assertIn('repair_report.xlsx', repair_xlsx_response['Content-Disposition'])
        self.assertEqual(repair_pdf_response.status_code, 200)
        self.assertIn('repair_report.pdf', repair_pdf_response['Content-Disposition'])
        self.assertEqual(inventory_csv_response.status_code, 200)
        self.assertIn('inventory_report.csv', inventory_csv_response['Content-Disposition'])
        self.assertIn('REP-INV-001', inventory_csv)
        self.assertIn('Report inventory item', inventory_csv)
        self.assertEqual(movement_csv_response.status_code, 200)
        self.assertIn('movement_report.csv', movement_csv_response['Content-Disposition'])
        self.assertIn(str(movement.id), movement_csv)
        self.assertIn('Report movement item', movement_csv)
        self.assertEqual(movement_xlsx_response.status_code, 200)
        self.assertIn('movement_report.xlsx', movement_xlsx_response['Content-Disposition'])
        self.assertEqual(movement_pdf_response.status_code, 200)
        self.assertIn('movement_report.pdf', movement_pdf_response['Content-Disposition'])

    def test_access_secret_can_be_created_with_development_key_fallback(self):
        access_type = AccessType.objects.create(code='web-test', name='Web test')
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=access_type,
            title='Router admin',
            username='admin',
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('access_secret_create', kwargs={'pk': access.pk}),
            {
                'secret_type': 'password',
                'label': 'Пароль',
                'raw_value': 'secret-password',
                'is_active': 'on',
            },
        )
        secret = AccessSecret.objects.get(access=access)
        revealed = reveal_access_secret(secret, self.admin_user, response.wsgi_request, True)

        self.assertRedirects(response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertEqual(revealed, 'secret-password')

    def test_global_search_groups_accessible_results(self):
        access_type = AccessType.objects.create(code='search-web', name='Search web')
        access = EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=access_type,
            title='GLOBAL-SEARCH access',
            host='global-search.local',
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        repair = EquipmentRepair.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            repair_date='2026-05-05',
            description='GLOBAL-SEARCH repair',
            created_by=self.admin_user,
        )
        session = InventorySession.objects.create(
            name='GLOBAL-SEARCH inventory',
            act_number='GSEARCH-001',
            legal_entity=self.legal_entity,
            location=self.location,
            status='in_progress',
            created_by=self.admin_user,
        )
        movement = EquipmentMovement.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            from_location=self.location,
            to_location=self.location,
            from_cost_center=self.cost_center,
            to_cost_center=self.cost_center,
            from_warehouse=self.warehouse,
            to_warehouse=self.warehouse,
            moved_by=self.admin_user,
            comment='GLOBAL-SEARCH movement',
        )
        EquipmentTag.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            tag_type='QR',
            code='GLOBAL-SEARCH-TAG',
            payload=f'https://ays-crm.ru/equipment/{self.equipment.id}/',
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('global_search'), {'q': 'GLOBAL-SEARCH'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertContains(response, reverse('equipment_access_detail', kwargs={'pk': access.pk}))
        self.assertContains(response, reverse('inventory_session_detail', kwargs={'pk': session.pk}))
        self.assertContains(response, 'GLOBAL-SEARCH repair')
        self.assertContains(response, 'GLOBAL-SEARCH movement')
        self.assertContains(response, 'GLOBAL-SEARCH-TAG')
        self.assertContains(response, str(movement.equipment.serial_number))
        self.assertContains(response, access.title)
        self.assertContains(response, repair.equipment.name)

    def test_global_search_respects_equipment_access_scope(self):
        EquipmentTag.objects.create(
            equipment=self.other_equipment,
            legal_entity=self.other_legal_entity,
            tag_type='QR',
            code='HIDDEN-GLOBAL-TAG',
            payload=f'https://ays-crm.ru/equipment/{self.other_equipment.id}/',
        )
        self.client.force_login(self.limited_user)

        response = self.client.get(reverse('global_search'), {'q': 'HIDDEN-GLOBAL'})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'HIDDEN-GLOBAL-TAG')
        self.assertNotContains(response, self.other_equipment.name)

    def test_notifications_show_items_requiring_attention(self):
        old_started_at = timezone.now() - timezone.timedelta(days=10)
        old_inventory_date = timezone.localdate() - timezone.timedelta(days=220)
        expiring_access_date = timezone.localdate() + timezone.timedelta(days=5)
        self.equipment.last_inventory_date = old_inventory_date
        self.equipment.warranty_until = expiring_access_date
        self.equipment.save(update_fields=['last_inventory_date', 'warranty_until', 'updated_at'])
        repair = EquipmentRepair.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            repair_date=timezone.localdate(),
            status=EquipmentRepair.STATUS_IN_PROGRESS,
            description='Notification repair',
            created_by=self.admin_user,
        )
        EquipmentRepair.objects.filter(pk=repair.pk).update(created_at=old_started_at)
        InventorySession.objects.create(
            name='Notification inventory',
            act_number='NOTIFY-INV',
            legal_entity=self.legal_entity,
            location=self.location,
            status='in_progress',
            created_by=self.admin_user,
        )
        access_type = AccessType.objects.create(code='notify-web', name='Notify web')
        EquipmentAccess.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            location=self.location,
            cost_center=self.cost_center,
            access_type=access_type,
            title='Notification access',
            expires_at=expiring_access_date,
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('notifications'))
        home_response = self.client.get(reverse('dashboard_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ремонты долго в работе')
        self.assertContains(response, 'Незавершенная инвентаризация')
        self.assertContains(response, 'Оборудование давно не инвентаризировалось')
        self.assertContains(response, 'Истекающие доступы')
        self.assertContains(response, 'Истекает гарантия')
        self.assertContains(response, 'Notification repair')
        self.assertContains(response, 'NOTIFY-INV')
        self.assertContains(response, 'Notification access')
        self.assertContains(home_response, reverse('notifications'))
        self.assertContains(home_response, 'Требует внимания')

    def test_notifications_respect_access_scope(self):
        old_started_at = timezone.now() - timezone.timedelta(days=10)
        repair = EquipmentRepair.objects.create(
            equipment=self.other_equipment,
            legal_entity=self.other_legal_entity,
            repair_date=timezone.localdate(),
            status=EquipmentRepair.STATUS_IN_PROGRESS,
            description='Hidden notification repair',
            created_by=self.admin_user,
        )
        EquipmentRepair.objects.filter(pk=repair.pk).update(created_at=old_started_at)
        self.client.force_login(self.limited_user)

        response = self.client.get(reverse('notifications'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Hidden notification repair')
        self.assertNotContains(response, self.other_equipment.name)

    def test_inventory_session_flow_creates_act_items_and_confirmation(self):
        self.client.force_login(self.admin_user)

        create_response = self.client.post(
            reverse('inventory_session_create'),
            {
                'name': 'Инвентаризация бара',
                'act_number': 'INV-ACT-001',
                'legal_entity': self.legal_entity.pk,
                'location': self.location.pk,
                'period_start': '2026-05-06',
                'period_end': '2026-05-06',
                'comment': 'Плановая проверка',
            },
        )
        session = InventorySession.objects.get(act_number='INV-ACT-001')
        add_response = self.client.post(
            reverse('inventory_session_add_item', kwargs={'pk': session.pk}),
            {'equipment': self.equipment.pk},
        )
        item = InventoryItem.objects.get(session=session, equipment=self.equipment)
        check_response = self.client.post(
            reverse('inventory_item_check', kwargs={'pk': session.pk, 'item_pk': item.pk}),
            {
                'found': 'on',
                'actual_location': self.location.pk,
                'actual_warehouse': self.warehouse.pk,
                'condition_status': EquipmentInventory.CONDITION_OK,
                'estimated_value': '10000.00',
                'comment': 'Проверено по QR',
            },
        )
        confirm_response = self.client.post(reverse('inventory_session_confirm', kwargs={'pk': session.pk}))
        print_response = self.client.get(reverse('inventory_session_print', kwargs={'pk': session.pk}))

        session.refresh_from_db()
        item.refresh_from_db()
        self.equipment.refresh_from_db()

        self.assertRedirects(create_response, reverse('inventory_session_detail', kwargs={'pk': session.pk}))
        self.assertRedirects(add_response, reverse('inventory_session_detail', kwargs={'pk': session.pk}))
        self.assertRedirects(check_response, reverse('inventory_session_detail', kwargs={'pk': session.pk}))
        self.assertRedirects(confirm_response, reverse('inventory_session_detail', kwargs={'pk': session.pk}))
        self.assertEqual(session.status, 'completed')
        self.assertEqual(session.confirmed_by, self.admin_user)
        self.assertTrue(item.found)
        self.assertEqual(item.checked_by, self.admin_user)
        self.assertEqual(str(self.equipment.last_inventory_date), '2026-05-06')
        self.assertContains(print_response, 'Акт инвентаризации')
        self.assertContains(print_response, 'INV-ACT-001')
        self.assertNotContains(print_response, 'sidebar')
        self.assertNotContains(print_response, 'Equipment System')

    def test_equipment_can_be_added_to_active_inventory_from_card(self):
        session = InventorySession.objects.create(
            name='Быстрая инвентаризация',
            legal_entity=self.legal_entity,
            location=self.location,
            status='in_progress',
            created_by=self.admin_user,
        )
        self.client.force_login(self.admin_user)

        detail_response = self.client.get(reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        add_response = self.client.post(
            reverse('equipment_add_to_inventory_session', kwargs={'pk': self.equipment.pk}),
            {'session': session.pk},
        )

        self.assertContains(detail_response, 'Добавить в инвентаризацию')
        self.assertRedirects(add_response, reverse('inventory_session_detail', kwargs={'pk': session.pk}))
        self.assertTrue(InventoryItem.objects.filter(session=session, equipment=self.equipment).exists())

    def test_admin_can_view_audit_log(self):
        ActionLog.objects.create(
            actor=self.admin_user,
            action=ActionLog.ACTION_UPDATE,
            object_repr='Test object',
            message='Audit test',
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('audit_log'), {'q': 'Audit'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Audit test')

    def test_archived_equipment_is_hidden_from_default_list(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('equipment_archive', kwargs={'pk': self.equipment.pk}))
        default_list_response = self.client.get(reverse('equipment_list'))
        archived_list_response = self.client.get(reverse('equipment_list'), {'activity': 'archived'})
        all_list_response = self.client.get(reverse('equipment_list'), {'activity': 'all'})

        self.equipment.refresh_from_db()

        self.assertRedirects(response, reverse('equipment_detail', kwargs={'pk': self.equipment.pk}))
        self.assertFalse(self.equipment.is_active)
        self.assertNotContains(default_list_response, self.equipment.name)
        self.assertContains(archived_list_response, self.equipment.name)
        self.assertContains(all_list_response, self.equipment.name)

    def test_equipment_list_searches_by_qr_code(self):
        self.client.force_login(self.admin_user)
        EquipmentTag.objects.create(
            equipment=self.equipment,
            legal_entity=self.legal_entity,
            tag_type='QR',
            code='QR-SEARCH-001',
            payload=f'https://ays-crm.ru/equipment/{self.equipment.id}/',
        )

        by_code_response = self.client.get(reverse('equipment_list'), {'q': 'QR-SEARCH-001'})
        by_payload_response = self.client.get(reverse('equipment_list'), {'q': str(self.equipment.id)})

        self.assertContains(by_code_response, self.equipment.name)
        self.assertNotContains(by_code_response, self.other_equipment.name)
        self.assertContains(by_payload_response, self.equipment.name)
        self.assertNotContains(by_payload_response, self.other_equipment.name)

    def test_equipment_export_csv_respects_filters_and_access(self):
        self.client.force_login(self.limited_user)

        response = self.client.get(reverse('equipment_export_csv'), {'q': 'SER-001'})
        content = response.content.decode('utf-8-sig')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8-sig')
        self.assertIn('equipment_export.csv', response['Content-Disposition'])
        self.assertIn('SER-001', content)
        self.assertNotIn('SER-002', content)

    def test_location_editor_can_move_accessible_equipment(self):
        editor_user = User.objects.create_user(
            username='editor-user',
            password='password',
        )
        UserLocationAccess.objects.create(
            user=editor_user,
            location=self.location,
            access_level='edit',
        )
        self.client.force_login(editor_user)

        response = self.client.get(reverse('equipment_move', kwargs={'pk': self.equipment.pk}))
        list_response = self.client.get(reverse('equipment_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(list_response, 'Переместить')

    def test_scope_edit_guard_allows_only_editable_destinations(self):
        editor_user = User.objects.create_user(
            username='scope-editor-user',
            password='password',
        )
        UserLocationAccess.objects.create(
            user=editor_user,
            location=self.location,
            access_level='edit',
        )

        require_scope_edit_access(editor_user, self.legal_entity, self.location)

        with self.assertRaises(PermissionDenied):
            require_scope_edit_access(editor_user, self.other_legal_entity, self.other_location)

    def test_location_editor_cannot_move_equipment_to_uneditable_location(self):
        editor_user = User.objects.create_user(
            username='move-editor-user',
            password='password',
        )
        UserLocationAccess.objects.create(
            user=editor_user,
            location=self.location,
            access_level='edit',
        )
        self.client.force_login(editor_user)

        response = self.client.post(
            reverse('equipment_move', kwargs={'pk': self.equipment.pk}),
            {
                'legal_entity': self.other_legal_entity.id,
                'to_location': self.other_location.id,
                'to_cost_center': self.other_cost_center.id,
                'to_warehouse': self.other_warehouse.name,
                'comment': 'Invalid move',
            },
        )

        self.equipment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EquipmentMovement.objects.filter(equipment=self.equipment).exists())
        self.assertEqual(self.equipment.location, self.location)
        self.assertContains(response, 'Выберите корректный вариант')

    def test_location_editor_cannot_create_equipment_in_uneditable_location(self):
        editor_user = User.objects.create_user(
            username='create-editor-user',
            password='password',
        )
        UserLocationAccess.objects.create(
            user=editor_user,
            location=self.location,
            access_level='edit',
        )
        self.client.force_login(editor_user)

        response = self.client.post(
            reverse('equipment_create'),
            {
                'legal_entity': self.other_legal_entity.id,
                'location': self.other_location.id,
                'cost_center': self.other_cost_center.id,
                'warehouse': self.other_warehouse.name,
                'category': self.category.id,
                'status': self.status.id,
                'name': 'Unauthorized printer',
                'brand': '',
                'model': '',
                'serial_number': 'SER-004',
                'inventory_number': 'INV-004',
                'purchase_date': '',
                'warranty_until': '',
                'price': '',
                'responsible_user': '',
                'comment': '',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Equipment.objects.filter(serial_number='SER-004').exists())
        self.assertContains(response, 'Выберите корректный вариант')

    def test_cost_centers_ajax_filters_by_location(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('ajax_cost_centers'),
            {
                'location': self.location.id,
                'legal_entity': self.legal_entity.id,
            },
        )

        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['items'], [
            {
                'id': str(self.cost_center.id),
                'name': self.cost_center.name,
            }
        ])

    def test_warehouses_ajax_filters_by_cost_center(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('ajax_warehouses'),
            {
                'cost_center': self.cost_center.id,
            },
        )

        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['items'], [
            {
                'id': self.warehouse.name,
                'name': self.warehouse.name,
            }
        ])

    def test_ajax_cost_centers_are_limited_to_editable_scope(self):
        editor_user = User.objects.create_user(
            username='ajax-editor-user',
            password='password',
        )
        UserLocationAccess.objects.create(
            user=editor_user,
            location=self.location,
            access_level='edit',
        )
        self.client.force_login(editor_user)

        allowed_response = self.client.get(
            reverse('ajax_cost_centers'),
            {
                'location': self.location.id,
                'legal_entity': self.legal_entity.id,
            },
        )
        denied_response = self.client.get(
            reverse('ajax_cost_centers'),
            {
                'location': self.other_location.id,
                'legal_entity': self.other_legal_entity.id,
            },
        )

        self.assertEqual(allowed_response.json()['items'], [
            {
                'id': str(self.cost_center.id),
                'name': self.cost_center.name,
            }
        ])
        self.assertEqual(denied_response.json()['items'], [
            {
                'id': str(self.other_cost_center.id),
                'name': self.other_cost_center.name,
            }
        ])

    def test_ajax_warehouses_are_limited_to_editable_scope(self):
        editor_user = User.objects.create_user(
            username='ajax-warehouse-editor-user',
            password='password',
        )
        UserLocationAccess.objects.create(
            user=editor_user,
            location=self.location,
            access_level='edit',
        )
        self.client.force_login(editor_user)

        allowed_response = self.client.get(
            reverse('ajax_warehouses'),
            {
                'cost_center': self.cost_center.id,
            },
        )
        denied_response = self.client.get(
            reverse('ajax_warehouses'),
            {
                'cost_center': self.other_cost_center.id,
            },
        )

        self.assertEqual(allowed_response.json()['items'], [
            {
                'id': self.warehouse.name,
                'name': self.warehouse.name,
            }
        ])
        self.assertEqual(denied_response.json()['items'], [
            {
                'id': self.other_warehouse.name,
                'name': self.other_warehouse.name,
            }
        ])

    def test_anonymous_user_is_redirected_to_custom_login(self):
        response = self.client.get(reverse('equipment_list'))

        self.assertRedirects(response, '/login/?next=/equipment/')

    def test_custom_login_page_authenticates_user(self):
        login_response = self.client.get(reverse('login'))

        self.assertEqual(login_response.status_code, 200)
        self.assertTemplateUsed(login_response, 'registration/login.html')

        response = self.client.post(
            reverse('login'),
            {
                'username': 'admin-user',
                'password': 'password',
            },
        )

        self.assertRedirects(response, '/app/')

    def test_admin_panel_is_available_by_default_for_all_roles(self):
        self.client.force_login(self.limited_user)

        response = self.client.get(reverse('admin_panel_home'))

        self.assertEqual(response.status_code, 200)

    def test_staff_flag_without_admin_role_can_access_admin_panel_when_permission_enabled(self):
        staff_user = User.objects.create_user(
            username='staff-flag-user',
            password='password',
            is_staff=True,
            role='staff',
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse('admin_panel_home'))
        list_response = self.client.get(reverse('equipment_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(list_response, 'Администрирование')
        self.assertContains(list_response, 'Django Admin')

    def test_admin_panel_home_is_available_for_admin(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin_panel_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Юридические лица')
        self.assertContains(response, 'Пользователи')

    def test_company_admin_sees_all_directory_sections_when_permissions_enabled(self):
        company_admin = User.objects.create_user(
            username='company-admin-user',
            password='password',
            role='company_admin',
        )
        UserLegalEntityAccess.objects.create(
            user=company_admin,
            legal_entity=self.legal_entity,
            access_level='admin',
            allow_all_locations=True,
        )
        self.client.force_login(company_admin)

        home_response = self.client.get(reverse('admin_panel_home'))
        legal_entities_response = self.client.get(
            reverse('admin_section_list', kwargs={'section': 'legal-entities'}),
        )
        users_response = self.client.get(
            reverse('admin_section_list', kwargs={'section': 'users'}),
        )
        create_legal_entity_response = self.client.get(
            reverse('admin_section_create', kwargs={'section': 'legal-entities'}),
        )
        delete_legal_entity_response = self.client.get(
            reverse('admin_section_delete', kwargs={
                'section': 'legal-entities',
                'pk': self.legal_entity.pk,
            }),
        )

        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, 'Юридические лица')
        self.assertContains(home_response, 'Пользователи')
        self.assertContains(home_response, 'Категории оборудования')
        self.assertEqual(legal_entities_response.status_code, 200)
        self.assertContains(legal_entities_response, self.legal_entity.name)
        self.assertContains(legal_entities_response, self.other_legal_entity.name)
        self.assertContains(legal_entities_response, 'Добавить')
        self.assertContains(legal_entities_response, 'Удалить')
        self.assertEqual(users_response.status_code, 200)
        self.assertEqual(create_legal_entity_response.status_code, 200)
        self.assertEqual(delete_legal_entity_response.status_code, 200)

    def test_company_admin_can_create_cost_center_outside_scope_when_permissions_enabled(self):
        company_admin = User.objects.create_user(
            username='company-admin-cost-center-user',
            password='password',
            role='company_admin',
        )
        UserLegalEntityAccess.objects.create(
            user=company_admin,
            legal_entity=self.legal_entity,
            access_level='admin',
            allow_all_locations=True,
        )
        self.client.force_login(company_admin)

        response = self.client.post(
            reverse('admin_section_create', kwargs={'section': 'cost-centers'}),
            {
                'legal_entity': self.other_legal_entity.pk,
                'location': self.other_location.pk,
                'name': 'Unauthorized cost center',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(CostCenter.objects.filter(name='Unauthorized cost center').exists())

    def test_company_admin_can_manage_warehouse_outside_scope_when_permissions_enabled(self):
        company_admin = User.objects.create_user(
            username='company-admin-warehouse-user',
            password='password',
            role='company_admin',
        )
        UserLegalEntityAccess.objects.create(
            user=company_admin,
            legal_entity=self.legal_entity,
            access_level='admin',
            allow_all_locations=True,
        )
        self.client.force_login(company_admin)

        update_response = self.client.get(
            reverse('admin_section_update', kwargs={
                'section': 'warehouses',
                'pk': self.other_warehouse.pk,
            }),
        )
        create_response = self.client.post(
            reverse('admin_section_create', kwargs={'section': 'warehouses'}),
            {
                'legal_entity': self.other_legal_entity.pk,
                'location': self.other_location.pk,
                'cost_center': self.other_cost_center.pk,
                'name': 'Unauthorized warehouse',
                'is_active': 'on',
            },
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(create_response.status_code, 302)
        self.assertTrue(Warehouse.objects.filter(name='Unauthorized warehouse').exists())

    def test_admin_can_create_update_and_delete_category(self):
        self.client.force_login(self.admin_user)

        create_response = self.client.post(
            reverse('admin_section_create', kwargs={'section': 'equipment-categories'}),
            {'name': 'Кофейное оборудование'},
        )
        category = EquipmentCategory.objects.get(name='Кофейное оборудование')

        update_response = self.client.post(
            reverse('admin_section_update', kwargs={'section': 'equipment-categories', 'pk': category.pk}),
            {'name': 'Барное оборудование'},
        )
        category.refresh_from_db()

        delete_response = self.client.post(
            reverse('admin_section_delete', kwargs={'section': 'equipment-categories', 'pk': category.pk}),
        )

        self.assertRedirects(create_response, reverse('admin_section_list', kwargs={'section': 'equipment-categories'}))
        self.assertRedirects(update_response, reverse('admin_section_list', kwargs={'section': 'equipment-categories'}))
        self.assertRedirects(delete_response, reverse('admin_section_list', kwargs={'section': 'equipment-categories'}))
        self.assertEqual(category.name, 'Барное оборудование')
        self.assertFalse(EquipmentCategory.objects.filter(pk=category.pk).exists())

    def test_admin_delete_confirmation_page_is_shown_before_delete(self):
        self.client.force_login(self.admin_user)
        category = EquipmentCategory.objects.create(name='Временная категория')

        response = self.client.get(
            reverse('admin_section_delete', kwargs={'section': 'equipment-categories', 'pk': category.pk}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/admin_panel/confirm_delete.html')
        self.assertContains(response, 'Временная категория')

    def test_admin_can_create_warehouse_with_related_filters(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin_section_create', kwargs={'section': 'warehouses'}),
            {
                'legal_entity': self.legal_entity.pk,
                'location': self.location.pk,
                'cost_center': self.cost_center.pk,
                'name': 'Сервис',
                'is_active': 'on',
            },
        )

        self.assertRedirects(response, reverse('admin_section_list', kwargs={'section': 'warehouses'}))
        self.assertTrue(Warehouse.objects.filter(cost_center=self.cost_center, name='Сервис').exists())

    def test_admin_can_create_location_access(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin_section_create', kwargs={'section': 'location-accesses'}),
            {
                'user': self.limited_user.pk,
                'location': self.location.pk,
                'access_level': 'edit',
            },
        )

        self.assertRedirects(response, reverse('admin_section_list', kwargs={'section': 'location-accesses'}))
        self.assertTrue(
            self.limited_user.location_accesses.filter(location=self.location, access_level='edit').exists()
        )

    def test_qr_print_pdf_returns_pdf_for_selected_equipment(self):
        self.client.force_login(self.admin_user)

        with patch.object(
            EquipmentTag,
            'generate_qr_image',
            lambda tag: setattr(tag.qr_image, 'name', f'qr_codes/qr_{tag.code}.png'),
        ):
            response = self.client.get(
                reverse('qr_print_pdf'),
                {'ids': [str(self.equipment.id)]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response.content[:4], b'%PDF')
        self.assertIn('equipment_qr_labels.pdf', response['Content-Disposition'])
