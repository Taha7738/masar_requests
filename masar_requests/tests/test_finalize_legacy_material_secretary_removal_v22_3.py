"""
AR: اختبارات آلية للتحقق من منطق `test_finalize_legacy_material_secretary_removal_v22_3` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_finalize_legacy_material_secretary_removal_v22_3` behavior and regression prevention.
"""

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from masar_requests import preflight


class TestFinalizeLegacyMaterialSecretaryRemovalV223(
    FrappeTestCase
):
    """
    AR: فئة `TestFinalizeLegacyMaterialSecretaryRemovalV223` لتنظيم منطق اختبار `finalize` القديم المواد السكرتير `removal` `v22` `3`.
    EN: Class `TestFinalizeLegacyMaterialSecretaryRemovalV223` that organizes test finalize legacy material secretary removal v22 3 logic.
    """
    @patch.object(
        preflight,
        "_legacy_run_preflight_before_v22_3",
    )
    def test_legacy_secretary_role_error_is_ignored(
        self,
        legacy_preflight,
    ):
        """
        AR: اختبار سيناريو القديم السكرتير الدور `error` التحقق من كون `ignored` والتحقق من النتيجة المتوقعة.
        EN: Verify the legacy secretary role error is ignored scenario and its expected result.
        """
        legacy_preflight.return_value = {
            "ready": False,
            "errors": [
                (
                    "Secretary User user@example.com is missing "
                    "the Material Request Secretary role. "
                    "Run setup_material_request_all()."
                )
            ],
            "warnings": [],
            "info": [],
        }

        result = preflight.run_preflight()

        self.assertTrue(result["ready"])
        self.assertEqual(result["errors"], [])

    @patch.object(
        preflight,
        "_legacy_run_preflight_before_v22_3",
    )
    def test_real_preflight_errors_are_preserved(
        self,
        legacy_preflight,
    ):
        """
        AR: اختبار سيناريو `real` `preflight` `errors` `are` `preserved` والتحقق من النتيجة المتوقعة.
        EN: Verify the real preflight errors are preserved scenario and its expected result.
        """
        legacy_preflight.return_value = {
            "ready": False,
            "errors": [
                (
                    "Secretary User user@example.com is missing "
                    "the Material Request Secretary role."
                ),
                "A real configuration error.",
            ],
            "warnings": [],
            "info": [],
        }

        result = preflight.run_preflight()

        self.assertFalse(result["ready"])
        self.assertEqual(
            result["errors"],
            ["A real configuration error."],
        )
