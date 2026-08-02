"""
AR: اختبارات آلية للتحقق من منطق `test_adopt_existing_secretary_shares_v22_4` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_adopt_existing_secretary_shares_v22_4` behavior and regression prevention.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from masar_requests import secretary_access


class TestAdoptExistingSecretarySharesV224(
    FrappeTestCase
):
    """
    AR: فئة `TestAdoptExistingSecretarySharesV224` لتنظيم منطق اختبار `adopt` الموجود السكرتير `shares` `v22` `4`.
    EN: Class `TestAdoptExistingSecretarySharesV224` that organizes test adopt existing secretary shares v22 4 logic.
    """
    @patch(
        "masar_requests.secretary_access.frappe.db.get_value",
        return_value=frappe._dict(
            {
                "read": 1,
                "write": 0,
                "submit": 0,
                "share": 0,
            }
        ),
    )
    @patch(
        "masar_requests.secretary_access._existing_share",
        return_value="SHARE-1",
    )
    def test_existing_read_only_share_is_adopted(
        self,
        _existing_share,
        _get_value,
    ):
        """
        AR: اختبار سيناريو الموجود القراءة `only` مشاركة التحقق من كون `adopted` والتحقق من النتيجة المتوقعة.
        EN: Verify the existing read only share is adopted scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "doctype": "Material Request",
                "name": "MAT-MR-TEST",
            }
        )

        self.assertTrue(
            secretary_access._grant_read_share(
                doc,
                "secretary@example.com",
            )
        )

    @patch(
        "masar_requests.secretary_access.frappe.db.get_value",
        return_value=frappe._dict(
            {
                "read": 1,
                "write": 1,
                "submit": 0,
                "share": 0,
            }
        ),
    )
    @patch(
        "masar_requests.secretary_access._existing_share",
        return_value="SHARE-2",
    )
    def test_existing_write_share_is_not_adopted(
        self,
        _existing_share,
        _get_value,
    ):
        """
        AR: اختبار سيناريو الموجود الكتابة مشاركة التحقق من كون `not` `adopted` والتحقق من النتيجة المتوقعة.
        EN: Verify the existing write share is not adopted scenario and its expected result.
        """
        doc = frappe._dict(
            {
                "doctype": "Material Request",
                "name": "MAT-MR-TEST",
            }
        )

        self.assertFalse(
            secretary_access._grant_read_share(
                doc,
                "actor@example.com",
            )
        )
