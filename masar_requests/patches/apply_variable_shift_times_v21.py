"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `apply_variable_shift_times_v21` على المواقع القائمة.
EN: Idempotent migration patch for applying `apply_variable_shift_times_v21` changes to existing sites.

DETAILS / التفاصيل:
AR:
    ترقية V21 لتصحيح دعم أوقات الوردية المتغيرة حسب يوم الأسبوع وربطها
    بمحرك HRMS القياسي دون تعديل ملفات HRMS الأصلية.

EN:
    V21 migration for reliable weekday-specific Shift Type timings integrated
    with native HRMS without modifying HRMS source files.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from masar_requests.overrides.shift_type import (
    apply_shift_times_patch,
    generate_shift_times,
    refresh_unprocessed_checkins_for_shift,
)
from masar_requests.setup_leave_and_shift import (
    create_shift_time_child_table,
    get_leave_and_shift_custom_fields,
)


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `apply_variable_shift_times_v21`.
    EN: Execute execute within the `apply_variable_shift_times_v21` module.

    DETAILS / التفاصيل:
    AR:
            إنشاء الحقول الجديدة، ترقية الجدول الفرعي، وتفعيل الجدول تلقائيًا
            فقط للورديات التي كانت تحتوي بالفعل على أوقات مخصصة.

        EN:
            Create new fields, upgrade the child table, and auto-enable the feature
            only for Shift Types that already had custom timing rows.
    """
    if not apply_shift_times_patch():
        frappe.throw(
            frappe._(
                "The installed HRMS version is not compatible with the V21 variable shift timing layer. "
                "Native HRMS remains unchanged; review compatibility before enabling the feature."
            )
        )

    create_shift_time_child_table()
    shift_fields = {"Shift Type": get_leave_and_shift_custom_fields()["Shift Type"]}
    create_custom_fields(shift_fields, update=True)

    shift_names = frappe.get_all("Shift Type", pluck="name")
    for shift_name in shift_names:
        doc = frappe.get_doc("Shift Type", shift_name)
        existing_rows = list(doc.get("custom_shift_times") or [])
        if not existing_rows:
            continue

        # AR: السجلات القديمة كانت تعني أن المؤسسة تستخدم الأوقات المتغيرة.
        # EN: Existing rows indicate that the site already used variable timings.
        doc.custom_enable_variable_shift_times = 1
        doc.flags.ignore_variable_shift_checkins = True
        generate_shift_times(doc)
        doc.save(ignore_permissions=True)

        # AR: تحديث البصمات غير المعالجة حتى لا تبقى على نافذة الوقت القديمة.
        # EN: Refresh unprocessed checkins so none retain the previous base window.
        refresh_unprocessed_checkins_for_shift(shift_name)

    frappe.clear_cache(doctype="Shift Type")
    frappe.clear_cache(doctype="Shift Assignment")
    frappe.clear_cache(doctype="Employee Checkin")
    frappe.clear_cache(doctype="Attendance")
    frappe.clear_cache(doctype="Leave Application")
    frappe.clear_cache(doctype="Official Duty Request")
