# ======================================================================
# AR: صلاحيات طلب الإجازة والمشاركة التلقائية - تطبيق Masar Requests
# EN: Leave Application permissions and automatic sharing - Masar Requests
# ======================================================================

import frappe
from frappe import _
from frappe import share as frappe_share

from masar_requests.constants import (
    LEAVE_ACTION_DIRECT_MANAGER_APPROVE as ACTION_DIRECT_MANAGER_APPROVE,
    LEAVE_ACTION_FINAL_APPROVE as ACTION_FINAL_APPROVE,
    LEAVE_ACTION_REJECT as ACTION_REJECT,
    LEAVE_ACTION_SUBSTITUTE_APPROVE as ACTION_SUBSTITUTE_APPROVE,
    LEAVE_STATE_APPROVED as STATE_APPROVED,
    LEAVE_STATE_DRAFT as STATE_DRAFT,
    LEAVE_STATE_REJECTED as STATE_REJECTED,
    LEAVE_STATE_WAITING_DIRECT_MANAGER as STATE_WAITING_DIRECT_MANAGER,
    LEAVE_STATE_WAITING_HR_MANAGER as STATE_WAITING_HR_MANAGER,
    LEAVE_STATE_WAITING_SUBSTITUTE as STATE_WAITING_SUBSTITUTE,
)
from masar_requests.hr_user_read_only import is_hr_user_read_only


# ======================================================================
# AR: أسماء الحقول المخصصة في طلب الإجازة
# EN: Custom field names in Leave Application
# ======================================================================

SUBSTITUTE_EMPLOYEE_FIELD = "custom_substitute_employee"
SUBSTITUTE_EMPLOYEE_NAME_FIELD = "custom_substitute_employee_name"
SUBSTITUTE_USER_FIELD = "custom_substitute_user"
SUBSTITUTE_APPROVAL_FIELD = "custom_substitute_approval"

DIRECT_MANAGER_EMPLOYEE_FIELD = "custom_direct_manager_employee"
DIRECT_MANAGER_EMPLOYEE_NAME_FIELD = "custom_direct_manager_employee_name"
DIRECT_MANAGER_USER_FIELD = "custom_direct_manager_user"
DIRECT_MANAGER_APPROVAL_FIELD = "custom_direct_manager_approval"

DIRECT_MANAGER_SECRETARY_EMPLOYEE_FIELD = "custom_direct_manager_secretary_employee"
DIRECT_MANAGER_SECRETARY_NAME_FIELD = "custom_direct_manager_secretary_name"
DIRECT_MANAGER_SECRETARY_USER_FIELD = "custom_direct_manager_secretary_user"


# ======================================================================
# AR: حالات سير العمل - يجب أن تطابق الـ Workflow حرفياً
# EN: Workflow states - must exactly match the Workflow configuration
# ======================================================================

# AR: الحالات مستوردة من constants.py / EN: States are imported from constants.py.


# ======================================================================
# AR: حالات الموافقة المخزنة داخل حقول طلب الإجازة
# EN: Approval statuses stored inside Leave Application fields
# ======================================================================

APPROVAL_PENDING = "Pending"
APPROVAL_APPROVED = "Approved"
APPROVAL_REJECTED = "Rejected"
APPROVAL_BYPASSED = "Bypassed"


# ======================================================================
# AR: أسماء إجراءات سير العمل
# EN: Workflow action names
# ======================================================================

# AR: الإجراءات مستوردة من constants.py / EN: Actions are imported from constants.py.


# ======================================================================
# AR: المستخدمون والأدوار التي تمتلك صلاحية كاملة
# EN: Users and roles with unrestricted permissions
# ======================================================================

ADMIN_USERS = {"Administrator"}
ADMIN_ROLES = {"System Manager"}


# ======================================================================
# AR: الحقول التي يتم قراءتها من النسخة المحفوظة لمنع التلاعب بالصلاحيات
# EN: Fields read from the saved document to prevent permission escalation
# ======================================================================

PERMISSION_SNAPSHOT_FIELDS = [
    "name",
    "owner",
    "employee",
    "workflow_state",
    "docstatus",
    SUBSTITUTE_EMPLOYEE_FIELD,
    SUBSTITUTE_USER_FIELD,
    DIRECT_MANAGER_EMPLOYEE_FIELD,
    DIRECT_MANAGER_USER_FIELD,
    DIRECT_MANAGER_SECRETARY_EMPLOYEE_FIELD,
    DIRECT_MANAGER_SECRETARY_USER_FIELD,
]


# ======================================================================
# AR: التحقق من صلاحية Administrator أو System Manager
# EN: Check whether the user is Administrator or System Manager
# ======================================================================

def is_full_admin_user(user=None):
    # AR: التحقق من أن المستخدم هو Administrator أو يحمل دور مدير النظام.
    # EN: Check whether the user is Administrator or has the System Manager role.
    user = user or frappe.session.user

    if user in ADMIN_USERS:
        return True

    try:
        return bool(set(frappe.get_roles(user)) & ADMIN_ROLES)
    except Exception:
        return False


# ======================================================================
# AR: التحقق من امتلاك المستخدم لدور HR Manager
# EN: Check whether the user has the HR Manager role
# ======================================================================

def is_hr_manager_user(user=None):
    # AR: التحقق من أن المستخدم يحمل دور مدير الموارد البشرية.
    # EN: Check whether the user has the HR Manager role.
    user = user or frappe.session.user

    try:
        return "HR Manager" in frappe.get_roles(user)
    except Exception:
        return False


# ======================================================================
# AR: التحقق من أن المستخدم لديه صلاحية غير مقيدة على طلبات الإجازة
# EN: Check whether the user has unrestricted Leave Application access
# ======================================================================

def is_unrestricted_leave_user(user=None):
    # AR: التحقق من امتلاك المستخدم وصولًا غير مقيد إلى طلبات الإجازة.
    # EN: Check whether the user has unrestricted Leave Application access.
    user = user or frappe.session.user
    return is_full_admin_user(user) or is_hr_manager_user(user)


# Allow direct manager to view employee leave balance
# السماح للمدير المباشر برؤية رصيد إجازة الموظف

def can_access_employee_leave_data(employee, user=None):
    user = user or frappe.session.user

    # Employee himself
    # الموظف نفسه
    if frappe.db.get_value("Employee", employee, "user_id") == user:
        return True

    # HR / System administrators
    # مسؤولو النظام والموارد البشرية
    roles = frappe.get_roles(user)

    if "HR Manager" in roles or "System Manager" in roles:
        return True

    # Direct manager through reports_to
    # المدير المباشر عن طريق reports_to
    employee_manager = frappe.db.get_value(
        "Employee",
        employee,
        "reports_to"
    )

    if employee_manager:
        manager_user = frappe.db.get_value(
            "Employee",
            employee_manager,
            "user_id"
        )

        if manager_user == user:
            return True

    return False


# ======================================================================
# AR: جلب User المرتبط بسجل الموظف
# EN: Get the User ID linked to an Employee record
# ======================================================================

def _employee_user(employee):
    # AR: جلب حساب المستخدم المرتبط بسجل الموظف.
    # EN: Return the User account linked to an Employee.
    if not employee:
        return None

    return frappe.get_cached_value("Employee", employee, "user_id")


# ======================================================================
# AR: جلب مستخدم المدير المباشر من حقل reports_to
# EN: Get direct manager user from the reports_to field
# ======================================================================

def _employee_direct_manager_user(employee):
    # AR: جلب حساب المدير المباشر للموظف من حقل reports_to.
    # EN: Return the direct manager User resolved through reports_to.
    if not employee:
        return None

    manager_employee = frappe.get_cached_value(
        "Employee",
        employee,
        "reports_to",
    )

    if not manager_employee:
        return None

    return frappe.get_cached_value(
        "Employee",
        manager_employee,
        "user_id",
    )


# ======================================================================
# AR: جلب مستخدم سكرتير الموظف نفسه
# EN: Get the user of the employee's own secretary
# ======================================================================

def _employee_own_secretary_user(employee):
    # AR: جلب حساب السكرتير المرتبط بالموظف.
    # EN: Return the secretary User linked to an Employee.
    if not employee:
        return None

    secretary_employee = frappe.get_cached_value(
        "Employee",
        employee,
        "custom_secretary_employee",
    )

    if not secretary_employee:
        return None

    return frappe.get_cached_value(
        "Employee",
        secretary_employee,
        "user_id",
    )


# ======================================================================
# AR: جلب النسخة المحفوظة من المستند قبل التعديل
# EN: Get the saved document snapshot before changes
# ======================================================================

def _permission_snapshot(doc):
    # AR: جلب النسخة المحفوظة من المستند لاستخدامها في فحص الصلاحيات.
    # EN: Load the saved document snapshot for permission checks.
    before_save = getattr(doc, "_doc_before_save", None)

    if before_save:
        return before_save

    if getattr(doc, "name", None) and not doc.is_new():
        values = frappe.db.get_value(
            doc.doctype,
            doc.name,
            PERMISSION_SNAPSHOT_FIELDS,
            as_dict=True,
        )

        if values:
            values.doctype = doc.doctype
            return values

    return doc


# ======================================================================
# AR: تحديد علاقة المستخدم بالطلب
# EN: Determine the user's relationship to the leave request
# ======================================================================

def _relation_flags(doc, user):
    # AR: تحديد علاقة المستخدم بطلب الإجازة الحالي.
    # EN: Determine how the user is related to the current leave request.
    applicant_user = _employee_user(doc.get("employee"))

    manager_user = _employee_direct_manager_user(
        doc.get("employee")
    )

    own_secretary_user = _employee_own_secretary_user(
        doc.get("employee")
    )

    return frappe._dict(
        applicant=(
            doc.get("owner") == user
            or applicant_user == user
        ),
        substitute=(
            doc.get(SUBSTITUTE_USER_FIELD) == user
        ),
        direct_manager=(
            doc.get(DIRECT_MANAGER_USER_FIELD) == user
            or manager_user == user
        ),
        secretary=(
            doc.get(DIRECT_MANAGER_SECRETARY_USER_FIELD) == user
            or own_secretary_user == user
        ),
    )


# ======================================================================
# AR: التحقق من أن المستخدم سكرتير فقط وليس له دور آخر في الطلب
# EN: Check whether the user is secretary-only with no other request role
# ======================================================================

def _is_secretary_only(doc, user):
    # AR: التحقق من أن المستخدم سكرتير فقط ولا يملك دورًا آخر في الطلب.
    # EN: Check whether the user is only a secretary for this request.
    relation = _relation_flags(doc, user)

    return bool(
        relation.secretary
        and not relation.applicant
        and not relation.substitute
        and not relation.direct_manager
    )


# ======================================================================
# AR: تحديد صلاحية الكتابة حسب المرحلة وعلاقة المستخدم بالطلب
# EN: Determine write permission based on workflow stage and relation
# ======================================================================

def _can_write_leave(doc, user):
    # AR: تحديد إمكانية تعديل طلب الإجازة حسب المستخدم ومرحلة سير العمل.
    # EN: Determine write access from the user relation and workflow state.
    if is_unrestricted_leave_user(user):
        return True

    relation = _relation_flags(doc, user)
    state = doc.get("workflow_state") or STATE_DRAFT

    # AR: مقدم الطلب يعدل فقط في المسودة.
    # EN: Applicant can edit only in Draft.
    if relation.applicant and state == STATE_DRAFT:
        return True

    # AR: البديل يستطيع التعديل في مرحلة انتظار البديل فقط.
    # EN: Substitute can edit only during substitute stage.
    if relation.substitute and state == STATE_WAITING_SUBSTITUTE:
        return True

    # AR: المدير المباشر يستطيع الإجراء في مرحلته أو أثناء انتظار البديل.
    # EN: Direct manager can act in manager stage or substitute stage.
    if relation.direct_manager and state in {
        STATE_WAITING_SUBSTITUTE,
        STATE_WAITING_DIRECT_MANAGER,
    }:
        return True

    return False


# ======================================================================
# AR: البحث عن موظفين بدلاء من نفس إدارة مقدم الطلب
# EN: Search substitute employees from the applicant's department
# ======================================================================

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_same_department_substitute_employees(
    doctype, txt, searchfield, start, page_len, filters
):
    """
    AR:
        إرجاع الموظفين النشطين في نفس إدارة الموظف مقدم الطلب فقط،
        مع استبعاد مقدم الطلب والموظفين غير المرتبطين بحساب مستخدم.

    EN:
        Return active employees from the applicant's department only,
        excluding the applicant and employees without a linked User.
    """
    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    employee = filters.get("employee")

    if not employee:
        return []

    if not can_access_employee_leave_data(employee):
        frappe.throw(
            _("You are not allowed to search substitutes for this employee."),
            frappe.PermissionError,
        )

    applicant = frappe.db.get_value(
        "Employee",
        employee,
        ["department", "company"],
        as_dict=True,
    )

    if not applicant or not applicant.department:
        return []

    values = {
        "employee": employee,
        "department": applicant.department,
        "company": applicant.company or "",
        "txt": f"%{txt or ''}%",
        "start": int(start or 0),
        "page_len": int(page_len or 20),
    }

    return frappe.db.sql(
        """
        SELECT
            employee.name,
            employee.employee_name,
            employee.department
        FROM `tabEmployee` employee
        WHERE employee.status = 'Active'
          AND employee.department = %(department)s
          AND employee.name != %(employee)s
          AND COALESCE(employee.user_id, '') != ''
          AND (%(company)s = '' OR employee.company = %(company)s)
          AND (
                employee.name LIKE %(txt)s
                OR employee.employee_name LIKE %(txt)s
          )
        ORDER BY employee.employee_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )


# ======================================================================
# AR: التحقق الخادمي عند حفظ طلب الإجازة
# EN: Server-side validation when saving Leave Application
# ======================================================================

def validate_leave_application(doc, method=None):
    # AR: التحقق من صلاحيات وبيانات طلب الإجازة قبل الحفظ.
    # EN: Validate leave permissions and participant data before saving.
    user = frappe.session.user
    stored_doc = _permission_snapshot(doc)

    # AR: HR User للعرض والطباعة في طلبات الآخرين، ويعامل كموظف في طلبه الشخصي.
    # EN: HR User is read/print-only for others, and acts as an employee on a personal request.
    if is_hr_user_read_only(user) and not _relation_flags(stored_doc, user).applicant:
        frappe.throw(
            _(
                "HR User is allowed to view and print other employees' requests only. "
                "You may create and process your own request according to the normal workflow."
            ),
            frappe.PermissionError,
        )

    # AR: السكرتير فقط يستطيع العرض والطباعة ولا يستطيع التعديل.
    # EN: Secretary-only user can view and print but cannot modify.
    if (
        not is_unrestricted_leave_user(user)
        and _is_secretary_only(stored_doc, user)
    ):
        frappe.throw(
            _(
                "You are allowed to view and print this leave application only. "
                "You cannot approve, reject, or modify it."
            ),
            frappe.PermissionError,
        )

    set_substitute_user(doc)
    set_direct_manager_from_reports_to(doc)
    sync_leave_application_display_names(doc)
    sync_approval_status_fields(doc)


# ======================================================================
# AR: جلب مستخدم واسم الموظف البديل
# EN: Load substitute user and substitute employee name
# ======================================================================

def set_substitute_user(doc):
    # AR: تعبئة بيانات المستخدم والاسم للموظف البديل والتحقق منها.
    # EN: Resolve and validate the substitute Employee and User data.
    substitute_employee = doc.get(SUBSTITUTE_EMPLOYEE_FIELD)

    if not substitute_employee:
        doc.set(SUBSTITUTE_USER_FIELD, None)

        if doc.meta.has_field(SUBSTITUTE_EMPLOYEE_NAME_FIELD):
            doc.set(SUBSTITUTE_EMPLOYEE_NAME_FIELD, None)

        return

    if substitute_employee == doc.get("employee"):
        frappe.throw(
            _("The substitute employee cannot be the same as the leave applicant.")
        )

    # AR: جلب إدارة مقدم الطلب للتحقق من أن البديل من الإدارة نفسها.
    # EN: Load the applicant's department to validate the substitute.
    applicant_data = frappe.db.get_value(
        "Employee",
        doc.get("employee"),
        ["department", "company"],
        as_dict=True,
    )

    if not applicant_data or not applicant_data.department:
        frappe.throw(
            _("The employee {0} does not have a Department set.").format(
                doc.get("employee")
            )
        )

    substitute_data = frappe.db.get_value(
        "Employee",
        substitute_employee,
        ["user_id", "employee_name", "department", "company", "status"],
        as_dict=True,
    )

    if not substitute_data:
        frappe.throw(_("The selected substitute employee does not exist."))

    if substitute_data.status != "Active":
        frappe.throw(_("The substitute employee must be active."))

    if substitute_data.department != applicant_data.department:
        frappe.throw(
            _(
                "The substitute employee must belong to the same Department as the leave applicant."
            )
        )

    if (applicant_data.company or "") != (substitute_data.company or ""):
        frappe.throw(
            _(
                "The substitute employee must belong to the same Company as the leave applicant."
            )
        )

    if not substitute_data.user_id:
        frappe.throw(
            _("The substitute employee {0} does not have a linked User ID.").format(
                substitute_employee
            )
        )

    doc.set(SUBSTITUTE_USER_FIELD, substitute_data.user_id)

    if doc.meta.has_field(SUBSTITUTE_EMPLOYEE_NAME_FIELD):
        doc.set(
            SUBSTITUTE_EMPLOYEE_NAME_FIELD,
            substitute_data.employee_name,
        )


# ======================================================================
# AR: جلب المدير المباشر وسكرتيره من سجل Employee
# EN: Load direct manager and manager secretary from Employee record
# ======================================================================

def set_direct_manager_from_reports_to(doc):
    # AR: تعبئة بيانات المدير المباشر وسكرتيره اعتمادًا على reports_to.
    # EN: Resolve the direct manager and secretary through reports_to.
    if not doc.get("employee"):
        return

    manager_employee = frappe.db.get_value(
        "Employee",
        doc.get("employee"),
        "reports_to",
    )

    if not manager_employee:
        frappe.throw(
            _("The employee {0} does not have a direct manager set.").format(
                doc.get("employee")
            )
        )

    manager_data = frappe.db.get_value(
        "Employee",
        manager_employee,
        ["user_id", "employee_name", "custom_secretary_employee"],
        as_dict=True,
    )

    if not manager_data or not manager_data.user_id:
        frappe.throw(
            _("The direct manager {0} does not have a linked User ID.").format(
                manager_employee
            )
        )

    doc.set(DIRECT_MANAGER_EMPLOYEE_FIELD, manager_employee)
    doc.set(DIRECT_MANAGER_USER_FIELD, manager_data.user_id)

    if doc.meta.has_field(DIRECT_MANAGER_EMPLOYEE_NAME_FIELD):
        doc.set(
            DIRECT_MANAGER_EMPLOYEE_NAME_FIELD,
            manager_data.employee_name,
        )

    secretary_employee = manager_data.custom_secretary_employee

    if not secretary_employee:
        doc.set(DIRECT_MANAGER_SECRETARY_EMPLOYEE_FIELD, None)
        doc.set(DIRECT_MANAGER_SECRETARY_USER_FIELD, None)

        if doc.meta.has_field(DIRECT_MANAGER_SECRETARY_NAME_FIELD):
            doc.set(DIRECT_MANAGER_SECRETARY_NAME_FIELD, None)

        return

    secretary_data = frappe.db.get_value(
        "Employee",
        secretary_employee,
        ["user_id", "employee_name"],
        as_dict=True,
    )

    doc.set(
        DIRECT_MANAGER_SECRETARY_EMPLOYEE_FIELD,
        secretary_employee,
    )

    doc.set(
        DIRECT_MANAGER_SECRETARY_USER_FIELD,
        secretary_data.user_id if secretary_data else None,
    )

    if doc.meta.has_field(DIRECT_MANAGER_SECRETARY_NAME_FIELD):
        doc.set(
            DIRECT_MANAGER_SECRETARY_NAME_FIELD,
            secretary_data.employee_name if secretary_data else None,
        )


# ======================================================================
# AR: تخزين الأسماء المقروءة بدلاً من أرقام الموظفين
# EN: Store readable names instead of Employee IDs
# ======================================================================

def sync_leave_application_display_names(doc):
    # AR: مزامنة أسماء الأطراف الظاهرة داخل طلب الإجازة.
    # EN: Synchronize participant display names on the leave request.
    def set_if_field(fieldname, value):
        # AR: تعيين قيمة الحقل عند وجوده في نموذج طلب الإجازة.
        # EN: Set a field value only when the field exists.
        if doc.meta.has_field(fieldname):
            doc.set(fieldname, value)

    if doc.get("employee"):
        set_if_field(
            "employee_name",
            frappe.db.get_value(
                "Employee",
                doc.get("employee"),
                "employee_name",
            ),
        )

    if doc.get(SUBSTITUTE_EMPLOYEE_FIELD):
        set_if_field(
            SUBSTITUTE_EMPLOYEE_NAME_FIELD,
            frappe.db.get_value(
                "Employee",
                doc.get(SUBSTITUTE_EMPLOYEE_FIELD),
                "employee_name",
            ),
        )

    if doc.get(DIRECT_MANAGER_EMPLOYEE_FIELD):
        set_if_field(
            DIRECT_MANAGER_EMPLOYEE_NAME_FIELD,
            frappe.db.get_value(
                "Employee",
                doc.get(DIRECT_MANAGER_EMPLOYEE_FIELD),
                "employee_name",
            ),
        )

    if doc.get(DIRECT_MANAGER_SECRETARY_EMPLOYEE_FIELD):
        set_if_field(
            DIRECT_MANAGER_SECRETARY_NAME_FIELD,
            frappe.db.get_value(
                "Employee",
                doc.get(DIRECT_MANAGER_SECRETARY_EMPLOYEE_FIELD),
                "employee_name",
            ),
        )

    if doc.get("leave_approver"):
        approver_name = frappe.db.get_value(
            "User",
            doc.get("leave_approver"),
            "full_name",
        )

        set_if_field(
            "leave_approver_name",
            approver_name or doc.get("leave_approver"),
        )


# ======================================================================
# AR: جلب حالة Workflow السابقة
# EN: Get the previous workflow state
# ======================================================================

def _get_previous_workflow_state(doc):
    # AR: جلب حالة سير العمل السابقة للمستند.
    # EN: Return the document workflow state before the update.
    before_save = getattr(doc, "_doc_before_save", None)

    if before_save:
        return before_save.get("workflow_state")

    if getattr(doc, "name", None) and not doc.is_new():
        return frappe.db.get_value(
            doc.doctype,
            doc.name,
            "workflow_state",
        )

    return None


# ======================================================================
# AR: جلب قيم الموافقات السابقة
# EN: Get previously stored approval status values
# ======================================================================

def _get_previous_approval_values(doc):
    # AR: جلب قيم الاعتماد السابقة قبل تحديث الطلب.
    # EN: Return approval values stored before the update.
    before_save = getattr(doc, "_doc_before_save", None)

    if before_save:
        return frappe._dict(
            substitute=before_save.get(SUBSTITUTE_APPROVAL_FIELD),
            manager=before_save.get(DIRECT_MANAGER_APPROVAL_FIELD),
        )

    if getattr(doc, "name", None) and not doc.is_new():
        values = frappe.db.get_value(
            doc.doctype,
            doc.name,
            [
                SUBSTITUTE_APPROVAL_FIELD,
                DIRECT_MANAGER_APPROVAL_FIELD,
            ],
            as_dict=True,
        )

        if values:
            return frappe._dict(
                substitute=values.get(SUBSTITUTE_APPROVAL_FIELD),
                manager=values.get(DIRECT_MANAGER_APPROVAL_FIELD),
            )

    return frappe._dict(substitute=None, manager=None)


# ======================================================================
# AR: إعادة قيمة الموافقة السابقة أو استخدام قيمة بديلة
# EN: Return valid previous approval value or use fallback value
# ======================================================================

def _approval_or_fallback(value, fallback):
    # AR: إرجاع قيمة الاعتماد أو استخدام القيمة البديلة عند غيابها.
    # EN: Return an approval value or its fallback.
    valid_values = {
        APPROVAL_PENDING,
        APPROVAL_APPROVED,
        APPROVAL_REJECTED,
        APPROVAL_BYPASSED,
    }

    return value if value in valid_values else fallback


# ======================================================================
# AR: تحديث حالة اعتماد البديل والمدير حسب مسار الطلب
# EN: Update substitute and manager approval statuses by workflow route
# ======================================================================

def sync_approval_status_fields(doc):
    # AR: مزامنة حقول حالات الاعتماد مع انتقالات سير العمل.
    # EN: Synchronize approval status fields with workflow transitions.
    state = doc.get("workflow_state") or STATE_DRAFT
    previous_state = _get_previous_workflow_state(doc)
    previous_values = _get_previous_approval_values(doc)
    has_substitute = bool(doc.get(SUBSTITUTE_USER_FIELD))
    current_user = frappe.session.user

    is_substitute_actor = (
        doc.get(SUBSTITUTE_USER_FIELD) == current_user
    )

    is_manager_actor = (
        doc.get(DIRECT_MANAGER_USER_FIELD) == current_user
    )

    is_hr_or_system_actor = is_unrestricted_leave_user(
        current_user
    )

    # AR:
    # رفض الموظف البديل يعيد الطلب إلى الموظف لاختيار بديل جديد أو الإرسال
    # مباشرة إلى المسؤول المباشر. لا يتحول الطلب إلى رفض نهائي.
    #
    # EN:
    # Substitute rejection returns the request to the applicant for selecting
    # another substitute or routing directly to the manager; it is not final rejection.
    substitute_return = bool(
        previous_state == STATE_WAITING_SUBSTITUTE
        and state == STATE_DRAFT
        and is_substitute_actor
        and not is_hr_or_system_actor
    )
    if substitute_return:
        doc.set(SUBSTITUTE_APPROVAL_FIELD, APPROVAL_REJECTED)
        doc.set(DIRECT_MANAGER_APPROVAL_FIELD, APPROVAL_PENDING)
        doc.set(SUBSTITUTE_EMPLOYEE_FIELD, None)
        doc.set(SUBSTITUTE_USER_FIELD, None)
        if doc.meta.has_field(SUBSTITUTE_EMPLOYEE_NAME_FIELD):
            doc.set(SUBSTITUTE_EMPLOYEE_NAME_FIELD, None)
        return

    # AR: لا توجد موافقات منفذة في المسودة أو انتظار البديل.
    # EN: No approvals are completed in Draft or substitute waiting stage.
    if state in {STATE_DRAFT, STATE_WAITING_SUBSTITUTE}:
        doc.set(
            SUBSTITUTE_APPROVAL_FIELD,
            APPROVAL_PENDING if has_substitute else "",
        )
        doc.set(DIRECT_MANAGER_APPROVAL_FIELD, APPROVAL_PENDING)
        return

    # AR: الوصول إلى مرحلة المدير يعني أن البديل وافق أو تم تجاوزه.
    # EN: Reaching manager stage means substitute approved or was bypassed.
    if state == STATE_WAITING_DIRECT_MANAGER:
        if has_substitute:
            substitute_status = (
                APPROVAL_APPROVED
                if previous_state == STATE_WAITING_SUBSTITUTE
                else _approval_or_fallback(
                    previous_values.substitute,
                    APPROVAL_BYPASSED,
                )
            )
        else:
            substitute_status = ""

        doc.set(SUBSTITUTE_APPROVAL_FIELD, substitute_status)
        doc.set(DIRECT_MANAGER_APPROVAL_FIELD, APPROVAL_PENDING)
        return

    # AR: عند الوصول للموارد البشرية يكون المدير قد اعتمد.
    # EN: When reaching HR stage, the manager is considered approved.
    if state == STATE_WAITING_HR_MANAGER:
        if has_substitute:
            if previous_state == STATE_WAITING_SUBSTITUTE:
                substitute_status = APPROVAL_BYPASSED
            else:
                substitute_status = _approval_or_fallback(
                    previous_values.substitute,
                    APPROVAL_APPROVED,
                )
        else:
            substitute_status = ""

        doc.set(SUBSTITUTE_APPROVAL_FIELD, substitute_status)
        doc.set(DIRECT_MANAGER_APPROVAL_FIELD, APPROVAL_APPROVED)
        return

    # AR: اعتماد نهائي مبكر من HR يجعل المراحل غير المنفذة Bypassed.
    # EN: Early final HR approval marks unperformed stages as Bypassed.
    if state == STATE_APPROVED:
        if previous_state == STATE_WAITING_SUBSTITUTE:
            doc.set(
                SUBSTITUTE_APPROVAL_FIELD,
                APPROVAL_BYPASSED if has_substitute else "",
            )
            doc.set(DIRECT_MANAGER_APPROVAL_FIELD, APPROVAL_BYPASSED)

        elif previous_state == STATE_WAITING_DIRECT_MANAGER:
            doc.set(
                SUBSTITUTE_APPROVAL_FIELD,
                APPROVAL_APPROVED if has_substitute else "",
            )
            doc.set(DIRECT_MANAGER_APPROVAL_FIELD, APPROVAL_BYPASSED)

        elif previous_state == STATE_WAITING_HR_MANAGER:
            doc.set(
                SUBSTITUTE_APPROVAL_FIELD,
                (
                    _approval_or_fallback(
                        previous_values.substitute,
                        APPROVAL_APPROVED,
                    )
                    if has_substitute
                    else ""
                ),
            )

            doc.set(
                DIRECT_MANAGER_APPROVAL_FIELD,
                _approval_or_fallback(
                    previous_values.manager,
                    APPROVAL_APPROVED,
                ),
            )

        else:
            doc.set(
                SUBSTITUTE_APPROVAL_FIELD,
                APPROVAL_BYPASSED if has_substitute else "",
            )
            doc.set(DIRECT_MANAGER_APPROVAL_FIELD, APPROVAL_BYPASSED)

        return

    # AR: عند الرفض نحدد الطرف الذي نفذ الرفض فعلاً.
    # EN: On rejection, record which actor actually rejected the request.
    if state == STATE_REJECTED:
        if previous_state == STATE_WAITING_SUBSTITUTE:
            if is_substitute_actor and not is_hr_or_system_actor:
                doc.set(SUBSTITUTE_APPROVAL_FIELD, APPROVAL_REJECTED)
                doc.set(DIRECT_MANAGER_APPROVAL_FIELD, APPROVAL_PENDING)

            elif is_manager_actor and not is_hr_or_system_actor:
                doc.set(
                    SUBSTITUTE_APPROVAL_FIELD,
                    APPROVAL_BYPASSED if has_substitute else "",
                )

                doc.set(
                    DIRECT_MANAGER_APPROVAL_FIELD,
                    APPROVAL_REJECTED,
                )

            else:
                doc.set(
                    SUBSTITUTE_APPROVAL_FIELD,
                    APPROVAL_BYPASSED if has_substitute else "",
                )

                doc.set(
                    DIRECT_MANAGER_APPROVAL_FIELD,
                    APPROVAL_BYPASSED,
                )

        elif previous_state == STATE_WAITING_DIRECT_MANAGER:
            doc.set(
                SUBSTITUTE_APPROVAL_FIELD,
                APPROVAL_APPROVED if has_substitute else "",
            )

            doc.set(
                DIRECT_MANAGER_APPROVAL_FIELD,
                (
                    APPROVAL_REJECTED
                    if is_manager_actor and not is_hr_or_system_actor
                    else APPROVAL_BYPASSED
                ),
            )

        elif previous_state == STATE_WAITING_HR_MANAGER:
            doc.set(
                SUBSTITUTE_APPROVAL_FIELD,
                (
                    _approval_or_fallback(
                        previous_values.substitute,
                        APPROVAL_APPROVED,
                    )
                    if has_substitute
                    else ""
                ),
            )

            doc.set(
                DIRECT_MANAGER_APPROVAL_FIELD,
                _approval_or_fallback(
                    previous_values.manager,
                    APPROVAL_APPROVED,
                ),
            )

        else:
            doc.set(
                SUBSTITUTE_APPROVAL_FIELD,
                APPROVAL_BYPASSED if has_substitute else "",
            )

            doc.set(
                DIRECT_MANAGER_APPROVAL_FIELD,
                APPROVAL_BYPASSED,
            )


# ======================================================================
# AR: تنفيذ بعد حفظ أو تحديث طلب الإجازة
# EN: Run after saving or updating Leave Application
# ======================================================================

def on_update_leave_application(doc, method=None):
    # AR: مزامنة المشاركات وإرسال الإشعارات بعد تحديث طلب الإجازة.
    # EN: Synchronize shares and send notifications after an update.
    sync_leave_application_shares(doc)
    send_leave_workflow_notifications(doc)


# ======================================================================
# AR: منح مشاركة لطلب الإجازة نفسه
# EN: Grant a DocShare permission for the Leave Application document
# ======================================================================

def _grant_docshare(doc, user, write=0):
    # AR: منح مستخدم محدد مشاركة على طلب الإجازة بصلاحية مناسبة.
    if (
        not user
        or user == "Administrator"
        or not frappe.db.exists("User", user)
    ):
        return

    existing_share = frappe.db.get_value(
        "DocShare",
        {"share_doctype": doc.doctype, "share_name": doc.name, "user": user},
        "name"
    )

    if existing_share:
        frappe.db.set_value("DocShare", existing_share, {"read": 1, "write": 1 if write else 0}, update_modified=False)
    else:
        share = frappe.new_doc("DocShare")
        share.share_doctype = doc.doctype
        share.share_name = doc.name
        share.user = user
        share.read = 1
        share.write = 1 if write else 0
        share.submit = 0
        share.share = 0
        share.flags.ignore_share_permission = True
        share.insert(ignore_permissions=True)


# ======================================================================
# AR: منح قراءة فقط لسجل موظف مرتبط بطلب الإجازة
# EN: Grant read-only access to an Employee related to the leave request
# ======================================================================

def _grant_employee_docshare(employee, user):
    # AR: منح قراءة فقط لسجل موظف مرتبط بطلب الإجازة.
    if (
        not employee
        or not user
        or user == "Administrator"
        or not frappe.db.exists("Employee", employee)
        or not frappe.db.exists("User", user)
    ):
        return

    existing_share = frappe.db.get_value(
        "DocShare",
        {"share_doctype": "Employee", "share_name": employee, "user": user},
        "name"
    )

    if existing_share:
        frappe.db.set_value("DocShare", existing_share, {"read": 1, "write": 0}, update_modified=False)
    else:
        share = frappe.new_doc("DocShare")
        share.share_doctype = "Employee"
        share.share_name = employee
        share.user = user
        share.read = 1
        share.write = 0
        share.submit = 0
        share.share = 0
        share.flags.ignore_share_permission = True
        share.insert(ignore_permissions=True)


# ======================================================================
# AR: مزامنة مشاركات طلب الإجازة مع الأطراف والموارد البشرية
# EN: Synchronize Leave Application sharing with participants and HR
# ======================================================================

def sync_leave_application_shares(doc, method=None):
    # AR: مزامنة مشاركات طلب الإجازة مع جميع الأطراف المرتبطة.
    # EN: Synchronize Leave Application shares for all participants.
    permissions = {}

    # AR: حفظ أقوى صلاحية مطلوبة لكل مستخدم ضمن عملية المزامنة.
    # EN: Keep the strongest required permission for each user.
    def grant(user, write):
        if not user:
            return

        permissions[user] = max(
            permissions.get(user, 0),
            1 if write else 0,
        )

    applicant_user = _employee_user(doc.get("employee"))

    grant(applicant_user, True)
    grant(doc.get(SUBSTITUTE_USER_FIELD), True)
    grant(doc.get(DIRECT_MANAGER_USER_FIELD), True)

    secretary_user = doc.get(
        DIRECT_MANAGER_SECRETARY_USER_FIELD
    )

    secretary_has_actor_role = secretary_user in {
        applicant_user,
        doc.get(SUBSTITUTE_USER_FIELD),
        doc.get(DIRECT_MANAGER_USER_FIELD),
    }

    # AR: السكرتير قراءة فقط إلا إذا كان بديل أو مدير أو مقدم الطلب.
    # EN: Secretary is read-only unless also substitute, manager, or applicant.
    grant(secretary_user, secretary_has_actor_role)

    related_employees = {
        doc.get("employee"),
        doc.get(SUBSTITUTE_EMPLOYEE_FIELD),
        doc.get(DIRECT_MANAGER_EMPLOYEE_FIELD),
        doc.get(DIRECT_MANAGER_SECRETARY_EMPLOYEE_FIELD),
    }

    related_employees.discard(None)
    related_employees.discard("")

    # AR: إزالة مشاركة أي بديل قديم بعد رفضه أو استبداله.
    # EN: Remove stale request shares after a substitute is rejected or replaced.
    previous = doc.get_doc_before_save()
    if previous:
        previous_users = {
            _employee_user(previous.get("employee")),
            previous.get(SUBSTITUTE_USER_FIELD),
            previous.get(DIRECT_MANAGER_USER_FIELD),
            previous.get(DIRECT_MANAGER_SECRETARY_USER_FIELD),
        }
        current_users = set(permissions)
        for stale_user in previous_users - current_users:
            if stale_user:
                frappe.db.delete(
                    "DocShare",
                    {
                        "share_doctype": doc.doctype,
                        "share_name": doc.name,
                        "user": stale_user,
                    },
                )

    # AR: مشاركة طلب الإجازة نفسه مع أطرافه.
    # EN: Share the Leave Application document with its participants.
    for user, can_write in permissions.items():
        _grant_docshare(doc, user, write=can_write)

    # AR: الموارد البشرية تقرأ سجلات الموظفين المرتبطة بالطلب فقط.
    # EN: HR can read only Employee records related to this leave request.
    employee_viewers = set(permissions)
    employee_viewers.update(
        get_users_with_role_safe("HR Manager")
    )

    for user in employee_viewers:
        for employee in related_employees:
            _grant_employee_docshare(employee, user)


# ======================================================================
# AR: إرسال تنبيهات لأطراف المرحلة الحالية
# EN: Send notifications to users responsible for the current workflow stage
# ======================================================================

def _translate_leave_notification_for_user(target, source, *args):
    """
    AR:
        ترجمة إشعار طلب الإجازة وفق لغة المستخدم المستهدف، وليس لغة منفذ
        إجراء سير العمل الحالي.

    EN:
        Translate a Leave notification using the target user's language,
        not the workflow actor's current session language.
    """
    language = (
        frappe.get_cached_value("User", target, "language")
        or getattr(frappe.local, "lang", None)
        or "en"
    )
    return _(source, lang=language).format(*args)


def send_leave_workflow_notifications(doc):
    """
    AR:
        إرسال إشعارات المرحلة الحالية. عند انتظار البديل يصل الطلب أيضاً
        للمسؤول المباشر ليعتمد فوراً أو ينتظر قرار البديل. رفض البديل يعيد
        الطلب للموظف مع إشعار واضح لإعادة الاختيار.

    EN:
        Notify the current stage. While waiting for the substitute, the direct
        manager is also notified and may approve immediately or wait. Substitute
        rejection returns the request to the applicant for reselection.
    """
    state = doc.get("workflow_state")
    previous_state = _get_previous_workflow_state(doc)

    if not state or doc.docstatus >= 2:
        return

    messages_by_target = {}

    if (
        state == STATE_DRAFT
        and previous_state == STATE_WAITING_SUBSTITUTE
        and doc.get(SUBSTITUTE_APPROVAL_FIELD) == APPROVAL_REJECTED
    ):
        targets = {doc.owner}
        applicant_user = _employee_user(doc.get("employee"))
        if applicant_user:
            targets.add(applicant_user)

        source = (
            "↩️ Leave Request Returned: The substitute rejected request {0}. "
            "Please select another substitute or send it directly to your manager."
        )
        for target in targets:
            messages_by_target[target] = _translate_leave_notification_for_user(
                target, source, doc.name
            )

    elif state == STATE_WAITING_SUBSTITUTE:
        substitute_user = doc.get(SUBSTITUTE_USER_FIELD)
        manager_user = doc.get(DIRECT_MANAGER_USER_FIELD)
        secretary_user = doc.get(DIRECT_MANAGER_SECRETARY_USER_FIELD)

        if substitute_user:
            source = (
                "⚠️ Leave Request Action Required: {0} has requested you as a substitute."
            )
            messages_by_target[substitute_user] = _translate_leave_notification_for_user(
                substitute_user, source, doc.employee_name
            )

        manager_source = (
            "⚠️ Leave Request Available: Request {0} from {1} is waiting for the substitute. "
            "You may approve it now or wait for the substitute decision."
        )
        for target in {manager_user, secretary_user}:
            if target:
                messages_by_target[target] = _translate_leave_notification_for_user(
                    target, manager_source, doc.name, doc.employee_name
                )

    elif state == STATE_WAITING_DIRECT_MANAGER:
        source = (
            "⚠️ Leave Request Action Required: New request from {0} is awaiting approval."
        )
        for target in {
            doc.get(DIRECT_MANAGER_USER_FIELD),
            doc.get(DIRECT_MANAGER_SECRETARY_USER_FIELD),
        }:
            if target:
                messages_by_target[target] = _translate_leave_notification_for_user(
                    target, source, doc.employee_name
                )

    elif state == STATE_WAITING_HR_MANAGER:
        source = (
            "⚠️ Leave Request Action Required: Request from {0} reached HR."
        )
        for target in get_users_with_role_safe("HR Manager"):
            messages_by_target[target] = _translate_leave_notification_for_user(
                target, source, doc.employee_name
            )

    elif state == STATE_APPROVED:
        target = doc.owner
        source = (
            "✅ Leave Request Approved: Your leave application ({0}) has been fully approved."
        )
        messages_by_target[target] = _translate_leave_notification_for_user(
            target, source, doc.name
        )

    elif state == STATE_REJECTED:
        target = doc.owner
        source = (
            "❌ Leave Request Rejected: Your leave application ({0}) has been rejected."
        )
        messages_by_target[target] = _translate_leave_notification_for_user(
            target, source, doc.name
        )

    for target, message in messages_by_target.items():
        if (
            target
            and target != "Administrator"
            and target != frappe.session.user
            and frappe.db.exists("User", target)
        ):
            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "subject": message,
                    "for_user": target,
                    "document_type": "Leave Application",
                    "document_name": doc.name,
                    "type": "Alert",
                }
            ).insert(ignore_permissions=True)


# ======================================================================
# AR: دالة توافق عند حذف الطلب
# EN: Compatibility hook when a Leave Application is deleted
# ======================================================================

def remove_leave_application_shares(doc, method=None):
    # AR: إزالة مشاركات طلب الإجازة عند حذف المستند.
    # EN: Remove Leave Application shares when the document is deleted.
    pass


# ======================================================================
# AR: إعادة مزامنة المشاركات لجميع الطلبات القديمة
# EN: Resynchronize shares for all existing leave requests
# ======================================================================

def resync_all_leave_application_shares():
    # AR: إعادة مزامنة مشاركات جميع طلبات الإجازة الموجودة.
    # EN: Re-synchronize shares for all existing leave requests.
    names = frappe.get_all(
        "Leave Application",
        pluck="name",
    )

    for name in names:
        sync_leave_application_shares(
            frappe.get_doc("Leave Application", name)
        )

    frappe.db.commit()
    return len(names)


# ======================================================================
# AR: إعادة تعبئة أسماء العرض لجميع الطلبات القديمة
# EN: Refill display names for all existing leave requests
# ======================================================================

def resync_all_leave_application_display_names():
    # AR: إصلاح أسماء العرض لجميع طلبات الإجازة القديمة.
    # EN: Repair display names on all existing leave requests.
    names = frappe.get_all(
        "Leave Application",
        pluck="name",
    )

    for name in names:
        doc = frappe.get_doc("Leave Application", name)
        sync_leave_application_display_names(doc)

        values = {}

        for fieldname in (
            "employee_name",
            SUBSTITUTE_EMPLOYEE_NAME_FIELD,
            DIRECT_MANAGER_EMPLOYEE_NAME_FIELD,
            DIRECT_MANAGER_SECRETARY_NAME_FIELD,
            "leave_approver_name",
        ):
            if doc.meta.has_field(fieldname):
                values[fieldname] = doc.get(fieldname)

        if values:
            frappe.db.set_value(
                "Leave Application",
                name,
                values,
                update_modified=False,
            )

    frappe.db.commit()
    return len(names)


# ======================================================================
# AR: جلب المدير المباشر الحالي من Employee
# EN: Get the current direct manager Employee
# ======================================================================

def _current_direct_manager_employee(employee):
    # AR: جلب سجل المدير المباشر الحالي للموظف.
    # EN: Return the current direct manager Employee.
    if not employee:
        return None

    return frappe.get_cached_value(
        "Employee",
        employee,
        "reports_to",
    )


# ======================================================================
# AR: جلب الاسم المقروء للموظف
# EN: Get readable employee name
# ======================================================================

def _readable_employee_name(employee):
    # AR: جلب الاسم المقروء للموظف.
    # EN: Return a readable Employee name.
    if not employee:
        return None

    return frappe.get_cached_value(
        "Employee",
        employee,
        "employee_name",
    )


# ======================================================================
# AR: تحديد إجراءات Workflow المتاحة للمستخدم
# EN: Determine available Workflow actions for the user
# ======================================================================

def _available_leave_actions(doc, user=None):
    # AR: تحديد إجراءات سير العمل المتاحة للمستخدم الحالي.
    # EN: Return workflow actions available to the current user.
    user = user or frappe.session.user
    state = doc.get("workflow_state") or STATE_DRAFT
    relation = _relation_flags(doc, user)
    applicant_user = _employee_user(doc.get("employee"))
    actions = []

    # AR: لا تظهر إجراءات HR User على طلبات الآخرين؛ طلبه الشخصي يتبع دور Employee.
    # EN: HR User gets no actions on others' requests; a personal request follows Employee rules.
    if is_hr_user_read_only(user) and not relation.applicant:
        return actions

    # AR: HR وSystem Manager يستطيعان الاعتماد النهائي أو الرفض
    # من جميع المراحل النشطة، بما فيها Draft.
    #
    # EN: HR and System Manager can finally approve or reject
    # from every active stage, including Draft.
    if is_unrestricted_leave_user(user):
        if state in {
            STATE_DRAFT,
            STATE_WAITING_SUBSTITUTE,
            STATE_WAITING_DIRECT_MANAGER,
            STATE_WAITING_HR_MANAGER,
        }:
            actions.extend([
                ACTION_FINAL_APPROVE,
                ACTION_REJECT,
            ])

        return actions

    # AR: البديل يتصرف في مرحلة انتظار البديل فقط.
    # EN: Substitute acts only in substitute waiting stage.
    if relation.substitute and state == STATE_WAITING_SUBSTITUTE:
        actions.extend([
            ACTION_SUBSTITUTE_APPROVE,
            ACTION_REJECT,
        ])

        return actions

    current_manager_user = _employee_direct_manager_user(
        doc.get("employee")
    )

    is_actual_direct_manager = bool(
        relation.direct_manager
        or current_manager_user == user
        or doc.get(DIRECT_MANAGER_USER_FIELD) == user
    )

    # AR: المدير المباشر يستطيع الاعتماد أو الرفض في مرحلته.
    # EN: Direct manager can approve or reject in their allowed stage.
    if (
        is_actual_direct_manager
        and applicant_user != user
        and state in {
            STATE_WAITING_SUBSTITUTE,
            STATE_WAITING_DIRECT_MANAGER,
        }
    ):
        actions.extend([
            ACTION_DIRECT_MANAGER_APPROVE,
            ACTION_REJECT,
        ])

    return actions


# ======================================================================
# AR: API لإرجاع أسماء الأطراف والأزرار المتاحة في الواجهة
# EN: API to return participant names and available UI actions
# ======================================================================

@frappe.whitelist()
def get_leave_application_ui_context(docname):
    # AR: إرجاع بيانات الأطراف والإجراءات اللازمة لواجهة طلب الإجازة.
    # EN: Return participants and actions required by the form UI.
    doc = frappe.get_doc("Leave Application", docname)
    doc.check_permission("read")

    sync_leave_application_display_names(doc)

    manager_employee = (
        doc.get(DIRECT_MANAGER_EMPLOYEE_FIELD)
        or _current_direct_manager_employee(doc.get("employee"))
    )

    manager_name = (
        doc.get(DIRECT_MANAGER_EMPLOYEE_NAME_FIELD)
        or _readable_employee_name(manager_employee)
    )

    substitute_name = (
        doc.get(SUBSTITUTE_EMPLOYEE_NAME_FIELD)
        or _readable_employee_name(
            doc.get(SUBSTITUTE_EMPLOYEE_FIELD)
        )
    )

    secretary_name = (
        doc.get(DIRECT_MANAGER_SECRETARY_NAME_FIELD)
        or _readable_employee_name(
            doc.get(DIRECT_MANAGER_SECRETARY_EMPLOYEE_FIELD)
        )
    )

    approver_name = doc.get("leave_approver_name")

    if not approver_name and doc.get("leave_approver"):
        approver_name = frappe.get_cached_value(
            "User",
            doc.get("leave_approver"),
            "full_name",
        )

    return {
        "employee_name": (
            doc.get("employee_name")
            or _readable_employee_name(doc.get("employee"))
        ),
        "substitute_employee_name": substitute_name,
        "direct_manager_employee_name": manager_name,
        "direct_manager_secretary_name": secretary_name,
        "leave_approver_name": approver_name,
        "actions": _available_leave_actions(doc),
        "workflow_state": doc.get("workflow_state"),
    }


# ======================================================================
# AR: API لتنفيذ إجراء Workflow بشكل آمن
# EN: API to safely apply a Workflow action
# ======================================================================

@frappe.whitelist()
def apply_masar_requests_leave_workflow_action(docname, action):
    # AR: تنفيذ إجراء سير عمل طلب الإجازة بعد التحقق من الصلاحية.
    # EN: Apply an authorized Leave Application workflow action.
    doc = frappe.get_doc("Leave Application", docname)
    doc.check_permission("read")

    allowed_actions = _available_leave_actions(doc)

    if action not in allowed_actions:
        frappe.throw(
            _("You are not allowed to perform this workflow action."),
            frappe.PermissionError,
        )

    from frappe.model.workflow import apply_workflow

    updated_doc = apply_workflow(doc.as_dict(), action)
    return updated_doc.as_dict()


# ======================================================================
# AR: إصلاح بيانات العرض للطلبات القديمة
# EN: Repair display data for old Leave Applications
# ======================================================================

@frappe.whitelist()
def repair_all_leave_application_display_data():
    # AR: إصلاح بيانات العرض لجميع طلبات الإجازة كعملية إدارية.
    # EN: Repair display data on every leave request as an admin task.
    frappe.only_for("System Manager")

    names = frappe.get_all(
        "Leave Application",
        pluck="name",
    )

    for name in names:
        doc = frappe.get_doc("Leave Application", name)

        set_direct_manager_from_reports_to(doc)
        sync_leave_application_display_names(doc)

        values = {}

        for fieldname in (
            DIRECT_MANAGER_EMPLOYEE_FIELD,
            DIRECT_MANAGER_USER_FIELD,
            DIRECT_MANAGER_SECRETARY_EMPLOYEE_FIELD,
            DIRECT_MANAGER_SECRETARY_USER_FIELD,
            "employee_name",
            SUBSTITUTE_EMPLOYEE_NAME_FIELD,
            DIRECT_MANAGER_EMPLOYEE_NAME_FIELD,
            DIRECT_MANAGER_SECRETARY_NAME_FIELD,
            "leave_approver_name",
        ):
            if doc.meta.has_field(fieldname):
                values[fieldname] = doc.get(fieldname)

        if values:
            frappe.db.set_value(
                "Leave Application",
                name,
                values,
                update_modified=False,
            )

    frappe.db.commit()
    frappe.clear_cache(doctype="Leave Application")

    return len(names)


# ======================================================================
# AR: جلب المستخدمين الذين يحملون دوراً محدداً
# EN: Get all users assigned to a specific role
# ======================================================================

def get_users_with_role_safe(role):
    # AR: جلب المستخدمين المسند إليهم دور محدد.
    # EN: Return users assigned to a specified role.
    return frappe.get_all(
        "Has Role",
        filters={"role": role},
        pluck="parent",
    )


# ======================================================================
# AR: فلترة طلبات الإجازة الظاهرة للمستخدم في القائمة
# EN: Filter Leave Applications visible to the user in list view
# ======================================================================

def leave_application_query(user=None):
    # AR: إنشاء شرط يحدد طلبات الإجازة الظاهرة للمستخدم في القوائم.
    # EN: Build the list query condition for visible leave requests.
    user = user or frappe.session.user

    # AR: HR وSystem Manager يشاهدون كل الطلبات.
    # EN: HR and System Manager can view all requests.
    if is_unrestricted_leave_user(user) or is_hr_user_read_only(user):
        return None

    escaped_user = frappe.db.escape(user)

    return f"""(
        `tabLeave Application`.`owner` = {escaped_user}

        OR EXISTS (
            SELECT 1
            FROM `tabEmployee` applicant_employee
            WHERE applicant_employee.`name` =
                `tabLeave Application`.`employee`
            AND applicant_employee.`user_id` = {escaped_user}
        )

        OR `tabLeave Application`.`custom_substitute_user` =
            {escaped_user}

        OR `tabLeave Application`.`custom_direct_manager_user` =
            {escaped_user}

        OR `tabLeave Application`.`custom_direct_manager_secretary_user` =
            {escaped_user}

        OR EXISTS (
            SELECT 1
            FROM `tabEmployee` applicant_employee
            INNER JOIN `tabEmployee` manager_employee
                ON manager_employee.`name` =
                    applicant_employee.`reports_to`
            WHERE applicant_employee.`name` =
                `tabLeave Application`.`employee`
            AND manager_employee.`user_id` = {escaped_user}
        )

        OR EXISTS (
            SELECT 1
            FROM `tabEmployee` applicant_employee
            INNER JOIN `tabEmployee` own_secretary_employee
                ON own_secretary_employee.`name` =
                    applicant_employee.`custom_secretary_employee`
            WHERE applicant_employee.`name` =
                `tabLeave Application`.`employee`
            AND own_secretary_employee.`user_id` = {escaped_user}
        )
    )"""


# ======================================================================
# AR: فحص الصلاحية على مستند طلب إجازة محدد
# EN: Check permission for a specific Leave Application document
# ======================================================================

def leave_application_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    # AR: فحص صلاحية المستخدم على طلب إجازة محدد.
    # EN: Check a user permission on one Leave Application.
    user = user or frappe.session.user
    permission_type = permission_type or ptype or "read"

    # AR: فحص الإنشاء لا يملك مستندًا محفوظًا؛ تطبق صلاحيات الدور الطبيعية.
    # EN: Create permission has no saved document; defer to normal role permissions.
    if permission_type == "create":
        return None

    reference_doc = _permission_snapshot(doc)
    relation = _relation_flags(reference_doc, user)

    # AR: HR User يقرأ ويطبع طلبات الآخرين فقط، أما طلبه الشخصي فيعامل كموظف.
    # EN: HR User is read/print-only for others; a personal request follows Employee permissions.
    if is_hr_user_read_only(user) and not relation.applicant:
        return permission_type in {"read", "print"}

    # AR: الموارد البشرية ومدير النظام لديهم صلاحية كاملة.
    # EN: HR and System Manager have full permissions.
    if is_unrestricted_leave_user(user):
        return True

    is_related = any(relation.values())

    if permission_type in {"read", "print"}:
        return bool(is_related)

    if permission_type == "write":
        return _can_write_leave(reference_doc, user)

    if permission_type == "delete":
        state = reference_doc.get("workflow_state") or STATE_DRAFT

        return bool(
            relation.applicant
            and state == STATE_DRAFT
        )

    if permission_type in {
        "submit",
        "cancel",
        "amend",
        "share",
        "email",
        "export",
        "import",
    }:
        return False

    return False


# ======================================================================
# AR: دالة توافق قديمة، لا تمنح صلاحية عامة على Employee
# EN: Legacy compatibility function; grants no general Employee permission
# ======================================================================

def employee_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    # AR: دالة توافق قديمة لا تمنح صلاحية عامة على سجلات الموظفين.
    # EN: Legacy compatibility function that grants no broad Employee access.
    return None


# ======================================================================
# AR: دوال قديمة معطلة لمنع إنشاء User Permissions دائمة
# EN: Disabled legacy functions to avoid permanent User Permissions
# ======================================================================

def sync_leave_employee_user_permissions(doc):
    # AR: دالة توافق معطلة لمنع إنشاء صلاحيات مستخدم دائمة.
    # EN: Disabled compatibility function for permanent User Permissions.
    return


def add_employee_user_permission(user, employee):
    # AR: دالة توافق معطلة لمنع إضافة صلاحية موظف دائمة.
    # EN: Disabled compatibility function for permanent Employee permissions.
    return
