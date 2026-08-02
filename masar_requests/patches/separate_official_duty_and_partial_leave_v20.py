"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `separate_official_duty_and_partial_leave_v20` على المواقع القائمة.
EN: Idempotent migration patch for applying `separate_official_duty_and_partial_leave_v20` changes to existing sites.
"""

# ============================================================================
# AR: V20 فصل المهمة الرسمية وإصلاح حضور/رواتب الإجازة الجزئية
# EN: V20 Official Duty separation and partial-leave attendance/payroll fix
# ============================================================================

import frappe

from masar_requests.hr_user_read_only import setup_hr_user_read_only_permissions
from masar_requests.setup_official_duty_request import (
    cleanup_legacy_attendance_request_customization,
    migrate_legacy_official_duty_records,
    setup_official_duty_request_all,
)
from masar_requests.setup_partial_leave_attendance import (
    setup_partial_leave_attendance_fields,
)


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `separate_official_duty_and_partial_leave_v20`.
    EN: Execute execute within the `separate_official_duty_and_partial_leave_v20` module.

    DETAILS / التفاصيل:
    AR:
            ترتيب الترقية متعمد: إنشاء المستند والحقول، نسخ السجلات التاريخية،
            ثم حذف تخصيصات Attendance Request القديمة. لا تحذف الترقية أي
            Attendance Request أو Attendance أو Employee Checkin تاريخي.

        EN:
            Upgrade order is intentional: create the new model/fields, migrate
            historical records, then remove legacy Attendance Request customization.
            No historical Attendance Request, Attendance, or Employee Checkin is deleted.
    """
    setup_official_duty_request_all()
    setup_partial_leave_attendance_fields()

    migrated = migrate_legacy_official_duty_records()
    cleanup_result = cleanup_legacy_attendance_request_customization()
    setup_hr_user_read_only_permissions()

    for doctype in (
        "Official Duty Request",
        "Attendance Request",
        "Attendance",
        "Leave Application",
        "Salary Slip",
    ):
        frappe.clear_cache(doctype=doctype)
    frappe.clear_cache()

    # AR: تسجيل ملخص غير مزعج في السجل للمراجعة بعد migrate.
    # EN: Log a concise migration summary for post-migrate review.
    frappe.logger("masar_requests").info(
        "V20 migration complete: migrated=%s cleanup=%s",
        migrated,
        cleanup_result,
    )
