"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `fix_leave_partial_option_layout_v21_8_1` على المواقع القائمة.
EN: Idempotent migration patch for applying `fix_leave_partial_option_layout_v21_8_1` changes to existing sites.
"""

import json

import frappe

from masar_requests.setup_leave_and_shift import (
    _masar_apply_leave_layout_v218,
)


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `fix_leave_partial_option_layout_v21_8_1`.
    EN: Execute execute within the `fix_leave_partial_option_layout_v21_8_1` module.
    """
    result = _masar_apply_leave_layout_v218()

    frappe.clear_cache(doctype="Leave Application")
    frappe.clear_cache()

    frappe.logger("masar_requests").info(
        "V21.8.1 Leave partial-option layout applied: %s",
        result,
    )


def verify():
    """
    AR: تنفيذ `verify` ضمن وحدة `fix_leave_partial_option_layout_v21_8_1`.
    EN: Execute verify within the `fix_leave_partial_option_layout_v21_8_1` module.
    """
    meta = frappe.get_meta("Leave Application", cached=False)

    field_order_value = frappe.db.get_value(
        "Property Setter",
        {
            "doc_type": "Leave Application",
            "doctype_or_field": "DocType",
            "property": "field_order",
        },
        "value",
    )

    field_order = json.loads(field_order_value or "[]")

    tracked = (
        "half_day",
        "quarter_day",
        "is_hourly",
        "from_date",
        "to_date",
        "column_break1",
        "description",
    )

    result = {
        "field_order_positions": {
            fieldname: (
                field_order.index(fieldname)
                if fieldname in field_order
                else None
            )
            for fieldname in tracked
        },
        "fields": {},
    }

    for fieldname in tracked:
        field = meta.get_field(fieldname)
        if not field:
            continue

        result["fields"][fieldname] = {
            "hidden": int(field.get("hidden") or 0),
            "depends_on": field.get("depends_on"),
            "label": field.get("label"),
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result
