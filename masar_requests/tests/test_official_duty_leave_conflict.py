"""
AR: اختبارات آلية للتحقق من منطق `test_official_duty_leave_conflict` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_official_duty_leave_conflict` behavior and regression prevention.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from masar_requests.official_duty_request_permissions import (
    _validate_no_approved_leave_overlap,
    get_official_duty_leave_conflicts,
)


class TestOfficialDutyLeaveConflict(FrappeTestCase):
    """
    AR: فئة `TestOfficialDutyLeaveConflict` لتنظيم منطق اختبار الرسمية المهمة الإجازة `conflict`.
    EN: Class `TestOfficialDutyLeaveConflict` that organizes test official duty leave conflict logic.
    """
    @patch(
        "masar_requests.official_duty_request_permissions."
        "frappe.get_all"
    )
    def test_conflict_query_uses_overlapping_date_range(
        self,
        mocked_get_all,
    ):
        """
        AR: اختبار سيناريو `conflict` `query` `uses` `overlapping` التاريخ `range` والتحقق من النتيجة المتوقعة.
        EN: Verify the conflict query uses overlapping date range scenario and its expected result.
        """
        mocked_get_all.return_value = []

        result = get_official_duty_leave_conflicts(
            "HR-EMP-TEST",
            "2026-08-01",
            "2026-08-03",
        )

        self.assertEqual(result, [])
        mocked_get_all.assert_called_once()

        filters = mocked_get_all.call_args.kwargs["filters"]

        self.assertIn(
            [
                "Leave Application",
                "from_date",
                "<=",
                frappe.utils.getdate("2026-08-03"),
            ],
            filters,
        )
        self.assertIn(
            [
                "Leave Application",
                "to_date",
                ">=",
                frappe.utils.getdate("2026-08-01"),
            ],
            filters,
        )

    @patch(
        "masar_requests.official_duty_request_permissions."
        "get_official_duty_leave_conflicts"
    )
    def test_save_is_blocked_when_approved_leave_exists(
        self,
        mocked_conflicts,
    ):
        """
        AR: اختبار سيناريو حفظ التحقق من كون `blocked` `when` `approved` الإجازة `exists` والتحقق من النتيجة المتوقعة.
        EN: Verify the save is blocked when approved leave exists scenario and its expected result.
        """
        mocked_conflicts.return_value = [
            frappe._dict(
                {
                    "name": "HR-LAP-TEST",
                    "leave_type": "Annual Leave",
                    "from_date": "2026-08-01",
                    "to_date": "2026-08-01",
                }
            )
        ]

        doc = frappe._dict(
            {
                "employee": "HR-EMP-TEST",
                "from_date": "2026-08-01",
                "to_date": "2026-08-01",
            }
        )

        with self.assertRaises(frappe.ValidationError):
            _validate_no_approved_leave_overlap(doc)

    @patch(
        "masar_requests.official_duty_request_permissions."
        "get_official_duty_leave_conflicts"
    )
    def test_save_is_allowed_when_no_leave_exists(
        self,
        mocked_conflicts,
    ):
        """
        AR: اختبار سيناريو حفظ التحقق من كون `allowed` `when` `no` الإجازة `exists` والتحقق من النتيجة المتوقعة.
        EN: Verify the save is allowed when no leave exists scenario and its expected result.
        """
        mocked_conflicts.return_value = []

        doc = frappe._dict(
            {
                "employee": "HR-EMP-TEST",
                "from_date": "2026-08-02",
                "to_date": "2026-08-02",
            }
        )

        _validate_no_approved_leave_overlap(doc)
