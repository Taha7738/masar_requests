"""
AR: إعداد وتهيئة مكونات التطبيق ضمن الوحدة `setup_attendance_request`.
EN: Application setup and configuration routines for the `setup_attendance_request` module.
"""

# ============================================================================
# AR: إعداد طلب المهمة الرسمية (Attendance Request)
# EN: Official Duty (Attendance Request) setup
# ============================================================================

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from masar_requests.constants import (
    APPROVAL_APPROVED,
    APPROVAL_BYPASSED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
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

ATTENDANCE_DOCTYPE = "Attendance Request"
ATTENDANCE_WORKFLOW_NAME = "Official Duty Workflow masar_requests"
APP_MODULE = "Masar Requests"

EMPLOYEE_ROLE = "Employee"
ALL_ROLE = "All"
HR_MANAGER_ROLE = "HR Manager"
SYSTEM_MANAGER_ROLE = "System Manager"

# AR: الحقول التي يملكها تخصيص المهمة الرسمية، بما فيها حقول الإصدارات القديمة.
# EN: Fields owned by this customization, including obsolete report-workflow fields.
ATTENDANCE_CUSTOM_FIELDNAMES = (
    "workflow_state",
    "custom_substitute_employee",
    "custom_substitute_employee_name",
    "custom_applicant_user",
    "custom_duty_progress_status",  # Legacy / قديم
    "custom_on_duty_section",
    "custom_mission_location",
    "custom_details_col",
    "custom_leaving_time",
    "custom_return_time_col",
    "custom_return_time",
    "custom_assignment_section",
    "custom_assignment_explanation",
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
    "custom_achievement_report_section",
    "custom_achievement_report",
    "custom_achievement_report_attachment",
    # AR: حقول دورة التقرير القديمة، تزال من الميتاداتا ولا تستخدم بعد الآن.
    # EN: Obsolete report-cycle metadata removed from the DocType metadata.
    "custom_report_revision_reason",
    "custom_report_submitted_by",
    "custom_report_submitted_on",
    "custom_report_manager_approved_by",
    "custom_report_manager_approved_on",
    "custom_report_hr_approved_by",
    "custom_report_hr_approved_on",
    "custom_report_returned_by",
    "custom_report_returned_on",
)


def setup_attendance_request_all():
    """
    AR: تنفيذ إعداد الحضور الطلب `all` ضمن وحدة `setup_attendance_request`.
    EN: Execute setup attendance request all within the `setup_attendance_request` module.

    DETAILS / التفاصيل:
    AR:
            إعادة بناء حقول المهمة الرسمية، ترتيب الواجهة، الصلاحيات، وسير العمل.
            يعتمد سير العمل نفس مراحل طلب الإجازة، والتقرير مطلوب من أول إنشاء.

        EN:
            Rebuild Official Duty fields, layout, permissions, and workflow.
            The workflow mirrors Leave Application and the report is required at creation.
    """
    print("Setting up Official Duty (Attendance Request)...")

    layout_anchor = reset_attendance_request_layout()
    create_attendance_custom_fields(layout_anchor)
    configure_employee_link_display()
    apply_attendance_request_field_properties()
    apply_attendance_request_field_order()
    fix_attendance_standard_permissions()
    create_attendance_workflow_prerequisites()
    create_attendance_workflow()
    validate_attendance_request_layout(layout_anchor)

    frappe.clear_cache(doctype=ATTENDANCE_DOCTYPE)
    frappe.clear_cache(doctype="Employee")
    print("Official Duty setup completed successfully.")


def reset_attendance_request_layout():
    """
    AR: تنفيذ `reset` الحضور الطلب `layout` ضمن وحدة `setup_attendance_request`.
    EN: Execute reset attendance request layout within the `setup_attendance_request` module.
    """
    stale_fields = frappe.get_all(
        "Custom Field",
        filters={"dt": ATTENDANCE_DOCTYPE},
        fields=["name", "fieldname", "module"],
    )

    fields_to_delete = [
        row
        for row in stale_fields
        if row.module == APP_MODULE or row.fieldname in ATTENDANCE_CUSTOM_FIELDNAMES
    ]
    stale_fieldnames = [row.fieldname for row in fields_to_delete if row.fieldname]

    if stale_fieldnames:
        frappe.db.delete(
            "Property Setter",
            {
                "doc_type": ATTENDANCE_DOCTYPE,
                "field_name": ("in", stale_fieldnames),
            },
        )

    for row in fields_to_delete:
        # AR: حذف تعريف الحقل لا يحذف عمود قاعدة البيانات أو البيانات التاريخية.
        # EN: Deleting field metadata does not drop the DB column or historical values.
        frappe.db.delete("Custom Field", {"name": row.name})

    frappe.db.delete(
        "Property Setter",
        {"doc_type": ATTENDANCE_DOCTYPE, "property": "field_order"},
    )

    frappe.clear_cache(doctype=ATTENDANCE_DOCTYPE)
    meta = frappe.get_meta(ATTENDANCE_DOCTYPE, cached=False)
    if not meta.fields:
        frappe.throw(f"{ATTENDANCE_DOCTYPE} does not contain layout fields.")
    return meta.fields[-1].fieldname


def _hidden_field(fieldname, label, insert_after, fieldtype="Data", options=None):
    """
    AR: تنفيذ `hidden` الحقل ضمن وحدة `setup_attendance_request`.
    EN: Execute hidden field within the `setup_attendance_request` module.
    """
    field = {
        "fieldname": fieldname,
        "fieldtype": fieldtype,
        "label": label,
        "read_only": 1,
        "hidden": 1,
        "allow_on_submit": 1,
        "no_copy": 1,
        "module": APP_MODULE,
        "insert_after": insert_after,
    }
    if options:
        field["options"] = options
        field["ignore_user_permissions"] = 1
    return field


def get_attendance_custom_fields(standard_anchor):
    """
    AR: تنفيذ استرجاع الحضور `custom` الحقول ضمن وحدة `setup_attendance_request`.
    EN: Execute get attendance custom fields within the `setup_attendance_request` module.

    DETAILS / التفاصيل:
    AR:
            الموظف البديل تحت الموظف، الوردية تحته، تفاصيل المهمة في ثلاثة أعمدة،
            وتقرير الإنجاز والمرفق ظاهران من أول الطلب دون دورة اعتماد مستقلة.

        EN:
            Place Substitute under Employee, Shift below it, duty details in three columns,
            and show the report/attachment from creation without a separate report workflow.
    """
    depends_on_duty = 'eval:doc.reason == "On Duty"'
    approval_options = "\n".join(
        [APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_REJECTED, APPROVAL_BYPASSED]
    )

    return [
        # ------------------------------------------------------------------
        # AR: أعلى النموذج: الموظف ← البديل ← الوردية.
        # EN: Top of form: Employee -> Substitute -> Shift.
        # ------------------------------------------------------------------
        {
            "fieldname": "custom_substitute_employee",
            "fieldtype": "Link",
            "label": "Substitute Employee",
            "options": "Employee",
            "ignore_user_permissions": 1,
            "depends_on": depends_on_duty,
            "module": APP_MODULE,
            "insert_after": "employee",
        },
        {
            "fieldname": "custom_substitute_employee_name",
            "fieldtype": "Data",
            "label": "Substitute Employee Name",
            "fetch_from": "custom_substitute_employee.employee_name",
            "read_only": 1,
            "hidden": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
            "module": APP_MODULE,
            "insert_after": "custom_substitute_employee",
        },
        {
            "fieldname": "custom_applicant_user",
            "fieldtype": "Link",
            "label": "Applicant User",
            "options": "User",
            "read_only": 1,
            "hidden": 1,
            "ignore_user_permissions": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
            "module": APP_MODULE,
            "insert_after": "custom_substitute_employee_name",
        },
        # ------------------------------------------------------------------
        # AR: كتلة تفاصيل المهمة الرسمية.
        # EN: Official-duty details block.
        # ------------------------------------------------------------------
        {
            "fieldname": "workflow_state",
            "fieldtype": "Link",
            "options": "Workflow State",
            "label": "Workflow State",
            "hidden": 1,
            "read_only": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
            "module": APP_MODULE,
            "insert_after": standard_anchor,
        },
        {
            "fieldname": "custom_on_duty_section",
            "fieldtype": "Section Break",
            "label": "Official Duty Details",
            "depends_on": depends_on_duty,
            "module": APP_MODULE,
            "insert_after": "workflow_state",
        },
        {
            "fieldname": "custom_mission_location",
            "fieldtype": "Data",
            "label": "Mission Location",
            "reqd": 1,
            "module": APP_MODULE,
            "insert_after": "custom_on_duty_section",
        },
        {
            "fieldname": "custom_details_col",
            "fieldtype": "Column Break",
            "module": APP_MODULE,
            "insert_after": "custom_mission_location",
        },
        {
            "fieldname": "custom_leaving_time",
            "fieldtype": "Time",
            "label": "Leaving Time",
            "reqd": 1,
            "module": APP_MODULE,
            "insert_after": "custom_details_col",
        },
        {
            "fieldname": "custom_return_time_col",
            "fieldtype": "Column Break",
            "module": APP_MODULE,
            "insert_after": "custom_leaving_time",
        },
        {
            "fieldname": "custom_return_time",
            "fieldtype": "Time",
            "label": "Return Time",
            "reqd": 1,
            "module": APP_MODULE,
            "insert_after": "custom_return_time_col",
        },
        {
            "fieldname": "custom_assignment_section",
            "fieldtype": "Section Break",
            "label": "Assignment Explanation",
            "depends_on": depends_on_duty,
            "module": APP_MODULE,
            "insert_after": "custom_return_time",
        },
        {
            "fieldname": "custom_assignment_explanation",
            "fieldtype": "Small Text",
            "label": "Assignment Explanation",
            "reqd": 1,
            "module": APP_MODULE,
            "insert_after": "custom_assignment_section",
        },
        # ------------------------------------------------------------------
        # AR: التقرير مطلوب من أول الطلب، والمرفق متاح من البداية.
        # EN: The report is required at creation; its attachment is available immediately.
        # ------------------------------------------------------------------
        {
            "fieldname": "custom_achievement_report_section",
            "fieldtype": "Section Break",
            "label": "Achievement Report",
            "depends_on": depends_on_duty,
            "module": APP_MODULE,
            "insert_after": "custom_assignment_explanation",
        },
        {
            "fieldname": "custom_achievement_report",
            "fieldtype": "Text Editor",
            "label": "Achievement Report",
            "description": "Use the editor toolbar to format headings, colors, lists, and emphasis.",
            "reqd": 1,
            "module": APP_MODULE,
            "insert_after": "custom_achievement_report_section",
        },
        {
            "fieldname": "custom_achievement_report_attachment",
            "fieldtype": "Attach",
            "label": "Achievement Report Attachment",
            "module": APP_MODULE,
            "insert_after": "custom_achievement_report",
        },
        # ------------------------------------------------------------------
        # AR: حقول التدقيق والموافقات؛ مخفية وتستخدم للطباعة.
        # EN: Hidden approval/audit fields used by the print format.
        # ------------------------------------------------------------------
        {
            **_hidden_field(
                "custom_substitute_approval",
                "Substitute Status",
                "custom_achievement_report_attachment",
                "Select",
            ),
            "options": approval_options,
        },
        _hidden_field(
            "custom_substitute_approved_by",
            "Substitute Approved By",
            "custom_substitute_approval",
            "Link",
            "User",
        ),
        _hidden_field(
            "custom_substitute_approved_on",
            "Substitute Approved On",
            "custom_substitute_approved_by",
            "Datetime",
        ),
        _hidden_field(
            "custom_substitute_user",
            "Substitute User",
            "custom_substitute_approved_on",
            "Link",
            "User",
        ),
        _hidden_field(
            "custom_direct_manager_employee",
            "Direct Manager",
            "custom_substitute_user",
            "Link",
            "Employee",
        ),
        {
            **_hidden_field(
                "custom_direct_manager_approval",
                "Manager Status",
                "custom_direct_manager_employee",
                "Select",
            ),
            "options": approval_options,
        },
        _hidden_field(
            "custom_direct_manager_approved_by",
            "Manager Approved By",
            "custom_direct_manager_approval",
            "Link",
            "User",
        ),
        _hidden_field(
            "custom_direct_manager_approved_on",
            "Manager Approved On",
            "custom_direct_manager_approved_by",
            "Datetime",
        ),
        _hidden_field(
            "custom_direct_manager_user",
            "Direct Manager User",
            "custom_direct_manager_approved_on",
            "Link",
            "User",
        ),
        _hidden_field(
            "custom_hr_approved_by",
            "HR Approved By",
            "custom_direct_manager_user",
            "Link",
            "User",
        ),
        _hidden_field(
            "custom_hr_approved_on",
            "HR Approved On",
            "custom_hr_approved_by",
            "Datetime",
        ),
    ]


def create_attendance_custom_fields(layout_anchor=None):
    """
    AR: تنفيذ إنشاء الحضور `custom` الحقول ضمن وحدة `setup_attendance_request`.
    EN: Execute create attendance custom fields within the `setup_attendance_request` module.
    """
    if not layout_anchor:
        meta = frappe.get_meta(ATTENDANCE_DOCTYPE, cached=False)
        if not meta.fields:
            frappe.throw(f"{ATTENDANCE_DOCTYPE} does not contain layout fields.")
        layout_anchor = meta.fields[-1].fieldname

    create_custom_fields(
        {ATTENDANCE_DOCTYPE: get_attendance_custom_fields(layout_anchor)},
        update=True,
    )


def configure_employee_link_display():
    """
    AR: تنفيذ `configure` الموظف `link` `display` ضمن وحدة `setup_attendance_request`.
    EN: Execute configure employee link display within the `setup_attendance_request` module.
    """
    frappe.db.set_value(
        "DocType", "Employee", "title_field", "employee_name", update_modified=False
    )
    frappe.db.set_value(
        "DocType", "Employee", "show_title_field_in_link", 1, update_modified=False
    )


def _ensure_default_company():
    """
    AR: تنفيذ ضمان `default` `company` ضمن وحدة `setup_attendance_request`.
    EN: Execute ensure default company within the `setup_attendance_request` module.
    """
    meta = frappe.get_meta(ATTENDANCE_DOCTYPE, cached=False)
    company_field = meta.get_field("company")
    if not company_field:
        return

    candidates = [
        company_field.default,
        frappe.db.get_single_value("Global Defaults", "default_company"),
        frappe.db.get_value("Company", {}, "name"),
    ]
    default_company = next(
        (company for company in candidates if company and frappe.db.exists("Company", company)),
        None,
    )
    if not default_company:
        frappe.throw("Unable to hide Company because no valid default Company is configured.")

    make_property_setter(
        ATTENDANCE_DOCTYPE, "company", "default", default_company, "Data"
    )


def apply_attendance_request_field_properties():
    """
    AR: تنفيذ تطبيق الحضور الطلب الحقل `properties` ضمن وحدة `setup_attendance_request`.
    EN: Execute apply attendance request field properties within the `setup_attendance_request` module.
    """
    _ensure_default_company()
    meta = frappe.get_meta(ATTENDANCE_DOCTYPE, cached=False)

    fields_to_hide = (
        "employee_name",
        "department",
        "company",
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
    )

    for fieldname in fields_to_hide:
        if meta.has_field(fieldname):
            make_property_setter(
                ATTENDANCE_DOCTYPE, fieldname, "hidden", 1, "Check"
            )

    if meta.has_field("employee"):
        make_property_setter(
            ATTENDANCE_DOCTYPE, "employee", "read_only", 1, "Check"
        )

    # AR: القيمة الداخلية On Duty تظهر مترجمة إلى "في الخدمة".
    # EN: Default Reason to On Duty.
    if meta.has_field("reason"):
        make_property_setter(
            ATTENDANCE_DOCTYPE, "reason", "default", "On Duty", "Text"
        )


def _get_attendance_shift_fieldname(meta):
    """
    AR: تنفيذ استرجاع الحضور الوردية `fieldname` ضمن وحدة `setup_attendance_request`.
    EN: Execute get attendance shift fieldname within the `setup_attendance_request` module.
    """
    return next(
        (
            candidate
            for candidate in ("shift", "shift_type", "custom_shift")
            if meta.has_field(candidate)
        ),
        None,
    )


def apply_attendance_request_field_order():
    """
    AR: تنفيذ تطبيق الحضور الطلب الحقل `order` ضمن وحدة `setup_attendance_request`.
    EN: Execute apply attendance request field order within the `setup_attendance_request` module.
    """
    frappe.clear_cache(doctype=ATTENDANCE_DOCTYPE)
    meta = frappe.get_meta(ATTENDANCE_DOCTYPE, cached=False)
    field_order = [field.fieldname for field in meta.fields]

    if "employee" not in field_order or "custom_substitute_employee" not in field_order:
        frappe.throw("Attendance Request does not contain the required employee fields.")

    shift_fieldname = _get_attendance_shift_fieldname(meta)
    top_chain = ["custom_substitute_employee"]
    if shift_fieldname:
        top_chain.append(shift_fieldname)
    top_chain.extend(["custom_substitute_employee_name", "custom_applicant_user"])
    top_chain = [fieldname for fieldname in top_chain if fieldname in field_order]

    for fieldname in top_chain:
        while fieldname in field_order:
            field_order.remove(fieldname)

    employee_index = field_order.index("employee")
    field_order[employee_index + 1 : employee_index + 1] = top_chain

    make_property_setter(
        doctype=ATTENDANCE_DOCTYPE,
        fieldname=None,
        property="field_order",
        value=json.dumps(field_order),
        property_type="Text",
        for_doctype=True,
    )


def fix_attendance_standard_permissions():
    """
    AR: تنفيذ `fix` الحضور `standard` الصلاحيات ضمن وحدة `setup_attendance_request`.
    EN: Execute fix attendance standard permissions within the `setup_attendance_request` module.
    """
    make_property_setter(
        ATTENDANCE_DOCTYPE,
        "employee",
        "ignore_user_permissions",
        1,
        "Check",
    )


def validate_attendance_request_layout(layout_anchor):
    """
    AR: تنفيذ التحقق من صحة الحضور الطلب `layout` ضمن وحدة `setup_attendance_request`.
    EN: Execute validate attendance request layout within the `setup_attendance_request` module.
    """
    frappe.clear_cache(doctype=ATTENDANCE_DOCTYPE)
    meta = frappe.get_meta(ATTENDANCE_DOCTYPE, cached=False)
    field_order = [field.fieldname for field in meta.fields]

    required = [field["fieldname"] for field in get_attendance_custom_fields(layout_anchor)]
    missing = [fieldname for fieldname in required if fieldname not in field_order]
    if missing:
        frappe.throw(
            "Attendance Request layout repair failed; missing fields: " + ", ".join(missing)
        )

    employee_index = field_order.index("employee")
    substitute_index = field_order.index("custom_substitute_employee")
    if substitute_index != employee_index + 1:
        frappe.throw("Substitute Employee must be placed directly after Employee.")

    shift_fieldname = _get_attendance_shift_fieldname(meta)
    if shift_fieldname:
        shift_index = field_order.index(shift_fieldname)
        if shift_index != substitute_index + 1:
            frappe.throw("Shift must be placed directly below Substitute Employee.")

    detail_sequence = [
        "custom_mission_location",
        "custom_details_col",
        "custom_leaving_time",
        "custom_return_time_col",
        "custom_return_time",
    ]
    detail_indexes = [field_order.index(fieldname) for fieldname in detail_sequence]
    if detail_indexes != list(range(detail_indexes[0], detail_indexes[0] + 5)):
        frappe.throw(
            "Mission Location, Leaving Time, and Return Time must form one three-column row."
        )


def create_attendance_workflow_prerequisites():
    """
    AR: تنفيذ إنشاء الحضور سير العمل `prerequisites` ضمن وحدة `setup_attendance_request`.
    EN: Execute create attendance workflow prerequisites within the `setup_attendance_request` module.
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


def get_hr_manager_override_transitions():
    """
    AR: تنفيذ استرجاع `hr` المدير `override` `transitions` ضمن وحدة `setup_attendance_request`.
    EN: Execute get hr manager override transitions within the `setup_attendance_request` module.
    """
    active_states = (
        ATTENDANCE_STATE_DRAFT,
        ATTENDANCE_STATE_WAITING_SUBSTITUTE,
        ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
        ATTENDANCE_STATE_WAITING_HR_MANAGER,
    )
    transitions = []
    for state in active_states:
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


def get_system_manager_workflow_transitions():
    """
    AR: تنفيذ استرجاع `system` المدير سير العمل `transitions` ضمن وحدة `setup_attendance_request`.
    EN: Execute get system manager workflow transitions within the `setup_attendance_request` module.
    """
    return [
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
            "state": ATTENDANCE_STATE_DRAFT,
            "action": ATTENDANCE_ACTION_FINAL_APPROVE,
            "next_state": ATTENDANCE_STATE_APPROVED,
            "allowed": SYSTEM_MANAGER_ROLE,
        },
        {
            "state": ATTENDANCE_STATE_DRAFT,
            "action": ATTENDANCE_ACTION_REJECT,
            "next_state": ATTENDANCE_STATE_REJECTED,
            "allowed": SYSTEM_MANAGER_ROLE,
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
            "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "action": ATTENDANCE_ACTION_FINAL_APPROVE,
            "next_state": ATTENDANCE_STATE_APPROVED,
            "allowed": SYSTEM_MANAGER_ROLE,
        },
        {
            "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "action": ATTENDANCE_ACTION_REJECT,
            "next_state": ATTENDANCE_STATE_REJECTED,
            "allowed": SYSTEM_MANAGER_ROLE,
        },
        {
            "state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "action": ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
            "next_state": ATTENDANCE_STATE_WAITING_HR_MANAGER,
            "allowed": SYSTEM_MANAGER_ROLE,
        },
        {
            "state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "action": ATTENDANCE_ACTION_FINAL_APPROVE,
            "next_state": ATTENDANCE_STATE_APPROVED,
            "allowed": SYSTEM_MANAGER_ROLE,
        },
        {
            "state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "action": ATTENDANCE_ACTION_REJECT,
            "next_state": ATTENDANCE_STATE_REJECTED,
            "allowed": SYSTEM_MANAGER_ROLE,
        },
        {
            "state": ATTENDANCE_STATE_WAITING_HR_MANAGER,
            "action": ATTENDANCE_ACTION_FINAL_APPROVE,
            "next_state": ATTENDANCE_STATE_APPROVED,
            "allowed": SYSTEM_MANAGER_ROLE,
        },
        {
            "state": ATTENDANCE_STATE_WAITING_HR_MANAGER,
            "action": ATTENDANCE_ACTION_REJECT,
            "next_state": ATTENDANCE_STATE_REJECTED,
            "allowed": SYSTEM_MANAGER_ROLE,
        },
    ]


def create_attendance_workflow():
    """
    AR: تنفيذ إنشاء الحضور سير العمل ضمن وحدة `setup_attendance_request`.
    EN: Execute create attendance workflow within the `setup_attendance_request` module.

    DETAILS / التفاصيل:
    AR:
            إنشاء سير عمل مطابق لمسار طلب الإجازة:
            - مع بديل: الموظف ← البديل ← المسؤول المباشر ← الموارد البشرية.
            - دون بديل: الموظف ← المسؤول المباشر ← الموارد البشرية.
            - المسؤول المباشر يستطيع الاعتماد أثناء انتظار البديل وتجاوزه.
            - رفض البديل يعيد الطلب إلى الموظف لاختيار بديل جديد.

        EN:
            Create a Leave-like workflow with optional substitute, manager override,
            and substitute rejection returning the request to Draft for reselection.
    """
    existing_workflow_name = frappe.db.get_value(
        "Workflow",
        {
            "workflow_name": ATTENDANCE_WORKFLOW_NAME,
            "document_type": ATTENDANCE_DOCTYPE,
        },
        "name",
    )

    if existing_workflow_name:
        workflow = frappe.get_doc("Workflow", existing_workflow_name)
        workflow.set("states", [])
        workflow.set("transitions", [])
    else:
        workflow = frappe.new_doc("Workflow")

    workflow.workflow_name = ATTENDANCE_WORKFLOW_NAME
    workflow.document_type = ATTENDANCE_DOCTYPE
    workflow.is_active = 1
    workflow.override_status = 0
    workflow.send_email_alert = 0
    workflow.workflow_state_field = "workflow_state"
    workflow.condition = 'doc.reason == "On Duty"'

    workflow_states = [
        {
            "state": ATTENDANCE_STATE_DRAFT,
            "doc_status": 0,
            "allow_edit": EMPLOYEE_ROLE,
            "update_field": "status",
            "update_value": "Open",
        },
        {
            "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "doc_status": 0,
            "allow_edit": ALL_ROLE,
            "update_field": "status",
            "update_value": "Open",
        },
        {
            "state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "doc_status": 0,
            "allow_edit": ALL_ROLE,
            "update_field": "status",
            "update_value": "Open",
        },
        {
            "state": ATTENDANCE_STATE_WAITING_HR_MANAGER,
            "doc_status": 0,
            "allow_edit": HR_MANAGER_ROLE,
            "update_field": "status",
            "update_value": "Open",
        },
        {
            "state": ATTENDANCE_STATE_APPROVED,
            "doc_status": 1,
            "allow_edit": HR_MANAGER_ROLE,
            "update_field": "status",
            "update_value": "Approved",
        },
        {
            "state": ATTENDANCE_STATE_REJECTED,
            "doc_status": 0,
            "allow_edit": HR_MANAGER_ROLE,
            "update_field": "status",
            "update_value": "Rejected",
        },
    ]

    applicant_condition = "doc.custom_applicant_user == frappe.session.user"
    workflow_transitions = [
        {
            "state": ATTENDANCE_STATE_DRAFT,
            "action": ATTENDANCE_ACTION_SEND_TO_SUBSTITUTE,
            "next_state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "allowed": EMPLOYEE_ROLE,
            "condition": (
                f"{applicant_condition} and doc.custom_substitute_user "
                "and doc.custom_direct_manager_user"
            ),
        },
        {
            "state": ATTENDANCE_STATE_DRAFT,
            "action": ATTENDANCE_ACTION_SEND_TO_DIRECT_MANAGER,
            "next_state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "allowed": EMPLOYEE_ROLE,
            "condition": (
                f"{applicant_condition} and doc.custom_direct_manager_user "
                "and not doc.custom_substitute_user"
            ),
        },
        {
            "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "action": ATTENDANCE_ACTION_SUBSTITUTE_APPROVE,
            "next_state": ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
            "allowed": ALL_ROLE,
            "condition": "doc.custom_substitute_user == frappe.session.user",
        },
        {
            # AR: رفض البديل يعيد الطلب للموظف بدلاً من إنهائه.
            # EN: Substitute rejection returns the request to Draft for reselection.
            "state": ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            "action": ATTENDANCE_ACTION_REJECT,
            "next_state": ATTENDANCE_STATE_DRAFT,
            "allowed": ALL_ROLE,
            "condition": "doc.custom_substitute_user == frappe.session.user",
        },
        {
            # AR: المدير يستطيع الاعتماد فوراً أثناء انتظار البديل.
            # EN: The direct manager may approve immediately while substitute is pending.
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

    workflow_transitions.extend(get_hr_manager_override_transitions())
    workflow_transitions.extend(get_system_manager_workflow_transitions())

    for row in workflow_states:
        workflow.append(
            "states",
            {
                "state": row["state"],
                "doc_status": row["doc_status"],
                "allow_edit": row["allow_edit"],
                "update_field": row["update_field"],
                "update_value": row["update_value"],
            },
        )

    for row in workflow_transitions:
        transition = {
            "state": row["state"],
            "action": row["action"],
            "next_state": row["next_state"],
            "allowed": row["allowed"],
            "allow_self_approval": 1,
        }
        if row.get("condition"):
            transition["condition"] = row["condition"]
        workflow.append("transitions", transition)

    if existing_workflow_name:
        workflow.save(ignore_permissions=True)
    else:
        workflow.insert(ignore_permissions=True)

    # AR: تعطيل أي Workflow آخر على Attendance Request لمنع التضارب.
    # EN: Deactivate other Attendance Request workflows to prevent conflicts.
    other_workflows = frappe.get_all(
        "Workflow",
        filters={"document_type": ATTENDANCE_DOCTYPE},
        pluck="name",
    )
    for workflow_name in other_workflows:
        if workflow_name != workflow.name:
            frappe.db.set_value("Workflow", workflow_name, "is_active", 0)
