"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `complete_remaining_requirements_v21_7` على المواقع القائمة.
EN: Idempotent migration patch for applying `complete_remaining_requirements_v21_7` changes to existing sites.
"""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


HR_OPERATIONAL_DOCTYPES = (
    "Attendance Request",
    "Attendance",
    "Employee Checkin",
)

LEAVE_VISIBLE_FIELDS = (
    "employee",
    "leave_type",
    "custom_substitute_employee",
    "half_day",
    "custom_quarter_day",
    "custom_is_quarter_day",
    "custom_hourly_leave",
    "custom_is_hourly_leave",
    "from_date",
    "to_date",
    "description",
    "reason",
)


def _field_exists(doctype, fieldname):
    """
    AR: تنفيذ الحقل `exists` ضمن وحدة `complete_remaining_requirements_v21_7`.
    EN: Execute field exists within the `complete_remaining_requirements_v21_7` module.
    """
    return frappe.get_meta(doctype, cached=False).has_field(fieldname)


def _set_property(doctype, fieldname, property_name, value, property_type):
    """
    AR: تنفيذ تعيين `property` ضمن وحدة `complete_remaining_requirements_v21_7`.
    EN: Execute set property within the `complete_remaining_requirements_v21_7` module.
    """
    if not _field_exists(doctype, fieldname):
        return False

    make_property_setter(
        doctype,
        fieldname,
        property_name,
        value,
        property_type,
    )
    return True


def setup_hr_manager_operational_visibility():
    """
    AR: تنفيذ إعداد `hr` المدير `operational` الظهور ضمن وحدة `complete_remaining_requirements_v21_7`.
    EN: Execute setup hr manager operational visibility within the `complete_remaining_requirements_v21_7` module.
    """
    changed = []

    for doctype in HR_OPERATIONAL_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue

        if _set_property(
            doctype,
            "employee",
            "ignore_user_permissions",
            1,
            "Check",
        ):
            changed.append(f"{doctype}.employee")

        if _set_property(
            doctype,
            "company",
            "ignore_user_permissions",
            1,
            "Check",
        ):
            changed.append(f"{doctype}.company")

    return changed


def setup_leave_application_layout():
    """
    AR: تنفيذ إعداد الإجازة `application` `layout` ضمن وحدة `complete_remaining_requirements_v21_7`.
    EN: Execute setup leave application layout within the `complete_remaining_requirements_v21_7` module.
    """
    changed = []

    for fieldname in LEAVE_VISIBLE_FIELDS:
        if not _field_exists("Leave Application", fieldname):
            continue

        _set_property(
            "Leave Application",
            fieldname,
            "hidden",
            0,
            "Check",
        )
        _set_property(
            "Leave Application",
            fieldname,
            "depends_on",
            "",
            "Data",
        )
        changed.append(fieldname)

    ordering = [
        ("custom_substitute_employee", "leave_type"),
        ("half_day", "custom_substitute_employee"),
        ("custom_quarter_day", "half_day"),
        ("custom_is_quarter_day", "half_day"),
        ("custom_hourly_leave", "custom_quarter_day"),
        ("custom_is_hourly_leave", "custom_is_quarter_day"),
        ("from_date", "custom_hourly_leave"),
        ("to_date", "from_date"),
        ("description", "to_date"),
        ("reason", "to_date"),
    ]

    for fieldname, insert_after in ordering:
        if (
            _field_exists("Leave Application", fieldname)
            and _field_exists("Leave Application", insert_after)
        ):
            _set_property(
                "Leave Application",
                fieldname,
                "insert_after",
                insert_after,
                "Data",
            )

    labels = {
        "custom_substitute_employee": "Substitute Employee",
        "custom_quarter_day": "Quarter Day",
        "custom_is_quarter_day": "Quarter Day",
        "custom_hourly_leave": "Hourly Leave",
        "custom_is_hourly_leave": "Hourly Leave",
        "description": "Reason",
        "reason": "Reason",
    }

    for fieldname, label in labels.items():
        _set_property(
            "Leave Application",
            fieldname,
            "label",
            label,
            "Data",
        )

    return changed


def setup_material_purchase_financials():
    """
    AR: تنفيذ إعداد المواد `purchase` `financials` ضمن وحدة `complete_remaining_requirements_v21_7`.
    EN: Execute setup material purchase financials within the `complete_remaining_requirements_v21_7` module.
    """
    create_custom_fields(
        {
            "Material Request": [
                {
                    "fieldname": "custom_estimated_total",
                    "label": "Estimated Request Total",
                    "fieldtype": "Currency",
                    "insert_after": "items",
                    "read_only": 1,
                    "hidden": 1,
                    "depends_on": "eval:doc.material_request_type=='Purchase'",
                    "description": "Sum of estimated item amounts for Purchase requests.",
                },
            ],
        },
        update=True,
    )

    for fieldname in ("rate", "amount"):
        _set_property(
            "Material Request Item",
            fieldname,
            "hidden",
            0,
            "Check",
        )
        _set_property(
            "Material Request Item",
            fieldname,
            "in_list_view",
            1,
            "Check",
        )
        _set_property(
            "Material Request Item",
            fieldname,
            "depends_on",
            "",
            "Data",
        )
        _set_property(
            "Material Request Item",
            fieldname,
            "columns",
            2,
            "Int",
        )

    _set_property(
        "Material Request Item",
        "rate",
        "label",
        "Estimated Rate",
        "Data",
    )
    _set_property(
        "Material Request Item",
        "amount",
        "label",
        "Estimated Amount",
        "Data",
    )
    _set_property(
        "Material Request Item",
        "amount",
        "read_only",
        1,
        "Check",
    )

    return {
        "rate": _field_exists("Material Request Item", "rate"),
        "amount": _field_exists("Material Request Item", "amount"),
        "total": _field_exists("Material Request", "custom_estimated_total"),
    }


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `complete_remaining_requirements_v21_7`.
    EN: Execute execute within the `complete_remaining_requirements_v21_7` module.
    """
    result = {
        "hr_visibility": setup_hr_manager_operational_visibility(),
        "leave_layout": setup_leave_application_layout(),
        "material_purchase": setup_material_purchase_financials(),
    }

    for doctype in (
        "Attendance Request",
        "Attendance",
        "Employee Checkin",
        "Leave Application",
        "Material Request",
        "Material Request Item",
    ):
        frappe.clear_cache(doctype=doctype)

    frappe.clear_cache()

    frappe.logger("masar_requests").info(
        "V21.7 remaining requirements installed: %s",
        result,
    )


def verify(user="ra@gmail.com"):
    """
    AR: تنفيذ `verify` ضمن وحدة `complete_remaining_requirements_v21_7`.
    EN: Execute verify within the `complete_remaining_requirements_v21_7` module.
    """
    original_user = frappe.session.user

    try:
        frappe.set_user(user)
        visibility = {}

        for doctype in HR_OPERATIONAL_DOCTYPES:
            total = frappe.db.count(doctype)
            visible_names = frappe.get_list(
                doctype,
                fields=["name"],
                limit_page_length=5000,
            )
            visibility[doctype] = {
                "database_total": total,
                "visible_to_user": len(visible_names),
                "has_read_permission": bool(
                    frappe.has_permission(doctype, ptype="read")
                ),
            }
    finally:
        frappe.set_user(original_user)

    leave_meta = frappe.get_meta("Leave Application", cached=False)
    leave_fields = {}

    for fieldname in LEAVE_VISIBLE_FIELDS:
        field = leave_meta.get_field(fieldname)
        if field:
            leave_fields[fieldname] = {
                "hidden": int(field.get("hidden") or 0),
                "depends_on": field.get("depends_on"),
                "insert_after": field.get("insert_after"),
            }

    item_meta = frappe.get_meta("Material Request Item", cached=False)
    material_fields = {}

    for fieldname in ("rate", "amount"):
        field = item_meta.get_field(fieldname)
        material_fields[fieldname] = {
            "hidden": int(field.get("hidden") or 0),
            "in_list_view": int(field.get("in_list_view") or 0),
            "columns": field.get("columns"),
            "label": field.get("label"),
        }

    result = {
        "user": user,
        "hr_visibility": visibility,
        "leave_fields": leave_fields,
        "material_fields": material_fields,
        "estimated_total_exists": bool(
            frappe.get_meta(
                "Material Request",
                cached=False,
            ).has_field("custom_estimated_total")
        ),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result
