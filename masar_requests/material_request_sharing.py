import frappe
from frappe import share as frappe_share


STATE_ROLE_MAP = {
    "Pending Stock Check": "Warehouse Manager",
    "Pending HR Manager": "HR Manager",
    "Pending Accounts Manager": "Accounts Manager",
    "Pending Sec Gen": "Secretary General",
    "Pending President": "University President",
}


def get_employee_user(employee):
    """Return the enabled User linked to an Employee."""
    if not employee:
        return None

    user = frappe.db.get_value("Employee", employee, "user_id")

    if not user:
        return None

    if not frappe.db.get_value("User", user, "enabled"):
        return None

    return user


def get_user_secretary(target_user):
    """Return the enabled secretary User linked to a principal User."""
    if not target_user:
        return None

    employee_meta = frappe.get_meta("Employee")

    if not employee_meta.has_field("custom_secretary_employee"):
        return None

    principal_employee = frappe.db.get_value(
        "Employee",
        {"user_id": target_user},
        "name",
    )

    if not principal_employee:
        return None

    secretary_employee = frappe.db.get_value(
        "Employee",
        principal_employee,
        "custom_secretary_employee",
    )

    if not secretary_employee:
        return None

    secretary_user = frappe.db.get_value(
        "Employee",
        secretary_employee,
        "user_id",
    )

    if not secretary_user:
        return None

    if not frappe.db.get_value("User", secretary_user, "enabled"):
        return None

    return secretary_user


def get_enabled_users_with_role(role):
    """Return enabled users assigned to a role."""
    users = frappe.get_all(
        "Has Role",
        filters={
            "role": role,
            "parenttype": "User",
        },
        pluck="parent",
    )

    return {
        user
        for user in users
        if user
        and user != "Administrator"
        and frappe.db.get_value("User", user, "enabled")
    }


def get_all_secretary_users():
    """Return all users configured as secretaries in Employee records."""
    employee_meta = frappe.get_meta("Employee")

    if not employee_meta.has_field("custom_secretary_employee"):
        return set()

    secretary_employees = frappe.get_all(
        "Employee",
        filters={
            "custom_secretary_employee": ["is", "set"],
        },
        pluck="custom_secretary_employee",
    )

    secretary_users = set()

    for secretary_employee in secretary_employees:
        secretary_user = frappe.db.get_value(
            "Employee",
            secretary_employee,
            "user_id",
        )

        if secretary_user and secretary_user != "Administrator":
            secretary_users.add(secretary_user)

    return secretary_users


def upsert_share(doc, target_user, can_write=False):
    """
    Grant exact access:
    - Current actor: read/write.
    - Current actor's secretary: read-only.
    """
    if (
        not target_user
        or target_user == "Administrator"
        or not frappe.db.exists("User", target_user)
    ):
        return False

    frappe_share.add_docshare(
        doc.doctype,
        doc.name,
        target_user,
        read=1,
        write=1 if can_write else 0,
        submit=0,
        share=0,
        notify=0,
        flags={"ignore_share_permission": True},
    )

    return True


def remove_share(doc, target_user):
    """Remove an obsolete user-specific DocShare."""
    if not target_user or target_user == "Administrator":
        return False

    share_names = frappe.get_all(
        "DocShare",
        filters={
            "share_doctype": doc.doctype,
            "share_name": doc.name,
            "user": target_user,
        },
        pluck="name",
    )

    for share_name in share_names:
        frappe.delete_doc(
            "DocShare",
            share_name,
            ignore_permissions=True,
            force=True,
        )

    return bool(share_names)


def get_current_actor_users(doc):
    """Resolve the users responsible for the current workflow stage."""
    actor_users = set()

    if doc.workflow_state == "Pending Direct Supervisor":
        manager_user = get_employee_user(doc.reports_to)

        if manager_user and manager_user != "Administrator":
            actor_users.add(manager_user)

    elif doc.workflow_state in STATE_ROLE_MAP:
        actor_users.update(
            get_enabled_users_with_role(
                STATE_ROLE_MAP[doc.workflow_state]
            )
        )

    return actor_users


def sync_material_request_shares(doc, method=None):
    """
    Synchronize Material Request access with its current workflow stage.

    Current actor:
        read + write

    Current actor's secretary:
        read + print only

    A secretary's share is removed when their principal is no longer
    responsible for the current workflow stage.
    """
    if not doc or doc.doctype != "Material Request" or not doc.name:
        return

    try:
        actor_users = get_current_actor_users(doc)

        secretary_users = {
            secretary_user
            for actor_user in actor_users
            if (secretary_user := get_user_secretary(actor_user))
        }

        managed_secretaries = get_all_secretary_users()

        # Remove secretary access after the principal's stage ends.
        for secretary_user in managed_secretaries:
            if (
                secretary_user not in secretary_users
                and secretary_user not in actor_users
            ):
                remove_share(doc, secretary_user)

        # A secretary receives read-only access.
        for secretary_user in secretary_users:
            upsert_share(
                doc,
                secretary_user,
                can_write=False,
            )

        # If a user is also an actual workflow actor, actor access wins.
        for actor_user in actor_users:
            upsert_share(
                doc,
                actor_user,
                can_write=True,
            )

    except Exception:
        frappe.log_error(
            title="Material Request Share Synchronization Failed",
            message=frappe.get_traceback(),
        )

        # Do not silently move the workflow while permissions are broken.
        raise


def resync_all_material_request_shares():
    """Apply the current sharing rules to all existing requests."""
    request_names = frappe.get_all(
        "Material Request",
        pluck="name",
    )

    for request_name in request_names:
        doc = frappe.get_doc(
            "Material Request",
            request_name,
        )

        sync_material_request_shares(
            doc,
            method="manual_resync",
        )

    frappe.db.commit()
    frappe.clear_cache(doctype="Material Request")

    return {
        "processed_requests": len(request_names),
    }
