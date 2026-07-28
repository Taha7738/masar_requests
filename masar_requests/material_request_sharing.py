import frappe
from frappe import share as frappe_share

from masar_requests.constants import (
    MR_STATE_PENDING_DIRECT_SUPERVISOR,
    MR_STATE_ROLE_MAP,
)


STATE_ROLE_MAP = MR_STATE_ROLE_MAP


def get_employee_user(employee):
    # AR: جلب حساب المستخدم المفعّل المرتبط بالموظف.
    # EN: Return the enabled User linked to an Employee.
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
    # AR: جلب حساب السكرتير المفعّل المرتبط بالمستخدم.
    # EN: Return the enabled secretary User linked to a principal.
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
    # AR: جلب المستخدمين المفعّلين الذين يحملون دورًا محددًا.
    # EN: Return enabled users assigned to a role.
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
    # AR: جلب جميع المستخدمين المسجلين كسكرتارية للموظفين.
    # EN: Return all Users configured as Employee secretaries.
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
    # AR: إنشاء أو تحديث المشاركة مع تجاوز صارم لقيود المشاركة
    if (
        not target_user
        or target_user == "Administrator"
        or not frappe.db.exists("User", target_user)
    ):
        return False

    existing_share = frappe.db.get_value(
        "DocShare",
        {
            "share_doctype": doc.doctype,
            "share_name": doc.name,
            "user": target_user,
        },
        "name"
    )

    if existing_share:
        # التحديث المباشر في قاعدة البيانات يتجاوز فحص الصلاحيات
        frappe.db.set_value(
            "DocShare",
            existing_share,
            {
                "read": 1,
                "write": 1 if can_write else 0,
            },
            update_modified=False,
        )
    else:
        # الإنشاء مع إيقاف فحص المشاركة برمجياً
        share = frappe.new_doc("DocShare")
        share.share_doctype = doc.doctype
        share.share_name = doc.name
        share.user = target_user
        share.read = 1
        share.write = 1 if can_write else 0
        share.submit = 0
        share.share = 0
        share.flags.ignore_share_permission = True
        share.insert(ignore_permissions=True)

    return True


def remove_share(doc, target_user):
    # AR: حذف مشاركة قديمة مع تجاوز صارم لقيود المشاركة لتجنب انهيار مسار العمل
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
        # الحل الجذري: جلب المستند وتفعيل علم التجاوز قبل الحذف
        share_doc = frappe.get_doc("DocShare", share_name)
        share_doc.flags.ignore_share_permission = True
        share_doc.delete(ignore_permissions=True)

    return bool(share_names)

def get_current_actor_users(doc):
    # AR: تحديد المستخدمين المسؤولين عن مرحلة طلب المواد الحالية.
    # EN: Resolve users responsible for the current Material Request stage.
    """Resolve the users responsible for the current workflow stage."""
    actor_users = set()

    if doc.workflow_state == MR_STATE_PENDING_DIRECT_SUPERVISOR:
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
    # AR: مزامنة وصول المسؤول الحالي وسكرتيره إلى طلب المواد.
    # EN: Synchronize current actor and secretary access to a request.
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
    # AR: إعادة مزامنة مشاركات جميع طلبات المواد.
    # EN: Re-synchronize shares for every Material Request.
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
