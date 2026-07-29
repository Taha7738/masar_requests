"""
AR: اختبارات رجوع لسير العمل الموحد وصلاحية HR User.
EN: Regression tests for the unified workflow and HR User read-only access.
"""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from masar_requests import hooks
from masar_requests.constants import (
    ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
    ATTENDANCE_ACTION_REJECT,
    ATTENDANCE_STATE_DRAFT,
    ATTENDANCE_STATE_WAITING_HR_MANAGER,
    ATTENDANCE_STATE_WAITING_SUBSTITUTE,
)
from masar_requests.hr_user_read_only import (
    is_hr_user_read_only,
    material_request_has_permission,
)
from masar_requests.material_request_engine import (
    allow_zero_valuation_for_internal_material_issue,
)
from masar_requests.setup_attendance_request import (
    get_attendance_custom_fields,
    get_hr_manager_override_transitions,
    get_system_manager_workflow_transitions,
)


class TestUnifiedRequestWorkflow(FrappeTestCase):
    """AR: التحقق من العقود الأساسية للتخصيص. EN: Verify core customization contracts."""

    def test_material_request_hr_permission_hook_is_registered(self):
        # AR: طلب المواد يستخدم حماية HR User الخادمية.
        # EN: Material Request uses the server-side HR User permission guard.
        self.assertIn("Material Request", hooks.has_permission)
        self.assertEqual(
            hooks.has_permission["Material Request"],
            "masar_requests.hr_user_read_only.material_request_has_permission",
        )

    def test_stock_entry_zero_valuation_hook_is_registered(self):
        # AR: حركة الصرف المرتبطة بطلب المواد تمر عبر الحماية المقيدة.
        # EN: Linked material issues use the guarded zero-valuation hook.
        self.assertIn("Stock Entry", hooks.doc_events)
        self.assertEqual(
            hooks.doc_events["Stock Entry"]["before_validate"],
            "masar_requests.material_request_engine."
            "allow_zero_valuation_for_internal_material_issue",
        )

    @patch("masar_requests.material_request_engine.frappe.db.get_value")
    def test_zero_valuation_is_limited_to_linked_internal_issues(self, get_value):
        # AR: التفعيل لا يشمل إلا سطر صرف مرتبط بطلب Material Issue.
        # EN: Only a row linked to a Material Issue request is enabled.
        get_value.return_value = "Material Issue"
        linked_row = SimpleNamespace(
            material_request="MAT-MR-TEST-0001",
            allow_zero_valuation_rate=0,
        )
        unrelated_row = SimpleNamespace(
            material_request=None,
            allow_zero_valuation_rate=0,
        )
        doc = SimpleNamespace(
            purpose="Material Issue",
            items=[linked_row, unrelated_row],
        )

        allow_zero_valuation_for_internal_material_issue(doc)

        self.assertEqual(linked_row.allow_zero_valuation_rate, 1)
        self.assertEqual(unrelated_row.allow_zero_valuation_rate, 0)
        get_value.assert_called_once_with(
            "Material Request",
            "MAT-MR-TEST-0001",
            "material_request_type",
        )

    @patch("masar_requests.material_request_engine.frappe.db.get_value")
    def test_zero_valuation_does_not_apply_to_other_stock_entries(self, get_value):
        # AR: الاستلام والتحويل لا يتأثران بالتعديل.
        # EN: Receipts and transfers remain unaffected.
        row = SimpleNamespace(
            material_request="MAT-MR-TEST-0001",
            allow_zero_valuation_rate=0,
        )
        doc = SimpleNamespace(
            purpose="Material Receipt",
            items=[row],
        )

        allow_zero_valuation_for_internal_material_issue(doc)

        self.assertEqual(row.allow_zero_valuation_rate, 0)
        get_value.assert_not_called()

    def test_attendance_report_is_required_at_creation(self):
        # AR: التقرير محرر نص مطلوب ويظهر في دورة الطلب الأولى.
        # EN: Report is a required rich-text field in the initial request cycle.
        fields = {
            field["fieldname"]: field
            for field in get_attendance_custom_fields("explanation")
        }
        self.assertEqual(fields["custom_achievement_report"]["fieldtype"], "Text Editor")
        self.assertEqual(fields["custom_achievement_report"]["reqd"], 1)
        self.assertIn("custom_achievement_report_attachment", fields)
        self.assertNotIn("custom_report_manager_approved_by", fields)
        self.assertNotIn("custom_duty_progress_status", fields)

    def test_manager_can_approve_while_substitute_is_pending(self):
        # AR: انتقال مدير النظام يعكس إمكانية تجاوز انتظار البديل.
        # EN: System Manager transitions preserve manager approval during substitute wait.
        transitions = get_system_manager_workflow_transitions()
        self.assertTrue(
            any(
                row["state"] == ATTENDANCE_STATE_WAITING_SUBSTITUTE
                and row["action"] == ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE
                and row["next_state"] == ATTENDANCE_STATE_WAITING_HR_MANAGER
                for row in transitions
            )
        )

    def test_hr_manager_can_finally_decide_from_draft_and_substitute_stage(self):
        # AR: مدير الموارد البشرية يحسم الطلب من أي مرحلة نشطة.
        # EN: HR Manager can finally decide from every active stage.
        transitions = get_hr_manager_override_transitions()
        covered = {(row["state"], row["action"]) for row in transitions}
        self.assertIn((ATTENDANCE_STATE_DRAFT, ATTENDANCE_ACTION_REJECT), covered)
        self.assertIn((ATTENDANCE_STATE_WAITING_SUBSTITUTE, ATTENDANCE_ACTION_REJECT), covered)

    @patch("masar_requests.hr_user_read_only.frappe.get_roles")
    def test_hr_user_is_read_print_only(self, get_roles):
        # AR: HR User لا يكتسب تعديل الطلب حتى لو حمل Employee.
        # EN: HR User stays read/print-only even when also assigned Employee.
        get_roles.return_value = ["HR User", "Employee"]
        self.assertTrue(is_hr_user_read_only("hr.user@example.com"))
        self.assertTrue(
            material_request_has_permission(None, "read", "hr.user@example.com")
        )
        self.assertTrue(
            material_request_has_permission(None, "print", "hr.user@example.com")
        )
        self.assertFalse(
            material_request_has_permission(None, "write", "hr.user@example.com")
        )
        self.assertFalse(
            material_request_has_permission(None, "submit", "hr.user@example.com")
        )
