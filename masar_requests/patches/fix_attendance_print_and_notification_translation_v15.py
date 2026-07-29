# ============================================================================
# AR: مزامنة تنسيق طباعة المهمة وترجمة إشعارات المهمة والإجازة — V15
# EN: Sync Official Duty print format and notification translations — V15
# ============================================================================

import json
from pathlib import Path

import frappe

PRINT_FORMAT_NAME = "Masar Attendance Request Form"
PRINT_FORMAT_DOCTYPE = "Attendance Request"


def _print_format_json_path():
    """
    AR: إعادة مسار ملف تنسيق الطباعة القياسي داخل التطبيق.
    EN: Return the standard print-format JSON path inside the app.
    """
    return Path(
        frappe.get_app_path(
            "masar_requests",
            "masar_requests",
            "print_format",
            "masar_attendance_request_form",
            "masar_attendance_request_form.json",
        )
    )


def _load_print_format_definition():
    """
    AR: قراءة تعريف تنسيق الطباعة من ملف JSON المرفق مع التطبيق.
    EN: Load the print-format definition shipped with the app.
    """
    path = _print_format_json_path()
    if not path.exists():
        frappe.throw(f"Missing print format definition: {path}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sync_print_format_to_database():
    """
    AR:
        تحديث سجل Print Format الموجود مباشرة من JSON. هذا ضروري لأن بعض
        المواقع تحتفظ بنسخة قاعدة بيانات أقدم حتى بعد استبدال الملف وتشغيل build.

    EN:
        Update the database Print Format directly from JSON. Some sites retain
        an older database copy even after replacing the file and rebuilding assets.
    """
    definition = _load_print_format_definition()
    values = {
        "doc_type": PRINT_FORMAT_DOCTYPE,
        "module": definition.get("module") or "Masar Requests",
        "standard": definition.get("standard") or "Yes",
        "custom_format": definition.get("custom_format", 1),
        "print_format_type": definition.get("print_format_type") or "Jinja",
        "html": definition.get("html") or "",
        "css": definition.get("css") or "",
        "disabled": definition.get("disabled", 0),
        "default_print_language": definition.get("default_print_language") or "ar",
        "margin_top": definition.get("margin_top", 0),
        "margin_bottom": definition.get("margin_bottom", 0),
        "margin_left": definition.get("margin_left", 0),
        "margin_right": definition.get("margin_right", 0),
        # "pdf_generator": definition.get("pdf_generator") or "wkhtmltopdf",
    }

    if frappe.db.exists("Print Format", PRINT_FORMAT_NAME):
        frappe.db.set_value(
            "Print Format",
            PRINT_FORMAT_NAME,
            values,
            update_modified=True,
        )
    else:
        frappe.get_doc(
            {
                "doctype": "Print Format",
                "name": PRINT_FORMAT_NAME,
                **values,
            }
        ).insert(ignore_permissions=True)


def execute():
    """
    AR:
        تطبيق تنسيق الطباعة الجديد ومسح كاش المستند والترجمات. الإشعارات
        الجديدة فقط ستُنشأ باللغة الصحيحة؛ سجلات الإشعارات التاريخية لا تُغيّر.

    EN:
        Apply the new print format and clear DocType/translation caches. Only new
        notifications are translated; historical Notification Log rows stay unchanged.
    """
    _sync_print_format_to_database()

    frappe.clear_cache(doctype=PRINT_FORMAT_DOCTYPE)
    frappe.clear_cache(doctype="Leave Application")
    frappe.clear_cache()
