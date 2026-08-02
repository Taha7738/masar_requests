"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `change_manual_resolution_to_data_v21_4_3` على المواقع القائمة.
EN: Idempotent migration patch for applying `change_manual_resolution_to_data_v21_4_3` changes to existing sites.
"""

import frappe

from masar_requests.manual_official_duty_reconciliation import (
    DETAIL_DOCTYPE,
    MANUAL_RESOLUTION_CONFIRMED,
    setup_manual_reconciliation_fields,
)


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `change_manual_resolution_to_data_v21_4_3`.
    EN: Execute execute within the `change_manual_resolution_to_data_v21_4_3` module.
    """
    setup_manual_reconciliation_fields()

    custom_field_name = frappe.db.get_value(
        "Custom Field",
        {
            "dt": DETAIL_DOCTYPE,
            "fieldname": "custom_manual_resolution",
        },
        "name",
    )
    if not custom_field_name:
        frappe.throw("custom_manual_resolution Custom Field was not found.")

    frappe.db.set_value(
        "Custom Field",
        custom_field_name,
        {
            "fieldtype": "Data",
            "options": None,
            "default": None,
            "read_only": 1,
            "allow_on_submit": 1,
        },
        update_modified=False,
    )

    frappe.db.sql(
        f"UPDATE `tab{DETAIL_DOCTYPE}` "
        "SET `custom_manual_resolution` = NULL "
        "WHERE COALESCE(`custom_manual_resolution`, '') NOT IN ('', %s)",
        (MANUAL_RESOLUTION_CONFIRMED,),
    )

    frappe.clear_cache(doctype=DETAIL_DOCTYPE)
