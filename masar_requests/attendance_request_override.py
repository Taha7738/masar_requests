"""Safe Attendance Request controller overrides for Frappe/HRMS v15.

AR:
    يعالج هذا الملف خطأ عرض جدول التحذيرات في بيئة التطوير عندما يرسل HRMS
    قائمة ثنائية الأبعاد إلى ``frappe.msgprint(as_table=True)`` ويكون طرفية
    التشغيل TTY، مما يؤدي إلى ``TypeError: unhashable type: 'list'``.

EN:
    This module keeps the standard HRMS behaviour while rendering the
    no-attendance warning table as HTML, avoiding the Frappe v15 TTY crash.
"""

from markupsafe import escape

import frappe
from frappe import _
from frappe.utils import date_diff, format_date
from hrms.hr.doctype.attendance_request.attendance_request import (
    AttendanceRequest as HRMSAttendanceRequest,
)


class CustomAttendanceRequest(HRMSAttendanceRequest):
    """Attendance Request controller with a safe warning-table renderer."""

    def validate_no_attendance_to_create(self):
        attendance_warnings = self.get_attendance_warnings()
        attendance_request_days = date_diff(self.to_date, self.from_date) + 1

        should_block = len(attendance_warnings) == attendance_request_days and not any(
            warning.get("action") == "Overwrite" for warning in attendance_warnings
        )
        if not should_block:
            return

        message = self._build_no_attendance_message(attendance_warnings)
        frappe.throw(
            message,
            title=_("No attendance records to create due to following reasons"),
        )

    def _build_no_attendance_message(self, attendance_warnings):
        """Return an HTML string instead of passing a nested list to msgprint."""
        holiday_only = bool(attendance_warnings) and all(
            warning.get("reason") == "Holiday" for warning in attendance_warnings
        )

        help_message = _(
            "The request cannot be saved because every selected day will be skipped."
        )
        if holiday_only:
            help_message += " " + _(
                "The selected period is marked as a holiday. Enable Include Holidays if this official duty must create attendance on holidays, or correct the employee Holiday List."
            )

        rows = []
        for warning in attendance_warnings:
            rows.append(
                "<tr>"
                f"<td>{escape(format_date(warning.get('date')))}</td>"
                f"<td>{escape(_(warning.get('reason') or ''))}</td>"
                f"<td>{escape(_(warning.get('action') or ''))}</td>"
                "</tr>"
            )

        return str(
            "<div>"
            f"<p>{escape(help_message)}</p>"
            '<div class="table-responsive">'
            '<table class="table table-bordered table-striped">'
            "<thead><tr>"
            f"<th>{escape(_('Date'))}</th>"
            f"<th>{escape(_('Reason'))}</th>"
            f"<th>{escape(_('Action'))}</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table></div></div>"
        )
