"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `fix_manual_resolution_select_v21_4_2` على المواقع القائمة.
EN: Idempotent migration patch for applying `fix_manual_resolution_select_v21_4_2` changes to existing sites.
"""

import frappe

from masar_requests.manual_official_duty_reconciliation import (
    DETAIL_DOCTYPE,
    MANUAL_RESOLUTION_CONFIRMED,
    get_manual_reconciliation_custom_fields,
)
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `fix_manual_resolution_select_v21_4_2`.
    EN: Execute execute within the `fix_manual_resolution_select_v21_4_2` module.
    """
    create_custom_fields(
        get_manual_reconciliation_custom_fields(),
        update=True,
    )

    custom_field_name = frappe.db.get_value(
        "Custom Field",
        {
            "dt": DETAIL_DOCTYPE,
            "fieldname": "custom_manual_resolution",
        },
        "name",
    )
    if custom_field_name:
        frappe.db.set_value(
            "Custom Field",
            custom_field_name,
            {
                "options": f"\n{MANUAL_RESOLUTION_CONFIRMED}",
                "default": None,
            },
            update_modified=False,
        )

    if frappe.get_meta(DETAIL_DOCTYPE, cached=False).has_field(
        "custom_manual_resolution"
    ):
        frappe.db.sql(
            f"UPDATE `tab{DETAIL_DOCTYPE}` "
            "SET `custom_manual_resolution` = NULL "
            "WHERE COALESCE(`custom_manual_resolution`, '') NOT IN ('', %s)",
            (MANUAL_RESOLUTION_CONFIRMED,),
        )

    frappe.clear_cache(doctype=DETAIL_DOCTYPE)
