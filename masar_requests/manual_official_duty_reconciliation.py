"""
AR: تنفيذ وظائف تطبيق مسار ضمن الوحدة `manual_official_duty_reconciliation`.
EN: Masar application functionality implemented by the `manual_official_duty_reconciliation` module.
"""

# ============================================================================
# AR: التسوية اليدوية الآمنة لساعات المهمة الرسمية غير المغطاة
# EN: Safe manual settlement of uncovered Official Duty hours
# ============================================================================

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt, getdate, now_datetime

from masar_requests.official_duty_engine import (
    COVERAGE_TOLERANCE_SECONDS,
    DETAIL_MANUAL_REVIEW,
    DETAIL_RECONCILED,
    OFFICIAL_DUTY_DOCTYPE,
    STATUS_MANUAL_REVIEW,
    STATUS_PARTIAL,
    STATUS_RECONCILED,
    _annotate_attendance,
    _approved_leave_exists,
    _attendance_data_is_ready,
    _attendance_for_date,
    _create_standard_attendance_request,
    _find_linked_attendance_request,
    _has_unrelated_attendance_request,
    _save_processing_result,
    _summarize_status,
    calculate_daily_coverage,
)

DETAIL_DOCTYPE = "Official Duty Attendance Detail"
MANUAL_RESOLUTION_CONFIRMED = "Confirmed Remaining Hours"
AUTHORIZED_ROLES = {"HR Manager", "System Manager"}
DETAIL_METADATA_FIELDS = {
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "parent",
    "parentfield",
    "parenttype",
    "doctype",
}


def get_manual_reconciliation_custom_fields():
    """
    AR: تنفيذ استرجاع اليدوي التسوية `custom` الحقول ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute get manual reconciliation custom fields within the `manual_official_duty_reconciliation` module.
    """
    return {
        OFFICIAL_DUTY_DOCTYPE: [
            {
                "fieldname": "custom_manual_reconciliation_section",
                "fieldtype": "Section Break",
                "label": "Manual Attendance Reconciliation",
                "insert_after": "attendance_details",
                "depends_on": (
                    'eval:doc.processing_status=="Manual Review" || '
                    '(doc.custom_total_manual_confirmed_hours || 0) > 0'
                ),
                "collapsible": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_total_manual_confirmed_hours",
                "fieldtype": "Float",
                "label": "Administratively Confirmed Hours",
                "insert_after": "custom_manual_reconciliation_section",
                "precision": 4,
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_last_manual_reconciled_by",
                "fieldtype": "Link",
                "label": "Last Manual Reconciliation By",
                "options": "User",
                "insert_after": "custom_total_manual_confirmed_hours",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_reconciliation_column",
                "fieldtype": "Column Break",
                "insert_after": "custom_last_manual_reconciled_by",
                "allow_on_submit": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_last_manual_reconciled_on",
                "fieldtype": "Datetime",
                "label": "Last Manual Reconciliation On",
                "insert_after": "custom_manual_reconciliation_column",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_reconciliation_summary",
                "fieldtype": "Small Text",
                "label": "Manual Reconciliation Summary",
                "insert_after": "custom_last_manual_reconciled_on",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
        ],
        DETAIL_DOCTYPE: [
            {
                "fieldname": "custom_manual_resolution",
                "fieldtype": "Data",
                "label": "Manual Resolution",
                "insert_after": "uncovered_hours",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_confirmed_hours",
                "fieldtype": "Float",
                "label": "Administratively Confirmed Hours",
                "insert_after": "custom_manual_resolution",
                "precision": 4,
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_notes",
                "fieldtype": "Small Text",
                "label": "Manual Reconciliation Notes",
                "insert_after": "custom_manual_confirmed_hours",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_reconciled_by",
                "fieldtype": "Link",
                "label": "Manually Reconciled By",
                "options": "User",
                "insert_after": "custom_manual_notes",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_reconciled_on",
                "fieldtype": "Datetime",
                "label": "Manually Reconciled On",
                "insert_after": "custom_manual_reconciled_by",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
        ],
        "Attendance": [
            {
                "fieldname": "custom_manual_confirmed_working_hours",
                "fieldtype": "Float",
                "label": "Administratively Confirmed Working Hours",
                "insert_after": "custom_physical_working_hours",
                "precision": 4,
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_reconciliation_decision",
                "fieldtype": "Data",
                "label": "Manual Reconciliation Decision",
                "insert_after": "custom_manual_confirmed_working_hours",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_reconciled_by",
                "fieldtype": "Link",
                "label": "Manually Reconciled By",
                "options": "User",
                "insert_after": "custom_manual_reconciliation_decision",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_reconciled_on",
                "fieldtype": "Datetime",
                "label": "Manually Reconciled On",
                "insert_after": "custom_manual_reconciled_by",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manual_reconciliation_note",
                "fieldtype": "Small Text",
                "label": "Manual Reconciliation Note",
                "insert_after": "custom_manual_reconciled_on",
                "read_only": 1,
                "allow_on_submit": 1,
                "no_copy": 1,
                "module": "Masar Requests",
            },
        ],
    }


def setup_manual_reconciliation_fields():
    """
    AR: تنفيذ إعداد اليدوي التسوية الحقول ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute setup manual reconciliation fields within the `manual_official_duty_reconciliation` module.
    """
    create_custom_fields(get_manual_reconciliation_custom_fields(), update=True)
    for doctype in (OFFICIAL_DUTY_DOCTYPE, DETAIL_DOCTYPE, "Attendance"):
        frappe.clear_cache(doctype=doctype)


def is_manual_reconciliation_authorized(user=None, roles=None):
    """
    AR: تنفيذ التحقق من كون اليدوي التسوية `authorized` ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute is manual reconciliation authorized within the `manual_official_duty_reconciliation` module.
    """
    user = user or frappe.session.user
    roles = set(roles if roles is not None else frappe.get_roles(user))
    return user == "Administrator" or bool(roles.intersection(AUTHORIZED_ROLES))


def _require_authorized_user():
    """
    AR: تنفيذ `require` `authorized` المستخدم ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute require authorized user within the `manual_official_duty_reconciliation` module.
    """
    if not is_manual_reconciliation_authorized():
        frappe.throw(
            _("Only HR Manager or System Manager can perform manual attendance reconciliation."),
            frappe.PermissionError,
        )


def _clean_detail_row(row):
    """
    AR: تنفيذ `clean` `detail` `row` ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute clean detail row within the `manual_official_duty_reconciliation` module.
    """
    as_dict = getattr(row, "as_dict", None)
    if callable(as_dict):
        values = as_dict()
    elif isinstance(row, dict):
        values = dict(row)
    else:
        values = dict(row or {})

    # Frappe may materialize an empty Select custom field as numeric 0 on
    # pre-existing child rows. Select validation rejects that value.
    manual_resolution = values.get("custom_manual_resolution")
    if manual_resolution not in (None, "", MANUAL_RESOLUTION_CONFIRMED):
        values["custom_manual_resolution"] = None

    return frappe._dict(
        {
            key: value
            for key, value in values.items()
            if key not in DETAIL_METADATA_FIELDS
        }
    )


def _validate_full_confirmation(uncovered_hours, confirmed_hours):
    """
    AR: تنفيذ التحقق من صحة `full` `confirmation` ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute validate full confirmation within the `manual_official_duty_reconciliation` module.
    """
    uncovered = flt(uncovered_hours, 4)
    confirmed = flt(confirmed_hours, 4)
    tolerance_hours = COVERAGE_TOLERANCE_SECONDS / 3600

    if uncovered <= tolerance_hours:
        frappe.throw(_("There are no uncovered hours requiring manual reconciliation."))
    if confirmed <= 0:
        frappe.throw(_("Administratively confirmed hours must be greater than zero."))
    if confirmed - uncovered > tolerance_hours:
        frappe.throw(
            _("Confirmed hours cannot exceed the currently uncovered hours ({0}).").format(
                uncovered
            )
        )
    if abs(confirmed - uncovered) > tolerance_hours:
        frappe.throw(
            _(
                "This action must confirm all currently uncovered hours ({0}). "
                "Partial manual confirmation remains unsupported to avoid an ambiguous attendance status."
            ).format(uncovered)
        )
    return uncovered


def _get_request(name):
    """
    AR: تنفيذ استرجاع الطلب ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute get request within the `manual_official_duty_reconciliation` module.
    """
    if not frappe.db.exists(OFFICIAL_DUTY_DOCTYPE, name):
        frappe.throw(_("Official Duty Request {0} was not found.").format(name))
    doc = frappe.get_doc(OFFICIAL_DUTY_DOCTYPE, name)
    if doc.docstatus != 1 or doc.workflow_state != "Approved":
        frappe.throw(_("Only an approved Official Duty Request can be manually reconciled."))
    return doc


def _manual_block_reason(doc, attendance_date, coverage=None):
    """
    AR: تنفيذ اليدوي `block` `reason` ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute manual block reason within the `manual_official_duty_reconciliation` module.
    """
    attendance_date = getdate(attendance_date)
    coverage = coverage or calculate_daily_coverage(doc, attendance_date)

    if not _attendance_data_is_ready(coverage):
        return _("Attendance data is not ready yet; wait until the shift processing window ends.")
    if _approved_leave_exists(doc.employee, attendance_date):
        return _("An approved Leave Application overlaps this date.")

    existing = _attendance_for_date(doc.employee, attendance_date, coverage.shift)
    linked_request = _find_linked_attendance_request(doc.name, attendance_date)

    if existing and existing.status in {"On Leave", "Work From Home"}:
        return _("Existing Attendance status {0} cannot be overridden manually.").format(
            existing.status
        )
    if (
        existing
        and existing.attendance_request
        and (
            not linked_request
            or existing.attendance_request != linked_request.name
        )
    ):
        return _("Attendance is linked to another Attendance Request {0}.").format(
            existing.attendance_request
        )

    unrelated = None
    if not linked_request:
        unrelated = _has_unrelated_attendance_request(
            doc.employee,
            attendance_date,
            existing.shift if existing and existing.shift else coverage.shift,
        )
    if unrelated:
        return _("Attendance Request {0} already covers this date.").format(unrelated)
    return None


@frappe.whitelist()
def get_manual_reconciliation_context(name: str):
    """
    AR: تنفيذ استرجاع اليدوي التسوية `context` ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute get manual reconciliation context within the `manual_official_duty_reconciliation` module.
    """
    _require_authorized_user()
    doc = _get_request(name)

    rows = []
    for child in doc.get("attendance_details") or []:
        if child.reconciliation_status != DETAIL_MANUAL_REVIEW:
            continue
        if flt(child.uncovered_hours) <= COVERAGE_TOLERANCE_SECONDS / 3600:
            continue

        coverage = calculate_daily_coverage(doc, child.attendance_date)
        blocked_reason = _manual_block_reason(
            doc,
            child.attendance_date,
            coverage=coverage,
        )
        rows.append(
            {
                "attendance_date": str(getdate(child.attendance_date)),
                "shift": coverage.shift,
                "shift_hours": flt(coverage.shift_hours, 4),
                "official_duty_hours": flt(coverage.official_duty_hours, 4),
                "physical_working_hours": flt(coverage.physical_working_hours, 4),
                "credited_working_hours": flt(coverage.credited_working_hours, 4),
                "uncovered_hours": flt(coverage.uncovered_hours, 4),
                "eligible": not blocked_reason,
                "blocked_reason": blocked_reason,
            }
        )

    return {
        "name": doc.name,
        "processing_status": doc.processing_status,
        "rows": rows,
        "eligible_rows": [row for row in rows if row["eligible"]],
    }


def _attendance_name_from_request(doc, attendance_date, request_name):
    """
    AR: تنفيذ الحضور `name` `from` الطلب ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute attendance name from request within the `manual_official_duty_reconciliation` module.
    """
    return frappe.db.get_value(
        "Attendance",
        {
            "employee": doc.employee,
            "attendance_date": attendance_date,
            "attendance_request": request_name,
            "docstatus": ("!=", 2),
        },
        "name",
    )


@frappe.whitelist()
def apply_manual_reconciliation(
    name: str,
    attendance_date,
    confirmed_hours,
    notes: str,
):
    """
    AR: تنفيذ تطبيق اليدوي التسوية ضمن وحدة `manual_official_duty_reconciliation`.
    EN: Execute apply manual reconciliation within the `manual_official_duty_reconciliation` module.
    """
    _require_authorized_user()
    attendance_date = getdate(attendance_date)
    notes = (notes or "").strip()
    if len(notes) < 5:
        frappe.throw(_("Manual reconciliation notes are required and must be descriptive."))

    frappe.db.sql(
        f"SELECT name FROM `tab{OFFICIAL_DUTY_DOCTYPE}` WHERE name = %s FOR UPDATE",
        name,
    )
    doc = _get_request(name)

    previous_rows = {
        getdate(row.attendance_date): row
        for row in (doc.get("attendance_details") or [])
        if row.get("attendance_date")
    }
    previous = previous_rows.get(attendance_date)
    if not previous:
        frappe.throw(_("No reconciliation detail exists for {0}.").format(attendance_date))
    if previous.reconciliation_status != DETAIL_MANUAL_REVIEW:
        frappe.throw(_("The selected date is no longer awaiting manual review."))

    coverage = calculate_daily_coverage(doc, attendance_date)
    blocked_reason = _manual_block_reason(doc, attendance_date, coverage=coverage)
    if blocked_reason:
        frappe.throw(blocked_reason, title=_("Manual Reconciliation Blocked"))

    manual_hours = _validate_full_confirmation(
        coverage.uncovered_hours,
        confirmed_hours,
    )
    adjusted = frappe._dict(coverage.copy())
    adjusted.pop("checkins", None)
    adjusted.custom_manual_confirmed_hours = manual_hours
    adjusted.credited_working_hours = flt(
        min(adjusted.shift_hours, adjusted.credited_working_hours + manual_hours),
        4,
    )
    adjusted.uncovered_hours = flt(
        max(adjusted.shift_hours - adjusted.credited_working_hours, 0),
        4,
    )
    adjusted.is_fully_covered = (
        adjusted.uncovered_hours <= COVERAGE_TOLERANCE_SECONDS / 3600
    )
    if not adjusted.is_fully_covered:
        frappe.throw(_("The manual confirmation did not fully cover the shift."))

    existing = _attendance_for_date(doc.employee, attendance_date, adjusted.shift)
    linked_request = _find_linked_attendance_request(doc.name, attendance_date)
    request_name = linked_request.name if linked_request else None

    original = frappe._dict(existing or {})
    if existing:
        attendance_name = existing.name
        if existing.status != "Present":
            frappe.db.set_value(
                "Attendance",
                attendance_name,
                {"status": "Present", "half_day_status": None},
                update_modified=False,
            )
    else:
        request_name = _create_standard_attendance_request(doc, adjusted)
        attendance_name = _attendance_name_from_request(
            doc,
            attendance_date,
            request_name,
        )
        if not attendance_name:
            frappe.throw(_("Attendance Request was submitted but no Attendance record was found."))

    _annotate_attendance(
        doc,
        adjusted,
        attendance_name,
        previous=original,
    )

    reconciled_on = now_datetime()
    reconciliation_note = _(
        "HR manually confirmed {0} uncovered hour(s) for Official Duty Request {1}."
    ).format(manual_hours, doc.name)
    frappe.db.set_value(
        "Attendance",
        attendance_name,
        {
            "custom_manual_confirmed_working_hours": manual_hours,
            "custom_manual_reconciliation_decision": MANUAL_RESOLUTION_CONFIRMED,
            "custom_manual_reconciled_by": frappe.session.user,
            "custom_manual_reconciled_on": reconciled_on,
            "custom_manual_reconciliation_note": notes,
            "custom_official_duty_note": reconciliation_note,
        },
        update_modified=False,
    )

    detail_rows = []
    for row_date, row in previous_rows.items():
        if row_date != attendance_date:
            detail_rows.append(_clean_detail_row(row))
            continue

        detail = frappe._dict(adjusted.copy())
        detail.reconciliation_status = DETAIL_RECONCILED
        detail.attendance = attendance_name
        detail.attendance_request = request_name
        detail.attendance_created_by_request = cint(bool(request_name))
        detail.previous_status = row.get("previous_status") or original.get("status")
        detail.previous_half_day_status = (
            row.get("previous_half_day_status") or original.get("half_day_status")
        )
        detail.previous_late_entry = cint(
            row.get("previous_late_entry") or original.get("late_entry")
        )
        detail.previous_early_exit = cint(
            row.get("previous_early_exit") or original.get("early_exit")
        )
        detail.custom_manual_resolution = MANUAL_RESOLUTION_CONFIRMED
        detail.custom_manual_confirmed_hours = manual_hours
        detail.custom_manual_notes = notes
        detail.custom_manual_reconciled_by = frappe.session.user
        detail.custom_manual_reconciled_on = reconciled_on
        detail.message = _(
            "HR confirmed {0} hour(s) administratively. "
            "{1} official-duty hour(s) + {2} administratively confirmed hour(s) "
            "= {3} credited hour(s)."
        ).format(
            manual_hours,
            adjusted.official_duty_hours,
            manual_hours,
            adjusted.credited_working_hours,
        )
        detail_rows.append(detail)

    detail_rows.sort(key=lambda row: getdate(row.get("attendance_date")))
    status = _summarize_status(detail_rows, doc.duty_type)
    if status == STATUS_RECONCILED:
        message = _("Attendance reconciliation completed, including HR-confirmed working hours.")
    elif status in {STATUS_MANUAL_REVIEW, STATUS_PARTIAL}:
        message = _("Some dates still require HR attendance review.")
    else:
        message = _("Manual reconciliation was saved.")

    doc.custom_total_manual_confirmed_hours = flt(
        sum(flt(row.get("custom_manual_confirmed_hours")) for row in detail_rows),
        4,
    )
    doc.custom_last_manual_reconciled_by = frappe.session.user
    doc.custom_last_manual_reconciled_on = reconciled_on
    doc.custom_manual_reconciliation_summary = notes
    _save_processing_result(doc, detail_rows, status, message)

    return {
        "name": doc.name,
        "attendance_date": str(attendance_date),
        "attendance": attendance_name,
        "attendance_request": request_name,
        "manual_confirmed_hours": manual_hours,
        "processing_status": status,
        "credited_working_hours": adjusted.credited_working_hours,
        "uncovered_hours": adjusted.uncovered_hours,
    }
