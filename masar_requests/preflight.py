"""
AR: فحص جاهزية Masar Requests قبل التسليم أو التشغيل في موقع العميل.
EN: Masar Requests production-readiness checks for a customer site.
"""

import frappe

from masar_requests import hooks as app_hooks


WORKFLOW_ROLES = (
    "Warehouse Manager",
    "HR Manager",
    "Accounts Manager",
    "Secretary General",
    "University President",
)

MATERIAL_REQUEST_ENGINE_HOOK = (
    "masar_requests.material_request_engine.before_save_material_request"
)


def _enabled_users_with_role(role):
    """AR: المستخدمون المفعلون في دور محدد. EN: Enabled users for one role."""
    users = frappe.get_all(
        "Has Role",
        filters={"parenttype": "User", "role": role},
        pluck="parent",
    )

    return sorted(
        user
        for user in set(users)
        if user and frappe.db.get_value("User", user, "enabled")
    )


def run_preflight():
    """
    AR:
        فحص للقراءة فقط؛ لا يعدّل أي بيانات. شغّله بعد ضبط الموظفين والأدوار
        وقبل تسليم الموقع. تكون النتيجة جاهزة فقط عندما تكون errors فارغة.

    EN:
        Read-only validation; it never changes data. Run it after employee and
        role configuration and before handover. The site is ready only when
        the errors list is empty.
    """
    result = {
        "ready": False,
        "errors": [],
        "warnings": [],
        "info": [],
    }

    # AR: التحقق من محرك Python الأصلي بدل Server Script القديم المحذوف.
    # EN: Validate the native Python engine instead of the removed Server Script.
    before_save_hook = (
        app_hooks.doc_events.get("Material Request", {}).get("before_save")
    )
    if before_save_hook != MATERIAL_REQUEST_ENGINE_HOOK:
        result["errors"].append(
            "Material Request native before_save engine is not registered in hooks.py."
        )

    legacy_scripts = (
        "Auto Share MR with Direct Supervisor masar_requests",
        "Warehouse Fission Engine masar_requests",
    )
    for script_name in legacy_scripts:
        if frappe.db.exists("Server Script", script_name):
            result["warnings"].append(
                f"Legacy Server Script still exists and should be removed: {script_name}."
            )

    # AR: التحقق من وجود مستخدم مفعل لكل مرحلة اعتماد.
    # EN: Ensure every approval stage has at least one enabled User.
    for role in WORKFLOW_ROLES:
        users = _enabled_users_with_role(role)

        if not users:
            result["errors"].append(
                f"No enabled User has the required role: {role}."
            )
            continue

        result["info"].append(
            {"role": role, "enabled_users": users}
        )

        # AR: كل من يحمل الدور يرى طلبات تلك المرحلة.
        # EN: Every user with the role can see requests at that stage.
        if len(users) > 1:
            result["warnings"].append(
                f"{role} has {len(users)} enabled users; all of them can see "
                "requests at that workflow stage."
            )

    employee_meta = frappe.get_meta("Employee")
    fields = ["name", "employee_name", "user_id", "reports_to"]

    has_secretary_field = employee_meta.has_field(
        "custom_secretary_employee"
    )

    if has_secretary_field:
        fields.append("custom_secretary_employee")
    else:
        result["errors"].append(
            "Employee.custom_secretary_employee is missing. "
            "Run the app setup."
        )

    # AR: التحقق من حسابات الموظفين والمديرين والسكرتارية.
    # EN: Validate Employee, manager, and secretary User accounts.
    for employee in frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=fields,
    ):
        if not employee.user_id:
            result["warnings"].append(
                f"Active employee {employee.name} has no User account."
            )

        if employee.reports_to:
            manager_user = frappe.db.get_value(
                "Employee",
                employee.reports_to,
                "user_id",
            )

            if not manager_user:
                result["errors"].append(
                    f"Manager {employee.reports_to} for employee "
                    f"{employee.name} has no User account."
                )

        if has_secretary_field and employee.custom_secretary_employee:
            secretary_user = frappe.db.get_value(
                "Employee",
                employee.custom_secretary_employee,
                "user_id",
            )

            if not secretary_user:
                result["errors"].append(
                    f"Secretary {employee.custom_secretary_employee} for "
                    f"employee {employee.name} has no User account."
                )

            elif "Material Request Secretary" not in frappe.get_roles(
                secretary_user
            ):
                result["errors"].append(
                    f"Secretary User {secretary_user} is missing the "
                    "Material Request Secretary role. "
                    "Run setup_material_request_all()."
                )

    result["ready"] = not result["errors"]
    return result
