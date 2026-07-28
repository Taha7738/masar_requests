# ============================================================================
# AR: مزامنة واجهة الإجازة وصلاحية HR User وطباعة الموافقات العربية — V17
# EN: Sync Leave UI, HR User access, and Arabic approval printing — V17
# ============================================================================

import json
from pathlib import Path

import frappe

from masar_requests.hr_user_read_only import setup_hr_user_read_only_permissions
from masar_requests.setup_leave_and_shift import apply_leave_application_layout_preferences


# AR: تنسيقات الطباعة التي يجب مزامنتها مع قاعدة البيانات.
# EN: Print formats that must be synchronized with the database.
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
    AR: إرجاع مسار ملف JSON القياسي داخل التطبيق.
    EN: Return the standard JSON definition path inside the app.
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
    AR: قراءة تعريف تنسيق الطباعة والتحقق من وجوده.
    EN: Load and validate a print-format definition.
    """
    path = _definition_path(folder, filename)
    if not path.exists():
        frappe.throw(f"Missing print format definition: {path}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _database_values(definition, doctype):
    """
    AR: تجهيز قيم سجل Print Format المراد حفظها.
    EN: Build database values for the Print Format record.
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
    AR: مزامنة ملف JSON مع سجل Print Format الفعلي في قاعدة البيانات.
    EN: Synchronize JSON with the active database Print Format record.
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
        1) عكس عمودي واجهة طلب الإجازة وإخفاء حالة اعتماد المدير.
        2) إعادة تطبيق صلاحية HR User للقراءة والطباعة مع استثناء طلبه الشخصي.
        3) مزامنة طباعة الإجازة والمواد بالنصوص المترجمة العربية فقط.

    EN:
        1) Swap Leave form columns and hide manager approval status.
        2) Reapply HR User read/print access with personal-request exemption.
        3) Sync Leave and Material printing with translated Arabic-only notices.
    """
    apply_leave_application_layout_preferences()
    setup_hr_user_read_only_permissions()

    for config in PRINT_FORMATS:
        _sync_print_format(config)
        frappe.clear_cache(doctype=config["doctype"])

    frappe.clear_cache()
