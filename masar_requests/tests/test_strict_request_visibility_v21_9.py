"""
AR: اختبارات آلية للتحقق من منطق `test_strict_request_visibility_v21_9` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_strict_request_visibility_v21_9` behavior and regression prevention.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from masar_requests import hooks
from masar_requests.strict_request_visibility import (
    _leave_related,
    _material_related,
    _official_related,
)


class TestStrictRequestVisibilityV219(FrappeTestCase):
    """
    AR: فئة `TestStrictRequestVisibilityV219` لتنظيم منطق اختبار الصارم الطلب الظهور `v21` `9`.
    EN: Class `TestStrictRequestVisibilityV219` that organizes test strict request visibility v21 9 logic.
    """
    def test_hooks_are_overridden(self):
        """
        AR: اختبار سيناريو `hooks` `are` `overridden` والتحقق من النتيجة المتوقعة.
        EN: Verify the hooks are overridden scenario and its expected result.
        """
        expected_prefix = "masar_requests.strict_request_visibility."

        for doctype in (
            "Leave Application",
            "Official Duty Request",
            "Material Request",
        ):
            self.assertTrue(
                hooks.permission_query_conditions[doctype].startswith(
                    expected_prefix
                )
            )
            self.assertTrue(
                hooks.has_permission[doctype].startswith(
                    expected_prefix
                )
            )

    @patch(
        "masar_requests.strict_request_visibility._employee_user",
        return_value="applicant@example.com",
    )
    @patch(
        "masar_requests.strict_request_visibility._roles",
        return_value={"Employee"},
    )
    def test_same_department_employee_is_not_related_to_leave(
        self,
        _roles,
        _employee_user,
    ):
        """
        AR: اختبار سيناريو `same` `department` الموظف التحقق من كون `not` `related` `to` الإجازة والتحقق من النتيجة المتوقعة.
        EN: Verify the same department employee is not related to leave scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "owner": "applicant@example.com",
                "employee": "EMP-1",
                "workflow_state": "Draft",
                "custom_substitute_user": None,
                "custom_direct_manager_user": "manager@example.com",
                "custom_direct_manager_secretary_user": None,
            }
        )

        self.assertFalse(
            _leave_related(doc, "other.employee@example.com")
        )

    @patch(
        "masar_requests.strict_request_visibility._employee_user",
        side_effect=lambda employee: {
            "EMP-1": "applicant@example.com",
            "EMP-MGR": "manager@example.com",
        }.get(employee),
    )
    @patch(
        "masar_requests.strict_request_visibility._roles",
        return_value={"Employee"},
    )
    def test_exact_direct_manager_is_related_to_material(
        self,
        _roles,
        _employee_user,
    ):
        """
        AR: اختبار سيناريو `exact` `direct` المدير التحقق من كون `related` `to` المواد والتحقق من النتيجة المتوقعة.
        EN: Verify the exact direct manager is related to material scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "name": "MAT-MR-TEST",
                "owner": "applicant@example.com",
                "reports_to": "EMP-MGR",
                "workflow_state": "Pending Direct Supervisor",
            }
        )

        self.assertTrue(
            _material_related(doc, "manager@example.com")
        )
        self.assertFalse(
            _material_related(doc, "other.employee@example.com")
        )

    @patch(
        "masar_requests.strict_request_visibility._employee_user",
        return_value="applicant@example.com",
    )
    @patch(
        "masar_requests.strict_request_visibility._roles",
        return_value={"Employee"},
    )
    def test_unrelated_employee_is_not_related_to_official_duty(
        self,
        _roles,
        _employee_user,
    ):
        """
        AR: اختبار سيناريو `unrelated` الموظف التحقق من كون `not` `related` `to` الرسمية المهمة والتحقق من النتيجة المتوقعة.
        EN: Verify the unrelated employee is not related to official duty scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "owner": "applicant@example.com",
                "employee": "EMP-1",
                "workflow_state": "Draft",
                "custom_applicant_user": "applicant@example.com",
                "custom_substitute_user": None,
                "custom_direct_manager_user": "manager@example.com",
                "custom_direct_manager_secretary_user": None,
                "processing_status": "Pending",
            }
        )

        self.assertFalse(
            _official_related(doc, "other.employee@example.com")
        )

    @patch(
        "masar_requests.strict_request_visibility._roles",
        return_value={"Warehouse Manager"},
    )
    def test_material_stage_role_sees_only_its_stage(self, _roles):
        """
        AR: اختبار سيناريو المواد `stage` الدور `sees` `only` `its` `stage` والتحقق من النتيجة المتوقعة.
        EN: Verify the material stage role sees only its stage scenario and its expected result.
        """
        pending_stock = frappe._dict(
            {
                "name": "MAT-MR-1",
                "owner": "applicant@example.com",
                "workflow_state": "Pending Stock Check",
                "reports_to": None,
            }
        )
        pending_hr = frappe._dict(
            {
                "name": "MAT-MR-2",
                "owner": "applicant@example.com",
                "workflow_state": "Pending HR Manager",
                "reports_to": None,
            }
        )

        self.assertTrue(
            _material_related(
                pending_stock,
                "warehouse@example.com",
            )
        )
        self.assertFalse(
            _material_related(
                pending_hr,
                "warehouse@example.com",
            )
        )
