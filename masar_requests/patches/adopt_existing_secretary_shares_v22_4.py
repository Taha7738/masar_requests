"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `adopt_existing_secretary_shares_v22_4` على المواقع القائمة.
EN: Idempotent migration patch for applying `adopt_existing_secretary_shares_v22_4` changes to existing sites.
"""

import frappe


TRACKING_DOCTYPE = "Masar Secretary Access"


def _strict_read_only_share_exists(row):
    """
    AR: تنفيذ الصارم القراءة `only` مشاركة `exists` ضمن وحدة `adopt_existing_secretary_shares_v22_4`.
    EN: Execute strict read only share exists within the `adopt_existing_secretary_shares_v22_4` module.
    """
    share = frappe.db.get_value(
        "DocShare",
        {
            "share_doctype": row.reference_doctype,
            "share_name": row.reference_name,
            "user": row.secretary_user,
        },
        ["read", "write", "submit", "share"],
        as_dict=True,
    )

    if not share:
        return False

    return bool(share.read) and not any(
        (
            share.write,
            share.submit,
            share.share,
        )
    )


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `adopt_existing_secretary_shares_v22_4`.
    EN: Execute execute within the `adopt_existing_secretary_shares_v22_4` module.
    """
    if not frappe.db.exists(
        "DocType",
        TRACKING_DOCTYPE,
    ):
        return

    adopted = 0

    rows = frappe.get_all(
        TRACKING_DOCTYPE,
        filters={
            "active": 1,
            "share_created_by_service": 0,
        },
        fields=[
            "name",
            "reference_doctype",
            "reference_name",
            "secretary_user",
        ],
    )

    for row in rows:
        if not _strict_read_only_share_exists(row):
            continue

        frappe.db.set_value(
            TRACKING_DOCTYPE,
            row.name,
            "share_created_by_service",
            1,
            update_modified=False,
        )
        adopted += 1

    frappe.clear_cache()

    frappe.logger("masar_requests").info(
        "V22.4 adopted existing read-only secretary shares=%s",
        adopted,
    )


def verify():
    """
    AR: تنفيذ `verify` ضمن وحدة `adopt_existing_secretary_shares_v22_4`.
    EN: Execute verify within the `adopt_existing_secretary_shares_v22_4` module.
    """
    active = frappe.get_all(
        TRACKING_DOCTYPE,
        filters={"active": 1},
        fields=[
            "reference_doctype",
            "reference_name",
            "actor_user",
            "secretary_user",
            "workflow_state",
            "share_created_by_service",
            "todo",
        ],
    )

    result = {
        "active_access": active,
        "unowned_active_shares": [
            row
            for row in active
            if not row.share_created_by_service
        ],
    }

    print(frappe.as_json(result, indent=2))
    return result
