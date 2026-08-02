"""
AR: اختبارات آلية للتحقق من منطق `test_unified_secretary_access_v22` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_unified_secretary_access_v22` behavior and regression prevention.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from masar_requests.secretary_access import (
    DIRECT_MANAGER_STATE,
    get_current_actor_users,
    get_desired_access_pairs,
)


class TestUnifiedSecretaryAccessV22(FrappeTestCase):
    """
    AR: فئة `TestUnifiedSecretaryAccessV22` لتنظيم منطق اختبار `unified` السكرتير الوصول `v22`.
    EN: Class `TestUnifiedSecretaryAccessV22` that organizes test unified secretary access v22 logic.
    """
    @patch(
        "masar_requests.secretary_access._direct_manager_user",
        return_value="manager@example.com",
    )
    def test_leave_uses_direct_manager_only(
        self,
        _direct_manager_user,
    ):
        """
        AR: اختبار سيناريو الإجازة `uses` `direct` المدير `only` والتحقق من النتيجة المتوقعة.
        EN: Verify the leave uses direct manager only scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "doctype": "Leave Application",
                "docstatus": 0,
                "workflow_state": DIRECT_MANAGER_STATE,
            }
        )

        self.assertEqual(
            get_current_actor_users(doc),
            ["manager@example.com"],
        )

    @patch(
        "masar_requests.secretary_access._direct_manager_user",
        return_value="manager@example.com",
    )
    def test_official_duty_uses_direct_manager_only(
        self,
        _direct_manager_user,
    ):
        """
        AR: اختبار سيناريو الرسمية المهمة `uses` `direct` المدير `only` والتحقق من النتيجة المتوقعة.
        EN: Verify the official duty uses direct manager only scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "doctype": "Official Duty Request",
                "docstatus": 0,
                "workflow_state": DIRECT_MANAGER_STATE,
            }
        )

        self.assertEqual(
            get_current_actor_users(doc),
            ["manager@example.com"],
        )

    @patch(
        "masar_requests.secretary_access._enabled_users_with_role",
        return_value=["warehouse@example.com"],
    )
    def test_material_uses_current_stage_role(
        self,
        _enabled_users_with_role,
    ):
        """
        AR: اختبار سيناريو المواد `uses` الحالي `stage` الدور والتحقق من النتيجة المتوقعة.
        EN: Verify the material uses current stage role scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "doctype": "Material Request",
                "docstatus": 0,
                "workflow_state": "Pending Stock Check",
            }
        )

        self.assertEqual(
            get_current_actor_users(doc),
            ["warehouse@example.com"],
        )

    @patch(
        "masar_requests.secretary_access._explicit_direct_manager_secretaries",
        return_value=["secretary@example.com"],
    )
    @patch(
        "masar_requests.secretary_access.get_secretaries_for_actor",
        return_value=[],
    )
    @patch(
        "masar_requests.secretary_access._direct_manager_user",
        return_value="manager@example.com",
    )
    def test_explicit_secretary_is_supported(
        self,
        _direct_manager_user,
        _get_secretaries,
        _explicit_secretaries,
    ):
        """
        AR: اختبار سيناريو `explicit` السكرتير التحقق من كون `supported` والتحقق من النتيجة المتوقعة.
        EN: Verify the explicit secretary is supported scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "doctype": "Leave Application",
                "docstatus": 0,
                "workflow_state": DIRECT_MANAGER_STATE,
            }
        )

        self.assertEqual(
            get_desired_access_pairs(doc),
            {
                (
                    "manager@example.com",
                    "secretary@example.com",
                )
            },
        )

    @patch(
        "masar_requests.secretary_access.get_secretaries_for_actor",
        return_value=["secretary@example.com"],
    )
    @patch(
        "masar_requests.secretary_access._enabled_users_with_role",
        return_value=["accounts@example.com"],
    )
    def test_material_secretary_pair_is_stage_specific(
        self,
        _enabled_users_with_role,
        _get_secretaries,
    ):
        """
        AR: اختبار سيناريو المواد السكرتير `pair` التحقق من كون `stage` `specific` والتحقق من النتيجة المتوقعة.
        EN: Verify the material secretary pair is stage specific scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "doctype": "Material Request",
                "docstatus": 0,
                "workflow_state": "Pending Accounts Manager",
            }
        )

        self.assertEqual(
            get_desired_access_pairs(doc),
            {
                (
                    "accounts@example.com",
                    "secretary@example.com",
                )
            },
        )

    def test_tracking_doctype_exists(self):
        """
        AR: اختبار سيناريو `tracking` `doctype` `exists` والتحقق من النتيجة المتوقعة.
        EN: Verify the tracking doctype exists scenario and its expected result.
        """
        self.assertTrue(
            frappe.db.exists(
                "DocType",
                "Masar Secretary Access",
            )
        )
