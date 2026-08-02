"""
AR: اختبارات آلية للتحقق من منطق `test_remaining_requirements_v21_7` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_remaining_requirements_v21_7` behavior and regression prevention.
"""

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRemainingRequirementsV217(FrappeTestCase):
    """
    AR: فئة `TestRemainingRequirementsV217` لتنظيم منطق اختبار `remaining` `requirements` `v21` `7`.
    EN: Class `TestRemainingRequirementsV217` that organizes test remaining requirements v21 7 logic.
    """
    def test_hr_operational_employee_links_ignore_user_permissions(self):
        """
        AR: اختبار سيناريو `hr` `operational` الموظف `links` `ignore` المستخدم الصلاحيات والتحقق من النتيجة المتوقعة.
        EN: Verify the hr operational employee links ignore user permissions scenario and its expected result.
        """
        for doctype in (
            "Attendance Request",
            "Attendance",
            "Employee Checkin",
        ):
            field = frappe.get_meta(
                doctype,
                cached=False,
            ).get_field("employee")
            self.assertTrue(field)
            self.assertTrue(field.ignore_user_permissions)

    def test_leave_dates_and_reason_are_visible(self):
        """
        AR: اختبار سيناريو الإجازة `dates` `and` `reason` `are` `visible` والتحقق من النتيجة المتوقعة.
        EN: Verify the leave dates and reason are visible scenario and its expected result.
        """
        meta = frappe.get_meta(
            "Leave Application",
            cached=False,
        )

        for fieldname in ("from_date", "to_date"):
            field = meta.get_field(fieldname)
            self.assertTrue(field)
            self.assertFalse(field.get("hidden"))
            self.assertEqual(
                field.get("depends_on"),
                "eval:!doc.half_day && !doc.quarter_day && !doc.is_hourly",
            )

        reason = (
            meta.get_field("description")
            or meta.get_field("reason")
        )
        self.assertTrue(reason)
        self.assertFalse(reason.get("hidden"))
        self.assertFalse(reason.get("depends_on"))

    def test_material_purchase_columns_are_available(self):
        """
        AR: اختبار سيناريو المواد `purchase` `columns` `are` `available` والتحقق من النتيجة المتوقعة.
        EN: Verify the material purchase columns are available scenario and its expected result.
        """
        meta = frappe.get_meta(
            "Material Request Item",
            cached=False,
        )

        for fieldname in ("rate", "amount"):
            field = meta.get_field(fieldname)
            self.assertTrue(field)
            self.assertFalse(field.hidden)
            self.assertTrue(field.in_list_view)

        self.assertTrue(
            frappe.get_meta(
                "Material Request",
                cached=False,
            ).has_field("custom_estimated_total")
        )

    def test_client_fixes_are_installed(self):
        """
        AR: اختبار سيناريو `client` `fixes` `are` `installed` والتحقق من النتيجة المتوقعة.
        EN: Verify the client fixes are installed scenario and its expected result.
        """
        package = Path(frappe.get_app_path("masar_requests"))

        leave_source = (
            package / "public/js/masar_requests.js"
        ).read_text(encoding="utf-8")
        material_source = (
            package / "public/js/material_request.js"
        ).read_text(encoding="utf-8")

        self.assertIn("MASAR_LEAVE_LAYOUT_V21_7", leave_source)
        self.assertIn("MASAR_PURCHASE_COLUMNS_V21_7", material_source)

    def test_manual_review_notification_is_installed(self):
        """
        AR: اختبار سيناريو اليدوي `review` الإشعار التحقق من كون `installed` والتحقق من النتيجة المتوقعة.
        EN: Verify the manual review notification is installed scenario and its expected result.
        """
        package = Path(frappe.get_app_path("masar_requests"))
        source = (
            package / "official_duty_request_permissions.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "MASAR_MANUAL_REVIEW_NOTIFICATION_V21_7",
            source,
        )
