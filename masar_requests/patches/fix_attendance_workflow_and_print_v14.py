"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `fix_attendance_workflow_and_print_v14` على المواقع القائمة.
EN: Idempotent migration patch for applying `fix_attendance_workflow_and_print_v14` changes to existing sites.
"""

# ============================================================================
# AR: إصلاح حاسم لمسار رفض البديل واعتماد المدير/الموارد والطباعة — V14
# EN: Definitive substitute-rejection, manager/HR approval, and print fix — V14
# ============================================================================

import json

import frappe

from masar_requests.attendance_request_permissions import (
    resync_all_attendance_request_shares,
)
from masar_requests.constants import (
    APPROVAL_APPROVED,
    APPROVAL_BYPASSED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    ATTENDANCE_STATE_APPROVED,
    ATTENDANCE_STATE_DRAFT,
    ATTENDANCE_STATE_REJECTED,
    ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
    ATTENDANCE_STATE_WAITING_HR_MANAGER,
    ATTENDANCE_STATE_WAITING_SUBSTITUTE,
)
from masar_requests.setup_attendance_request import setup_attendance_request_all

ATTENDANCE_DOCTYPE = "Attendance Request"

ACTIVE_STATES = {
    ATTENDANCE_STATE_DRAFT,
    ATTENDANCE_STATE_WAITING_SUBSTITUTE,
    ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
    ATTENDANCE_STATE_WAITING_HR_MANAGER,
}


def _workflow_change(data):
    """
    AR: تنفيذ سير العمل `change` ضمن وحدة `fix_attendance_workflow_and_print_v14`.
    EN: Execute workflow change within the `fix_attendance_workflow_and_print_v14` module.
    """
    if not data:
        return None

    try:
        payload = json.loads(data) if isinstance(data, str) else data
    except (TypeError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None

    for change in payload.get("changed", []):
        if (
            isinstance(change, (list, tuple))
            and len(change) >= 3
            and change[0] == "workflow_state"
        ):
            return change[1], change[2]

    return None


def _workflow_history(docname):
    """
    AR: تنفيذ سير العمل `history` ضمن وحدة `fix_attendance_workflow_and_print_v14`.
    EN: Execute workflow history within the `fix_attendance_workflow_and_print_v14` module.
    """
    versions = frappe.get_all(
        "Version",
        filters={"ref_doctype": ATTENDANCE_DOCTYPE, "docname": docname},
        fields=["owner", "creation", "data"],
        order_by="creation asc",
    )

    history = []
    for version in versions:
        transition = _workflow_change(version.data)
        if transition:
            history.append(
                {
                    "old_state": transition[0],
                    "new_state": transition[1],
                    "actor": version.owner,
                    "time": version.creation,
                }
            )
    return history


def _repair_rejected_substitute_request(row, history):
    """
    AR: تنفيذ `repair` `rejected` `substitute` الطلب ضمن وحدة `fix_attendance_workflow_and_print_v14`.
    EN: Execute repair rejected substitute request within the `fix_attendance_workflow_and_print_v14` module.

    DETAILS / التفاصيل:
    AR:
            تصحيح الطلبات التي رفضها البديل تحت Workflow قديم فتحولت خطأً إلى Rejected.
            تعاد إلى Draft، ويُحذف البديل المرفوض ليختار الموظف بديلاً جديداً أو يرسل
            مباشرة إلى المسؤول المباشر.

        EN:
            Repair requests rejected by a substitute under a stale workflow. Return them
            to Draft and clear the rejected substitute so the applicant can reselect or
            send directly to the manager.
    """
    if row.workflow_state != ATTENDANCE_STATE_REJECTED:
        return False

    substitute_user = row.custom_substitute_user
    if not substitute_user:
        return False

    rejected_by_substitute = any(
        item["old_state"] == ATTENDANCE_STATE_WAITING_SUBSTITUTE
        and item["new_state"] == ATTENDANCE_STATE_REJECTED
        and item["actor"] == substitute_user
        for item in history
    )

    # AR: دعم السجلات التي لا تحتوي Version كاملاً ولكن حقول التدقيق تؤكد رفض البديل.
    # EN: Support records with incomplete Version history when audit fields confirm rejection.
    if not rejected_by_substitute:
        rejected_by_substitute = bool(
            row.custom_substitute_approval == APPROVAL_REJECTED
            and row.custom_direct_manager_approval != APPROVAL_REJECTED
            and not row.custom_hr_approved_by
        )

    if not rejected_by_substitute:
        return False

    values = {
        "workflow_state": ATTENDANCE_STATE_DRAFT,
        "docstatus": 0,
        "custom_substitute_approval": APPROVAL_REJECTED,
        "custom_substitute_employee": None,
        "custom_substitute_employee_name": "",
        "custom_substitute_user": None,
        "custom_substitute_approved_by": None,
        "custom_substitute_approved_on": None,
        "custom_direct_manager_approval": APPROVAL_PENDING,
        "custom_direct_manager_approved_by": None,
        "custom_direct_manager_approved_on": None,
    }
    if frappe.get_meta(ATTENDANCE_DOCTYPE).has_field("status"):
        values["status"] = "Open"

    frappe.db.set_value(
        ATTENDANCE_DOCTYPE,
        row.name,
        values,
        update_modified=False,
    )
    return True


def _rebuild_approval_audit(row, history):
    """
    AR: تنفيذ `rebuild` `approval` تدقيق ضمن وحدة `fix_attendance_workflow_and_print_v14`.
    EN: Execute rebuild approval audit within the `fix_attendance_workflow_and_print_v14` module.

    DETAILS / التفاصيل:
    AR:
            إعادة بناء حقول توقيع البديل والمدير والاعتماد النهائي من التاريخ الحقيقي.
            أي مرحلة تم تجاوزها بواسطة صاحب الاعتماد النهائي تُسجل Bypassed، حتى يعرض
            تنسيق الطباعة عبارة «تم الاعتماد من قبل» بدلاً من اسم غير صحيح أو خانة فارغة.

        EN:
            Rebuild substitute, manager, and final-approver audit fields from actual
            workflow history. Stages skipped by the final approver are marked Bypassed
            so printing shows “Approved by” instead of an incorrect name or blank cell.
    """
    has_substitute = bool(row.custom_substitute_employee or row.custom_substitute_user)

    # AR: لا نمسح علامة رفض البديل من مسودة أعيدت للموظف؛ هذه العلامة تسمح
    #     له بتغيير البديل المقفول واختيار بديل جديد.
    # EN: Preserve the substitute-rejected marker on a returned Draft; it is the
    #     authorization token that allows the applicant to change the locked substitute.
    if (
        row.workflow_state == ATTENDANCE_STATE_DRAFT
        and row.custom_substitute_approval == APPROVAL_REJECTED
        and not has_substitute
    ):
        return False

    # AR: عند توفر سجل Version نعيد البناء من الصفر؛ وعند غيابه نحافظ على
    #     القيم الصحيحة الموجودة بدلاً من فقد توقيعات تاريخية سليمة.
    # EN: Rebuild from scratch when Version history exists; otherwise preserve
    #     existing valid audit values instead of losing historical signatures.
    if history:
        values = {
            "custom_substitute_approval": APPROVAL_PENDING if has_substitute else "",
            "custom_substitute_approved_by": None,
            "custom_substitute_approved_on": None,
            "custom_direct_manager_approval": APPROVAL_PENDING,
            "custom_direct_manager_approved_by": None,
            "custom_direct_manager_approved_on": None,
            "custom_hr_approved_by": None,
            "custom_hr_approved_on": None,
        }
    else:
        values = {
            "custom_substitute_approval": row.custom_substitute_approval or (APPROVAL_PENDING if has_substitute else ""),
            "custom_substitute_approved_by": row.custom_substitute_approved_by,
            "custom_substitute_approved_on": row.custom_substitute_approved_on,
            "custom_direct_manager_approval": row.custom_direct_manager_approval or APPROVAL_PENDING,
            "custom_direct_manager_approved_by": row.custom_direct_manager_approved_by,
            "custom_direct_manager_approved_on": row.custom_direct_manager_approved_on,
            "custom_hr_approved_by": row.custom_hr_approved_by,
            "custom_hr_approved_on": row.custom_hr_approved_on,
        }

    final_approved = False

    for item in history:
        old_state = item["old_state"]
        new_state = item["new_state"]
        actor = item["actor"]
        when = item["time"]

        # AR: موافقة البديل الفعلية.
        # EN: Actual substitute approval.
        if (
            old_state == ATTENDANCE_STATE_WAITING_SUBSTITUTE
            and new_state == ATTENDANCE_STATE_WAITING_DIRECT_MANAGER
        ):
            values["custom_substitute_approval"] = APPROVAL_APPROVED
            values["custom_substitute_approved_by"] = actor
            values["custom_substitute_approved_on"] = when
            continue

        # AR: اعتماد المدير أثناء انتظار البديل؛ البديل يعتبر متجاوزاً.
        # EN: Manager approval while substitute is pending; substitute is bypassed.
        if (
            old_state == ATTENDANCE_STATE_WAITING_SUBSTITUTE
            and new_state == ATTENDANCE_STATE_WAITING_HR_MANAGER
        ):
            values["custom_direct_manager_approval"] = APPROVAL_APPROVED
            values["custom_direct_manager_approved_by"] = actor
            values["custom_direct_manager_approved_on"] = when
            if has_substitute and values["custom_substitute_approval"] != APPROVAL_APPROVED:
                values["custom_substitute_approval"] = APPROVAL_BYPASSED
            continue

        # AR: اعتماد المدير بعد موافقة البديل أو بدون بديل.
        # EN: Manager approval after substitute approval or when no substitute exists.
        if (
            old_state == ATTENDANCE_STATE_WAITING_DIRECT_MANAGER
            and new_state == ATTENDANCE_STATE_WAITING_HR_MANAGER
        ):
            values["custom_direct_manager_approval"] = APPROVAL_APPROVED
            values["custom_direct_manager_approved_by"] = actor
            values["custom_direct_manager_approved_on"] = when
            continue

        # AR: الاعتماد النهائي من أي مرحلة نشطة.
        # EN: Final approval from any active stage.
        if old_state in ACTIVE_STATES and new_state == ATTENDANCE_STATE_APPROVED:
            final_approved = True
            values["custom_hr_approved_by"] = actor
            values["custom_hr_approved_on"] = when

            if has_substitute and values["custom_substitute_approval"] != APPROVAL_APPROVED:
                values["custom_substitute_approval"] = APPROVAL_BYPASSED
            elif not has_substitute:
                values["custom_substitute_approval"] = ""

            if values["custom_direct_manager_approval"] != APPROVAL_APPROVED:
                values["custom_direct_manager_approval"] = APPROVAL_BYPASSED
            continue

    # AR: حل احتياطي للسجلات المعتمدة التي فقدت سجل Version.
    # EN: Fallback for approved records whose Version history is incomplete.
    if row.workflow_state == ATTENDANCE_STATE_APPROVED and not final_approved:
        values["custom_hr_approved_by"] = row.custom_hr_approved_by or row.modified_by
        values["custom_hr_approved_on"] = row.custom_hr_approved_on or row.modified
        if has_substitute and values["custom_substitute_approval"] != APPROVAL_APPROVED:
            values["custom_substitute_approval"] = APPROVAL_BYPASSED
        if values["custom_direct_manager_approval"] != APPROVAL_APPROVED:
            values["custom_direct_manager_approval"] = APPROVAL_BYPASSED

    # AR: لا نعيد كتابة سجلات مرفوضة نهائياً؛ الإصلاح يخص المعتمدة أو النشطة فقط.
    # EN: Do not rewrite genuine final rejections; this repair targets active/approved records.
    if row.workflow_state == ATTENDANCE_STATE_REJECTED:
        return False

    frappe.db.set_value(
        ATTENDANCE_DOCTYPE,
        row.name,
        values,
        update_modified=False,
    )
    return True


def _repair_existing_requests():
    """
    AR: تنفيذ `repair` الموجود `requests` ضمن وحدة `fix_attendance_workflow_and_print_v14`.
    EN: Execute repair existing requests within the `fix_attendance_workflow_and_print_v14` module.
    """
    if not frappe.db.exists("DocType", ATTENDANCE_DOCTYPE):
        return {"returned_to_draft": 0, "audit_rebuilt": 0}

    fieldnames = {
        field.fieldname for field in frappe.get_meta(ATTENDANCE_DOCTYPE).fields
    }
    required = {
        "workflow_state",
        "custom_substitute_employee",
        "custom_substitute_user",
        "custom_substitute_approval",
        "custom_direct_manager_approval",
        "custom_hr_approved_by",
    }
    if not required.issubset(fieldnames):
        return {"returned_to_draft": 0, "audit_rebuilt": 0}

    rows = frappe.get_all(
        ATTENDANCE_DOCTYPE,
        fields=[
            "name",
            "workflow_state",
            "modified",
            "modified_by",
            "custom_substitute_employee",
            "custom_substitute_user",
            "custom_substitute_approval",
            "custom_substitute_approved_by",
            "custom_substitute_approved_on",
            "custom_direct_manager_approval",
            "custom_direct_manager_approved_by",
            "custom_direct_manager_approved_on",
            "custom_hr_approved_by",
            "custom_hr_approved_on",
        ],
        limit_page_length=0,
    )

    returned_to_draft = 0
    audit_rebuilt = 0

    for row in rows:
        history = _workflow_history(row.name)
        if _repair_rejected_substitute_request(row, history):
            returned_to_draft += 1
            continue
        if _rebuild_approval_audit(row, history):
            audit_rebuilt += 1

    return {
        "returned_to_draft": returned_to_draft,
        "audit_rebuilt": audit_rebuilt,
    }


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `fix_attendance_workflow_and_print_v14`.
    EN: Execute execute within the `fix_attendance_workflow_and_print_v14` module.

    DETAILS / التفاصيل:
    AR:
            1) إعادة بناء Workflow طلب المهمة باسم جديد في Patch Log لضمان التنفيذ.
            2) تفعيل اعتماد المدير أثناء انتظار البديل واعتماد HR النهائي من أي مرحلة.
            3) إعادة طلبات رفض البديل إلى الموظف بدلاً من الحالة مرفوضة.
            4) إصلاح حقول التوقيع المستخدمة في تنسيق الطباعة.
            5) إعادة مزامنة المشاركات ليصل الطلب فوراً للمدير.

        EN:
            1) Rebuild the Official Duty workflow through a new Patch Log entry.
            2) Enable manager approval during substitute waiting and HR final approval from any stage.
            3) Return substitute-rejected requests to the applicant instead of final Rejected.
            4) Repair print-signature audit fields.
            5) Re-sync shares so the manager receives the request immediately.
    """
    setup_attendance_request_all()
    result = _repair_existing_requests()
    resync_all_attendance_request_shares()

    frappe.clear_cache(doctype=ATTENDANCE_DOCTYPE)
    frappe.clear_cache()
    frappe.db.commit()

    print(
        "Attendance Request V14 repair completed: "
        f"returned_to_draft={result['returned_to_draft']}, "
        f"audit_rebuilt={result['audit_rebuilt']}"
    )
