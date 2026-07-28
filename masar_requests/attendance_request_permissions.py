# ============================================================================
# AR: صلاحيات وتحقق وإشعارات طلب المهمة الرسمية
# EN: Official Duty permissions, validation, sharing, and notifications
# ============================================================================

from datetime import date, datetime, time, timedelta
from html import unescape
from html.parser import HTMLParser

import frappe
from frappe import _

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
HR_USER_ROLE = "HR User"
HR_MANAGER_ROLE = "HR Manager"
SYSTEM_MANAGER_ROLE = "System Manager"

ACTIVE_WORKFLOW_STATES = {
    ATTENDANCE_STATE_DRAFT,
    ATTENDANCE_STATE_WAITING_SUBSTITUTE,
    ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
    ATTENDANCE_STATE_WAITING_HR_MANAGER,
}

WORKFLOW_ACTIONS = {
    ATTENDANCE_ACTION_SEND_TO_SUBSTITUTE,
    ATTENDANCE_ACTION_SEND_TO_DIRECT_MANAGER,
    ATTENDANCE_ACTION_SUBSTITUTE_APPROVE,
    ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
    ATTENDANCE_ACTION_FINAL_APPROVE,
    ATTENDANCE_ACTION_REJECT,
}

# AR: بيانات الطلب لا تتغير بعد أول حفظ، باستثناء اختيار بديل جديد بعد رفض البديل.
# EN: Request data is immutable after first save, except substitute reselection after rejection.
LOCKED_REQUEST_FIELDS = (
    "employee",
    "from_date",
    "to_date",
    "reason",
    "half_day",
    "half_day_date",
    "include_holidays",
    "explanation",
    "shift",
    "shift_type",
    "custom_shift",
    "custom_mission_location",
    "custom_leaving_time",
    "custom_return_time",
    "custom_assignment_explanation",
    "custom_achievement_report",
    "custom_achievement_report_attachment",
    "custom_substitute_employee",
)


class _RichTextExtractor(HTMLParser):
    """AR: استخراج النص الظاهر من HTML. EN: Extract visible text from rich HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _rich_text_has_content(value):
    """AR: التحقق من أن المحرر يحتوي نصاً فعلياً. EN: Check rich text for visible content."""
    if not value:
        return False

    parser = _RichTextExtractor()
    try:
        parser.feed(str(value))
        visible_text = " ".join(parser.parts)
    except Exception:
        visible_text = str(value)

    return bool(unescape(visible_text).replace("\xa0", " ").strip())


# ============================================================================
# AR: الأدوار والصلاحيات
# EN: Roles and permissions
# ============================================================================


def _roles(user=None):
    """AR: جلب أدوار المستخدم. EN: Return user roles as a set."""
    return set(frappe.get_roles(user or frappe.session.user))


def is_system_administrator(user=None):
    """AR: Administrator أو System Manager. EN: Administrator or System Manager."""
    user = user or frappe.session.user
    return user == "Administrator" or SYSTEM_MANAGER_ROLE in _roles(user)


def is_hr_manager_or_admin(user=None):
    """AR: مستخدم مخول بالاعتماد النهائي. EN: User allowed to perform final approval."""
    user = user or frappe.session.user
    return is_system_administrator(user) or HR_MANAGER_ROLE in _roles(user)


def is_hr_read_only_user(user=None):
    """
    AR: تحديد حساب HR User غير الإداري؛ يستثنى طلبه الشخصي لاحقًا في فحص الصلاحية.
    EN: Identify a non-privileged HR User; personal requests are exempted later.
    """
    user = user or frappe.session.user
    roles = _roles(user)
    return (
        HR_USER_ROLE in roles
        and HR_MANAGER_ROLE not in roles
        and SYSTEM_MANAGER_ROLE not in roles
        and user != "Administrator"
    )


def _employee_user(employee):
    """AR: حساب المستخدم المرتبط بالموظف. EN: User linked to an Employee."""
    if not employee:
        return None
    return frappe.db.get_value("Employee", employee, "user_id")


def _applicant_user(doc):
    """AR: تحديد حساب مقدم الطلب. EN: Resolve the request applicant User."""
    return (
        doc.get("custom_applicant_user")
        or _employee_user(doc.get("employee"))
        or doc.get("owner")
    )


def _is_applicant(doc, user=None):
    """AR: هل المستخدم مقدم الطلب؟ EN: Is the user the request applicant?"""
    user = user or frappe.session.user
    return user in {_applicant_user(doc), doc.get("owner")}


def _is_substitute(doc, user=None):
    """AR: هل المستخدم هو البديل المختار؟ EN: Is the user the selected substitute?"""
    user = user or frappe.session.user
    return bool(user and user == doc.get("custom_substitute_user"))


def _is_direct_manager(doc, user=None):
    """AR: هل المستخدم هو المسؤول المباشر؟ EN: Is the user the direct manager?"""
    user = user or frappe.session.user
    return bool(user and user == doc.get("custom_direct_manager_user"))


def _is_related_user(doc, user):
    """AR: هل المستخدم طرف مرتبط بالطلب؟ EN: Is the user related to this request?"""
    return bool(
        doc.get("owner") == user
        or doc.get("custom_applicant_user") == user
        or doc.get("custom_substitute_user") == user
        or doc.get("custom_direct_manager_user") == user
        or _employee_user(doc.get("employee")) == user
    )


def attendance_request_query(user=None):
    """
    AR: HR Manager وHR User يشاهدون كل الطلبات؛ بقية المستخدمين يشاهدون المرتبط فقط.
    EN: HR Manager and HR User see all requests; others see related requests only.
    """
    user = user or frappe.session.user
    if is_hr_manager_or_admin(user) or is_hr_read_only_user(user):
        return None

    escaped_user = frappe.db.escape(user)
    return f"""(
        `tabAttendance Request`.`owner` = {escaped_user}
        OR `tabAttendance Request`.`custom_applicant_user` = {escaped_user}
        OR `tabAttendance Request`.`custom_substitute_user` = {escaped_user}
        OR `tabAttendance Request`.`custom_direct_manager_user` = {escaped_user}
        OR EXISTS (
            SELECT 1
              FROM `tabEmployee` applicant_employee
             WHERE applicant_employee.`name` = `tabAttendance Request`.`employee`
               AND applicant_employee.`user_id` = {escaped_user}
        )
    )"""


def attendance_request_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    """
    AR: HR User يعرض ويطبع طلبات الآخرين، ويتعامل مع طلبه الشخصي حسب المرحلة.
    EN: HR User reads/prints others' requests and handles a personal request by stage.
    """
    user = user or frappe.session.user
    ptype = permission_type or ptype or "read"

    # AR: فحص الإنشاء لا يعتمد على مستند موجود؛ تطبق صلاحيات الدور الطبيعية.
    # EN: Create permission has no existing document; defer to normal role permissions.
    if ptype == "create":
        return None

    # AR: HR User يبقى للعرض والطباعة في طلبات الآخرين فقط.
    # EN: HR User remains read/print-only for other users' requests only.
    if is_hr_read_only_user(user) and not _is_applicant(doc, user):
        return ptype in {"read", "print"}

    if is_hr_manager_or_admin(user):
        return True

    if ptype in {"read", "print"}:
        return _is_related_user(doc, user)

    if ptype == "write":
        state = doc.get("workflow_state") or ATTENDANCE_STATE_DRAFT
        if _is_applicant(doc, user) and state == ATTENDANCE_STATE_DRAFT:
            return True
        # AR: استثناء للطلبات القديمة ذات التقرير الفارغ فقط.
        # EN: Exception only for legacy active requests with an empty report.
        if (
            _is_applicant(doc, user)
            and state in ACTIVE_WORKFLOW_STATES
            and not _rich_text_has_content(doc.get("custom_achievement_report"))
        ):
            return True
        if _is_substitute(doc, user) and state == ATTENDANCE_STATE_WAITING_SUBSTITUTE:
            return True
        if _is_direct_manager(doc, user) and state in {
            ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
        }:
            return True
        return False

    if ptype in {"delete", "cancel", "amend", "submit", "share"}:
        return False

    return _is_related_user(doc, user)


# ============================================================================
# AR: الموظف والبيانات الأساسية
# EN: Employee and base request data
# ============================================================================


def _current_user_employee(user=None, required=True):
    """AR: جلب سجل الموظف النشط للمستخدم. EN: Resolve the user's active Employee record."""
    user = user or frappe.session.user
    employees = frappe.get_all(
        "Employee",
        filters={"user_id": user, "status": "Active"},
        fields=["name", "employee_name", "department", "company", "user_id"],
        order_by="modified desc",
        limit_page_length=2,
    )

    if not employees:
        if required:
            frappe.throw(
                _("No active Employee record is linked to the current user account.")
            )
        return None

    if len(employees) > 1:
        frappe.throw(
            _(
                "More than one active Employee record is linked to the current user. "
                "Please ask HR to keep only one active link."
            )
        )

    return frappe._dict(employees[0])


@frappe.whitelist()
def get_current_user_employee():
    """AR: API لتهيئة الموظف في الطلب الجديد. EN: API used to initialize a new request."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Please sign in before creating an attendance request."))
    employee = _current_user_employee(required=False)
    return employee or {}


def set_request_employee_from_session(doc):
    """
    AR: فرض موظف المستخدم عند الإنشاء فقط، وعدم تطبيقه على منفذي الموافقات.
    EN: Enforce the user's Employee only at creation, never on workflow approvers.
    """
    user = frappe.session.user

    if doc.is_new():
        if is_system_administrator(user):
            if not doc.get("employee") and user != "Administrator":
                employee = _current_user_employee(required=False)
                if employee:
                    doc.set("employee", employee.name)
        else:
            employee = _current_user_employee(required=True)
            if doc.get("employee") and doc.get("employee") != employee.name:
                frappe.throw(
                    _(
                        "You can create an attendance request only for your own Employee record."
                    ),
                    frappe.PermissionError,
                )
            doc.set("employee", employee.name)

    if not doc.get("employee"):
        return

    employee_data = frappe.db.get_value(
        "Employee",
        doc.get("employee"),
        ["employee_name", "department", "company", "user_id"],
        as_dict=True,
    )
    if not employee_data:
        frappe.throw(_("The selected Employee record does not exist."))

    if doc.meta.has_field("custom_applicant_user") and not doc.get("custom_applicant_user"):
        doc.set("custom_applicant_user", employee_data.user_id or doc.get("owner"))

    if doc.is_new():
        if doc.meta.has_field("employee_name"):
            doc.set("employee_name", employee_data.employee_name)
        if doc.meta.has_field("department"):
            doc.set("department", employee_data.department)
        if doc.meta.has_field("company") and employee_data.company:
            doc.set("company", employee_data.company)


# ============================================================================
# AR: المقارنة والقفل
# EN: Comparison and locking
# ============================================================================


def _is_empty_value(value):
    return value is None or value == ""


def _normalize_time_for_compare(value):
    """AR: توحيد قيم Time للمقارنة. EN: Normalize Time values before comparison."""
    if _is_empty_value(value):
        return None
    if isinstance(value, timedelta):
        return round(value.total_seconds(), 6)
    if isinstance(value, time):
        return (
            value.hour * 3600
            + value.minute * 60
            + value.second
            + value.microsecond / 1_000_000
        )

    text = str(value).strip()
    if not text:
        return None

    days = 0
    if "," in text and "day" in text:
        day_part, text = [part.strip() for part in text.split(",", 1)]
        try:
            days = int(day_part.split()[0])
        except (TypeError, ValueError, IndexError):
            days = 0

    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        return str(value)

    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2]) if len(parts) == 3 else 0.0
    except (TypeError, ValueError):
        return str(value)

    return sign * (days * 86400 + hours * 3600 + minutes * 60 + seconds)


def _normalize_field_value(field, value):
    """AR: توحيد التاريخ والوقت قبل المقارنة. EN: Normalize dates/times before comparison."""
    if _is_empty_value(value):
        return None

    fieldtype = field.fieldtype if field else None
    try:
        if fieldtype == "Date":
            if isinstance(value, datetime):
                value = value.date()
            if isinstance(value, date):
                return value.isoformat()
            return frappe.utils.getdate(value).isoformat()
        if fieldtype == "Datetime":
            parsed = frappe.utils.get_datetime(value)
            return parsed.replace(microsecond=0).isoformat(sep=" ")
        if fieldtype == "Time":
            return _normalize_time_for_compare(value)
        if fieldtype == "Check":
            return frappe.utils.cint(value)
        if fieldtype in {"Int", "Long Int"}:
            return int(value)
        if fieldtype in {"Float", "Currency", "Percent"}:
            return float(value)
    except (AttributeError, TypeError, ValueError, OverflowError):
        pass

    return value


def _same_field_value(doc, previous, fieldname):
    field = doc.meta.get_field(fieldname)
    return _normalize_field_value(field, previous.get(fieldname)) == _normalize_field_value(
        field, doc.get(fieldname)
    )


def _get_previous_doc(doc):
    """AR: النسخة السابقة للمستند. EN: Return the saved document snapshot."""
    previous = doc.get_doc_before_save()
    if previous:
        return previous
    if getattr(doc, "name", None) and not doc.is_new():
        return frappe.get_doc(doc.doctype, doc.name)
    return None


def _get_previous_workflow_state(doc):
    """AR: حالة سير العمل السابقة. EN: Return the previous workflow state."""
    flagged = getattr(doc.flags, "masar_previous_workflow_state", None)
    if flagged is not None:
        return flagged
    previous = _get_previous_doc(doc)
    return previous.get("workflow_state") if previous else None


def _can_reselect_substitute(doc, previous):
    """
    AR: السماح لمقدم الطلب بتغيير البديل فقط بعد رفض البديل وإعادة الطلب للمسودة.
    EN: Allow substitute change only after substitute rejection returned the request to Draft.
    """
    return bool(
        previous
        and previous.get("workflow_state") == ATTENDANCE_STATE_DRAFT
        and previous.get("custom_substitute_approval") == APPROVAL_REJECTED
        and _is_applicant(doc)
    )


def _can_complete_legacy_report(doc, previous, user=None):
    """
    AR:
        استثناء ترحيل ضيق للطلبات القديمة التي أنشئت قبل جعل التقرير مطلوباً.
        يسمح لمقدم الطلب بإكمال التقرير الفارغ مرة واحدة في مرحلة نشطة.

    EN:
        Narrow migration exception for requests created before the report became
        mandatory. The applicant may complete a previously empty report once.
    """
    user = user or frappe.session.user
    if not previous or not _is_applicant(previous, user):
        return False
    previous_state = previous.get("workflow_state") or ATTENDANCE_STATE_DRAFT
    return bool(
        previous_state in ACTIVE_WORKFLOW_STATES
        and not _rich_text_has_content(previous.get("custom_achievement_report"))
    )


def validate_locked_request_fields(doc):
    """AR: منع تعديل بيانات الطلب بعد أول حفظ. EN: Block request-data edits after first save."""
    previous = _get_previous_doc(doc)
    if not previous:
        return

    allowed_changes = set()
    if _can_reselect_substitute(doc, previous):
        allowed_changes.add("custom_substitute_employee")

    # AR: السماح فقط بإكمال تقرير قديم كان فارغاً قبل ترقية V13.
    # EN: Allow only a legacy empty report to be completed after the V13 upgrade.
    if _can_complete_legacy_report(doc, previous):
        allowed_changes.update(
            {"custom_achievement_report", "custom_achievement_report_attachment"}
        )

    changed_fields = [
        fieldname
        for fieldname in LOCKED_REQUEST_FIELDS
        if fieldname not in allowed_changes
        and doc.meta.has_field(fieldname)
        and not _same_field_value(doc, previous, fieldname)
    ]
    if not changed_fields:
        return

    labels = []
    for fieldname in changed_fields:
        field = doc.meta.get_field(fieldname)
        labels.append(_(field.label) if field and field.label else fieldname)

    frappe.throw(
        _(
            "This request is locked after creation. The following fields cannot be changed: {0}"
        ).format(", ".join(labels)),
        frappe.PermissionError,
    )


# ============================================================================
# AR: التحقق من بيانات المهمة
# EN: Official Duty data validation
# ============================================================================


def _validate_official_duty_fields(doc):
    """AR: التحقق من الحقول المطلوبة والتقرير. EN: Validate mandatory duty fields and report."""
    if doc.reason != "On Duty":
        return

    mandatory_fields = (
        "custom_assignment_explanation",
        "custom_mission_location",
        "custom_leaving_time",
        "custom_return_time",
    )
    for fieldname in mandatory_fields:
        if not doc.get(fieldname):
            field = doc.meta.get_field(fieldname)
            label = _(field.label) if field and field.label else fieldname
            frappe.throw(_("Please fill in the required field: {0}").format(label))

    if not _rich_text_has_content(doc.get("custom_achievement_report")):
        frappe.throw(_("Please enter the Achievement Report before saving the request."))

    leaving_seconds = _normalize_time_for_compare(doc.custom_leaving_time)
    return_seconds = _normalize_time_for_compare(doc.custom_return_time)
    if (
        isinstance(leaving_seconds, (int, float))
        and isinstance(return_seconds, (int, float))
        and leaving_seconds >= return_seconds
    ):
        frappe.throw(_("Return Time must be after Leaving Time."))


# ============================================================================
# AR: البديل والمسؤول المباشر
# EN: Substitute and direct manager
# ============================================================================


def set_substitute_user(doc):
    """AR: التحقق من البديل وتعبئة حسابه واسمه. EN: Validate and resolve substitute data."""
    substitute_employee = doc.get("custom_substitute_employee")
    if not substitute_employee:
        doc.set("custom_substitute_user", None)
        doc.set("custom_substitute_employee_name", "")
        return

    if substitute_employee == doc.get("employee"):
        frappe.throw(_("The substitute employee cannot be the same as the applicant."))

    applicant_data = frappe.db.get_value(
        "Employee",
        doc.get("employee"),
        ["department", "company"],
        as_dict=True,
    )
    substitute_data = frappe.db.get_value(
        "Employee",
        substitute_employee,
        ["employee_name", "user_id", "status", "department", "company"],
        as_dict=True,
    )

    if not substitute_data or substitute_data.status != "Active":
        frappe.throw(_("The substitute employee must be active in the system."))
    if not substitute_data.user_id:
        frappe.throw(_("The substitute employee does not have a linked user account."))

    if applicant_data:
        if substitute_data.department != applicant_data.department:
            frappe.throw(_("The substitute employee must belong to the same Department."))
        if (substitute_data.company or "") != (applicant_data.company or ""):
            frappe.throw(_("The substitute employee must belong to the same Company."))

    doc.set("custom_substitute_user", substitute_data.user_id)
    doc.set("custom_substitute_employee_name", substitute_data.employee_name)


def set_direct_manager_from_reports_to(doc):
    """AR: تعبئة المسؤول المباشر من reports_to. EN: Resolve direct manager from reports_to."""
    if not doc.get("employee"):
        return

    manager_employee = frappe.db.get_value("Employee", doc.get("employee"), "reports_to")
    if not manager_employee:
        frappe.throw(_("This employee does not have a direct manager assigned."))

    manager_user = frappe.db.get_value("Employee", manager_employee, "user_id")
    if not manager_user:
        frappe.throw(_("The direct manager does not have a linked user account."))

    doc.set("custom_direct_manager_employee", manager_employee)
    doc.set("custom_direct_manager_user", manager_user)


# ============================================================================
# AR: إجراءات سير العمل وتسجيل المعتمدين
# EN: Workflow actions and approval-audit capture
# ============================================================================


def _requested_workflow_action():
    """AR: جلب اسم الإجراء المرسل إلى Frappe. EN: Return the exact workflow action."""
    action = frappe.form_dict.get("action") if getattr(frappe, "form_dict", None) else None
    return action if action in WORKFLOW_ACTIONS else None


def _is_transition(action, expected, previous_state, state, from_states, to_state):
    """AR: مطابقة الإجراء أو الانتقال كحل احتياطي. EN: Match action or state transition fallback."""
    if action:
        return action == expected
    return previous_state in from_states and state == to_state


def _require_actor(condition, message):
    """AR: التحقق من منفذ الإجراء. EN: Enforce the workflow actor."""
    if not condition and not is_system_administrator():
        frappe.throw(_(message), frappe.PermissionError)


def _clear_substitute_selection(doc):
    """AR: تفريغ البديل المرفوض لإجبار إعادة الاختيار. EN: Clear rejected substitute for reselection."""
    doc.set("custom_substitute_employee", None)
    doc.set("custom_substitute_employee_name", "")
    doc.set("custom_substitute_user", None)
    doc.set("custom_substitute_approved_by", None)
    doc.set("custom_substitute_approved_on", None)


def sync_approval_status_fields(doc):
    """
    AR:
        تسجيل الموافقات الفعلية، ووضع Bypassed عند تجاوز مرحلة، وإعادة الطلب
        للمسودة عند رفض البديل مع تفريغ البديل السابق.

    EN:
        Capture actual approvals, mark skipped stages as Bypassed, and return
        substitute rejection to Draft while clearing the rejected substitute.
    """
    state = doc.get("workflow_state") or ATTENDANCE_STATE_DRAFT
    previous_state = _get_previous_workflow_state(doc)
    action = _requested_workflow_action()
    actor = frappe.session.user
    now = frappe.utils.now_datetime()
    has_substitute = bool(doc.get("custom_substitute_user"))

    # AR: رفض البديل يعيد الطلب للمسودة ولا يعتبر رفضاً نهائياً.
    # EN: Substitute rejection returns to Draft and is not a final rejection.
    # AR:
    #   رفض الموظف البديل ليس رفضاً نهائياً للطلب. نعالج الحالتين:
    #   1) المسار الجديد يعيد الحالة مباشرة إلى Draft.
    #   2) المسار القديم قد يرسلها خطأً إلى Rejected؛ نصححها على الخادم إلى Draft.
    # EN:
    #   A substitute rejection is not a final request rejection. Handle both:
    #   1) the current workflow returns directly to Draft; and
    #   2) a stale workflow may incorrectly target Rejected, which is corrected server-side.
    substitute_return = bool(
        previous_state == ATTENDANCE_STATE_WAITING_SUBSTITUTE
        and state in {ATTENDANCE_STATE_DRAFT, ATTENDANCE_STATE_REJECTED}
        and (action == ATTENDANCE_ACTION_REJECT or not action)
        and _is_substitute(doc, actor)
        and not is_hr_manager_or_admin(actor)
    )
    if substitute_return:
        doc.set("workflow_state", ATTENDANCE_STATE_DRAFT)
        if doc.meta.has_field("status"):
            doc.set("status", "Open")
        doc.docstatus = 0
        doc.set("custom_substitute_approval", APPROVAL_REJECTED)
        doc.set("custom_direct_manager_approval", APPROVAL_PENDING)
        _clear_substitute_selection(doc)
        return

    if state == ATTENDANCE_STATE_DRAFT:
        # AR: عند اختيار بديل جديد تتحول الحالة من Rejected إلى Pending.
        # EN: Selecting a new substitute changes the status from Rejected to Pending.
        doc.set(
            "custom_substitute_approval",
            APPROVAL_PENDING if has_substitute else "",
        )
        doc.set("custom_direct_manager_approval", APPROVAL_PENDING)
        if has_substitute:
            doc.set("custom_substitute_approved_by", None)
            doc.set("custom_substitute_approved_on", None)
        return

    if _is_transition(
        action,
        ATTENDANCE_ACTION_SUBSTITUTE_APPROVE,
        previous_state,
        state,
        {ATTENDANCE_STATE_WAITING_SUBSTITUTE},
        ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
    ):
        _require_actor(
            _is_substitute(doc, actor),
            "Only the selected substitute employee can approve at this stage.",
        )
        doc.set("custom_substitute_approval", APPROVAL_APPROVED)
        if not doc.get("custom_substitute_approved_by"):
            doc.set("custom_substitute_approved_by", actor)
        if not doc.get("custom_substitute_approved_on"):
            doc.set("custom_substitute_approved_on", now)
        doc.set("custom_direct_manager_approval", APPROVAL_PENDING)
        return

    if _is_transition(
        action,
        ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
        previous_state,
        state,
        {
            ATTENDANCE_STATE_WAITING_SUBSTITUTE,
            ATTENDANCE_STATE_WAITING_DIRECT_MANAGER,
        },
        ATTENDANCE_STATE_WAITING_HR_MANAGER,
    ):
        _require_actor(
            _is_direct_manager(doc, actor),
            "Only the direct manager can approve at this stage.",
        )
        doc.set("custom_direct_manager_approval", APPROVAL_APPROVED)
        if not doc.get("custom_direct_manager_approved_by"):
            doc.set("custom_direct_manager_approved_by", actor)
        if not doc.get("custom_direct_manager_approved_on"):
            doc.set("custom_direct_manager_approved_on", now)

        if has_substitute and doc.get("custom_substitute_approval") != APPROVAL_APPROVED:
            doc.set("custom_substitute_approval", APPROVAL_BYPASSED)
        elif not has_substitute:
            doc.set("custom_substitute_approval", "")
        return

    if _is_transition(
        action,
        ATTENDANCE_ACTION_FINAL_APPROVE,
        previous_state,
        state,
        ACTIVE_WORKFLOW_STATES,
        ATTENDANCE_STATE_APPROVED,
    ):
        _require_actor(
            is_hr_manager_or_admin(actor),
            "Only HR Manager or System Manager can perform final approval.",
        )
        if not doc.get("custom_hr_approved_by"):
            doc.set("custom_hr_approved_by", actor)
        if not doc.get("custom_hr_approved_on"):
            doc.set("custom_hr_approved_on", now)

        if has_substitute and doc.get("custom_substitute_approval") != APPROVAL_APPROVED:
            doc.set("custom_substitute_approval", APPROVAL_BYPASSED)
        elif not has_substitute:
            doc.set("custom_substitute_approval", "")

        if doc.get("custom_direct_manager_approval") != APPROVAL_APPROVED:
            doc.set("custom_direct_manager_approval", APPROVAL_BYPASSED)
        return

    # AR: الرفض النهائي من المدير أو الموارد البشرية.
    # EN: Final rejection by direct manager or HR.
    if state == ATTENDANCE_STATE_REJECTED and previous_state in ACTIVE_WORKFLOW_STATES:
        if _is_direct_manager(doc, actor) and not is_hr_manager_or_admin(actor):
            doc.set("custom_direct_manager_approval", APPROVAL_REJECTED)
            if has_substitute and doc.get("custom_substitute_approval") != APPROVAL_APPROVED:
                doc.set("custom_substitute_approval", APPROVAL_BYPASSED)
        elif is_hr_manager_or_admin(actor):
            if has_substitute and doc.get("custom_substitute_approval") != APPROVAL_APPROVED:
                doc.set("custom_substitute_approval", APPROVAL_BYPASSED)
            if doc.get("custom_direct_manager_approval") != APPROVAL_APPROVED:
                doc.set("custom_direct_manager_approval", APPROVAL_BYPASSED)


def validate_attendance_request(doc, method=None):
    """
    AR: نقطة التحقق الرئيسية قبل الحفظ أو تنفيذ إجراء سير العمل.
    EN: Main server-side validation before save or workflow action.
    """
    # AR: منع تعديل طلبات الآخرين فقط؛ الطلب الشخصي يتبع المسار الطبيعي.
    # EN: Block edits to other users' requests only; personal requests follow normal workflow.
    if is_hr_read_only_user() and not _is_applicant(doc):
        frappe.throw(
            _(
                "HR User is allowed to view and print other employees' requests only. "
                "You may create and process your own request according to the normal workflow."
            ),
            frappe.PermissionError,
        )

    previous_state = _get_previous_workflow_state(doc)
    doc.flags.masar_previous_workflow_state = previous_state

    set_request_employee_from_session(doc)
    validate_locked_request_fields(doc)

    if doc.reason != "On Duty":
        return

    _validate_official_duty_fields(doc)

    # AR: البديل يمكن تغييره فقط في مسودة أعيدت بعد رفضه؛ القفل يتحقق قبل هذه النقطة.
    # EN: Substitute may change only in a returned Draft; locking is enforced above.
    set_substitute_user(doc)

    if doc.is_new() or not doc.get("custom_direct_manager_user"):
        set_direct_manager_from_reports_to(doc)

    sync_approval_status_fields(doc)


def before_submit_attendance_request(doc, method=None):
    """AR: ضمان تسجيل الاعتماد النهائي قبل submit. EN: Ensure final approver is captured before submit."""
    sync_approval_status_fields(doc)


# ============================================================================
# AR: المشاركات
# EN: Document sharing
# ============================================================================


def _grant_docshare(doc, user, write=0):
    """AR: إنشاء أو تحديث مشاركة المستند. EN: Create or update a document share."""
    if not user or user == "Administrator" or not frappe.db.exists("User", user):
        return

    existing_share = frappe.db.get_value(
        "DocShare",
        {
            "share_doctype": doc.doctype,
            "share_name": doc.name,
            "user": user,
        },
        "name",
    )
    values = {"read": 1, "write": 1 if write else 0, "submit": 0}

    if existing_share:
        frappe.db.set_value("DocShare", existing_share, values, update_modified=False)
        return

    share = frappe.new_doc("DocShare")
    share.update(
        {
            "share_doctype": doc.doctype,
            "share_name": doc.name,
            "user": user,
            "read": 1,
            "write": 1 if write else 0,
            "submit": 0,
            "share": 0,
        }
    )
    share.flags.ignore_share_permission = True
    share.insert(ignore_permissions=True)


def sync_attendance_request_shares(doc, method=None):
    """
    AR: مشاركة الطلب فوراً مع مقدم الطلب والبديل والمسؤول المباشر.
    EN: Share the request immediately with applicant, substitute, and direct manager.
    """
    if doc.reason != "On Duty" or not doc.name:
        return

    users = {
        _applicant_user(doc),
        doc.get("owner"),
        doc.get("custom_substitute_user"),
        doc.get("custom_direct_manager_user"),
    }
    users.discard(None)
    users.discard("")

    # AR: إزالة مشاركة البديل القديم بعد الرفض أو إعادة الاختيار.
    # EN: Remove stale participant shares after rejection or reselection.
    previous = doc.get_doc_before_save()
    if previous:
        previous_users = {
            _applicant_user(previous),
            previous.get("owner"),
            previous.get("custom_substitute_user"),
            previous.get("custom_direct_manager_user"),
        }
        for stale_user in previous_users - users:
            if stale_user:
                frappe.db.delete(
                    "DocShare",
                    {
                        "share_doctype": doc.doctype,
                        "share_name": doc.name,
                        "user": stale_user,
                    },
                )

    for user in users:
        # AR: الصلاحية الفعلية تُحسم أيضاً عبر has_permission حسب المرحلة.
        # EN: Effective write access is also constrained by has_permission per state.
        _grant_docshare(doc, user, write=1)


def resync_all_attendance_request_shares():
    """AR: إعادة مزامنة المشاركات القديمة. EN: Re-synchronize shares on existing requests."""
    names = frappe.get_all(ATTENDANCE_DOCTYPE, pluck="name")
    for name in names:
        sync_attendance_request_shares(frappe.get_doc(ATTENDANCE_DOCTYPE, name))
    frappe.db.commit()
    return len(names)


# ============================================================================
# AR: الإشعارات
# EN: Notifications
# ============================================================================


def get_users_with_role_safe(role):
    """AR: المستخدمون المفعّلون لدور معين. EN: Enabled users assigned to a role."""
    users = frappe.get_all(
        "Has Role",
        filters={"role": role, "parenttype": "User"},
        pluck="parent",
    )
    return [
        user
        for user in users
        if user and frappe.db.get_value("User", user, "enabled")
    ]


def _notification_already_exists(doc, target, subject):
    """AR: منع تكرار نفس الإشعار للمستخدم. EN: Prevent duplicate user notifications."""
    return bool(
        frappe.db.exists(
            "Notification Log",
            {
                "for_user": target,
                "document_type": ATTENDANCE_DOCTYPE,
                "document_name": doc.name,
                "subject": subject,
            },
        )
    )


def _translate_notification_for_user(target, source, *args):
    """
    AR:
        ترجمة نص الإشعار وفق لغة المستخدم المستهدف، لا وفق لغة المستخدم
        الذي نفذ إجراء سير العمل.

    EN:
        Translate the notification using the target user's language instead
        of the workflow actor's current session language.
    """
    language = (
        frappe.get_cached_value("User", target, "language")
        or getattr(frappe.local, "lang", None)
        or "en"
    )
    return _(source, lang=language).format(*args)


def _create_notification(doc, target, source, *args):
    """
    AR: إنشاء إشعار مترجم وغير مكرر. EN: Create a translated, de-duplicated notification.
    """
    if (
        not target
        or target == "Administrator"
        or target == frappe.session.user
        or not frappe.db.exists("User", target)
    ):
        return

    subject = _translate_notification_for_user(target, source, *args)
    if _notification_already_exists(doc, target, subject):
        return

    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "subject": subject,
            "for_user": target,
            "document_type": ATTENDANCE_DOCTYPE,
            "document_name": doc.name,
            "type": "Alert",
        }
    ).insert(ignore_permissions=True)


def _applicant_name(doc):
    return (
        doc.get("employee_name")
        or frappe.db.get_value("Employee", doc.get("employee"), "employee_name")
        or doc.get("employee")
        or doc.get("owner")
    )


def send_attendance_workflow_notifications(doc):
    """
    AR: إرسال الإشعارات حسب المرحلة، مع إشعار المدير فور انتظار البديل.
    EN: Send stage notifications, including immediate manager notice during substitute stage.
    """
    state = doc.get("workflow_state")
    previous_state = _get_previous_workflow_state(doc)
    if not state or state == previous_state or doc.docstatus >= 2:
        return

    applicant_name = _applicant_name(doc)

    if (
        state == ATTENDANCE_STATE_DRAFT
        and previous_state == ATTENDANCE_STATE_WAITING_SUBSTITUTE
        and doc.get("custom_substitute_approval") == APPROVAL_REJECTED
    ):
        source = (
            "↩️ Official Duty Returned: The substitute rejected request {0}. "
            "Please select another substitute or send it directly to your manager."
        )
        for target in {_applicant_user(doc), doc.get("owner")}:
            _create_notification(doc, target, source, doc.name)
        return

    if state == ATTENDANCE_STATE_WAITING_SUBSTITUTE:
        substitute_source = (
            "⚠️ Official Duty Action Required: {0} selected you as substitute for request {1}."
        )
        _create_notification(
            doc,
            doc.get("custom_substitute_user"),
            substitute_source,
            applicant_name,
            doc.name,
        )

        manager_source = (
            "⚠️ Official Duty Available: Request {0} from {1} is waiting for the substitute. "
            "You may approve it now or wait for the substitute decision."
        )
        _create_notification(
            doc,
            doc.get("custom_direct_manager_user"),
            manager_source,
            doc.name,
            applicant_name,
        )
        return

    if state == ATTENDANCE_STATE_WAITING_DIRECT_MANAGER:
        source = (
            "⚠️ Official Duty Action Required: Request {0} from {1} is awaiting your approval."
        )
        _create_notification(
            doc,
            doc.get("custom_direct_manager_user"),
            source,
            doc.name,
            applicant_name,
        )
        return

    if state == ATTENDANCE_STATE_WAITING_HR_MANAGER:
        source = (
            "⚠️ Official Duty Action Required: Request {0} from {1} reached HR for final approval."
        )
        for target in get_users_with_role_safe(HR_MANAGER_ROLE):
            _create_notification(doc, target, source, doc.name, applicant_name)
        return

    if state == ATTENDANCE_STATE_APPROVED:
        source = "✅ Official Duty Approved: Request {0} has been finally approved."
        for target in {_applicant_user(doc), doc.get("owner")}:
            _create_notification(doc, target, source, doc.name)
        return

    if state == ATTENDANCE_STATE_REJECTED:
        source = "❌ Official Duty Rejected: Request {0} has been rejected."
        for target in {_applicant_user(doc), doc.get("owner")}:
            _create_notification(doc, target, source, doc.name)



# ============================================================================
# AR: أحداث المستند
# EN: Document event handlers
# ============================================================================


def on_update_attendance_request(doc, method=None):
    """
    AR: مزامنة المشاركات والإشعارات بعد تحديث الطلب.
    EN: Synchronize shares and notifications after a request update.
    """
    sync_attendance_request_shares(doc)
    send_attendance_workflow_notifications(doc)


def on_submit_attendance_request(doc, method=None):
    """
    AR: مزامنة المشاركات والإشعارات بعد الاعتماد النهائي.
    EN: Synchronize shares and notifications after final submission.
    """
    sync_attendance_request_shares(doc)
    send_attendance_workflow_notifications(doc)
