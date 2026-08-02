"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `sync_leave_and_material_bypass_print_v16` على المواقع القائمة.
EN: Idempotent migration patch for applying `sync_leave_and_material_bypass_print_v16` changes to existing sites.
"""

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
    AR: تنفيذ `definition` `path` ضمن وحدة `sync_leave_and_material_bypass_print_v16`.
    EN: Execute definition path within the `sync_leave_and_material_bypass_print_v16` module.
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
    AR: تنفيذ تحميل `definition` ضمن وحدة `sync_leave_and_material_bypass_print_v16`.
    EN: Execute load definition within the `sync_leave_and_material_bypass_print_v16` module.
    """
    path = _definition_path(folder, filename)
    if not path.exists():
        frappe.throw(f"Missing print format definition: {path}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _database_values(definition, doctype):
    """
    AR: تنفيذ `database` `values` ضمن وحدة `sync_leave_and_material_bypass_print_v16`.
    EN: Execute database values within the `sync_leave_and_material_bypass_print_v16` module.
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
        # "pdf_generator": definition.get("pdf_generator") or "wkhtmltopdf",
    }


def _sync_print_format(config):
    """
    AR: تنفيذ مزامنة طباعة تنسيق ضمن وحدة `sync_leave_and_material_bypass_print_v16`.
    EN: Execute sync print format within the `sync_leave_and_material_bypass_print_v16` module.

    DETAILS / التفاصيل:
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
    AR: تنفيذ تنفيذ ضمن وحدة `sync_leave_and_material_bypass_print_v16`.
    EN: Execute execute within the `sync_leave_and_material_bypass_print_v16` module.

    DETAILS / التفاصيل:
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
