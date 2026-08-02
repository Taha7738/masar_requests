"""
AR: اختبارات آلية للتحقق من منطق `test_remove_legacy_material_secretary_role_v22_2` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_remove_legacy_material_secretary_role_v22_2` behavior and regression prevention.
"""

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from masar_requests import material_request_sharing
from masar_requests import setup_material_request


class TestRemoveLegacyMaterialSecretaryRoleV222(
    FrappeTestCase
):
    """
    AR: فئة `TestRemoveLegacyMaterialSecretaryRoleV222` لتنظيم منطق اختبار إزالة القديم المواد السكرتير الدور `v22` `2`.
    EN: Class `TestRemoveLegacyMaterialSecretaryRoleV222` that organizes test remove legacy material secretary role v22 2 logic.
    """
    def test_legacy_role_sync_assigns_nothing(self):
        """
        AR: اختبار سيناريو القديم الدور مزامنة `assigns` `nothing` والتحقق من النتيجة المتوقعة.
        EN: Verify the legacy role sync assigns nothing scenario and its expected result.
        """
        self.assertEqual(
            setup_material_request
            .sync_material_request_secretary_roles(),
            0,
        )

    def test_legacy_secretary_lookup_is_disabled(self):
        """
        AR: اختبار سيناريو القديم السكرتير `lookup` التحقق من كون `disabled` والتحقق من النتيجة المتوقعة.
        EN: Verify the legacy secretary lookup is disabled scenario and its expected result.
        """
        self.assertIsNone(
            material_request_sharing.get_user_secretary(
                "manager@example.com"
            )
        )
        self.assertEqual(
            material_request_sharing.get_all_secretary_users(),
            set(),
        )

    @patch(
        "masar_requests.setup_material_request.frappe.clear_cache"
    )
    @patch(
        "masar_requests.setup_material_request.frappe.db.delete"
    )
    @patch(
        "masar_requests.setup_material_request.frappe.db.exists",
        return_value=False,
    )
    def test_cleanup_function_removes_old_permission_sources(
        self,
        _exists,
        db_delete,
        _clear_cache,
    ):
        """
        AR: اختبار سيناريو `cleanup` `function` `removes` `old` صلاحية `sources` والتحقق من النتيجة المتوقعة.
        EN: Verify the cleanup function removes old permission sources scenario and its expected result.
        """
        setup_material_request.setup_university_secretary_role()

        db_delete.assert_any_call(
            "Custom DocPerm",
            {
                "parent": "Material Request",
                "role": "Material Request Secretary",
            },
        )
        db_delete.assert_any_call(
            "Has Role",
            {"role": "Material Request Secretary"},
        )
