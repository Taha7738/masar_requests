"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `apply_strict_request_visibility_v21_9` على المواقع القائمة.
EN: Idempotent migration patch for applying `apply_strict_request_visibility_v21_9` changes to existing sites.
"""

import frappe


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `apply_strict_request_visibility_v21_9`.
    EN: Execute execute within the `apply_strict_request_visibility_v21_9` module.

    DETAILS / التفاصيل:
    Clear permission caches and remove only stale ordinary-employee DocShares
        from Leave/Official requests. Material Request sharing is not rewritten,
        preserving the existing senior-management and secretary rules.
    """
    protected_roles = {
        "System Manager",
        "HR Manager",
        "HR User",
        "Official Duty Secretary",
    }

    removed = {
        "Leave Application": 0,
        "Official Duty Request": 0,
    }

    for doctype in removed:
        shares = frappe.get_all(
            "DocShare",
            filters={"share_doctype": doctype},
            fields=["name", "share_name", "user"],
        )

        for row in shares:
            if not row.user or row.user == "Administrator":
                continue

            roles = set(frappe.get_roles(row.user))
            if roles & protected_roles:
                continue

            doc = frappe.get_doc(doctype, row.share_name)

            participant_users = {
                doc.get("owner"),
                doc.get("custom_applicant_user"),
                doc.get("custom_substitute_user"),
                doc.get("custom_direct_manager_user"),
                doc.get("custom_direct_manager_secretary_user"),
            }

            if row.user in participant_users:
                continue

            frappe.delete_doc(
                "DocShare",
                row.name,
                ignore_permissions=True,
                force=True,
            )
            removed[doctype] += 1

    frappe.clear_cache(doctype="Leave Application")
    frappe.clear_cache(doctype="Official Duty Request")
    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache()

    frappe.logger("masar_requests").info(
        "V21.9 strict visibility applied; removed stale shares=%s",
        removed,
    )


def verify_hooks():
    """
    AR: تنفيذ `verify` `hooks` ضمن وحدة `apply_strict_request_visibility_v21_9`.
    EN: Execute verify hooks within the `apply_strict_request_visibility_v21_9` module.
    """
    from masar_requests import hooks

    result = {
        "permission_query_conditions": {
            doctype: hooks.permission_query_conditions.get(doctype)
            for doctype in (
                "Leave Application",
                "Official Duty Request",
                "Material Request",
            )
        },
        "has_permission": {
            doctype: hooks.has_permission.get(doctype)
            for doctype in (
                "Leave Application",
                "Official Duty Request",
                "Material Request",
            )
        },
    }

    print(frappe.as_json(result, indent=2))
    return result
