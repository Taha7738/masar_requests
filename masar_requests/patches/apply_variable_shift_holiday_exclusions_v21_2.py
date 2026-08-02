"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `apply_variable_shift_holiday_exclusions_v21_2` على المواقع القائمة.
EN: Idempotent migration patch for applying `apply_variable_shift_holiday_exclusions_v21_2` changes to existing sites.

DETAILS / التفاصيل:
AR:
    ترقية V21.2 لمزامنة جدول أوقات الوردية مع أيام العمل الفعلية، بحيث
    تُستبعد أيام العطلة الأسبوعية المتكررة من قائمة العطلات دون التأثير
    على العطلات الرسمية ذات التاريخ الواحد.

EN:
    V21.2 migration that synchronizes variable Shift Type rows with actual
    working weekdays, excluding recurring weekly-off days while leaving
    one-off official holidays under native HRMS date-based handling.
"""

import frappe

from masar_requests.overrides.shift_type import (
    generate_shift_times,
    refresh_unprocessed_checkins_for_shift,
)


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `apply_variable_shift_holiday_exclusions_v21_2`.
    EN: Execute execute within the `apply_variable_shift_holiday_exclusions_v21_2` module.

    DETAILS / التفاصيل:
    AR:
            تنظيف صفوف أيام العطلة الأسبوعية من جميع الورديات المفعّل فيها
            الجدول، مع الحفاظ على أوقات بقية الأيام وإعادة حساب البصمات غير
            المعالجة فقط.

        EN:
            Remove recurring weekly-off rows from enabled variable schedules,
            preserve all remaining weekday times, and refresh only unprocessed
            checkins.
    """
    if not frappe.db.exists(
        "Custom Field",
        {"dt": "Shift Type", "fieldname": "custom_shift_times"},
    ):
        return

    shift_names = frappe.get_all(
        "Shift Type",
        filters={"custom_enable_variable_shift_times": 1},
        pluck="name",
    )

    for shift_name in shift_names:
        doc = frappe.get_doc("Shift Type", shift_name)
        before = [
            (
                row.get("day_of_week"),
                str(row.get("start_time") or ""),
                str(row.get("end_time") or ""),
            )
            for row in doc.get("custom_shift_times") or []
        ]

        doc.flags.ignore_variable_shift_checkins = True
        generate_shift_times(doc)

        after = [
            (
                row.get("day_of_week"),
                str(row.get("start_time") or ""),
                str(row.get("end_time") or ""),
            )
            for row in doc.get("custom_shift_times") or []
        ]

        if before == after:
            continue

        doc.save(ignore_permissions=True)
        refresh_unprocessed_checkins_for_shift(shift_name)

    frappe.clear_cache(doctype="Shift Type")
    frappe.clear_cache(doctype="Shift Assignment")
    frappe.clear_cache(doctype="Employee Checkin")
    frappe.clear_cache(doctype="Attendance")
    frappe.clear_cache(doctype="Leave Application")
    frappe.clear_cache(doctype="Official Duty Request")
