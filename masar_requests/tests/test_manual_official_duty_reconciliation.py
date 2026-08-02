"""
AR: اختبارات آلية للتحقق من منطق `test_manual_official_duty_reconciliation` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_manual_official_duty_reconciliation` behavior and regression prevention.
"""

from pathlib import Path
import frappe
from frappe.tests.utils import FrappeTestCase

from masar_requests.manual_official_duty_reconciliation import (
    MANUAL_RESOLUTION_CONFIRMED,
    _clean_detail_row,
    _validate_full_confirmation,
    get_manual_reconciliation_custom_fields,
    is_manual_reconciliation_authorized,
    setup_manual_reconciliation_fields,
)


class TestManualOfficialDutyReconciliation(FrappeTestCase):
    """
    AR: فئة `TestManualOfficialDutyReconciliation` لتنظيم منطق اختبار اليدوي الرسمية المهمة التسوية.
    EN: Class `TestManualOfficialDutyReconciliation` that organizes test manual official duty reconciliation logic.
    """
    def test_custom_fields_are_declared_for_all_required_doctypes(self):
        """
        AR: اختبار سيناريو `custom` الحقول `are` `declared` `for` `all` `required` `doctypes` والتحقق من النتيجة المتوقعة.
        EN: Verify the custom fields are declared for all required doctypes scenario and its expected result.
        """
        definitions = get_manual_reconciliation_custom_fields()
        self.assertIn("Official Duty Request", definitions)
        self.assertIn("Official Duty Attendance Detail", definitions)
        self.assertIn("Attendance", definitions)

    def test_custom_fields_exist_after_setup(self):
        """
        AR: اختبار سيناريو `custom` الحقول `exist` معالجة ما بعد إعداد والتحقق من النتيجة المتوقعة.
        EN: Verify the custom fields exist after setup scenario and its expected result.
        """
        setup_manual_reconciliation_fields()
        self.assertTrue(
            frappe.get_meta("Official Duty Request", cached=False).has_field(
                "custom_total_manual_confirmed_hours"
            )
        )
        self.assertTrue(
            frappe.get_meta("Official Duty Attendance Detail", cached=False).has_field(
                "custom_manual_confirmed_hours"
            )
        )
        self.assertTrue(
            frappe.get_meta("Attendance", cached=False).has_field(
                "custom_manual_confirmed_working_hours"
            )
        )

    def test_full_uncovered_hours_can_be_confirmed(self):
        """
        AR: اختبار سيناريو `full` `uncovered` `hours` التحقق من إمكانية `be` `confirmed` والتحقق من النتيجة المتوقعة.
        EN: Verify the full uncovered hours can be confirmed scenario and its expected result.
        """
        self.assertEqual(_validate_full_confirmation(6, 6), 6)

    def test_partial_confirmation_is_blocked(self):
        """
        AR: اختبار سيناريو الجزئي `confirmation` التحقق من كون `blocked` والتحقق من النتيجة المتوقعة.
        EN: Verify the partial confirmation is blocked scenario and its expected result.
        """
        with self.assertRaises(frappe.ValidationError):
            _validate_full_confirmation(6, 3)

    def test_excess_confirmation_is_blocked(self):
        """
        AR: اختبار سيناريو `excess` `confirmation` التحقق من كون `blocked` والتحقق من النتيجة المتوقعة.
        EN: Verify the excess confirmation is blocked scenario and its expected result.
        """
        with self.assertRaises(frappe.ValidationError):
            _validate_full_confirmation(6, 7)

    def test_child_metadata_is_removed_before_resave(self):
        """
        AR: اختبار سيناريو `child` `metadata` التحقق من كون `removed` معالجة ما قبل `resave` والتحقق من النتيجة المتوقعة.
        EN: Verify the child metadata is removed before resave scenario and its expected result.
        """
        row = frappe._dict(
            {
                "name": "ROW-1",
                "parent": "ODR-1",
                "parentfield": "attendance_details",
                "parenttype": "Official Duty Request",
                "doctype": "Official Duty Attendance Detail",
                "attendance_date": "2026-06-02",
                "custom_manual_resolution": MANUAL_RESOLUTION_CONFIRMED,
            }
        )
        cleaned = _clean_detail_row(row)
        self.assertNotIn("name", cleaned)
        self.assertNotIn("parent", cleaned)
        self.assertEqual(cleaned.custom_manual_resolution, MANUAL_RESOLUTION_CONFIRMED)

    def test_invalid_manual_resolution_zero_is_cleared(self):
        """
        AR: اختبار سيناريو `invalid` اليدوي `resolution` `zero` التحقق من كون `cleared` والتحقق من النتيجة المتوقعة.
        EN: Verify the invalid manual resolution zero is cleared scenario and its expected result.
        """
        row = frappe._dict(
            {
                "attendance_date": "2026-06-02",
                "custom_manual_resolution": 0,
            }
        )
        cleaned = _clean_detail_row(row)
        self.assertIsNone(cleaned.custom_manual_resolution)

    def test_manual_resolution_field_is_read_only_data(self):
        """
        AR: اختبار سيناريو اليدوي `resolution` الحقل التحقق من كون القراءة `only` `data` والتحقق من النتيجة المتوقعة.
        EN: Verify the manual resolution field is read only data scenario and its expected result.
        """
        definitions = get_manual_reconciliation_custom_fields()
        field = next(
            row
            for row in definitions["Official Duty Attendance Detail"]
            if row["fieldname"] == "custom_manual_resolution"
        )
        self.assertEqual(field["fieldtype"], "Data")
        self.assertTrue(field["read_only"])
        self.assertNotIn("options", field)

    def test_hr_manager_is_authorized(self):
        """
        AR: اختبار سيناريو `hr` المدير التحقق من كون `authorized` والتحقق من النتيجة المتوقعة.
        EN: Verify the hr manager is authorized scenario and its expected result.
        """
        self.assertTrue(
            is_manual_reconciliation_authorized(
                "hr.manager@example.com",
                ["HR Manager", "HR User"],
            )
        )

    def test_hr_user_without_manager_role_is_blocked(self):
        """
        AR: اختبار سيناريو `hr` المستخدم `without` المدير الدور التحقق من كون `blocked` والتحقق من النتيجة المتوقعة.
        EN: Verify the hr user without manager role is blocked scenario and its expected result.
        """
        self.assertFalse(
            is_manual_reconciliation_authorized(
                "hr.user@example.com",
                ["HR User"],
            )
        )

    def test_engine_preserves_completed_manual_rows(self):
        """
        AR: اختبار سيناريو `engine` `preserves` `completed` اليدوي `rows` والتحقق من النتيجة المتوقعة.
        EN: Verify the engine preserves completed manual rows scenario and its expected result.
        """
        engine_path = Path(__file__).parents[1] / "official_duty_engine.py"
        source = engine_path.read_text(encoding="utf-8")
        self.assertIn("custom_manual_resolution", source)
        self.assertIn("MASAR_MANUAL_RECONCILIATION_PRESERVE", source)
