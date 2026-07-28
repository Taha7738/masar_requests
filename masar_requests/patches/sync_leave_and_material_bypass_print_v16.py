# ==========================================================================
# AR: مزامنة ملاحظات تجاوز سير العمل في طباعة الإجازة وطلب المواد — V16
# EN: Sync workflow-bypass notes for Leave and Material print formats — V16
# ==========================================================================

import json
from pathlib import Path

import frappe


# AR: تعريفات تنسيقات الطباعة المطلوب تحديثها في قاعدة البيانات.
# EN: Print-format definitions that must be synchronized to the database.
PRINT_FORMATS = (
    {
        "name": "Masar Leave Application Form",
        "doctype": "Leave Application",
        "folder": "masar_leave_application_form",
        "filename": "masar_leave_application_form.json",
    },
    {
        "name": "Masar-Material Supply & Issue Request",
        "doctype": "Material Request",
        "folder": "masar_material_supply_&_issue_request",
        "filename": "masar_material_supply_&_issue_request.json",
    },
)


def _definition_path(folder, filename):
    """
    AR: إرجاع مسار ملف JSON الخاص بتنسيق الطباعة داخل التطبيق.
    EN: Return the app path for a print-format JSON definition.
    """
    return Path(
        frappe.get_app_path(
            "masar_requests",
            "masar_requests",
            "print_format",
            folder,
            filename,
        )
    )


def _load_definition(folder, filename):
    """
    AR: قراءة تعريف تنسيق الطباعة والتحقق من وجود الملف.
    EN: Load a print-format definition and validate that the file exists.
    """
    path = _definition_path(folder, filename)
    if not path.exists():
        frappe.throw(f"Missing print format definition: {path}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _database_values(definition, doctype):
    """
    AR: تجهيز الحقول التي تُحفظ في سجل Print Format بقاعدة البيانات.
    EN: Build the values stored on the database Print Format record.
    """
    return {
        "doc_type": doctype,
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
        "pdf_generator": definition.get("pdf_generator") or "wkhtmltopdf",
    }


def _sync_print_format(config):
    """
    AR:
        تحديث تنسيق الطباعة الموجود مباشرة من ملف JSON؛ وذلك لمنع استمرار
        نسخة قديمة داخل قاعدة البيانات بعد استبدال الملفات فقط.

    EN:
        Synchronize the database Print Format directly from JSON so an older
        database copy cannot remain active after files are replaced.
    """
    definition = _load_definition(config["folder"], config["filename"])
    values = _database_values(definition, config["doctype"])

    if frappe.db.exists("Print Format", config["name"]):
        frappe.db.set_value(
            "Print Format",
            config["name"],
            values,
            update_modified=True,
        )
        return

    frappe.get_doc(
        {
            "doctype": "Print Format",
            "name": config["name"],
            **values,
        }
    ).insert(ignore_permissions=True)


def execute():
    """
    AR:
        تطبيق ملاحظات الاعتماد الإجباري على طباعة الإجازة وطلب المواد فقط.
        لا يُغيّر هذا الـPatch أي انتقال أو شرط أو صلاحية في سير العمل.

    EN:
        Apply forced-approval notes to Leave and Material printing only.
        This patch does not modify workflow transitions, conditions, or roles.
    """
    for config in PRINT_FORMATS:
        _sync_print_format(config)
        frappe.clear_cache(doctype=config["doctype"])

    frappe.clear_cache()
