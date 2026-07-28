"""Migrate existing sites from legacy Server Scripts to native Python hooks."""

import frappe


def execute():
    """Remove obsolete scripts and correct workflow edit roles.

    AR: Patch آمن للمواقع الحالية؛ لا يعيد بناء Workflow ولا يحذف المعاملات.
    EN: Safe existing-site patch; it neither rebuilds the Workflow nor deletes requests.
    """
    for script_name in (
        "Auto Share MR with Direct Supervisor masar_requests",
        "Warehouse Fission Engine masar_requests",
    ):
        if frappe.db.exists("Server Script", script_name):
            frappe.delete_doc(
                "Server Script",
                script_name,
                ignore_permissions=True,
                force=True,
            )

    workflow_name = "Material Request Approval masar_requests"
    allow_edit_by_state = {
        "Pending Stock Check": "Warehouse Manager",
        "Pending HR Manager": "HR Manager",
        "Pending Accounts Manager": "Accounts Manager",
        "Pending Sec Gen": "Secretary General",
        "Pending President": "University President",
    }

    if frappe.db.exists("Workflow", workflow_name):
        for state, role in allow_edit_by_state.items():
            row_name = frappe.db.get_value(
                "Workflow Document State",
                {"parent": workflow_name, "state": state},
                "name",
            )
            if row_name:
                frappe.db.set_value(
                    "Workflow Document State",
                    row_name,
                    "allow_edit",
                    role,
                    update_modified=False,
                )

    frappe.clear_cache(doctype="Material Request")

