"""
AR: اختبارات آلية للتحقق من منطق `test_leave_layout_visibility_v21_8` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_leave_layout_visibility_v21_8` behavior and regression prevention.
"""

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase


class TestLeaveLayoutVisibilityV218(FrappeTestCase):
    """
    AR: فئة `TestLeaveLayoutVisibilityV218` لتنظيم منطق اختبار الإجازة `layout` الظهور `v21` `8`.
    EN: Class `TestLeaveLayoutVisibilityV218` that organizes test leave layout visibility v21 8 logic.
    """
    def test_leave_core_fields_are_visible(self):
        """
        AR: اختبار سيناريو الإجازة `core` الحقول `are` `visible` والتحقق من النتيجة المتوقعة.
        EN: Verify the leave core fields are visible scenario and its expected result.
        """
        meta = frappe.get_meta("Leave Application", cached=False)

        for fieldname in (
            "section_break_5",
            "column_break1",
            "from_date",
            "to_date",
            "description",
        ):
            field = meta.get_field(fieldname)
            self.assertTrue(field, fieldname)
            self.assertFalse(field.get("hidden"), fieldname)

        for fieldname in ("from_date", "to_date"):
            field = meta.get_field(fieldname)
            self.assertEqual(
                field.get("depends_on"),
                "eval:!doc.half_day && !doc.quarter_day && !doc.is_hourly",
                fieldname,
            )

        description = meta.get_field("description")
        self.assertFalse(
            description.get("depends_on"),
            "description",
        )

    def test_leave_field_order_is_correct(self):
        """
        AR: اختبار سيناريو الإجازة الحقل `order` التحقق من كون `correct` والتحقق من النتيجة المتوقعة.
        EN: Verify the leave field order is correct scenario and its expected result.
        """
        value = frappe.db.get_value(
            "Property Setter",
            {
                "doc_type": "Leave Application",
                "doctype_or_field": "DocType",
                "property": "field_order",
            },
            "value",
        )
        order = json.loads(value or "[]")

        required = [
            "section_break_5",
            "half_day",
            "quarter_day",
            "is_hourly",
            "from_date",
            "to_date",
            "column_break1",
            "description",
        ]

        for fieldname in required:
            self.assertIn(fieldname, order)

        positions = [order.index(fieldname) for fieldname in required]
        self.assertEqual(positions, sorted(positions))

    def test_permanent_setup_override_is_installed(self):
        """
        AR: اختبار سيناريو `permanent` إعداد `override` التحقق من كون `installed` والتحقق من النتيجة المتوقعة.
        EN: Verify the permanent setup override is installed scenario and its expected result.
        """
        source = Path(
            frappe.get_app_path(
                "masar_requests",
                "setup_leave_and_shift.py",
            )
        ).read_text(encoding="utf-8")

        self.assertIn(
            "MASAR_LEAVE_LAYOUT_SOURCE_V21_8",
            source,
        )

    def test_client_visibility_fix_is_installed(self):
        """
        AR: اختبار سيناريو `client` الظهور `fix` التحقق من كون `installed` والتحقق من النتيجة المتوقعة.
        EN: Verify the client visibility fix is installed scenario and its expected result.
        """
        source = Path(
            frappe.get_app_path(
                "masar_requests",
                "public/js/masar_requests.js",
            )
        ).read_text(encoding="utf-8")

        self.assertIn(
            "MASAR_LEAVE_LAYOUT_CLIENT_V21_8",
            source,
        )
