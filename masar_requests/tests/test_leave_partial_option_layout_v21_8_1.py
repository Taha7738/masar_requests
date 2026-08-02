"""
AR: اختبارات آلية للتحقق من منطق `test_leave_partial_option_layout_v21_8_1` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_leave_partial_option_layout_v21_8_1` behavior and regression prevention.
"""

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase


class TestLeavePartialOptionLayoutV2181(FrappeTestCase):
    """
    AR: فئة `TestLeavePartialOptionLayoutV2181` لتنظيم منطق اختبار الإجازة الجزئي `option` `layout` `v21` `8` `1`.
    EN: Class `TestLeavePartialOptionLayoutV2181` that organizes test leave partial option layout v21 8 1 logic.
    """
    def test_options_are_before_normal_dates(self):
        """
        AR: اختبار سيناريو `options` `are` معالجة ما قبل `normal` `dates` والتحقق من النتيجة المتوقعة.
        EN: Verify the options are before normal dates scenario and its expected result.
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
            "half_day",
            "quarter_day",
            "is_hourly",
            "from_date",
            "to_date",
        ]

        for fieldname in required:
            self.assertIn(fieldname, order)

        positions = [order.index(fieldname) for fieldname in required]
        self.assertEqual(positions, sorted(positions))

    def test_normal_dates_hide_for_partial_options(self):
        """
        AR: اختبار سيناريو `normal` `dates` `hide` `for` الجزئي `options` والتحقق من النتيجة المتوقعة.
        EN: Verify the normal dates hide for partial options scenario and its expected result.
        """
        meta = frappe.get_meta("Leave Application", cached=False)
        expected = (
            "eval:!doc.half_day && !doc.quarter_day && !doc.is_hourly"
        )

        for fieldname in ("from_date", "to_date"):
            field = meta.get_field(fieldname)
            self.assertTrue(field)
            self.assertFalse(field.get("hidden"))
            self.assertEqual(field.get("depends_on"), expected)

    def test_reason_remains_visible(self):
        """
        AR: اختبار سيناريو `reason` `remains` `visible` والتحقق من النتيجة المتوقعة.
        EN: Verify the reason remains visible scenario and its expected result.
        """
        field = frappe.get_meta(
            "Leave Application",
            cached=False,
        ).get_field("description")

        self.assertTrue(field)
        self.assertFalse(field.get("hidden"))
        self.assertFalse(field.get("depends_on"))

    def test_client_override_is_installed(self):
        """
        AR: اختبار سيناريو `client` `override` التحقق من كون `installed` والتحقق من النتيجة المتوقعة.
        EN: Verify the client override is installed scenario and its expected result.
        """
        source = Path(
            frappe.get_app_path(
                "masar_requests",
                "public/js/masar_requests.js",
            )
        ).read_text(encoding="utf-8")

        self.assertIn(
            "MASAR_LEAVE_LAYOUT_CLIENT_V21_8_1",
            source,
        )
        self.assertIn(
            "frm.toggle_display(fieldname, !partialSelected)",
            source,
        )
