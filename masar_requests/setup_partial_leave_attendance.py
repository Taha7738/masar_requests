"""
AR: إعداد وتهيئة مكونات التطبيق ضمن الوحدة `setup_partial_leave_attendance`.
EN: Application setup and configuration routines for the `setup_partial_leave_attendance` module.
"""

# ============================================================================
# AR: إعداد حقول تسوية الإجازة الجزئية على سجل الحضور
# EN: Partial-leave reconciliation fields on Attendance
# ============================================================================

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


PARTIAL_LEAVE_ATTENDANCE_FIELDS = (
    "custom_partial_leave_section",
    "custom_partial_leave_application",
    "custom_partial_leave_type",
    "custom_partial_leave_hours",
    "custom_partial_leave_day_fraction",
    "custom_partial_leave_column",
    "custom_partial_leave_from_time",
    "custom_partial_leave_to_time",
    "custom_partial_leave_reconciliation_status",
    "custom_partial_leave_attendance_created",
    "custom_partial_leave_previous_status",
    "custom_partial_leave_previous_half_day_status",
    "custom_partial_leave_previous_leave_type",
    "custom_partial_leave_previous_leave_application",
)

# AR: حقول حالة التسوية على طلب الإجازة نفسه.
# EN: Reconciliation-state fields stored on Leave Application itself.
PARTIAL_LEAVE_APPLICATION_FIELDS = (
    "custom_partial_attendance_section",
    "custom_partial_attendance_status",
    "custom_partial_attendance",
    "custom_partial_attendance_column",
    "custom_partial_attendance_last_processed_on",
    "custom_partial_attendance_message",
)


def get_partial_leave_attendance_fields():
    """
    AR: تنفيذ استرجاع الجزئي الإجازة الحضور الحقول ضمن وحدة `setup_partial_leave_attendance`.
    EN: Execute get partial leave attendance fields within the `setup_partial_leave_attendance` module.

    DETAILS / التفاصيل:
    AR:
            تعريف حقول تدقيق دقيقة على Attendance لربع اليوم والإجازة بالساعات.
            تظل حالة الحضور اليومية قياسية، بينما تحفظ هذه الحقول الكسر والساعات.

        EN:
            Define precise audit fields on Attendance for quarter-day and hourly
            leave. The daily status stays native while these fields store hours
            and the exact day fraction.
    """
    partial_eval = "eval:doc.quarter_day || doc.is_hourly"
    return {
        "Leave Application": [
            {
                "fieldname": "custom_partial_attendance_section",
                "fieldtype": "Section Break",
                "label": "Partial Attendance Reconciliation",
                "insert_after": "custom_shift_hours",
                "depends_on": partial_eval,
                "collapsible": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_attendance_status",
                "fieldtype": "Select",
                "label": "Partial Attendance Status",
                "options": "Pending\nWaiting for Shift End\nReconciled\nManual Review\nFailed\nCancelled",
                "default": "Pending",
                "insert_after": "custom_partial_attendance_section",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_attendance",
                "fieldtype": "Link",
                "label": "Partial Attendance",
                "options": "Attendance",
                "insert_after": "custom_partial_attendance_status",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_attendance_column",
                "fieldtype": "Column Break",
                "insert_after": "custom_partial_attendance",
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_attendance_last_processed_on",
                "fieldtype": "Datetime",
                "label": "Last Partial Attendance Processing",
                "insert_after": "custom_partial_attendance_column",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_attendance_message",
                "fieldtype": "Small Text",
                "label": "Partial Attendance Message",
                "insert_after": "custom_partial_attendance_last_processed_on",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
        ],
        "Attendance": [
            {
                "fieldname": "custom_partial_leave_section",
                "fieldtype": "Section Break",
                "label": "Partial Leave Reconciliation",
                "insert_after": "attendance_request",
                "depends_on": "custom_partial_leave_application",
                "collapsible": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_application",
                "fieldtype": "Link",
                "label": "Partial Leave Application",
                "options": "Leave Application",
                "insert_after": "custom_partial_leave_section",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_type",
                "fieldtype": "Link",
                "label": "Partial Leave Type",
                "options": "Leave Type",
                "insert_after": "custom_partial_leave_application",
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_hours",
                "fieldtype": "Float",
                "label": "Partial Leave Hours",
                "insert_after": "custom_partial_leave_type",
                "precision": 4,
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_day_fraction",
                "fieldtype": "Float",
                "label": "Partial Leave Day Fraction",
                "insert_after": "custom_partial_leave_hours",
                "precision": 4,
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_column",
                "fieldtype": "Column Break",
                "insert_after": "custom_partial_leave_day_fraction",
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_from_time",
                "fieldtype": "Time",
                "label": "Partial Leave From Time",
                "insert_after": "custom_partial_leave_column",
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_to_time",
                "fieldtype": "Time",
                "label": "Partial Leave To Time",
                "insert_after": "custom_partial_leave_from_time",
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_reconciliation_status",
                "fieldtype": "Select",
                "label": "Partial Leave Reconciliation Status",
                "options": "Reconciled\nManual Review\nCancelled",
                "insert_after": "custom_partial_leave_to_time",
                "read_only": 1,
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_attendance_created",
                "fieldtype": "Check",
                "label": "Attendance Created for Partial Leave",
                "insert_after": "custom_partial_leave_reconciliation_status",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_previous_status",
                "fieldtype": "Data",
                "label": "Previous Attendance Status",
                "insert_after": "custom_partial_leave_attendance_created",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_previous_half_day_status",
                "fieldtype": "Data",
                "label": "Previous Half Day Status",
                "insert_after": "custom_partial_leave_previous_status",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_previous_leave_type",
                "fieldtype": "Link",
                "label": "Previous Leave Type",
                "options": "Leave Type",
                "insert_after": "custom_partial_leave_previous_half_day_status",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_partial_leave_previous_leave_application",
                "fieldtype": "Link",
                "label": "Previous Leave Application",
                "options": "Leave Application",
                "insert_after": "custom_partial_leave_previous_leave_type",
                "read_only": 1,
                "hidden": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            },
        ]
    }


def setup_partial_leave_attendance_fields():
    """
    AR: تنفيذ إعداد الجزئي الإجازة الحضور الحقول ضمن وحدة `setup_partial_leave_attendance`.
    EN: Execute setup partial leave attendance fields within the `setup_partial_leave_attendance` module.
    """
    create_custom_fields(get_partial_leave_attendance_fields(), update=True)
    frappe.clear_cache(doctype="Leave Application")
    frappe.clear_cache(doctype="Attendance")


def teardown_partial_leave_attendance_fields():
    """
    AR: تنفيذ `teardown` الجزئي الإجازة الحضور الحقول ضمن وحدة `setup_partial_leave_attendance`.
    EN: Execute teardown partial leave attendance fields within the `setup_partial_leave_attendance` module.
    """
    for doctype, fieldnames in (
        ("Leave Application", PARTIAL_LEAVE_APPLICATION_FIELDS),
        ("Attendance", PARTIAL_LEAVE_ATTENDANCE_FIELDS),
    ):
        frappe.db.delete(
            "Custom Field",
            {
                "dt": doctype,
                "fieldname": ("in", list(fieldnames)),
            },
        )
        frappe.clear_cache(doctype=doctype)
