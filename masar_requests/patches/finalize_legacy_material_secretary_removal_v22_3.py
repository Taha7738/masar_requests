"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `finalize_legacy_material_secretary_removal_v22_3` على المواقع القائمة.
EN: Idempotent migration patch for applying `finalize_legacy_material_secretary_removal_v22_3` changes to existing sites.
"""

import frappe


ROLE_NAME = "Material Request Secretary"
TRACKING_DOCTYPE = "Masar Secretary Access"

PENDING_STATES = {
    "Leave Application": [
        "Waiting for Direct Manager Approval",
    ],
    "Official Duty Request": [
        "Waiting for Direct Manager Approval",
    ],
    "Material Request": [
        "Pending Direct Supervisor",
        "Waiting for Direct Manager Approval",
        "Pending Stock Check",
        "Pending HR Manager",
        "Pending Accounts Manager",
        "Pending Sec Gen",
        "Pending President",
    ],
}


def _remove_legacy_role():
    """
    AR: تنفيذ إزالة القديم الدور ضمن وحدة `finalize_legacy_material_secretary_removal_v22_3`.
    EN: Execute remove legacy role within the `finalize_legacy_material_secretary_removal_v22_3` module.
    """
    frappe.db.delete(
        "Custom DocPerm",
        {
            "parent": "Material Request",
            "role": ROLE_NAME,
        },
    )
    frappe.db.delete(
        "DocPerm",
        {
            "parent": "Material Request",
            "role": ROLE_NAME,
        },
    )
    frappe.db.delete(
        "Has Role",
        {"role": ROLE_NAME},
    )
    # Some Frappe installations do not have the optional
    # `tabRole Profile Role` child table. Guard it explicitly.
    if frappe.db.table_exists("Role Profile Role"):
        frappe.db.delete(
            "Role Profile Role",
            {"role": ROLE_NAME},
        )

    if frappe.db.exists("Role", ROLE_NAME):
        try:
            frappe.delete_doc(
                "Role",
                ROLE_NAME,
                ignore_permissions=True,
                force=True,
            )
        except Exception:
            role_meta = frappe.get_meta(
                "Role",
                cached=False,
            )
            if role_meta.has_field("disabled"):
                frappe.db.set_value(
                    "Role",
                    ROLE_NAME,
                    "disabled",
                    1,
                    update_modified=False,
                )


def _adopt_existing_active_shares():
    """
    AR: تنفيذ `adopt` الموجود النشط `shares` ضمن وحدة `finalize_legacy_material_secretary_removal_v22_3`.
    EN: Execute adopt existing active shares within the `finalize_legacy_material_secretary_removal_v22_3` module.

    DETAILS / التفاصيل:
    Mark old secretary shares as owned by the unified service before resync.
        This lets sync_secretary_access revoke the old user's share safely when
        the configured secretary has changed.
    """
    if not frappe.db.exists(
        "DocType",
        TRACKING_DOCTYPE,
    ):
        return 0

    adopted = 0

    rows = frappe.get_all(
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

    for row in rows:
        if row.share_created_by_service:
            continue

        share_exists = frappe.db.exists(
            "DocShare",
            {
                "share_doctype": "Material Request",
                "share_name": row.reference_name,
                "user": row.secretary_user,
                "read": 1,
            },
        )

        if not share_exists:
            continue

        frappe.db.set_value(
            TRACKING_DOCTYPE,
            row.name,
            "share_created_by_service",
            1,
            update_modified=False,
        )
        adopted += 1

    return adopted


def _resync_pending_requests():
    """
    AR: تنفيذ `resync` `pending` `requests` ضمن وحدة `finalize_legacy_material_secretary_removal_v22_3`.
    EN: Execute resync pending requests within the `finalize_legacy_material_secretary_removal_v22_3` module.
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
                "workflow_state": ("in", states),
                "docstatus": ("!=", 2),
            },
            pluck="name",
        )

        for name in names:
            sync_secretary_access(
                frappe.get_doc(doctype, name)
            )

        synced[doctype] = len(names)
        frappe.clear_cache(doctype=doctype)

    return synced


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `finalize_legacy_material_secretary_removal_v22_3`.
    EN: Execute execute within the `finalize_legacy_material_secretary_removal_v22_3` module.
    """
    _remove_legacy_role()
    adopted = _adopt_existing_active_shares()
    synced = _resync_pending_requests()

    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache()

    frappe.logger("masar_requests").info(
        "V22.3 finalized legacy secretary removal; "
        "adopted=%s synced=%s",
        adopted,
        synced,
    )


def verify():
    """
    AR: تنفيذ `verify` ضمن وحدة `finalize_legacy_material_secretary_removal_v22_3`.
    EN: Execute verify within the `finalize_legacy_material_secretary_removal_v22_3` module.
    """
    active_access = (
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
                "workflow_state",
                "share_created_by_service",
                "todo",
            ],
        )
        if frappe.db.exists(
            "DocType",
            TRACKING_DOCTYPE,
        )
        else []
    )

    inactive_access = (
        frappe.get_all(
            TRACKING_DOCTYPE,
            filters={
                "reference_doctype": "Material Request",
                "active": 0,
            },
            fields=[
                "reference_name",
                "actor_user",
                "secretary_user",
                "workflow_state",
                "revoked_on",
            ],
            order_by="modified desc",
            limit_page_length=10,
        )
        if frappe.db.exists(
            "DocType",
            TRACKING_DOCTYPE,
        )
        else []
    )

    result = {
        "legacy_role_exists": bool(
            frappe.db.exists("Role", ROLE_NAME)
        ),
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
        "legacy_docperms": frappe.db.count(
            "DocPerm",
            {
                "parent": "Material Request",
                "role": ROLE_NAME,
            },
        ),
        "active_secretary_access": active_access,
        "recent_inactive_access": inactive_access,
    }

    print(frappe.as_json(result, indent=2))
    return result
