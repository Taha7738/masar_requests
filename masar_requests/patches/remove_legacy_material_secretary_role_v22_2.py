"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `remove_legacy_material_secretary_role_v22_2` على المواقع القائمة.
EN: Idempotent migration patch for applying `remove_legacy_material_secretary_role_v22_2` changes to existing sites.
"""

import frappe


ROLE_NAME = "Material Request Secretary"
TRACKING_DOCTYPE = "Masar Secretary Access"


def execute():
    # Remove the legacy role assignment and DocPerm.
    """
    AR: تنفيذ تنفيذ ضمن وحدة `remove_legacy_material_secretary_role_v22_2`.
    EN: Execute execute within the `remove_legacy_material_secretary_role_v22_2` module.
    """
    frappe.db.delete(
        "Custom DocPerm",
        {
            "parent": "Material Request",
            "role": ROLE_NAME,
        },
    )
    frappe.db.delete("Has Role", {"role": ROLE_NAME})

    if frappe.db.exists("Role", ROLE_NAME):
        role_meta = frappe.get_meta("Role", cached=False)
        if role_meta.has_field("disabled"):
            frappe.db.set_value(
                "Role",
                ROLE_NAME,
                "disabled",
                1,
                update_modified=False,
            )

    # Existing secretary shares created by the old code are now adopted by
    # the unified service so it can revoke them when the stage changes.
    adopted = 0

    if frappe.db.exists("DocType", TRACKING_DOCTYPE):
        active_rows = frappe.get_all(
            TRACKING_DOCTYPE,
            filters={
                "reference_doctype": "Material Request",
                "active": 1,
            },
            fields=[
                "name",
                "reference_name",
                "secretary_user",
                "share_created_by_service",
            ],
        )

        for row in active_rows:
            share_exists = frappe.db.exists(
                "DocShare",
                {
                    "share_doctype": "Material Request",
                    "share_name": row.reference_name,
                    "user": row.secretary_user,
                    "read": 1,
                },
            )

            if share_exists and not row.share_created_by_service:
                frappe.db.set_value(
                    TRACKING_DOCTYPE,
                    row.name,
                    "share_created_by_service",
                    1,
                    update_modified=False,
                )
                adopted += 1

    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache()

    frappe.logger("masar_requests").info(
        "V22.2 removed legacy Material Request Secretary role; "
        "adopted secretary shares=%s",
        adopted,
    )


def verify():
    """
    AR: تنفيذ `verify` ضمن وحدة `remove_legacy_material_secretary_role_v22_2`.
    EN: Execute verify within the `remove_legacy_material_secretary_role_v22_2` module.
    """
    result = {
        "legacy_role_assignments": frappe.db.count(
            "Has Role",
            {"role": ROLE_NAME},
        ),
        "legacy_custom_docperms": frappe.db.count(
            "Custom DocPerm",
            {
                "parent": "Material Request",
                "role": ROLE_NAME,
            },
        ),
        "role_exists": bool(
            frappe.db.exists("Role", ROLE_NAME)
        ),
        "active_secretary_access": (
            frappe.get_all(
                TRACKING_DOCTYPE,
                filters={
                    "reference_doctype": "Material Request",
                    "active": 1,
                },
                fields=[
                    "reference_name",
                    "actor_user",
                    "secretary_user",
                    "share_created_by_service",
                    "todo",
                ],
            )
            if frappe.db.exists("DocType", TRACKING_DOCTYPE)
            else []
        ),
    }

    print(frappe.as_json(result, indent=2))
    return result
