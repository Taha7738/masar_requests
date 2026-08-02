"""
AR: إعداد وتهيئة مكونات التطبيق ضمن الوحدة `setup_official_duty_request`.
EN: Application setup and configuration routines for the `setup_official_duty_request` module.
"""

# ============================================================================
# AR: إعداد مستند المهمة الرسمية المستقل وتنظيف تخصيص Attendance Request القديم
# EN: Independent Official Duty setup and legacy Attendance Request cleanup
# ============================================================================

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from masar_requests.constants import (
    ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
    ATTENDANCE_ACTION_FINAL_APPROVE,
    ATTENDANCE_ACTION_REJECT,
    ATTENDANCE_ACTION_SEND_TO_DIRECT_MANAGER,
    ATTENDANCE_ACTION_SEND_TO_SUBSTITUTE,
    ATTENDANCE_ACTION_SUBSTITUTE_APPROVE,
    ATTENDANCE_STATE_APPROVED,
    ATTENDANCE_STATE_DRAFT,
    ATTENDANCE_STATE_REJECTED,
    ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
    ATTENDANCE_STATE_WAITING_HR_MANAGER,
    ATTENDANCE_STATE_WAITING_SUBSTITUTE,
)
from masar_requests.manual_official_duty_reconciliation import setup_manual_reconciliation_fields
from masar_requests.setup_attendance_request import (
    ATTENDANCE_CUSTOM_FIELDNAMES,
    ATTENDANCE_WORKFLOW_NAME,
)

OFFICIAL_DUTY_DOCTYPE = "Official Duty Request"
OFFICIAL_DUTY_WORKFLOW_NAME = "Official Duty Request Workflow masar_requests"
LEGACY_ATTENDANCE_DOCTYPE = "Attendance Request"
LEGACY_PRINT_FORMAT = "Masar Attendance Request Form"

EMPLOYEE_ROLE = "Employee"
ALL_ROLE = "All"
HR_MANAGER_ROLE = "HR Manager"
SYSTEM_MANAGER_ROLE = "System Manager"


def get_official_duty_integration_fields():
    """
    AR: تنفيذ استرجاع الرسمية المهمة `integration` الحقول ضمن وحدة `setup_official_duty_request`.
    EN: Execute get official duty integration fields within the `setup_official_duty_request` module.

    DETAILS / التفاصيل:
    AR:
            حقول ربط تقنية فقط على Attendance Request وAttendance. لا تغير هذه
            الحقول سلوك المستند القياسي أو واجهته الأساسية.

        EN:
            Technical link/audit fields only on Attendance Request and Attendance.
            They do not replace or alter the native Attendance Request controller.
    """
    return {
        "Attendance Request": [
            {
                "fieldname": "custom_official_duty_request",
                "fieldtype": "Link",
                "label": "Official Duty Request",
                "options": OFFICIAL_DUTY_DOCTYPE,
                "insert_after": "explanation",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            }
        ],
        "Attendance": [
            {
                "fieldname": "custom_official_duty_section",
                "fieldtype": "Section Break",
                "label": "Official Duty Reconciliation",
                "insert_after": "attendance_request",
                "depends_on": "custom_official_duty_request",
                "collapsible": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_official_duty_request",
                "fieldtype": "Link",
                "label": "Official Duty Request",
                "options": OFFICIAL_DUTY_DOCTYPE,
                "insert_after": "custom_official_duty_section",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_official_duty_hours",
                "fieldtype": "Float",
                "label": "Official Duty Hours",
                "insert_after": "custom_official_duty_request",
                "precision": 4,
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_physical_working_hours",
                "fieldtype": "Float",
                "label": "Physical Working Hours",
                "insert_after": "custom_official_duty_hours",
                "precision": 4,
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_official_duty_column",
                "fieldtype": "Column Break",
                "insert_after": "custom_physical_working_hours",
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_credited_working_hours",
                "fieldtype": "Float",
                "label": "Credited Working Hours",
                "insert_after": "custom_official_duty_column",
                "precision": 4,
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_uncovered_hours",
                "fieldtype": "Float",
                "label": "Uncovered Hours",
                "insert_after": "custom_credited_working_hours",
                "precision": 4,
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_missing_checkout_explained",
                "fieldtype": "Check",
                "label": "Missing Checkout Explained",
                "insert_after": "custom_uncovered_hours",
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_official_duty_reconciliation_status",
                "fieldtype": "Select",
                "label": "Official Duty Reconciliation Status",
                "options": "Pending\nWaiting for Shift End\nReconciled\nManual Review\nFailed",
                "insert_after": "custom_missing_checkout_explained",
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_official_duty_note",
                "fieldtype": "Small Text",
                "label": "Official Duty Note",
                "insert_after": "custom_official_duty_reconciliation_status",
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_official_duty_previous_status",
                "fieldtype": "Data",
                "label": "Previous Official Duty Attendance Status",
                "insert_after": "custom_official_duty_note",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_official_duty_previous_half_day_status",
                "fieldtype": "Data",
                "label": "Previous Official Duty Half Day Status",
                "insert_after": "custom_official_duty_previous_status",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_official_duty_previous_late_entry",
                "fieldtype": "Check",
                "label": "Previous Official Duty Late Entry",
                "insert_after": "custom_official_duty_previous_half_day_status",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_official_duty_previous_early_exit",
                "fieldtype": "Check",
                "label": "Previous Official Duty Early Exit",
                "insert_after": "custom_official_duty_previous_late_entry",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
        ],
    }


def setup_official_duty_request_all():
    """
    AR: تنفيذ إعداد الرسمية المهمة الطلب `all` ضمن وحدة `setup_official_duty_request`.
    EN: Execute setup official duty request all within the `setup_official_duty_request` module.
    """
    create_custom_fields(get_official_duty_integration_fields(), update=True)
    setup_manual_reconciliation_fields()
    create_official_duty_workflow_prerequisites()
    create_official_duty_workflow()

    for doctype in (OFFICIAL_DUTY_DOCTYPE, "Attendance Request", "Attendance"):
        frappe.clear_cache(doctype=doctype)


def create_official_duty_workflow_prerequisites():
    """
    AR: تنفيذ إنشاء الرسمية المهمة سير العمل `prerequisites` ضمن وحدة `setup_official_duty_request`.
    EN: Execute create official duty workflow prerequisites within the `setup_official_duty_request` module.
    """
    states = [
        ATTENDANCE_STATE_DRAFT,
        ATTENDANCE_STATE_WAITING_SUBSTITUTE,
        ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
        ATTENDANCE_STATE_WAITING_HR_MANAGER,
        ATTENDANCE_STATE_APPROVED,
        ATTENDANCE_STATE_REJECTED,
    ]
    for state in states:
        if not frappe.db.exists("Workflow State", state):
            frappe.get_doc(
                {"doctype": "Workflow State", "workflow_state_name": state}
            ).insert(ignore_permissions=True)

    actions = [
        ATTENDANCE_ACTION_SEND_TO_SUBSTITUTE,
        ATTENDANCE_ACTION_SEND_TO_DIRECT_MANAGER,
        ATTENDANCE_ACTION_SUBSTITUTE_APPROVE,
        ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
        ATTENDANCE_ACTION_FINAL_APPROVE,
        ATTENDANCE_ACTION_REJECT,
    ]
    for action in actions:
        if not frappe.db.exists("Workflow Action Master", action):
            frappe.get_doc(
                {
                    "doctype": "Workflow Action Master",
                    "workflow_action_name": action,
                }
            ).insert(ignore_permissions=True)


def _hr_override_transitions():
    """
    AR: تنفيذ `hr` `override` `transitions` ضمن وحدة `setup_official_duty_request`.
    EN: Execute hr override transitions within the `setup_official_duty_request` module.
    """
    transitions = []
    for state in (
        ATTENDANCE_STATE_DRAFT,
        ATTENDANCE_STATE_WAITING_SUBSTITUTE,
        ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
        ATTENDANCE_STATE_WAITING_HR_MANAGER,
    ):
        transitions.extend(
            [
                {
                    "state": state,
                    "action": ATTENDANCE_ACTION_FINAL_APPROVE,
                    "next_state": ATTENDANCE_STATE_APPROVED,
                    "allowed": HR_MANAGER_ROLE,
                },
                {
                    "state": state,
                    "action": ATTENDANCE_ACTION_REJECT,
                    "next_state": ATTENDANCE_STATE_REJECTED,
                    "allowed": HR_MANAGER_ROLE,
                },
            ]
        )
    return transitions


def _system_manager_transitions():
    """
    AR: تنفيذ `system` المدير `transitions` ضمن وحدة `setup_official_duty_request`.
    EN: Execute system manager transitions within the `setup_official_duty_request` module.
    """
    transitions = []
    for state in (
        ATTENDANCE_STATE_DRAFT,
        ATTENDANCE_STATE_WAITING_SUBSTITUTE,
        ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
        ATTENDANCE_STATE_WAITING_HR_MANAGER,
    ):
        transitions.extend(
            [
                {
                    "state": state,
                    "action": ATTENDANCE_ACTION_FINAL_APPROVE,
                    "next_state": ATTENDANCE_STATE_APPROVED,
                    "allowed": SYSTEM_MANAGER_ROLE,
                },
                {
                    "state": state,
                    "action": ATTENDANCE_ACTION_REJECT,
                    "next_state": ATTENDANCE_STATE_REJECTED,
                    "allowed": SYSTEM_MANAGER_ROLE,
                },
            ]
        )
    transitions.extend(
        [
            {
                "state": ATTENDANCE_STATE_DRAFT,
                "action": ATTENDANCE_ACTION_SEND_TO_SUBSTITUTE,
                "next_state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
                "allowed": SYSTEM_MANAGER_ROLE,
                "condition": "doc.custom_substitute_user and doc.custom_direct_manager_user",
            },
            {
                "state": ATTENDANCE_STATE_DRAFT,
                "action": ATTENDANCE_ACTION_SEND_TO_DIRECT_MANAGER,
                "next_state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
                "allowed": SYSTEM_MANAGER_ROLE,
                "condition": "doc.custom_direct_manager_user and not doc.custom_substitute_user",
            },
            {
                "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
                "action": ATTENDANCE_ACTION_SUBSTITUTE_APPROVE,
                "next_state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
                "allowed": SYSTEM_MANAGER_ROLE,
            },
            {
                "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
                "action": ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
                "next_state": ATTENDANCE_STATE_WAITING_HR_MANAGER,
                "allowed": SYSTEM_MANAGER_ROLE,
            },
            {
                "state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
                "action": ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
                "next_state": ATTENDANCE_STATE_WAITING_HR_MANAGER,
                "allowed": SYSTEM_MANAGER_ROLE,
            },
        ]
    )
    return transitions


def create_official_duty_workflow():
    """
    AR: تنفيذ إنشاء الرسمية المهمة سير العمل ضمن وحدة `setup_official_duty_request`.
    EN: Execute create official duty workflow within the `setup_official_duty_request` module.

    DETAILS / التفاصيل:
    AR:
            إنشاء سير العمل على Official Duty Request فقط، مع البديل الاختياري
            واعتماد المدير وتجاوز الموارد البشرية. لا يلمس Attendance Request.

        EN:
            Create workflow only on Official Duty Request with optional substitute,
            manager approval, and HR override. Attendance Request stays native.
    """
    existing = frappe.db.get_value(
        "Workflow",
        {
            "workflow_name": OFFICIAL_DUTY_WORKFLOW_NAME,
            "document_type": OFFICIAL_DUTY_DOCTYPE,
        },
        "name",
    )
    workflow = frappe.get_doc("Workflow", existing) if existing else frappe.new_doc("Workflow")
    workflow.set("states", [])
    workflow.set("transitions", [])
    workflow.workflow_name = OFFICIAL_DUTY_WORKFLOW_NAME
    workflow.document_type = OFFICIAL_DUTY_DOCTYPE
    workflow.is_active = 1
    workflow.override_status = 0
    workflow.send_email_alert = 0
    workflow.workflow_state_field = "workflow_state"
    workflow.condition = ""

    for row in [
        {"state": ATTENDANCE_STATE_DRAFT, "doc_status": 0, "allow_edit": EMPLOYEE_ROLE, "update_value": "Open"},
        {"state": ATTENDANCE_STATE_WAITING_SUBSTITUTE, "doc_status": 0, "allow_edit": ALL_ROLE, "update_value": "Open"},
        {"state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER, "doc_status": 0, "allow_edit": ALL_ROLE, "update_value": "Open"},
        {"state": ATTENDANCE_STATE_WAITING_HR_MANAGER, "doc_status": 0, "allow_edit": HR_MANAGER_ROLE, "update_value": "Open"},
        {"state": ATTENDANCE_STATE_APPROVED, "doc_status": 1, "allow_edit": HR_MANAGER_ROLE, "update_value": "Approved"},
        {"state": ATTENDANCE_STATE_REJECTED, "doc_status": 0, "allow_edit": HR_MANAGER_ROLE, "update_value": "Rejected"},
    ]:
        workflow.append(
            "states",
            {
                "state": row["state"],
                "doc_status": row["doc_status"],
                "allow_edit": row["allow_edit"],
                "update_field": "status",
                "update_value": row["update_value"],
            },
        )

    applicant_condition = "doc.custom_applicant_user == frappe.session.user"
    transitions = [
        {
            "state": ATTENDANCE_STATE_DRAFT,
            "action": ATTENDANCE_ACTION_SEND_TO_SUBSTITUTE,
            "next_state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "allowed": EMPLOYEE_ROLE,
            "condition": f"{applicant_condition} and doc.custom_substitute_user and doc.custom_direct_manager_user",
        },
        {
            "state": ATTENDANCE_STATE_DRAFT,
            "action": ATTENDANCE_ACTION_SEND_TO_DIRECT_MANAGER,
            "next_state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "allowed": EMPLOYEE_ROLE,
            "condition": f"{applicant_condition} and doc.custom_direct_manager_user and not doc.custom_substitute_user",
        },
        {
            "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "action": ATTENDANCE_ACTION_SUBSTITUTE_APPROVE,
            "next_state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "allowed": ALL_ROLE,
            "condition": "doc.custom_substitute_user == frappe.session.user",
        },
        {
            "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "action": ATTENDANCE_ACTION_REJECT,
            "next_state": ATTENDANCE_STATE_DRAFT,
            "allowed": ALL_ROLE,
            "condition": "doc.custom_substitute_user == frappe.session.user",
        },
        {
            "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "action": ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
            "next_state": ATTENDANCE_STATE_WAITING_HR_MANAGER,
            "allowed": ALL_ROLE,
            "condition": "doc.custom_direct_manager_user == frappe.session.user",
        },
        {
            "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "action": ATTENDANCE_ACTION_REJECT,
            "next_state": ATTENDANCE_STATE_REJECTED,
            "allowed": ALL_ROLE,
            "condition": "doc.custom_direct_manager_user == frappe.session.user",
        },
        {
            "state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "action": ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
            "next_state": ATTENDANCE_STATE_WAITING_HR_MANAGER,
            "allowed": ALL_ROLE,
            "condition": "doc.custom_direct_manager_user == frappe.session.user",
        },
        {
            "state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "action": ATTENDANCE_ACTION_REJECT,
            "next_state": ATTENDANCE_STATE_REJECTED,
            "allowed": ALL_ROLE,
            "condition": "doc.custom_direct_manager_user == frappe.session.user",
        },
    ]
    transitions.extend(_hr_override_transitions())
    transitions.extend(_system_manager_transitions())

    for row in transitions:
        values = {
            "state": row["state"],
            "action": row["action"],
            "next_state": row["next_state"],
            "allowed": row["allowed"],
            "allow_self_approval": 1,
        }
        if row.get("condition"):
            values["condition"] = row["condition"]
        workflow.append("transitions", values)

    if existing:
        workflow.save(ignore_permissions=True)
    else:
        workflow.insert(ignore_permissions=True)

    # AR: تعطيل أي Workflow منافس على المستند الجديد فقط.
    # EN: Deactivate competing workflows only on the new DocType.
    for name in frappe.get_all(
        "Workflow", filters={"document_type": OFFICIAL_DUTY_DOCTYPE}, pluck="name"
    ):
        if name != workflow.name:
            frappe.db.set_value("Workflow", name, "is_active", 0, update_modified=False)


def _legacy_meta_fields():
    """
    AR: تنفيذ القديم `meta` الحقول ضمن وحدة `setup_official_duty_request`.
    EN: Execute legacy meta fields within the `setup_official_duty_request` module.

    DETAILS / التفاصيل:
    AR:
            إرجاع أعمدة قاعدة البيانات الفعلية لمستند Attendance Request فقط.
            لا نعتمد على جميع حقول الميتاداتا لأن حقول التخطيط مثل Section Break
            وColumn Break تظهر في الميتاداتا لكنها لا تنشئ أعمدة داخل الجدول.

        EN:
            Return only the physical database columns of Attendance Request.
            Metadata-only layout fields such as Section Break and Column Break do
            not create table columns and must never be selected in database queries.
    """
    try:
        return set(frappe.db.get_table_columns(LEGACY_ATTENDANCE_DOCTYPE) or [])
    except Exception:
        # AR: مسار احتياطي محافظ لإصدارات Frappe التي يتعذر فيها جلب الأعمدة.
        # EN: Conservative fallback for Frappe versions where column lookup fails.
        meta = frappe.get_meta(LEGACY_ATTENDANCE_DOCTYPE)
        physical_fields = {
            field.fieldname
            for field in meta.fields
            if field.fieldname and not getattr(field, "no_value", 0)
        }
        return physical_fields | {
            "name",
            "owner",
            "creation",
            "modified",
            "modified_by",
            "docstatus",
            "idx",
        }


def migrate_legacy_official_duty_records():
    """
    AR: تنفيذ ترحيل القديم الرسمية المهمة `records` ضمن وحدة `setup_official_duty_request`.
    EN: Execute migrate legacy official duty records within the `setup_official_duty_request` module.

    DETAILS / التفاصيل:
    AR:
            نسخ طلبات المهمة القديمة من Attendance Request إلى المستند الجديد دون
            إعادة إنشاء الحضور أو تشغيل التسوية مرة ثانية.

        EN:
            Copy legacy duty records from Attendance Request into the new DocType
            without recreating Attendance or re-running reconciliation.
    """
    if not frappe.db.exists("DocType", OFFICIAL_DUTY_DOCTYPE):
        return 0

    fields = _legacy_meta_fields()
    legacy_markers = {
        "custom_mission_location",
        "custom_assignment_explanation",
        "custom_achievement_report",
    }
    if not fields.intersection(legacy_markers):
        return 0

    # AR:
    # لا نفترض وجود حقول غير قياسية مثل status على Attendance Request.
    # نختار فقط الحقول الموجودة فعليًا في الميتاداتا، مع السماح بالحقول
    # النظامية الضمنية التي لا تظهر ضمن meta.fields.
    #
    # EN:
    # Do not assume non-native fields such as status exist on Attendance Request.
    # Select only fields present in metadata, plus implicit system columns that
    # are not listed in meta.fields.
    implicit_system_fields = {"name", "owner", "docstatus"}
    available_fields = fields | implicit_system_fields

    candidate_fields = [
        "name",
        "owner",
        "docstatus",
        "employee",
        "employee_name",
        "company",
        "department",
        "from_date",
        "to_date",
        "reason",
        "include_holidays",
        "shift",
        "workflow_state",
        "status",
        *sorted(fields.intersection(set(ATTENDANCE_CUSTOM_FIELDNAMES))),
    ]
    select_fields = list(
        dict.fromkeys(
            fieldname
            for fieldname in candidate_fields
            if fieldname in available_fields
        )
    )

    records = frappe.get_all(
        LEGACY_ATTENDANCE_DOCTYPE,
        filters={"reason": "On Duty"},
        fields=select_fields,
        limit_page_length=0,
        order_by="creation asc",
    )
    migrated = 0
    for row in records:
        if frappe.db.exists(OFFICIAL_DUTY_DOCTYPE, {"legacy_attendance_request": row.name}):
            continue

        # AR: لا ننقل طلب On Duty قياسياً لم يستخدم حقول تخصيص المهمة القديمة.
        # EN: Do not migrate a native On Duty request that never used legacy duty fields.
        if not any(row.get(fieldname) for fieldname in legacy_markers):
            continue

        leaving_time = row.get("custom_leaving_time")
        return_time = row.get("custom_return_time")
        duty_type = "Hourly" if leaving_time and return_time and row.from_date == row.to_date else "Full Day"
        doc = frappe.new_doc(OFFICIAL_DUTY_DOCTYPE)
        doc.flags.legacy_migration = True
        doc.owner = row.owner
        doc.employee = row.employee
        doc.employee_name = row.get("employee_name")
        doc.company = row.get("company")
        doc.department = row.get("department")
        doc.from_date = row.from_date
        doc.to_date = row.to_date
        doc.duty_type = duty_type
        doc.include_holidays = cint(row.get("include_holidays"))
        doc.shift = row.get("shift")
        doc.reason = "On Duty"
        doc.custom_mission_location = row.get("custom_mission_location") or _("Not specified in legacy request")
        doc.custom_leaving_time = leaving_time if duty_type == "Hourly" else None
        doc.custom_return_time = return_time if duty_type == "Hourly" else None
        doc.custom_assignment_explanation = (
            row.get("custom_assignment_explanation")
            or _("Migrated from Attendance Request {0}").format(row.name)
        )
        doc.custom_achievement_report = (
            row.get("custom_achievement_report")
            or _("Legacy request migrated without an achievement report.")
        )
        doc.custom_achievement_report_attachment = row.get("custom_achievement_report_attachment")
        for fieldname in (
            "custom_substitute_employee",
            "custom_substitute_employee_name",
            "custom_applicant_user",
            "custom_substitute_approval",
            "custom_substitute_approved_by",
            "custom_substitute_approved_on",
            "custom_substitute_user",
            "custom_direct_manager_employee",
            "custom_direct_manager_approval",
            "custom_direct_manager_approved_by",
            "custom_direct_manager_approved_on",
            "custom_direct_manager_user",
            "custom_hr_approved_by",
            "custom_hr_approved_on",
        ):
            if row.get(fieldname) is not None:
                doc.set(fieldname, row.get(fieldname))
        doc.legacy_attendance_request = row.name
        doc.processing_status = "Legacy Linked"
        doc.processing_message = _("Historical record linked to Attendance Request {0}.").format(row.name)
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)

        workflow_state = row.get("workflow_state") or (
            ATTENDANCE_STATE_APPROVED if row.docstatus == 1 else ATTENDANCE_STATE_DRAFT
        )
        status = row.get("status") or ("Approved" if row.docstatus == 1 else "Open")
        frappe.db.set_value(
            OFFICIAL_DUTY_DOCTYPE,
            doc.name,
            {
                "docstatus": cint(row.docstatus),
                "workflow_state": workflow_state,
                "status": status,
                "processing_status": "Legacy Linked",
            },
            update_modified=False,
        )

        # AR: حفظ رابط تقني فقط على الطلب التاريخي لتسهيل التتبع ومنع التكرار.
        # EN: Store only a technical link on the historical request for traceability.
        if frappe.get_meta(LEGACY_ATTENDANCE_DOCTYPE).has_field(
            "custom_official_duty_request"
        ):
            frappe.db.set_value(
                LEGACY_ATTENDANCE_DOCTYPE,
                row.name,
                "custom_official_duty_request",
                doc.name,
                update_modified=False,
            )
        migrated += 1

    return migrated


def _delete_property_setter(doc_type, field_name, property_name):
    """
    AR: تنفيذ حذف `property` `setter` ضمن وحدة `setup_official_duty_request`.
    EN: Execute delete property setter within the `setup_official_duty_request` module.
    """
    frappe.db.delete(
        "Property Setter",
        {
            "doc_type": doc_type,
            "field_name": field_name,
            "property": property_name,
        },
    )


def _legacy_hr_user_permission_filters():
    """
    AR: تنفيذ القديم `hr` المستخدم صلاحية `filters` ضمن وحدة `setup_official_duty_request`.
    EN: Execute legacy hr user permission filters within the `setup_official_duty_request` module.
    """
    return {
        # AR:
        # Custom DocPerm في Frappe v15 مستند مستقل وليس جدولًا فرعيًا،
        # لذلك لا يحتوي على parenttype أو parentfield.
        #
        # EN:
        # Custom DocPerm is a standalone DocType in Frappe v15, not a child table;
        # therefore it has no parenttype or parentfield columns.
        "parent": LEGACY_ATTENDANCE_DOCTYPE,
        "role": "HR User",
        "permlevel": 0,
        "read": 1,
        "print": 1,
        "write": 0,
        "create": 0,
        "delete": 0,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "email": 0,
        "report": 0,
        "share": 0,
        "export": 0,
        "import": 0,
        "if_owner": 0,
    }


def _is_legacy_attendance_property_setter(row):
    """
    AR: تنفيذ التحقق من كون القديم الحضور `property` `setter` ضمن وحدة `setup_official_duty_request`.
    EN: Execute is legacy attendance property setter within the `setup_official_duty_request` module.
    """
    field_name = row.get("field_name") or ""
    property_name = row.get("property") or ""
    if field_name in ATTENDANCE_CUSTOM_FIELDNAMES:
        return True
    if (field_name, property_name) in {
        ("employee_name", "hidden"),
        ("department", "hidden"),
        ("company", "hidden"),
        ("company", "default"),
        ("employee", "read_only"),
        ("employee", "ignore_user_permissions"),
        ("reason", "default"),
    }:
        return True
    return property_name == "field_order" and any(
        fieldname in (row.get("value") or "")
        for fieldname in ATTENDANCE_CUSTOM_FIELDNAMES
    )


def cleanup_legacy_attendance_request_customization():
    """
    AR: تنفيذ `cleanup` القديم الحضور الطلب `customization` ضمن وحدة `setup_official_duty_request`.
    EN: Execute cleanup legacy attendance request customization within the `setup_official_duty_request` module.

    DETAILS / التفاصيل:
    AR:
            إعادة Attendance Request إلى سلوكه القياسي بحذف تخصيصات هذا التطبيق
            فقط: الحقول، Property Setters، Workflow، Print Format، وصلاحية HR User
            المخصصة. لا يحذف سجلات Attendance Request التاريخية.

        EN:
            Restore native Attendance Request behavior by removing only this app's
            fields, property setters, workflow, print format, and custom HR User row.
            Historical Attendance Request documents are preserved.
    """
    if not frappe.db.exists("DocType", LEGACY_ATTENDANCE_DOCTYPE):
        return {
            "migrated_before_cleanup": 0,
            "custom_fields": 0,
            "property_setters": 0,
            "workflow": 0,
            "print_format": 0,
        }

    # AR:
    # حماية إضافية للأمر اليدوي: لا نحذف حقول المهمة القديمة قبل وجود المستند
    # الجديد، ثم نحاول ترحيل أي سجل متبقٍ بصورة idempotent قبل الحذف.
    #
    # EN:
    # Safety for manual execution: never remove legacy duty fields before the
    # new DocType exists, and idempotently migrate any remaining record first.
    if not frappe.db.exists("DocType", OFFICIAL_DUTY_DOCTYPE):
        frappe.throw(
            _(
                "Official Duty Request is not synchronized yet. Run bench migrate before cleanup."
            )
        )
    migrated_before_cleanup = migrate_legacy_official_duty_records()

    custom_fields = frappe.get_all(
        "Custom Field",
        filters={
            "dt": LEGACY_ATTENDANCE_DOCTYPE,
            "fieldname": ("in", list(ATTENDANCE_CUSTOM_FIELDNAMES)),
        },
        pluck="name",
    )
    for name in custom_fields:
        frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

    before_count = frappe.db.count("Property Setter", {"doc_type": LEGACY_ATTENDANCE_DOCTYPE})
    frappe.db.delete(
        "Property Setter",
        {
            "doc_type": LEGACY_ATTENDANCE_DOCTYPE,
            "field_name": ("in", list(ATTENDANCE_CUSTOM_FIELDNAMES)),
        },
    )
    for field_name, property_name in (
        ("employee_name", "hidden"),
        ("department", "hidden"),
        ("company", "hidden"),
        ("company", "default"),
        ("employee", "read_only"),
        ("employee", "ignore_user_permissions"),
        ("reason", "default"),
    ):
        _delete_property_setter(LEGACY_ATTENDANCE_DOCTYPE, field_name, property_name)

    # AR: حذف ترتيب الحقول فقط عندما يحتوي بوضوح حقول المهمة القديمة.
    # EN: Delete field_order only when it clearly contains legacy duty fields.
    field_order_rows = frappe.get_all(
        "Property Setter",
        filters={
            "doc_type": LEGACY_ATTENDANCE_DOCTYPE,
            "property": "field_order",
        },
        fields=["name", "value"],
    )
    for row in field_order_rows:
        if any(fieldname in (row.value or "") for fieldname in ATTENDANCE_CUSTOM_FIELDNAMES):
            frappe.delete_doc("Property Setter", row.name, ignore_permissions=True, force=True)

    workflow_deleted = 0
    if frappe.db.exists("Workflow", ATTENDANCE_WORKFLOW_NAME):
        frappe.delete_doc(
            "Workflow", ATTENDANCE_WORKFLOW_NAME, ignore_permissions=True, force=True
        )
        workflow_deleted = 1

    print_deleted = 0
    if frappe.db.exists("Print Format", LEGACY_PRINT_FORMAT):
        frappe.delete_doc(
            "Print Format", LEGACY_PRINT_FORMAT, ignore_permissions=True, force=True
        )
        print_deleted = 1

    # AR: إزالة صف الصلاحية الذي أنشأه التطبيق حتى تعود صلاحيات HRMS القياسية.
    # EN: Remove the app-created permission row so native HRMS permissions apply.
    # AR:
    # حذف صف التطبيق فقط عبر بصمته الدقيقة، وعدم حذف صلاحية مختلفة أنشأها العميل.
    # EN:
    # Delete only the exact app-created row and preserve any different customer permission.
    custom_perms = frappe.get_all(
        "Custom DocPerm",
        filters=_legacy_hr_user_permission_filters(),
        pluck="name",
    )
    for name in custom_perms:
        frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)

    frappe.clear_cache(doctype=LEGACY_ATTENDANCE_DOCTYPE)
    after_count = frappe.db.count("Property Setter", {"doc_type": LEGACY_ATTENDANCE_DOCTYPE})
    return {
        "migrated_before_cleanup": migrated_before_cleanup,
        "custom_fields": len(custom_fields),
        "property_setters": max(before_count - after_count, 0),
        "workflow": workflow_deleted,
        "print_format": print_deleted,
        "custom_permissions": len(custom_perms),
    }


def audit_legacy_attendance_request_customization():
    """
    AR: تنفيذ تدقيق القديم الحضور الطلب `customization` ضمن وحدة `setup_official_duty_request`.
    EN: Execute audit legacy attendance request customization within the `setup_official_duty_request` module.
    """
    custom_fields = frappe.get_all(
        "Custom Field",
        filters={
            "dt": LEGACY_ATTENDANCE_DOCTYPE,
            "fieldname": ("in", list(ATTENDANCE_CUSTOM_FIELDNAMES)),
        },
        pluck="fieldname",
    )
    all_property_setters = frappe.get_all(
        "Property Setter",
        filters={"doc_type": LEGACY_ATTENDANCE_DOCTYPE},
        fields=["name", "field_name", "property", "value"],
    )
    legacy_property_setters = [
        row for row in all_property_setters if _is_legacy_attendance_property_setter(row)
    ]
    legacy_custom_permissions = frappe.get_all(
        "Custom DocPerm",
        filters=_legacy_hr_user_permission_filters(),
        pluck="name",
    )
    return {
        "legacy_custom_fields": custom_fields,
        "legacy_workflow_exists": bool(frappe.db.exists("Workflow", ATTENDANCE_WORKFLOW_NAME)),
        "legacy_print_format_exists": bool(frappe.db.exists("Print Format", LEGACY_PRINT_FORMAT)),
        "legacy_property_setters": legacy_property_setters,
        "legacy_custom_permissions": legacy_custom_permissions,
        "preserved_non_app_property_setter_count": max(
            len(all_property_setters) - len(legacy_property_setters), 0
        ),
        "native_hooks_removed_from_code": True,
    }


def teardown_official_duty_request():
    """
    AR: تنفيذ `teardown` الرسمية المهمة الطلب ضمن وحدة `setup_official_duty_request`.
    EN: Execute teardown official duty request within the `setup_official_duty_request` module.

    DETAILS / التفاصيل:
    AR:
            تنظيف حقول الربط الخارجية وسير العمل عند إلغاء تثبيت التطبيق.
            لا يحذف أي سجل Employee Checkin، كما لا يعيد تخصيص Attendance Request القديم.

        EN:
            Remove external integration fields and workflow during app uninstall.
            Employee Checkin records are never deleted, and legacy Attendance Request
            customization is not recreated.
    """
    for doctype, fields in get_official_duty_integration_fields().items():
        fieldnames = [field["fieldname"] for field in fields]
        frappe.db.delete(
            "Custom Field",
            {"dt": doctype, "fieldname": ("in", fieldnames)},
        )
        frappe.clear_cache(doctype=doctype)

    if frappe.db.exists("Workflow", OFFICIAL_DUTY_WORKFLOW_NAME):
        frappe.delete_doc(
            "Workflow",
            OFFICIAL_DUTY_WORKFLOW_NAME,
            ignore_permissions=True,
            force=True,
        )
