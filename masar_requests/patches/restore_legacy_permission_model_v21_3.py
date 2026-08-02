"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `restore_legacy_permission_model_v21_3` على المواقع القائمة.
EN: Idempotent migration patch for applying `restore_legacy_permission_model_v21_3` changes to existing sites.
"""

# ============================================================================
# AR: استعادة نموذج الصلاحيات السابق للمهمة والإجازة والمواد — V21.3
# EN: Restore the legacy request permission model — V21.3
# ============================================================================

import json
from pathlib import Path

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from masar_requests.hr_user_read_only import setup_hr_user_read_only_permissions
from masar_requests.leave_application_permissions import (
    resync_all_leave_application_shares,
)
from masar_requests.official_duty_request_permissions import (
    resync_all_official_duty_request_shares,
)
from masar_requests.setup_material_request import (
    resync_all_material_request_shares,
)


OFFICIAL_DUTY_DOCTYPE = "Official Duty Request"


def _backup_and_remove_custom_permissions():
    """
    AR: تنفيذ `backup` `and` إزالة `custom` الصلاحيات ضمن وحدة `restore_legacy_permission_model_v21_3`.
    EN: Execute backup and remove custom permissions within the `restore_legacy_permission_model_v21_3` module.
    """
    rows = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": OFFICIAL_DUTY_DOCTYPE},
        fields=["*"],
        order_by="idx asc",
    )

    backup_dir = Path(frappe.get_site_path("private", "backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / "official_duty_custom_docperm_before_v21_3.json"
    backup_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    for row in rows:
        frappe.delete_doc(
            "Custom DocPerm",
            row.name,
            ignore_permissions=True,
            force=True,
        )

    return len(rows), str(backup_path)


def _restore_employee_link_behavior():
    """
    AR: تنفيذ استعادة الموظف `link` `behavior` ضمن وحدة `restore_legacy_permission_model_v21_3`.
    EN: Execute restore employee link behavior within the `restore_legacy_permission_model_v21_3` module.
    """
    make_property_setter(
        OFFICIAL_DUTY_DOCTYPE,
        "employee",
        "ignore_user_permissions",
        1,
        "Check",
    )

    docfield_name = frappe.db.get_value(
        "DocField",
        {
            "parent": OFFICIAL_DUTY_DOCTYPE,
            "fieldname": "employee",
        },
        "name",
    )
    if docfield_name:
        frappe.db.set_value(
            "DocField",
            docfield_name,
            "ignore_user_permissions",
            1,
            update_modified=False,
        )


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `restore_legacy_permission_model_v21_3`.
    EN: Execute execute within the `restore_legacy_permission_model_v21_3` module.
    """
    removed, backup_path = _backup_and_remove_custom_permissions()
    _restore_employee_link_behavior()

    # Leave and Material Request keep their unchanged legacy permission code.
    # The modified setup function intentionally skips Custom DocPerm on ODR.
    setup_hr_user_read_only_permissions()

    official_count = resync_all_official_duty_request_shares()
    leave_count = resync_all_leave_application_shares()
    material_count = resync_all_material_request_shares()

    frappe.db.commit()

    for doctype in (
        OFFICIAL_DUTY_DOCTYPE,
        "Leave Application",
        "Material Request",
        "Attendance Request",
        "Employee",
    ):
        frappe.clear_cache(doctype=doctype)

    frappe.clear_cache()

    return {
        "removed_official_duty_custom_permissions": removed,
        "custom_permission_backup": backup_path,
        "official_duty_shares_resynced": official_count,
        "leave_shares_resynced": leave_count,
        "material_shares_resynced": material_count,
    }
