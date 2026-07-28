# =======================================================================
# AR: تنظيف التخصيصات عند إزالة التطبيق
# EN: Cleanup customizations upon app uninstallation
# =======================================================================

import frappe

from masar_requests.setup_attendance_request import (
    ATTENDANCE_CUSTOM_FIELDNAMES,
    ATTENDANCE_DOCTYPE,
    ATTENDANCE_WORKFLOW_NAME,
)


def cleanup_attendance_request():
    # AR: حذف الحقول وسير العمل الخاصة بطلب الحضور.
    # EN: Delete Attendance Request fields and workflow owned by the app.
    custom_field_names = frappe.get_all(
        "Custom Field",
        filters={
            "dt": ATTENDANCE_DOCTYPE,
            "fieldname": ("in", ATTENDANCE_CUSTOM_FIELDNAMES),
        },
        pluck="name",
    )
    for custom_field_name in custom_field_names:
        frappe.delete_doc(
            "Custom Field",
            custom_field_name,
            ignore_permissions=True,
            force=True,
        )

    frappe.db.delete(
        "Property Setter",
        {"doc_type": ATTENDANCE_DOCTYPE, "property": "field_order"},
    )

    if frappe.db.exists("Workflow", ATTENDANCE_WORKFLOW_NAME):
        frappe.delete_doc(
            "Workflow",
            ATTENDANCE_WORKFLOW_NAME,
            ignore_permissions=True,
            force=True,
        )

    frappe.clear_cache(doctype=ATTENDANCE_DOCTYPE)
