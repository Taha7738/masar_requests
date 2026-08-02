"""
AR: اختبارات آلية للتحقق من منطق `test_official_duty_reconciliation_retry` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_official_duty_reconciliation_retry` behavior and regression prevention.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from masar_requests.official_duty_engine import (
    _normalize_previous_detail,
)


class TestOfficialDutyReconciliationRetry(FrappeTestCase):
    """
    AR: فئة `TestOfficialDutyReconciliationRetry` لتنظيم منطق اختبار الرسمية المهمة التسوية `retry`.
    EN: Class `TestOfficialDutyReconciliationRetry` that organizes test official duty reconciliation retry logic.
    """
    def test_child_document_is_normalized_with_as_dict(self):
        """
        AR: اختبار سيناريو `child` المستند التحقق من كون `normalized` `with` `as` `dict` والتحقق من النتيجة المتوقعة.
        EN: Verify the child document is normalized with as dict scenario and its expected result.
        """
        row = frappe.get_doc(
            {
                "doctype": "Official Duty Attendance Detail",
                "attendance_date": "2026-08-01",
                "reconciliation_status": "Manual Review",
                "message": "Previous reconciliation result",
                "official_duty_hours": 7,
            }
        )

        normalized = _normalize_previous_detail(row)

        self.assertIsInstance(normalized, frappe._dict)
        self.assertEqual(
            str(normalized.attendance_date),
            "2026-08-01",
        )
        self.assertEqual(
            normalized.reconciliation_status,
            "Manual Review",
        )
        self.assertEqual(
            normalized.official_duty_hours,
            7,
        )

    def test_regular_dictionary_is_supported(self):
        """
        AR: اختبار سيناريو `regular` `dictionary` التحقق من كون `supported` والتحقق من النتيجة المتوقعة.
        EN: Verify the regular dictionary is supported scenario and its expected result.
        """
        normalized = _normalize_previous_detail(
            {
                "attendance": "HR-ATT-TEST",
                "previous_status": "Absent",
            }
        )

        self.assertIsInstance(normalized, frappe._dict)
        self.assertEqual(
            normalized.attendance,
            "HR-ATT-TEST",
        )
        self.assertEqual(
            normalized.previous_status,
            "Absent",
        )

    def test_empty_previous_detail_is_supported(self):
        """
        AR: اختبار سيناريو `empty` `previous` `detail` التحقق من كون `supported` والتحقق من النتيجة المتوقعة.
        EN: Verify the empty previous detail is supported scenario and its expected result.
        """
        normalized = _normalize_previous_detail(None)

        self.assertIsInstance(normalized, frappe._dict)
        self.assertEqual(normalized, {})
