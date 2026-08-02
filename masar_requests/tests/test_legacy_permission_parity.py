"""
AR: اختبارات آلية للتحقق من منطق `test_legacy_permission_parity` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_legacy_permission_parity` behavior and regression prevention.
"""

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from masar_requests.hr_user_read_only import STANDARD_PERMISSION_DOCTYPES


DOCTYPE = "Official Duty Request"


class TestLegacyPermissionParity(FrappeTestCase):
    """
    AR: فئة `TestLegacyPermissionParity` لتنظيم منطق اختبار القديم صلاحية `parity`.
    EN: Class `TestLegacyPermissionParity` that organizes test legacy permission parity logic.
    """
    def test_official_duty_employee_link_ignores_user_permissions(self):
        """
        AR: اختبار سيناريو الرسمية المهمة الموظف `link` `ignores` المستخدم الصلاحيات والتحقق من النتيجة المتوقعة.
        EN: Verify the official duty employee link ignores user permissions scenario and its expected result.
        """
        field = frappe.get_meta(DOCTYPE, cached=False).get_field("employee")
        self.assertTrue(field)
        self.assertEqual(int(field.ignore_user_permissions or 0), 1)

    def test_official_duty_json_contains_legacy_role_matrix(self):
        """
        AR: اختبار سيناريو الرسمية المهمة `json` `contains` القديم الدور `matrix` والتحقق من النتيجة المتوقعة.
        EN: Verify the official duty json contains legacy role matrix scenario and its expected result.
        """
        path = (
            Path(__file__).parents[1]
            / "masar_requests"
            / "doctype"
            / "official_duty_request"
            / "official_duty_request.json"
        )
        definition = json.loads(path.read_text(encoding="utf-8"))
        fields = {
            row["fieldname"]: row
            for row in definition["fields"]
        }
        self.assertEqual(
            fields["employee"].get("ignore_user_permissions"),
            1,
        )

        roles = {
            row["role"]
            for row in definition.get("permissions", [])
        }
        self.assertTrue(
            {
                "System Manager",
                "HR Manager",
                "HR User",
                "Employee",
                "Employee Self Service",
                "Official Duty Secretary",
            }.issubset(roles)
        )

    def test_official_duty_uses_standard_not_single_custom_permissions(self):
        """
        AR: اختبار سيناريو الرسمية المهمة `uses` `standard` `not` `single` `custom` الصلاحيات والتحقق من النتيجة المتوقعة.
        EN: Verify the official duty uses standard not single custom permissions scenario and its expected result.
        """
        self.assertIn(DOCTYPE, STANDARD_PERMISSION_DOCTYPES)
        rows = frappe.get_all(
            "Custom DocPerm",
            filters={"parent": DOCTYPE},
            pluck="name",
        )
        self.assertEqual(rows, [])

    def test_hr_manager_can_open_existing_official_duty(self):
        """
        AR: اختبار سيناريو `hr` المدير التحقق من إمكانية فتح الموجود الرسمية المهمة والتحقق من النتيجة المتوقعة.
        EN: Verify the hr manager can open existing official duty scenario and its expected result.
        """
        user = "ra@gmail.com"
        name = "ODR-2026-00016"

        if not (
            frappe.db.exists("User", user)
            and frappe.db.exists(DOCTYPE, name)
        ):
            self.skipTest("Site-specific HR Manager test data is unavailable.")

        doc = frappe.get_doc(DOCTYPE, name)
        self.assertIn("HR Manager", frappe.get_roles(user))
        self.assertTrue(
            frappe.has_permission(
                DOCTYPE,
                "read",
                doc=doc,
                user=user,
            )
        )
        self.assertTrue(
            frappe.has_permission(
                DOCTYPE,
                "write",
                doc=doc,
                user=user,
            )
        )

    def test_nonprivileged_hr_user_can_read_but_not_write_other_request(self):
        """
        AR: اختبار سيناريو `nonprivileged` `hr` المستخدم التحقق من إمكانية القراءة `but` `not` الكتابة `other` الطلب والتحقق من النتيجة المتوقعة.
        EN: Verify the nonprivileged hr user can read but not write other request scenario and its expected result.
        """
        name = "ODR-2026-00016"
        if not frappe.db.exists(DOCTYPE, name):
            self.skipTest("Site-specific Official Duty test data is unavailable.")

        candidates = [
            row.parent
            for row in frappe.get_all(
                "Has Role",
                filters={
                    "role": "HR User",
                    "parenttype": "User",
                },
                fields=["parent"],
            )
            if row.parent != "Administrator"
            and frappe.db.get_value("User", row.parent, "enabled")
            and "HR Manager" not in frappe.get_roles(row.parent)
            and "System Manager" not in frappe.get_roles(row.parent)
        ]

        if not candidates:
            self.skipTest("A nonprivileged HR User is unavailable.")

        user = candidates[0]
        doc = frappe.get_doc(DOCTYPE, name)

        self.assertTrue(
            frappe.has_permission(
                DOCTYPE,
                "read",
                doc=doc,
                user=user,
            )
        )
        self.assertFalse(
            frappe.has_permission(
                DOCTYPE,
                "write",
                doc=doc,
                user=user,
            )
        )
