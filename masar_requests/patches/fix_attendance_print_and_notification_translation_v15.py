"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `fix_attendance_print_and_notification_translation_v15` على المواقع القائمة.
EN: Idempotent migration patch for applying `fix_attendance_print_and_notification_translation_v15` changes to existing sites.
"""

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
    AR: تنفيذ طباعة تنسيق `json` `path` ضمن وحدة `fix_attendance_print_and_notification_translation_v15`.
    EN: Execute print format json path within the `fix_attendance_print_and_notification_translation_v15` module.
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
    AR: تنفيذ تحميل طباعة تنسيق `definition` ضمن وحدة `fix_attendance_print_and_notification_translation_v15`.
    EN: Execute load print format definition within the `fix_attendance_print_and_notification_translation_v15` module.
    """
    path = _print_format_json_path()
    if not path.exists():
        frappe.throw(f"Missing print format definition: {path}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sync_print_format_to_database():
    """
    AR: تنفيذ مزامنة طباعة تنسيق `to` `database` ضمن وحدة `fix_attendance_print_and_notification_translation_v15`.
    EN: Execute sync print format to database within the `fix_attendance_print_and_notification_translation_v15` module.

    DETAILS / التفاصيل:
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
    AR: تنفيذ تنفيذ ضمن وحدة `fix_attendance_print_and_notification_translation_v15`.
    EN: Execute execute within the `fix_attendance_print_and_notification_translation_v15` module.

    DETAILS / التفاصيل:
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
