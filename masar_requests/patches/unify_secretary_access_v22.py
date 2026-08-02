"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `unify_secretary_access_v22` على المواقع القائمة.
EN: Idempotent migration patch for applying `unify_secretary_access_v22` changes to existing sites.
"""

import frappe


PENDING_STATES = {
    "Leave Application": (
        "Waiting for Direct Manager Approval",
    ),
    "Official Duty Request": (
        "Waiting for Direct Manager Approval",
    ),
    "Material Request": (
        "Pending Direct Supervisor",
        "Waiting for Direct Manager Approval",
        "Pending Stock Check",
        "Pending HR Manager",
        "Pending Accounts Manager",
        "Pending Sec Gen",
        "Pending President",
    ),
}


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `unify_secretary_access_v22`.
    EN: Execute execute within the `unify_secretary_access_v22` module.
    """
    from masar_requests.secretary_access import (
        sync_secretary_access,
    )

    synced = {}

    for doctype, states in PENDING_STATES.items():
        if not frappe.db.exists("DocType", doctype):
            continue

        names = frappe.get_all(
            doctype,
            filters={
                "workflow_state": ("in", list(states)),
                "docstatus": ("!=", 2),
            },
            pluck="name",
        )

        count = 0
        for name in names:
            sync_secretary_access(
                frappe.get_doc(doctype, name)
            )
            count += 1

        synced[doctype] = count
        frappe.clear_cache(doctype=doctype)

    frappe.clear_cache()

    frappe.logger("masar_requests").info(
        "Unified secretary access V22 synced: %s",
        synced,
    )


def verify():
    """
    AR: تنفيذ `verify` ضمن وحدة `unify_secretary_access_v22`.
    EN: Execute verify within the `unify_secretary_access_v22` module.
    """
    from masar_requests import hooks

    result = {
        "tracking_doctype_exists": bool(
            frappe.db.exists(
                "DocType",
                "Masar Secretary Access",
            )
        ),
        "doc_events": {
            doctype: hooks.doc_events.get(doctype)
            for doctype in (
                "Leave Application",
                "Official Duty Request",
                "Material Request",
            )
        },
        "active_access_count": frappe.db.count(
            "Masar Secretary Access",
            {"active": 1},
        ),
    }

    print(frappe.as_json(result, indent=2))
    return result
