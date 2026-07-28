# ============================================================================
# AR: ترقية V13 — توحيد المهمة مع الإجازة وإلغاء دورة التقرير المستقلة
# EN: V13 migration — align Official Duty with Leave and remove report workflow
# ============================================================================

import frappe

from masar_requests.attendance_request_permissions import (
    resync_all_attendance_request_shares,
)
from masar_requests.hr_user_read_only import setup_hr_user_read_only_permissions
from masar_requests.setup_attendance_request import setup_attendance_request_all
from masar_requests.setup_leave_and_shift import create_leave_application_workflow

ATTENDANCE_DOCTYPE = "Attendance Request"

# AR: الحالات التي كانت تخص دورة تقرير الإنجاز القديمة.
# EN: States that belonged to the obsolete Achievement Report workflow.
OBSOLETE_REPORT_STATES = {
    "Approved - Awaiting Achievement Report",
    "Waiting for Achievement Report Manager Approval",
    "Waiting for Achievement Report HR Approval",
    "Achievement Report Revision Required",
    "Completed",
}

OBSOLETE_REPORT_ACTIONS = {
    "Submit Achievement Report",
    "Approve Achievement Report",
    "Final Approve Achievement Report",
    "Return Achievement Report",
}


def _migrate_existing_attendance_requests():
    """
    AR:
        تحويل الطلبات الموجودة في مراحل التقرير القديمة إلى الحالة النهائية
        معتمدة، لأن V13 يعتمد دورة موافقة واحدة فقط.

    EN:
        Convert requests left in obsolete report stages to final Approved,
        because V13 uses one approval cycle only.
    """
    if not frappe.db.exists("DocType", ATTENDANCE_DOCTYPE):
        return 0

    rows = frappe.get_all(
        ATTENDANCE_DOCTYPE,
        filters={"workflow_state": ["in", sorted(OBSOLETE_REPORT_STATES)]},
        fields=["name", "workflow_state"],
    )

    for row in rows:
        values = {"workflow_state": "Approved", "docstatus": 1}
        meta = frappe.get_meta(ATTENDANCE_DOCTYPE)
        if meta.has_field("status"):
            values["status"] = "Approved"

        frappe.db.set_value(
            ATTENDANCE_DOCTYPE,
            row.name,
            values,
            update_modified=False,
        )

    return len(rows)


def _remove_other_attendance_workflows():
    """
    AR: حذف مسارات Attendance القديمة بعد إنشاء المسار النهائي الوحيد.
    EN: Delete obsolete Attendance workflows after creating the single final workflow.
    """
    from masar_requests.setup_attendance_request import ATTENDANCE_WORKFLOW_NAME

    workflows = frappe.get_all(
        "Workflow",
        filters={"document_type": ATTENDANCE_DOCTYPE},
        fields=["name", "workflow_name"],
    )
    removed = []
    for workflow in workflows:
        if workflow.workflow_name == ATTENDANCE_WORKFLOW_NAME:
            continue
        frappe.delete_doc(
            "Workflow",
            workflow.name,
            ignore_permissions=True,
            force=True,
        )
        removed.append(workflow.name)
    return removed


def _master_is_referenced(doctype, name):
    """AR: فحص آمن قبل حذف حالة أو إجراء. EN: Safely check master references."""
    try:
        if doctype == "Workflow State":
            return bool(
                frappe.db.exists("Workflow Document State", {"state": name})
                or frappe.db.exists("Workflow Transition", {"state": name})
                or frappe.db.exists("Workflow Transition", {"next_state": name})
            )
        if doctype == "Workflow Action Master":
            return bool(frappe.db.exists("Workflow Transition", {"action": name}))
    except Exception:
        # AR: عند اختلاف نسخة Frappe نترك السجل بدلاً من حذف غير آمن.
        # EN: On schema differences, preserve the record rather than deleting unsafely.
        return True
    return True


def _remove_obsolete_workflow_masters():
    """
    AR: حذف حالات وإجراءات التقرير القديمة فقط عندما لا يستخدمها Workflow آخر.
    EN: Delete obsolete report states/actions only when no workflow references them.
    """
    removed = []
    for doctype, names in (
        ("Workflow State", OBSOLETE_REPORT_STATES),
        ("Workflow Action Master", OBSOLETE_REPORT_ACTIONS),
    ):
        for name in names:
            if frappe.db.exists(doctype, name) and not _master_is_referenced(doctype, name):
                frappe.delete_doc(
                    doctype,
                    name,
                    ignore_permissions=True,
                    force=True,
                )
                removed.append(f"{doctype}: {name}")
    return removed


def execute():
    """
    AR:
        1) إعادة بناء طلب المهمة بسير عمل الإجازة الجاهز.
        2) تعديل رفض البديل في الإجازة ليعود للموظف.
        3) منح HR User العرض والطباعة فقط للطلبات الثلاثة.
        4) ترحيل السجلات القديمة وتنظيف حالات التقرير غير المستخدمة.

    EN:
        1) Rebuild Official Duty with the ready Leave workflow.
        2) Rebuild Leave so substitute rejection returns to the applicant.
        3) Grant HR User read/print-only access to all three request types.
        4) Migrate legacy records and remove unused report workflow masters.
    """
    setup_attendance_request_all()
    create_leave_application_workflow()
    setup_hr_user_read_only_permissions()
    _migrate_existing_attendance_requests()
    resync_all_attendance_request_shares()
    _remove_other_attendance_workflows()
    _remove_obsolete_workflow_masters()

    for doctype in ("Attendance Request", "Leave Application", "Material Request"):
        frappe.clear_cache(doctype=doctype)
    frappe.clear_cache()
