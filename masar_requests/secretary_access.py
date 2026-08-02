"""
AR: تنفيذ وظائف تطبيق مسار ضمن الوحدة `secretary_access`.
EN: Masar application functionality implemented by the `secretary_access` module.
"""

from __future__ import annotations

from collections.abc import Iterable

import frappe
from frappe import _
from frappe.utils import now_datetime


TRACKING_DOCTYPE = "Masar Secretary Access"

SUPPORTED_DOCTYPES = {
    "Leave Application",
    "Official Duty Request",
    "Material Request",
}

DIRECT_MANAGER_STATE = "Waiting for Direct Manager Approval"

MATERIAL_STAGE_ROLES = {
    "Pending Stock Check": "Warehouse Manager",
    "Pending HR Manager": "HR Manager",
    "Pending Accounts Manager": "Accounts Manager",
    "Pending Sec Gen": "Secretary General",
    "Pending President": "University President",
}

MATERIAL_DIRECT_MANAGER_STATES = {
    "Pending Direct Supervisor",
    "Waiting for Direct Manager Approval",
}

SECRETARY_USER_FIELDS = (
    "custom_secretary_user",
    "secretary_user",
)

SECRETARY_EMPLOYEE_FIELDS = (
    "custom_secretary_employee",
    "secretary_employee",
    "custom_secretary",
    "secretary",
)


def _unique(values: Iterable[str | None]) -> list[str]:
    """
    AR: تنفيذ `unique` ضمن وحدة `secretary_access`.
    EN: Execute unique within the `secretary_access` module.
    """
    return list(dict.fromkeys(value for value in values if value))


def _enabled_user(user: str | None) -> bool:
    """
    AR: تنفيذ `enabled` المستخدم ضمن وحدة `secretary_access`.
    EN: Execute enabled user within the `secretary_access` module.
    """
    return bool(
        user
        and user != "Guest"
        and frappe.db.exists("User", user)
        and frappe.db.get_value("User", user, "enabled")
    )


def _employee_for_user(user: str | None) -> str | None:
    """
    AR: تنفيذ الموظف `for` المستخدم ضمن وحدة `secretary_access`.
    EN: Execute employee for user within the `secretary_access` module.
    """
    if not user:
        return None

    return frappe.db.get_value(
        "Employee",
        {
            "user_id": user,
            "status": "Active",
        },
        "name",
    )


def _user_for_employee(employee: str | None) -> str | None:
    """
    AR: تنفيذ المستخدم `for` الموظف ضمن وحدة `secretary_access`.
    EN: Execute user for employee within the `secretary_access` module.
    """
    if not employee:
        return None

    user = frappe.db.get_value("Employee", employee, "user_id")
    return user if _enabled_user(user) else None


def _direct_manager_user(doc) -> str | None:
    """
    AR: تنفيذ `direct` المدير المستخدم ضمن وحدة `secretary_access`.
    EN: Execute direct manager user within the `secretary_access` module.
    """
    explicit = doc.get("custom_direct_manager_user")
    if _enabled_user(explicit):
        return explicit

    reports_to = doc.get("reports_to")
    if reports_to:
        user = _user_for_employee(reports_to)
        if user:
            return user

    employee = (
        doc.get("employee")
        or doc.get("custom_employee")
        or doc.get("requesting_employee")
        or doc.get("custom_requesting_employee")
    )
    if not employee:
        return None

    manager_employee = frappe.db.get_value(
        "Employee",
        employee,
        "reports_to",
    )
    return _user_for_employee(manager_employee)


def _enabled_users_with_role(role: str) -> list[str]:
    """
    AR: تنفيذ `enabled` `users` `with` الدور ضمن وحدة `secretary_access`.
    EN: Execute enabled users with role within the `secretary_access` module.
    """
    users = frappe.get_all(
        "Has Role",
        filters={
            "role": role,
            "parenttype": "User",
        },
        pluck="parent",
    )

    return _unique(
        user
        for user in users
        if user != "Administrator" and _enabled_user(user)
    )


def get_secretaries_for_actor(actor_user: str) -> list[str]:
    """
    AR: تنفيذ استرجاع `secretaries` `for` `actor` ضمن وحدة `secretary_access`.
    EN: Execute get secretaries for actor within the `secretary_access` module.

    DETAILS / التفاصيل:
    Resolve secretary accounts from the actor's active Employee record.

        Both direct User fields and Employee-link fields are supported so the
        service remains compatible with existing installations.
    """
    employee = _employee_for_user(actor_user)
    if not employee:
        return []

    meta = frappe.get_meta("Employee", cached=False)
    secretaries = []

    for fieldname in SECRETARY_USER_FIELDS:
        field = meta.get_field(fieldname)
        if not field:
            continue

        value = frappe.db.get_value("Employee", employee, fieldname)
        if _enabled_user(value):
            secretaries.append(value)

    for fieldname in SECRETARY_EMPLOYEE_FIELDS:
        field = meta.get_field(fieldname)
        if not field:
            continue

        value = frappe.db.get_value("Employee", employee, fieldname)
        if not value:
            continue

        if field.options == "User" and _enabled_user(value):
            secretaries.append(value)
            continue

        secretary_user = _user_for_employee(value)
        if secretary_user:
            secretaries.append(secretary_user)

    return _unique(secretaries)


def _explicit_direct_manager_secretaries(doc) -> list[str]:
    """
    AR: تنفيذ `explicit` `direct` المدير `secretaries` ضمن وحدة `secretary_access`.
    EN: Execute explicit direct manager secretaries within the `secretary_access` module.
    """
    users = []

    for fieldname in (
        "custom_direct_manager_secretary_user",
        "direct_manager_secretary_user",
    ):
        value = doc.get(fieldname)
        if _enabled_user(value):
            users.append(value)

    return _unique(users)


def get_current_actor_users(doc) -> list[str]:
    """
    AR: تنفيذ استرجاع الحالي `actor` `users` ضمن وحدة `secretary_access`.
    EN: Execute get current actor users within the `secretary_access` module.
    """
    state = doc.get("workflow_state")

    if doc.doctype in {
        "Leave Application",
        "Official Duty Request",
    }:
        if state != DIRECT_MANAGER_STATE:
            return []

        return _unique([_direct_manager_user(doc)])

    if doc.doctype == "Material Request":
        if state in MATERIAL_DIRECT_MANAGER_STATES:
            return _unique([_direct_manager_user(doc)])

        role = MATERIAL_STAGE_ROLES.get(state)
        if role:
            return _enabled_users_with_role(role)

    return []


def get_desired_access_pairs(doc) -> set[tuple[str, str]]:
    """
    AR: تنفيذ استرجاع `desired` الوصول `pairs` ضمن وحدة `secretary_access`.
    EN: Execute get desired access pairs within the `secretary_access` module.

    DETAILS / التفاصيل:
    Return {(actor_user, secretary_user), ...} for the current stage.
    """
    if (
        not doc
        or doc.doctype not in SUPPORTED_DOCTYPES
        or doc.docstatus == 2
    ):
        return set()

    pairs = set()
    actors = get_current_actor_users(doc)

    for actor_user in actors:
        secretaries = get_secretaries_for_actor(actor_user)

        if doc.doctype in {
            "Leave Application",
            "Official Duty Request",
        }:
            secretaries = _unique(
                secretaries
                + _explicit_direct_manager_secretaries(doc)
            )

        for secretary_user in secretaries:
            if secretary_user == actor_user:
                continue
            pairs.add((actor_user, secretary_user))

    return pairs


def _existing_share(doc, user: str) -> str | None:
    """
    AR: تنفيذ الموجود مشاركة ضمن وحدة `secretary_access`.
    EN: Execute existing share within the `secretary_access` module.
    """
    return frappe.db.get_value(
        "DocShare",
        {
            "share_doctype": doc.doctype,
            "share_name": doc.name,
            "user": user,
        },
        "name",
    )


def _grant_read_share(doc, user: str) -> bool:
    """
    AR: تنفيذ منح القراءة مشاركة ضمن وحدة `secretary_access`.
    EN: Execute grant read share within the `secretary_access` module.

    DETAILS / التفاصيل:
    Return True when the unified service owns the secretary share.

        A pre-existing strictly read-only share is adopted because the legacy
        secretary role/sharing code has been retired. Elevated or unrelated
        shares are never adopted or removed by this service.
    """
    existing_name = _existing_share(doc, user)

    if existing_name:
        permissions = frappe.db.get_value(
            "DocShare",
            existing_name,
            ["read", "write", "submit", "share"],
            as_dict=True,
        ) or {}

        is_strict_read_only = bool(permissions.get("read")) and not any(
            permissions.get(fieldname)
            for fieldname in ("write", "submit", "share")
        )
        return is_strict_read_only

    from frappe import share as frappe_share

    frappe_share.add_docshare(
        doctype=doc.doctype,
        name=doc.name,
        user=user,
        read=1,
        write=0,
        submit=0,
        share=0,
        notify=0,
        flags={"ignore_share_permission": True},
    )
    return True

def _remove_service_share(doc, user: str) -> None:
    """
    AR: تنفيذ إزالة `service` مشاركة ضمن وحدة `secretary_access`.
    EN: Execute remove service share within the `secretary_access` module.
    """
    names = frappe.get_all(
        "DocShare",
        filters={
            "share_doctype": doc.doctype,
            "share_name": doc.name,
            "user": user,
        },
        pluck="name",
    )

    for name in names:
        frappe.delete_doc(
            "DocShare",
            name,
            ignore_permissions=True,
            force=True,
        )


def _existing_open_todo(doc, user: str) -> str | None:
    """
    AR: تنفيذ الموجود فتح `todo` ضمن وحدة `secretary_access`.
    EN: Execute existing open todo within the `secretary_access` module.
    """
    return frappe.db.get_value(
        "ToDo",
        {
            "allocated_to": user,
            "reference_type": doc.doctype,
            "reference_name": doc.name,
            "status": "Open",
        },
        "name",
    )


def _create_todo(doc, user: str) -> tuple[str | None, bool]:
    """
    AR: تنفيذ إنشاء `todo` ضمن وحدة `secretary_access`.
    EN: Execute create todo within the `secretary_access` module.
    """
    existing = _existing_open_todo(doc, user)
    if existing:
        return existing, False

    todo = frappe.get_doc(
        {
            "doctype": "ToDo",
            "allocated_to": user,
            "reference_type": doc.doctype,
            "reference_name": doc.name,
            "description": _(
                "Follow up {0} {1} while it is awaiting your manager."
            ).format(_(doc.doctype), doc.name),
            "priority": "Medium",
            "status": "Open",
            "assigned_by": frappe.session.user or "Administrator",
        }
    )
    todo.insert(ignore_permissions=True)
    return todo.name, True


def _close_service_todo(name: str | None) -> None:
    """
    AR: تنفيذ إغلاق `service` `todo` ضمن وحدة `secretary_access`.
    EN: Execute close service todo within the `secretary_access` module.
    """
    if not name or not frappe.db.exists("ToDo", name):
        return

    frappe.db.set_value(
        "ToDo",
        name,
        {
            "status": "Closed",
            "date": now_datetime(),
        },
        update_modified=False,
    )


def _notification_subject(doc) -> str:
    """
    AR: تنفيذ الإشعار `subject` ضمن وحدة `secretary_access`.
    EN: Execute notification subject within the `secretary_access` module.
    """
    return _(
        "{0} {1} is awaiting action from the manager you support."
    ).format(_(doc.doctype), doc.name)


def _send_notification_once(doc, secretary_user: str) -> None:
    """
    AR: تنفيذ `send` الإشعار `once` ضمن وحدة `secretary_access`.
    EN: Execute send notification once within the `secretary_access` module.
    """
    subject = _notification_subject(doc)

    exists = frappe.db.exists(
        "Notification Log",
        {
            "for_user": secretary_user,
            "document_type": doc.doctype,
            "document_name": doc.name,
            "subject": subject,
        },
    )
    if exists:
        return

    notification = frappe.get_doc(
        {
            "doctype": "Notification Log",
            "subject": subject,
            "for_user": secretary_user,
            "document_type": doc.doctype,
            "document_name": doc.name,
            "type": "Alert",
        }
    )
    notification.insert(ignore_permissions=True)


def _active_records(doc) -> list:
    """
    AR: تنفيذ النشط `records` ضمن وحدة `secretary_access`.
    EN: Execute active records within the `secretary_access` module.
    """
    if not frappe.db.exists("DocType", TRACKING_DOCTYPE):
        return []

    names = frappe.get_all(
        TRACKING_DOCTYPE,
        filters={
            "reference_doctype": doc.doctype,
            "reference_name": doc.name,
            "active": 1,
        },
        pluck="name",
    )
    return [frappe.get_doc(TRACKING_DOCTYPE, name) for name in names]


def _grant_pair(doc, actor_user: str, secretary_user: str) -> None:
    """
    AR: تنفيذ منح `pair` ضمن وحدة `secretary_access`.
    EN: Execute grant pair within the `secretary_access` module.
    """
    existing_name = frappe.db.get_value(
        TRACKING_DOCTYPE,
        {
            "reference_doctype": doc.doctype,
            "reference_name": doc.name,
            "actor_user": actor_user,
            "secretary_user": secretary_user,
            "active": 1,
        },
        "name",
    )
    if existing_name:
        frappe.db.set_value(
            TRACKING_DOCTYPE,
            existing_name,
            "workflow_state",
            doc.get("workflow_state"),
            update_modified=False,
        )
        return

    share_created = _grant_read_share(doc, secretary_user)
    todo_name, todo_created = _create_todo(doc, secretary_user)

    access = frappe.get_doc(
        {
            "doctype": TRACKING_DOCTYPE,
            "reference_doctype": doc.doctype,
            "reference_name": doc.name,
            "actor_user": actor_user,
            "secretary_user": secretary_user,
            "workflow_state": doc.get("workflow_state"),
            "active": 1,
            "share_created_by_service": int(share_created),
            "todo": todo_name,
            "todo_created_by_service": int(todo_created),
            "granted_on": now_datetime(),
        }
    )
    access.insert(ignore_permissions=True)

    _send_notification_once(doc, secretary_user)


def _revoke_record(doc, access) -> None:
    """
    AR: تنفيذ سحب `record` ضمن وحدة `secretary_access`.
    EN: Execute revoke record within the `secretary_access` module.
    """
    if access.get("share_created_by_service"):
        _remove_service_share(doc, access.secretary_user)

    if access.get("todo_created_by_service"):
        _close_service_todo(access.todo)

    access.db_set(
        {
            "active": 0,
            "revoked_on": now_datetime(),
        },
        update_modified=False,
    )


def sync_secretary_access(doc, method=None):
    """
    AR: تنفيذ مزامنة السكرتير الوصول ضمن وحدة `secretary_access`.
    EN: Execute sync secretary access within the `secretary_access` module.

    DETAILS / التفاصيل:
    Central event handler used by all supported request DocTypes.
    """
    if (
        not doc
        or doc.doctype not in SUPPORTED_DOCTYPES
        or not doc.get("name")
        or not frappe.db.exists("DocType", TRACKING_DOCTYPE)
    ):
        return

    desired = get_desired_access_pairs(doc)
    active_records = _active_records(doc)
    active_pairs = {
        (record.actor_user, record.secretary_user): record
        for record in active_records
    }

    for pair, record in active_pairs.items():
        if pair not in desired:
            _revoke_record(doc, record)

    for actor_user, secretary_user in desired:
        if (actor_user, secretary_user) not in active_pairs:
            _grant_pair(doc, actor_user, secretary_user)


def revoke_secretary_access(doc, method=None):
    """
    AR: تنفيذ سحب السكرتير الوصول ضمن وحدة `secretary_access`.
    EN: Execute revoke secretary access within the `secretary_access` module.
    """
    if (
        not doc
        or not doc.get("name")
        or not frappe.db.exists("DocType", TRACKING_DOCTYPE)
    ):
        return

    for access in _active_records(doc):
        _revoke_record(doc, access)


def has_active_secretary_access(
    doctype: str,
    name: str,
    user: str | None = None,
) -> bool:
    """
    AR: تنفيذ التحقق من وجود النشط السكرتير الوصول ضمن وحدة `secretary_access`.
    EN: Execute has active secretary access within the `secretary_access` module.
    """
    user = user or frappe.session.user

    if not name or not user:
        return False

    if not frappe.db.exists("DocType", TRACKING_DOCTYPE):
        return False

    return bool(
        frappe.db.exists(
            TRACKING_DOCTYPE,
            {
                "reference_doctype": doctype,
                "reference_name": name,
                "secretary_user": user,
                "active": 1,
            },
        )
    )


def secretary_query_condition(
    doctype: str,
    table: str,
    user: str | None = None,
) -> str:
    """
    AR: تنفيذ السكرتير `query` `condition` ضمن وحدة `secretary_access`.
    EN: Execute secretary query condition within the `secretary_access` module.
    """
    user = user or frappe.session.user

    if not frappe.db.exists("DocType", TRACKING_DOCTYPE):
        return "0=1"

    return f"""EXISTS (
        SELECT 1
          FROM `tab{TRACKING_DOCTYPE}` secretary_access
         WHERE secretary_access.`reference_doctype` =
               {frappe.db.escape(doctype)}
           AND secretary_access.`reference_name` = {table}.`name`
           AND secretary_access.`secretary_user` =
               {frappe.db.escape(user)}
           AND secretary_access.`active` = 1
    )"""


@frappe.whitelist()
def audit_document(doctype: str, name: str):
    """
    AR: تنفيذ تدقيق المستند ضمن وحدة `secretary_access`.
    EN: Execute audit document within the `secretary_access` module.
    """
    doc = frappe.get_doc(doctype, name)

    result = {
        "doctype": doctype,
        "name": name,
        "workflow_state": doc.get("workflow_state"),
        "actors": get_current_actor_users(doc),
        "desired_pairs": sorted(
            [list(pair) for pair in get_desired_access_pairs(doc)]
        ),
        "active_access": frappe.get_all(
            TRACKING_DOCTYPE,
            filters={
                "reference_doctype": doctype,
                "reference_name": name,
                "active": 1,
            },
            fields=[
                "actor_user",
                "secretary_user",
                "workflow_state",
                "share_created_by_service",
                "todo",
                "todo_created_by_service",
            ],
        ),
    }

    print(frappe.as_json(result, indent=2))
    return result
