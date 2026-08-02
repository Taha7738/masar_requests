"""
AR: منطق الصلاحيات والتحكم في الوصول ضمن الوحدة `strict_request_visibility`.
EN: Permission and access-control logic for the `strict_request_visibility` module.

DETAILS / التفاصيل:
Strict participant/stage visibility for Leave Application, Official Duty Request,
and Material Request.

Policy:
- ordinary employees never gain access merely because they share a department;
- applicant/owner, selected substitute, and exact direct manager remain related;
- workflow administrative roles see only the stage currently assigned to them;
- Material Request senior-management access remains unchanged;
- existing business validation and workflow write rules remain delegated to the
  original permission functions.
"""

from __future__ import annotations

import frappe


READ_TYPES = {
    None,
    "read",
    "print",
    "email",
    "export",
    "report",
    "select",
}

SYSTEM_WIDE_ROLES = {"System Manager"}

LEAVE_HR_STATES = {
    "Waiting for HR Manager Approval",
    "Approved",
}

OFFICIAL_HR_STATES = {
    "Waiting for HR Manager Approval",
    "Approved",
}

OFFICIAL_HR_PROCESSING = {
    "Manual Review",
    "Partially Reconciled",
    "Reconciled",
}

MATERIAL_STAGE_ROLES = {
    "Pending Stock Check": "Warehouse Manager",
    "Pending HR Manager": "HR Manager",
    "Pending Accounts Manager": "Accounts Manager",
    "Pending Sec Gen": "Secretary General",
    "Pending President": "University President",
}

MATERIAL_HIGH_LEVEL_ROLES = {
    "Secretary General",
    "University President",
}


def _roles(user):
    """
    AR: تنفيذ `roles` ضمن وحدة `strict_request_visibility`.
    EN: Execute roles within the `strict_request_visibility` module.
    """
    try:
        return set(frappe.get_roles(user))
    except Exception:
        return set()


def _is_system_wide(user):
    """
    AR: تنفيذ التحقق من كون `system` `wide` ضمن وحدة `strict_request_visibility`.
    EN: Execute is system wide within the `strict_request_visibility` module.
    """
    return user == "Administrator" or bool(_roles(user) & SYSTEM_WIDE_ROLES)


def _meta_has_field(doctype, fieldname):
    """
    AR: تنفيذ `meta` التحقق من وجود الحقل ضمن وحدة `strict_request_visibility`.
    EN: Execute meta has field within the `strict_request_visibility` module.
    """
    try:
        return frappe.get_meta(doctype, cached=False).has_field(fieldname)
    except Exception:
        return False


def _doc_get(doc, fieldname, default=None):
    """
    AR: تنفيذ المستند استرجاع ضمن وحدة `strict_request_visibility`.
    EN: Execute doc get within the `strict_request_visibility` module.
    """
    if doc is None:
        return default
    if hasattr(doc, "get"):
        return doc.get(fieldname, default)
    return getattr(doc, fieldname, default)


def _employee_for_user(user):
    """
    AR: تنفيذ الموظف `for` المستخدم ضمن وحدة `strict_request_visibility`.
    EN: Execute employee for user within the `strict_request_visibility` module.
    """
    if not user:
        return None
    return frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        "name",
    )


def _employee_user(employee):
    """
    AR: تنفيذ الموظف المستخدم ضمن وحدة `strict_request_visibility`.
    EN: Execute employee user within the `strict_request_visibility` module.
    """
    if not employee:
        return None
    return frappe.db.get_value("Employee", employee, "user_id")


def _manager_user_from_employee(employee):
    """
    AR: تنفيذ المدير المستخدم `from` الموظف ضمن وحدة `strict_request_visibility`.
    EN: Execute manager user from employee within the `strict_request_visibility` module.
    """
    if not employee:
        return None

    manager_employee = frappe.db.get_value(
        "Employee",
        employee,
        "reports_to",
    )
    return _employee_user(manager_employee)


def _current_stage_role_allowed(doc, user, stage_role_map):
    """
    AR: تنفيذ الحالي `stage` الدور `allowed` ضمن وحدة `strict_request_visibility`.
    EN: Execute current stage role allowed within the `strict_request_visibility` module.
    """
    state = _doc_get(doc, "workflow_state")
    required_role = stage_role_map.get(state)
    return bool(required_role and required_role in _roles(user))


def _sql_user_employee_match(
    table,
    employee_field,
    escaped_user,
):
    """
    AR: تنفيذ `sql` المستخدم الموظف `match` ضمن وحدة `strict_request_visibility`.
    EN: Execute sql user employee match within the `strict_request_visibility` module.
    """
    return f"""EXISTS (
        SELECT 1
          FROM `tabEmployee` strict_employee
         WHERE strict_employee.`name` = {table}.`{employee_field}`
           AND strict_employee.`user_id` = {escaped_user}
    )"""


def _sql_manager_match(
    table,
    employee_field,
    escaped_user,
):
    """
    AR: تنفيذ `sql` المدير `match` ضمن وحدة `strict_request_visibility`.
    EN: Execute sql manager match within the `strict_request_visibility` module.
    """
    return f"""EXISTS (
        SELECT 1
          FROM `tabEmployee` strict_applicant
          JOIN `tabEmployee` strict_manager
            ON strict_manager.`name` = strict_applicant.`reports_to`
         WHERE strict_applicant.`name` = {table}.`{employee_field}`
           AND strict_manager.`user_id` = {escaped_user}
    )"""


def _sql_material_reports_to_match(table, escaped_user):
    """
    AR: تنفيذ `sql` المواد `reports` `to` `match` ضمن وحدة `strict_request_visibility`.
    EN: Execute sql material reports to match within the `strict_request_visibility` module.
    """
    return f"""EXISTS (
        SELECT 1
          FROM `tabEmployee` strict_manager
         WHERE strict_manager.`name` = {table}.`reports_to`
           AND strict_manager.`user_id` = {escaped_user}
    )"""


def _sql_docshare_match(doctype, table, escaped_user):
    """
    AR: تنفيذ `sql` `docshare` `match` ضمن وحدة `strict_request_visibility`.
    EN: Execute sql docshare match within the `strict_request_visibility` module.
    """
    escaped_doctype = frappe.db.escape(doctype)
    return f"""EXISTS (
        SELECT 1
          FROM `tabDocShare` strict_share
         WHERE strict_share.`share_doctype` = {escaped_doctype}
           AND strict_share.`share_name` = {table}.`name`
           AND strict_share.`user` = {escaped_user}
           AND strict_share.`read` = 1
    )"""


# ---------------------------------------------------------------------------
# Leave Application
# ---------------------------------------------------------------------------

def _leave_related(doc, user):
    """
    AR: تنفيذ الإجازة `related` ضمن وحدة `strict_request_visibility`.
    EN: Execute leave related within the `strict_request_visibility` module.
    """
    if _is_system_wide(user):
        return True

    employee = _doc_get(doc, "employee")
    applicant_user = _employee_user(employee)

    if user in {
        _doc_get(doc, "owner"),
        applicant_user,
        _doc_get(doc, "custom_substitute_user"),
        _doc_get(doc, "custom_direct_manager_user"),
    }:
        return True

    if (
        user == _doc_get(doc, "custom_direct_manager_secretary_user")
        and _doc_get(doc, "workflow_state")
        == "Waiting for Direct Manager Approval"
    ):
        return True

    roles = _roles(user)
    state = _doc_get(doc, "workflow_state")

    if roles & {"HR Manager", "HR User"}:
        if state in LEAVE_HR_STATES:
            return True

        if (
            state == "Rejected"
            and _doc_get(doc, "custom_direct_manager_approval") == "Approved"
        ):
            return True

    return False


def leave_application_query(user=None):
    """
    AR: تنفيذ الإجازة `application` `query` ضمن وحدة `strict_request_visibility`.
    EN: Execute leave application query within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user

    if _is_system_wide(user):
        return None

    table = "`tabLeave Application`"
    escaped_user = frappe.db.escape(user)

    conditions = [
        f"{table}.`owner` = {escaped_user}",
        _sql_user_employee_match(
            table,
            "employee",
            escaped_user,
        ),
    ]

    for fieldname in (
        "custom_substitute_user",
        "custom_direct_manager_user",
    ):
        if _meta_has_field("Leave Application", fieldname):
            conditions.append(
                f"{table}.`{fieldname}` = {escaped_user}"
            )

    if _meta_has_field(
        "Leave Application",
        "custom_direct_manager_secretary_user",
    ):
        conditions.append(
            f"""(
                {table}.`custom_direct_manager_secretary_user` = {escaped_user}
                AND {table}.`workflow_state` =
                    'Waiting for Direct Manager Approval'
            )"""
        )

    roles = _roles(user)

    if roles & {"HR Manager", "HR User"}:
        hr_conditions = [
            f"{table}.`workflow_state` IN "
            "('Waiting for HR Manager Approval', 'Approved')"
        ]

        if _meta_has_field(
            "Leave Application",
            "custom_direct_manager_approval",
        ):
            hr_conditions.append(
                f"""(
                    {table}.`workflow_state` = 'Rejected'
                    AND {table}.`custom_direct_manager_approval` = 'Approved'
                )"""
            )

        conditions.append("(" + " OR ".join(hr_conditions) + ")")

    return "(" + " OR ".join(conditions) + ")"


def leave_application_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    """
    AR: تنفيذ الإجازة `application` التحقق من وجود صلاحية ضمن وحدة `strict_request_visibility`.
    EN: Execute leave application has permission within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user
    requested = permission_type or ptype or "read"

    if requested == "create":
        return None

    if not _leave_related(doc, user):
        return False

    if requested in READ_TYPES:
        return True

    from masar_requests.leave_application_permissions import (
        leave_application_has_permission as original,
    )

    result = original(
        doc,
        ptype=ptype,
        user=user,
        permission_type=permission_type,
    )
    return result


# ---------------------------------------------------------------------------
# Official Duty Request
# ---------------------------------------------------------------------------

def _official_related(doc, user):
    """
    AR: تنفيذ الرسمية `related` ضمن وحدة `strict_request_visibility`.
    EN: Execute official related within the `strict_request_visibility` module.
    """
    if _is_system_wide(user):
        return True

    employee = _doc_get(doc, "employee")
    applicant_user = (
        _doc_get(doc, "custom_applicant_user")
        or _employee_user(employee)
    )

    if user in {
        _doc_get(doc, "owner"),
        applicant_user,
        _doc_get(doc, "custom_substitute_user"),
        _doc_get(doc, "custom_direct_manager_user"),
    }:
        return True

    if (
        user == _doc_get(doc, "custom_direct_manager_secretary_user")
        and _doc_get(doc, "workflow_state")
        == "Waiting for Direct Manager Approval"
    ):
        return True

    roles = _roles(user)
    state = _doc_get(doc, "workflow_state")
    processing_status = _doc_get(doc, "processing_status")

    if roles & {"HR Manager", "HR User"}:
        if (
            state in OFFICIAL_HR_STATES
            or processing_status in OFFICIAL_HR_PROCESSING
        ):
            return True

    return False


def official_duty_request_query(user=None):
    """
    AR: تنفيذ الرسمية المهمة الطلب `query` ضمن وحدة `strict_request_visibility`.
    EN: Execute official duty request query within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user

    if _is_system_wide(user):
        return None

    table = "`tabOfficial Duty Request`"
    escaped_user = frappe.db.escape(user)

    conditions = [
        f"{table}.`owner` = {escaped_user}",
        _sql_user_employee_match(
            table,
            "employee",
            escaped_user,
        ),
    ]

    for fieldname in (
        "custom_applicant_user",
        "custom_substitute_user",
        "custom_direct_manager_user",
    ):
        if _meta_has_field("Official Duty Request", fieldname):
            conditions.append(
                f"{table}.`{fieldname}` = {escaped_user}"
            )

    if _meta_has_field(
        "Official Duty Request",
        "custom_direct_manager_secretary_user",
    ):
        conditions.append(
            f"""(
                {table}.`custom_direct_manager_secretary_user` = {escaped_user}
                AND {table}.`workflow_state` =
                    'Waiting for Direct Manager Approval'
            )"""
        )

    roles = _roles(user)

    if roles & {"HR Manager", "HR User"}:
        hr_conditions = [
            f"{table}.`workflow_state` IN "
            "('Waiting for HR Manager Approval', 'Approved')"
        ]

        if _meta_has_field(
            "Official Duty Request",
            "processing_status",
        ):
            hr_conditions.append(
                f"{table}.`processing_status` IN "
                "('Manual Review', 'Partially Reconciled', 'Reconciled')"
            )

        conditions.append("(" + " OR ".join(hr_conditions) + ")")

    return "(" + " OR ".join(conditions) + ")"


def official_duty_request_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    """
    AR: تنفيذ الرسمية المهمة الطلب التحقق من وجود صلاحية ضمن وحدة `strict_request_visibility`.
    EN: Execute official duty request has permission within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user
    requested = permission_type or ptype or "read"

    if requested == "create":
        return None

    if not _official_related(doc, user):
        return False

    if requested in READ_TYPES:
        return True

    from masar_requests.official_duty_request_permissions import (
        official_duty_request_has_permission as original,
    )

    return original(
        doc,
        ptype=ptype,
        user=user,
        permission_type=permission_type,
    )


# ---------------------------------------------------------------------------
# Material Request
# ---------------------------------------------------------------------------

def _material_employee_field():
    """
    AR: تنفيذ المواد الموظف الحقل ضمن وحدة `strict_request_visibility`.
    EN: Execute material employee field within the `strict_request_visibility` module.
    """
    for fieldname in (
        "employee",
        "custom_employee",
        "requesting_employee",
        "custom_requesting_employee",
    ):
        if _meta_has_field("Material Request", fieldname):
            return fieldname
    return None


def _material_related(doc, user):
    """
    AR: تنفيذ المواد `related` ضمن وحدة `strict_request_visibility`.
    EN: Execute material related within the `strict_request_visibility` module.
    """
    roles = _roles(user)

    if (
        _is_system_wide(user)
        or bool(roles & MATERIAL_HIGH_LEVEL_ROLES)
    ):
        return True

    if user == _doc_get(doc, "owner"):
        return True

    applicant_user = _doc_get(doc, "custom_applicant_user")
    if applicant_user and applicant_user == user:
        return True

    employee_field = _material_employee_field()
    if employee_field:
        employee = _doc_get(doc, employee_field)

        if _employee_user(employee) == user:
            return True

    reports_to = _doc_get(doc, "reports_to")
    if reports_to and _employee_user(reports_to) == user:
        return True

    if _current_stage_role_allowed(
        doc,
        user,
        MATERIAL_STAGE_ROLES,
    ):
        return True

    if "Material Request Secretary" in roles:
        return bool(
            frappe.db.exists(
                "DocShare",
                {
                    "share_doctype": "Material Request",
                    "share_name": _doc_get(doc, "name"),
                    "user": user,
                    "read": 1,
                },
            )
        )

    return False


def material_request_query(user=None):
    """
    AR: تنفيذ المواد الطلب `query` ضمن وحدة `strict_request_visibility`.
    EN: Execute material request query within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user
    roles = _roles(user)

    if (
        _is_system_wide(user)
        or bool(roles & MATERIAL_HIGH_LEVEL_ROLES)
    ):
        return None

    table = "`tabMaterial Request`"
    escaped_user = frappe.db.escape(user)

    conditions = [
        f"{table}.`owner` = {escaped_user}",
    ]

    if _meta_has_field(
        "Material Request",
        "custom_applicant_user",
    ):
        conditions.append(
            f"{table}.`custom_applicant_user` = {escaped_user}"
        )

    employee_field = _material_employee_field()
    if employee_field:
        conditions.append(
            _sql_user_employee_match(
                table,
                employee_field,
                escaped_user,
            )
        )

    if _meta_has_field("Material Request", "reports_to"):
        conditions.append(
            _sql_material_reports_to_match(
                table,
                escaped_user,
            )
        )

    for state, role in MATERIAL_STAGE_ROLES.items():
        if role in roles:
            conditions.append(
                f"{table}.`workflow_state` = "
                f"{frappe.db.escape(state)}"
            )

    if "Material Request Secretary" in roles:
        conditions.append(
            _sql_docshare_match(
                "Material Request",
                table,
                escaped_user,
            )
        )

    return "(" + " OR ".join(conditions) + ")"


def material_request_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    """
    AR: تنفيذ المواد الطلب التحقق من وجود صلاحية ضمن وحدة `strict_request_visibility`.
    EN: Execute material request has permission within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user
    requested = permission_type or ptype or "read"

    if requested == "create":
        return None

    if not _material_related(doc, user):
        return False

    if requested in READ_TYPES:
        return True

    from masar_requests.hr_user_read_only import (
        material_request_has_permission as original,
    )

    return original(
        doc,
        ptype=ptype,
        user=user,
        permission_type=permission_type,
    )


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------

@frappe.whitelist()
def verify_document_access(doctype, name, users):
    """
    AR: تنفيذ `verify` المستند الوصول ضمن وحدة `strict_request_visibility`.
    EN: Execute verify document access within the `strict_request_visibility` module.
    """
    if isinstance(users, str):
        users = frappe.parse_json(users)

    doc = frappe.get_doc(doctype, name)
    original_user = frappe.session.user
    rows = []

    query_map = {
        "Leave Application": leave_application_query,
        "Official Duty Request": official_duty_request_query,
        "Material Request": material_request_query,
    }
    permission_map = {
        "Leave Application": leave_application_has_permission,
        "Official Duty Request": official_duty_request_has_permission,
        "Material Request": material_request_has_permission,
    }

    try:
        for user in users:
            frappe.set_user(user)
            rows.append(
                {
                    "user": user,
                    "roles": frappe.get_roles(user),
                    "read": bool(
                        permission_map[doctype](
                            doc,
                            ptype="read",
                            user=user,
                        )
                    ),
                    "write": bool(
                        permission_map[doctype](
                            doc,
                            ptype="write",
                            user=user,
                        )
                    ),
                    "list_condition": query_map[doctype](user),
                }
            )
    finally:
        frappe.set_user(original_user)

    print(frappe.as_json(rows, indent=2))
    return rows


# MASAR_UNIFIED_SECRETARY_VISIBILITY_V22
# These final definitions deliberately replace all earlier secretary-specific
# branches while preserving applicant, manager, HR, material-stage and
# senior-management access.

from masar_requests.secretary_access import (
    has_active_secretary_access,
    secretary_query_condition,
)


def _leave_core_related(doc, user):
    """
    AR: تنفيذ الإجازة `core` `related` ضمن وحدة `strict_request_visibility`.
    EN: Execute leave core related within the `strict_request_visibility` module.
    """
    if _is_system_wide(user):
        return True

    applicant_user = _employee_user(_doc_get(doc, "employee"))

    if user in {
        _doc_get(doc, "owner"),
        applicant_user,
        _doc_get(doc, "custom_substitute_user"),
        _doc_get(doc, "custom_direct_manager_user"),
    }:
        return True

    roles = _roles(user)
    state = _doc_get(doc, "workflow_state")

    if roles & {"HR Manager", "HR User"}:
        if state in LEAVE_HR_STATES:
            return True

        if (
            state == "Rejected"
            and _doc_get(doc, "custom_direct_manager_approval")
            == "Approved"
        ):
            return True

    return False


def leave_application_query(user=None):
    """
    AR: تنفيذ الإجازة `application` `query` ضمن وحدة `strict_request_visibility`.
    EN: Execute leave application query within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user

    if _is_system_wide(user):
        return None

    table = "`tabLeave Application`"
    escaped_user = frappe.db.escape(user)

    conditions = [
        f"{table}.`owner` = {escaped_user}",
        _sql_user_employee_match(
            table,
            "employee",
            escaped_user,
        ),
    ]

    for fieldname in (
        "custom_substitute_user",
        "custom_direct_manager_user",
    ):
        if _meta_has_field("Leave Application", fieldname):
            conditions.append(
                f"{table}.`{fieldname}` = {escaped_user}"
            )

    roles = _roles(user)

    if roles & {"HR Manager", "HR User"}:
        hr_conditions = [
            f"{table}.`workflow_state` IN "
            "('Waiting for HR Manager Approval', 'Approved')"
        ]

        if _meta_has_field(
            "Leave Application",
            "custom_direct_manager_approval",
        ):
            hr_conditions.append(
                f"""(
                    {table}.`workflow_state` = 'Rejected'
                    AND {table}.`custom_direct_manager_approval` = 'Approved'
                )"""
            )

        conditions.append("(" + " OR ".join(hr_conditions) + ")")

    conditions.append(
        secretary_query_condition(
            "Leave Application",
            table,
            user,
        )
    )

    return "(" + " OR ".join(conditions) + ")"


def leave_application_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    """
    AR: تنفيذ الإجازة `application` التحقق من وجود صلاحية ضمن وحدة `strict_request_visibility`.
    EN: Execute leave application has permission within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user
    requested = permission_type or ptype or "read"

    if requested == "create":
        return None

    core_related = _leave_core_related(doc, user)
    secretary_related = has_active_secretary_access(
        "Leave Application",
        _doc_get(doc, "name"),
        user,
    )

    if not core_related and not secretary_related:
        return False

    if requested in READ_TYPES:
        return True

    if secretary_related and not core_related:
        return False

    from masar_requests.leave_application_permissions import (
        leave_application_has_permission as original,
    )

    return original(
        doc,
        ptype=ptype,
        user=user,
        permission_type=permission_type,
    )


def _official_core_related(doc, user):
    """
    AR: تنفيذ الرسمية `core` `related` ضمن وحدة `strict_request_visibility`.
    EN: Execute official core related within the `strict_request_visibility` module.
    """
    if _is_system_wide(user):
        return True

    applicant_user = (
        _doc_get(doc, "custom_applicant_user")
        or _employee_user(_doc_get(doc, "employee"))
    )

    if user in {
        _doc_get(doc, "owner"),
        applicant_user,
        _doc_get(doc, "custom_substitute_user"),
        _doc_get(doc, "custom_direct_manager_user"),
    }:
        return True

    roles = _roles(user)
    state = _doc_get(doc, "workflow_state")
    processing_status = _doc_get(doc, "processing_status")

    if roles & {"HR Manager", "HR User"}:
        if (
            state in OFFICIAL_HR_STATES
            or processing_status in OFFICIAL_HR_PROCESSING
        ):
            return True

    return False


def official_duty_request_query(user=None):
    """
    AR: تنفيذ الرسمية المهمة الطلب `query` ضمن وحدة `strict_request_visibility`.
    EN: Execute official duty request query within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user

    if _is_system_wide(user):
        return None

    table = "`tabOfficial Duty Request`"
    escaped_user = frappe.db.escape(user)

    conditions = [
        f"{table}.`owner` = {escaped_user}",
        _sql_user_employee_match(
            table,
            "employee",
            escaped_user,
        ),
    ]

    for fieldname in (
        "custom_applicant_user",
        "custom_substitute_user",
        "custom_direct_manager_user",
    ):
        if _meta_has_field("Official Duty Request", fieldname):
            conditions.append(
                f"{table}.`{fieldname}` = {escaped_user}"
            )

    roles = _roles(user)

    if roles & {"HR Manager", "HR User"}:
        hr_conditions = [
            f"{table}.`workflow_state` IN "
            "('Waiting for HR Manager Approval', 'Approved')"
        ]

        if _meta_has_field(
            "Official Duty Request",
            "processing_status",
        ):
            hr_conditions.append(
                f"{table}.`processing_status` IN "
                "('Manual Review', 'Partially Reconciled', 'Reconciled')"
            )

        conditions.append("(" + " OR ".join(hr_conditions) + ")")

    conditions.append(
        secretary_query_condition(
            "Official Duty Request",
            table,
            user,
        )
    )

    return "(" + " OR ".join(conditions) + ")"


def official_duty_request_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    """
    AR: تنفيذ الرسمية المهمة الطلب التحقق من وجود صلاحية ضمن وحدة `strict_request_visibility`.
    EN: Execute official duty request has permission within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user
    requested = permission_type or ptype or "read"

    if requested == "create":
        return None

    core_related = _official_core_related(doc, user)
    secretary_related = has_active_secretary_access(
        "Official Duty Request",
        _doc_get(doc, "name"),
        user,
    )

    if not core_related and not secretary_related:
        return False

    if requested in READ_TYPES:
        return True

    if secretary_related and not core_related:
        return False

    from masar_requests.official_duty_request_permissions import (
        official_duty_request_has_permission as original,
    )

    return original(
        doc,
        ptype=ptype,
        user=user,
        permission_type=permission_type,
    )


def _material_core_related(doc, user):
    """
    AR: تنفيذ المواد `core` `related` ضمن وحدة `strict_request_visibility`.
    EN: Execute material core related within the `strict_request_visibility` module.
    """
    roles = _roles(user)

    if (
        _is_system_wide(user)
        or bool(roles & MATERIAL_HIGH_LEVEL_ROLES)
    ):
        return True

    if user == _doc_get(doc, "owner"):
        return True

    applicant_user = _doc_get(doc, "custom_applicant_user")
    if applicant_user and applicant_user == user:
        return True

    employee_field = _material_employee_field()
    if employee_field:
        employee = _doc_get(doc, employee_field)
        if _employee_user(employee) == user:
            return True

    reports_to = _doc_get(doc, "reports_to")
    if reports_to and _employee_user(reports_to) == user:
        return True

    if _current_stage_role_allowed(
        doc,
        user,
        MATERIAL_STAGE_ROLES,
    ):
        return True

    return False


def material_request_query(user=None):
    """
    AR: تنفيذ المواد الطلب `query` ضمن وحدة `strict_request_visibility`.
    EN: Execute material request query within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user
    roles = _roles(user)

    if (
        _is_system_wide(user)
        or bool(roles & MATERIAL_HIGH_LEVEL_ROLES)
    ):
        return None

    table = "`tabMaterial Request`"
    escaped_user = frappe.db.escape(user)

    conditions = [
        f"{table}.`owner` = {escaped_user}",
    ]

    if _meta_has_field(
        "Material Request",
        "custom_applicant_user",
    ):
        conditions.append(
            f"{table}.`custom_applicant_user` = {escaped_user}"
        )

    employee_field = _material_employee_field()
    if employee_field:
        conditions.append(
            _sql_user_employee_match(
                table,
                employee_field,
                escaped_user,
            )
        )

    if _meta_has_field("Material Request", "reports_to"):
        conditions.append(
            _sql_material_reports_to_match(
                table,
                escaped_user,
            )
        )

    for state, role in MATERIAL_STAGE_ROLES.items():
        if role in roles:
            conditions.append(
                f"{table}.`workflow_state` = "
                f"{frappe.db.escape(state)}"
            )

    conditions.append(
        secretary_query_condition(
            "Material Request",
            table,
            user,
        )
    )

    return "(" + " OR ".join(conditions) + ")"


def material_request_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    """
    AR: تنفيذ المواد الطلب التحقق من وجود صلاحية ضمن وحدة `strict_request_visibility`.
    EN: Execute material request has permission within the `strict_request_visibility` module.
    """
    user = user or frappe.session.user
    requested = permission_type or ptype or "read"

    if requested == "create":
        return None

    core_related = _material_core_related(doc, user)
    secretary_related = has_active_secretary_access(
        "Material Request",
        _doc_get(doc, "name"),
        user,
    )

    if not core_related and not secretary_related:
        return False

    if requested in READ_TYPES:
        return True

    if secretary_related and not core_related:
        return False

    from masar_requests.hr_user_read_only import (
        material_request_has_permission as original,
    )

    return original(
        doc,
        ptype=ptype,
        user=user,
        permission_type=permission_type,
    )
