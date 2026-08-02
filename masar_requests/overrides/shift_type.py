"""
AR: تنفيذ وظائف تطبيق مسار ضمن الوحدة `shift_type`.
EN: Masar application functionality implemented by the `shift_type` module.

DETAILS / التفاصيل:
AR:
    طبقة توافق احترافية لدعم أوقات وردية مختلفة حسب يوم الأسبوع، مع
    المحافظة على منطق HRMS القياسي بقدر الإمكان. لا تعدّل هذه الوحدة
    ملفات HRMS الأصلية، بل تغلف نقاط الحساب المركزية وقت التشغيل بصورة
    محمية وقابلة للتراجع إلى السلوك القياسي عند اختلاف الإصدار.

EN:
    Compatibility layer for weekday-specific Shift Type timings while
    preserving native HRMS behaviour as much as possible. This module does
    not edit HRMS source files; it wraps central timing functions at runtime
    and safely falls back to native behaviour when the installed HRMS API is
    not compatible.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from datetime import date, datetime, time, timedelta
from typing import Iterable

import frappe
from frappe import _
from frappe.utils import cint, cstr, get_datetime, get_time, getdate, now_datetime

LOGGER = logging.getLogger("masar_requests.variable_shift_times")
SUPPORTED_HRMS_MAJOR = 15

DAY_NAMES = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)

# AR: تحفظ المراجع الأصلية لتجنب الترقيع المتكرر وللسماح بالرجوع الآمن.
# EN: Keep original references for idempotent patching and safe fallback.
_ORIGINAL_GET_SHIFT_DETAILS = None
_ORIGINAL_HAS_OVERLAPPING_TIMINGS = None
_ORIGINAL_GET_SHIFT_EVENTS = None
_ORIGINAL_GET_ACTUAL_SHIFT_END = None
_ORIGINAL_MARK_ABSENT_NO_CHECKIN = None
_ORIGINAL_MARK_ABSENT_HALF_DAY = None
_PATCH_APPLIED = False
_PATCH_COMPATIBLE = False


def _time_to_timedelta(value) -> timedelta:
    """
    AR: تنفيذ الوقت `to` `timedelta` ضمن وحدة `shift_type`.
    EN: Execute time to timedelta within the `shift_type` module.
    """
    if isinstance(value, timedelta):
        return value
    if isinstance(value, time):
        return timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)

    parsed = get_time(value)
    return timedelta(hours=parsed.hour, minutes=parsed.minute, seconds=parsed.second)


def _time_to_seconds(value) -> int:
    """
    AR: تنفيذ الوقت `to` `seconds` ضمن وحدة `shift_type`.
    EN: Execute time to seconds within the `shift_type` module.
    """
    return int(_time_to_timedelta(value).total_seconds())


def _duration_minutes(start_time, end_time) -> int:
    """
    AR: تنفيذ `duration` `minutes` ضمن وحدة `shift_type`.
    EN: Execute duration minutes within the `shift_type` module.
    """
    start_seconds = _time_to_seconds(start_time)
    end_seconds = _time_to_seconds(end_time)
    if end_seconds <= start_seconds:
        end_seconds += 24 * 60 * 60
    return round((end_seconds - start_seconds) / 60)


def _is_variable_schedule_enabled(shift_doc) -> bool:
    """
    AR: تنفيذ التحقق من كون `variable` `schedule` `enabled` ضمن وحدة `shift_type`.
    EN: Execute is variable schedule enabled within the `shift_type` module.
    """
    return bool(
        shift_doc
        and shift_doc.meta.has_field("custom_enable_variable_shift_times")
        and cint(shift_doc.get("custom_enable_variable_shift_times"))
    )


def _is_schedule_effective(shift_doc, anchor_date: date) -> bool:
    """
    AR: تنفيذ التحقق من كون `schedule` `effective` ضمن وحدة `shift_type`.
    EN: Execute is schedule effective within the `shift_type` module.
    """
    if not shift_doc.meta.has_field("custom_shift_times_effective_from"):
        return True

    effective_from = shift_doc.get("custom_shift_times_effective_from")
    return not effective_from or getdate(anchor_date) >= getdate(effective_from)


def _get_shift_doc(shift_type_name: str):
    """
    AR: تنفيذ استرجاع الوردية المستند ضمن وحدة `shift_type`.
    EN: Execute get shift doc within the `shift_type` module.
    """
    if not shift_type_name:
        return None
    return frappe.get_cached_doc("Shift Type", shift_type_name)


def get_weekly_off_days(holiday_list_name: str | None) -> set[str]:
    """
    AR: تنفيذ استرجاع `weekly` `off` `days` ضمن وحدة `shift_type`.
    EN: Execute get weekly off days within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            إرجاع أيام العطلة الأسبوعية المتكررة فقط من قائمة العطلات.
            لا تُعامل العطلات الرسمية ذات التاريخ الواحد كعطلة أسبوعية، لأن
            جدول الوردية يمثل أيام الأسبوع وليس تواريخ منفردة.

        EN:
            Return recurring weekly-off weekdays only. One-off official holidays
            are intentionally ignored because the shift table represents weekdays,
            not individual calendar dates.
    """
    if not holiday_list_name:
        return set()

    weekly_off_days: set[str] = set()

    try:
        holiday_dates = frappe.get_all(
            "Holiday",
            filters={
                "parent": holiday_list_name,
                "parenttype": "Holiday List",
                "weekly_off": 1,
            },
            pluck="holiday_date",
        )
        weekly_off_days.update(
            getdate(holiday_date).strftime("%A")
            for holiday_date in holiday_dates
            if holiday_date
        )
    except Exception:
        # AR: بعض النسخ القديمة قد لا تحتوي علم weekly_off في جدول Holiday.
        # EN: Older versions may not expose the weekly_off flag on Holiday rows.
        LOGGER.debug(
            "Could not infer weekly-off days from Holiday rows; using Holiday List fallback.",
            exc_info=True,
        )

    try:
        configured_weekly_off = frappe.db.get_value(
            "Holiday List", holiday_list_name, "weekly_off"
        )
        if configured_weekly_off in DAY_NAMES:
            weekly_off_days.add(configured_weekly_off)
    except Exception:
        LOGGER.debug(
            "Could not read Holiday List weekly_off fallback.",
            exc_info=True,
        )

    return weekly_off_days


def get_working_weekdays(holiday_list_name: str | None) -> tuple[str, ...]:
    """
    AR: تنفيذ استرجاع `working` `weekdays` ضمن وحدة `shift_type`.
    EN: Execute get working weekdays within the `shift_type` module.
    """
    excluded = get_weekly_off_days(holiday_list_name)
    return tuple(day for day in DAY_NAMES if day not in excluded)


@frappe.whitelist()
def get_variable_shift_working_days(holiday_list: str | None = None):
    """
    AR: تنفيذ استرجاع `variable` الوردية `working` `days` ضمن وحدة `shift_type`.
    EN: Execute get variable shift working days within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            واجهة آمنة لصفحة Shift Type لإحضار أيام العمل. تُعاد أسماء الأيام
            بالإنجليزية لأنها القيم القياسية المحفوظة في حقل Select.

        EN:
            Safe endpoint for the Shift Type form. English day names are returned
            because they are the canonical Select values stored in the database.
    """
    excluded_days = get_weekly_off_days(holiday_list)
    working_days = [day for day in DAY_NAMES if day not in excluded_days]
    return {
        "working_days": working_days,
        "excluded_days": [day for day in DAY_NAMES if day in excluded_days],
    }


def get_weekday_times(shift_doc, anchor_date: date):
    """
    AR: تنفيذ استرجاع `weekday` `times` ضمن وحدة `shift_type`.
    EN: Execute get weekday times within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            إرجاع وقت البداية والنهاية لليوم المحدد. عند تعطيل الميزة أو عدم
            وجود صف صالح يستخدم النظام وقت Shift Type القياسي دون تغيير.

        EN:
            Return start/end time for the requested weekday. Native Shift Type
            times are used when the feature is disabled or no valid row exists.
    """
    start_time = shift_doc.start_time
    end_time = shift_doc.end_time
    source = "Standard"

    if not _is_variable_schedule_enabled(shift_doc):
        return start_time, end_time, source
    if not _is_schedule_effective(shift_doc, getdate(anchor_date)):
        return start_time, end_time, source

    day_name = getdate(anchor_date).strftime("%A")
    for row in shift_doc.get("custom_shift_times") or []:
        if row.get("day_of_week") != day_name:
            continue
        if row.get("start_time") is None or row.get("end_time") is None:
            break
        return row.get("start_time"), row.get("end_time"), "Weekday Schedule"

    return start_time, end_time, source


def build_shift_window_for_anchor(shift_doc, anchor_date: date):
    """
    AR: تنفيذ بناء الوردية `window` `for` `anchor` ضمن وحدة `shift_type`.
    EN: Execute build shift window for anchor within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            بناء نافذة وردية قياسية لتاريخ البداية المحدد، بما يشمل هوامش
            الدخول قبل الوردية والخروج بعدها ودعم الورديات الليلية.

        EN:
            Build a native-shaped shift window for an anchor date, including
            check-in/check-out margins and overnight shifts.
    """
    anchor_date = getdate(anchor_date)
    start_time, end_time, source = get_weekday_times(shift_doc, anchor_date)

    start_datetime = datetime.combine(anchor_date, datetime.min.time()) + _time_to_timedelta(start_time)
    end_datetime = datetime.combine(anchor_date, datetime.min.time()) + _time_to_timedelta(end_time)
    if end_datetime <= start_datetime:
        end_datetime += timedelta(days=1)

    before_minutes = cint(shift_doc.get("begin_check_in_before_shift_start_time") or 0)
    after_minutes = cint(shift_doc.get("allow_check_out_after_shift_end_time") or 0)

    return frappe._dict(
        {
            "anchor_date": anchor_date,
            "start_time": start_time,
            "end_time": end_time,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "actual_start": start_datetime - timedelta(minutes=before_minutes),
            "actual_end": end_datetime + timedelta(minutes=after_minutes),
            "source": source,
        }
    )


def _select_shift_window(candidates, for_timestamp: datetime, native_anchor: date | None = None):
    """
    AR: تنفيذ `select` الوردية `window` ضمن وحدة `shift_type`.
    EN: Execute select shift window within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            اختيار النافذة التي تحتوي البصمة أولًا. عند عدم وجود تطابق نستخدم
            تاريخ البداية الذي حدده HRMS القياسي، ثم أقرب نافذة زمنية.

        EN:
            Prefer the window containing the timestamp. Otherwise use the native
            HRMS anchor date, then the closest window as a deterministic fallback.
    """
    containing = [
        candidate
        for candidate in candidates
        if candidate.actual_start <= for_timestamp <= candidate.actual_end
    ]
    if containing:
        return sorted(containing, key=lambda row: row.start_datetime, reverse=True)[0]

    if native_anchor:
        for candidate in candidates:
            if candidate.anchor_date == getdate(native_anchor):
                return candidate

    return min(
        candidates,
        key=lambda row: abs((row.start_datetime - for_timestamp).total_seconds()),
    )


def custom_get_shift_details(shift_type_name: str, for_timestamp: datetime | None = None):
    """
    AR: تنفيذ `custom` استرجاع الوردية `details` ضمن وحدة `shift_type`.
    EN: Execute custom get shift details within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            غلاف متوافق لدالة HRMS المركزية get_shift_details. يعيد نفس البنية
            القياسية تمامًا، لكنه يستبدل وقت اليوم فقط عند تفعيل الجدول.

        EN:
            Compatibility wrapper around HRMS get_shift_details. It returns the
            native structure and overrides only the weekday timing when enabled.
    """
    if not callable(_ORIGINAL_GET_SHIFT_DETAILS):
        return frappe._dict()

    native_details = _ORIGINAL_GET_SHIFT_DETAILS(shift_type_name, for_timestamp)
    if not shift_type_name or not native_details:
        return native_details

    shift_doc = _get_shift_doc(shift_type_name)
    if not _is_variable_schedule_enabled(shift_doc):
        return native_details

    timestamp = get_datetime(for_timestamp or now_datetime())
    native_anchor = (
        native_details.get("start_datetime").date()
        if native_details.get("start_datetime")
        else timestamp.date()
    )

    candidates = [
        build_shift_window_for_anchor(shift_doc, timestamp.date() + timedelta(days=offset))
        for offset in (-1, 0, 1)
    ]
    selected = _select_shift_window(candidates, timestamp, native_anchor)

    # AR: نحافظ على قاموس Shift Type الذي أنشأه HRMS ونبدل الوقت فقط.
    # EN: Preserve the HRMS-created Shift Type dict and override timing only.
    shift_type = frappe._dict(dict(native_details.get("shift_type") or {}))
    shift_type.start_time = selected.start_time
    shift_type.end_time = selected.end_time

    return frappe._dict(
        {
            "shift_type": shift_type,
            "start_datetime": selected.start_datetime,
            "end_datetime": selected.end_datetime,
            "actual_start": selected.actual_start,
            "actual_end": selected.actual_end,
        }
    )


def _weekly_intervals(shift_type_name: str) -> list[tuple[int, int]]:
    """
    AR: تنفيذ `weekly` `intervals` ضمن وحدة `shift_type`.
    EN: Execute weekly intervals within the `shift_type` module.
    """
    shift_doc = _get_shift_doc(shift_type_name)
    if not shift_doc:
        return []

    # AR: نستخدم أسبوعًا حاليًا/مستقبليًا حتى يُحترم تاريخ بدء النفاذ.
    # EN: Use a current/future week so the effective-from date is respected.
    reference_date = getdate()
    effective_from = shift_doc.get("custom_shift_times_effective_from")
    if effective_from and getdate(effective_from) > reference_date:
        reference_date = getdate(effective_from)
    days_until_sunday = (6 - reference_date.weekday()) % 7
    reference_sunday = reference_date + timedelta(days=days_until_sunday)
    intervals = []
    working_days = set(get_working_weekdays(shift_doc.get("holiday_list")))
    for index in range(7):
        anchor = reference_sunday + timedelta(days=index)
        if anchor.strftime("%A") not in working_days:
            continue
        start_time, end_time, _source = get_weekday_times(shift_doc, anchor)
        start = index * 86400 + _time_to_seconds(start_time)
        end = index * 86400 + _time_to_seconds(end_time)
        if end <= start:
            end += 86400
        intervals.append((start, end))

    # AR: نسخ أول يوم بعد نهاية الأسبوع لكشف تداخل وردية السبت الليلية مع الأحد.
    # EN: Duplicate week boundaries to detect Saturday-night/Sunday overlaps.
    week = 7 * 86400
    return intervals + [(start + week, end + week) for start, end in intervals]


def custom_has_overlapping_timings(shift_1: str, shift_2: str) -> bool:
    """
    AR: تنفيذ `custom` التحقق من وجود `overlapping` `timings` ضمن وحدة `shift_type`.
    EN: Execute custom has overlapping timings within the `shift_type` module.
    """
    try:
        intervals_1 = _weekly_intervals(shift_1)
        intervals_2 = _weekly_intervals(shift_2)
        if not intervals_1 or not intervals_2:
            if callable(_ORIGINAL_HAS_OVERLAPPING_TIMINGS):
                return _ORIGINAL_HAS_OVERLAPPING_TIMINGS(shift_1, shift_2)
            return False

        week = 7 * 86400
        expanded_2 = intervals_2 + [(s - week, e - week) for s, e in intervals_2]
        for start_1, end_1 in intervals_1:
            for start_2, end_2 in expanded_2:
                if end_1 > start_2 and start_1 < end_2:
                    return True
        return False
    except Exception:
        LOGGER.warning("Variable shift overlap validation fell back to native HRMS.", exc_info=True)
        if callable(_ORIGINAL_HAS_OVERLAPPING_TIMINGS):
            return _ORIGINAL_HAS_OVERLAPPING_TIMINGS(shift_1, shift_2)
        raise


def custom_get_shift_events(assignments: list[dict]) -> list[dict]:
    """
    AR: تنفيذ `custom` استرجاع الوردية `events` ضمن وحدة `shift_type`.
    EN: Execute custom get shift events within the `shift_type` module.
    """
    try:
        events = []
        for raw_assignment in assignments or []:
            assignment = frappe._dict(raw_assignment)
            shift_doc = _get_shift_doc(assignment.shift_type)
            if not shift_doc:
                raise frappe.DoesNotExistError(assignment.shift_type)

            current_date = getdate(assignment.start_date)
            end_date = getdate(assignment.end_date or getdate())
            while current_date <= end_date:
                window = build_shift_window_for_anchor(shift_doc, current_date)
                event = {
                    "name": assignment.name,
                    "doctype": "Shift Assignment",
                    "start_date": window.start_datetime,
                    "end_date": window.end_datetime,
                    "title": cstr(assignment.employee_name) + ": " + cstr(assignment.shift_type),
                    "docstatus": assignment.docstatus,
                    "allDay": 0,
                    "convertToUserTz": 0,
                }
                if event not in events:
                    events.append(event)
                current_date += timedelta(days=1)

        return events
    except Exception:
        LOGGER.warning(
            "Variable shift calendar rendering fell back to native HRMS.",
            exc_info=True,
        )
        if callable(_ORIGINAL_GET_SHIFT_EVENTS):
            return _ORIGINAL_GET_SHIFT_EVENTS(assignments)
        raise


def custom_get_actual_shift_end(shift, current_datetime):
    """
    AR: تنفيذ `custom` استرجاع `actual` الوردية `end` ضمن وحدة `shift_type`.
    EN: Execute custom get actual shift end within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            تحديد آخر نهاية وردية فعلية وفق جدول اليوم. تستخدمها مزامنة البصمات
            التلقائية، وتختار آخر نافذة انتهت بدل الاعتماد على وقت الوردية العام.

        EN:
            Resolve the latest actual shift end using weekday timings for automatic
            checkin synchronization instead of the base Shift Type start time.
    """
    try:
        current_datetime = get_datetime(current_datetime)
        shift_name = shift.name if hasattr(shift, "name") else shift.get("name")
        shift_doc = _get_shift_doc(shift_name)
        if not shift_doc or not _is_variable_schedule_enabled(shift_doc):
            if callable(_ORIGINAL_GET_ACTUAL_SHIFT_END):
                return _ORIGINAL_GET_ACTUAL_SHIFT_END(shift, current_datetime)
            return current_datetime

        candidates = [
            build_shift_window_for_anchor(
                shift_doc,
                current_datetime.date() + timedelta(days=offset),
            )
            for offset in (-1, 0)
        ]
        completed = [row.actual_end for row in candidates if row.actual_end < current_datetime]
        if completed:
            return max(completed)
        return candidates[-1].actual_end
    except Exception:
        LOGGER.warning("Variable shift last-sync calculation fell back to native HRMS.", exc_info=True)
        if callable(_ORIGINAL_GET_ACTUAL_SHIFT_END):
            return _ORIGINAL_GET_ACTUAL_SHIFT_END(shift, current_datetime)
        raise


def custom_mark_absent_for_dates_with_no_attendance(self, employee: str):
    """
    AR: تنفيذ `custom` `mark` `absent` `for` `dates` `with` `no` الحضور ضمن وحدة `shift_type`.
    EN: Execute custom mark absent for dates with no attendance within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            تغليف محدود لمنطق الغياب القياسي بحيث يستخدم بداية الوردية الصحيحة
            لكل يوم. عند حدوث خطأ غير متوقع يرجع إلى دالة HRMS الأصلية.

        EN:
            Limited wrapper for native no-checkin absence handling using the
            date-specific shift start. Unexpected failures fall back to HRMS.
    """
    try:
        from hrms.hr.doctype.attendance.attendance import mark_attendance
        from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift

        for attendance_date in self.get_dates_for_attendance(employee):
            window = get_shift_window_for_date(self.name, attendance_date)
            timestamp = (
                window.start_datetime
                if window
                else datetime.combine(getdate(attendance_date), get_time(self.start_time))
            )
            shift_details = get_employee_shift(employee, timestamp, True)
            if not shift_details or shift_details.shift_type.name != self.name:
                continue

            attendance = mark_attendance(employee, attendance_date, "Absent", self.name)
            if not attendance:
                continue

            frappe.get_doc(
                {
                    "doctype": "Comment",
                    "comment_type": "Comment",
                    "reference_doctype": "Attendance",
                    "reference_name": attendance,
                    "content": frappe._(
                        "Employee was marked Absent due to missing Employee Checkins."
                    ),
                }
            ).insert(ignore_permissions=True)
    except Exception:
        LOGGER.warning(
            "Variable shift no-checkin absence handling fell back to native HRMS.",
            exc_info=True,
        )
        if callable(_ORIGINAL_MARK_ABSENT_NO_CHECKIN):
            return _ORIGINAL_MARK_ABSENT_NO_CHECKIN(self, employee)
        raise


def custom_mark_absent_for_half_day_dates(self, employee):
    """
    AR: تنفيذ `custom` `mark` `absent` `for` `half` `day` `dates` ضمن وحدة `shift_type`.
    EN: Execute custom mark absent for half day dates within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            تغليف معالجة النصف الآخر كغياب مع استخدام توقيت اليوم الصحيح.
            يحافظ على السلوك القياسي ويرجع إليه عند فشل طبقة التوافق.

        EN:
            Wrap native other-half absence handling with the correct weekday
            timing and fall back to standard HRMS on compatibility failures.
    """
    try:
        from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift

        half_day_attendances = frappe.get_all(
            "Attendance",
            filters={
                "employee": employee,
                "status": "Half Day",
                "modify_half_day_status": 1,
                "attendance_date": ["<=", getdate(self.last_sync_of_checkin)],
            },
            fields=["name", "attendance_date"],
        )
        for attendance in half_day_attendances:
            window = get_shift_window_for_date(self.name, attendance.attendance_date)
            timestamp = (
                window.start_datetime
                if window
                else datetime.combine(getdate(attendance.attendance_date), get_time(self.start_time))
            )
            shift_details = get_employee_shift(employee, timestamp, True)
            if not shift_details or shift_details.shift_type.name != self.name:
                continue

            frappe.db.set_value(
                "Attendance",
                attendance.name,
                {
                    "shift": self.name,
                    "half_day_status": "Absent",
                    "modify_half_day_status": 0,
                },
            )
            frappe.get_doc(
                {
                    "doctype": "Comment",
                    "comment_type": "Comment",
                    "reference_doctype": "Attendance",
                    "reference_name": attendance.name,
                    "content": frappe._(
                        "Employee was marked Absent for other half due to missing Employee Checkins."
                    ),
                }
            ).insert(ignore_permissions=True)
    except Exception:
        LOGGER.warning(
            "Variable shift half-day absence handling fell back to native HRMS.",
            exc_info=True,
        )
        if callable(_ORIGINAL_MARK_ABSENT_HALF_DAY):
            return _ORIGINAL_MARK_ABSENT_HALF_DAY(self, employee)
        raise


def _serialize_schedule(doc) -> tuple:
    """
    AR: تنفيذ `serialize` `schedule` ضمن وحدة `shift_type`.
    EN: Execute serialize schedule within the `shift_type` module.
    """
    rows = []
    for row in doc.get("custom_shift_times") or []:
        rows.append(
            (
                row.get("day_of_week"),
                str(row.get("start_time") or ""),
                str(row.get("end_time") or ""),
            )
        )
    return (
        cint(doc.get("custom_enable_variable_shift_times")),
        str(doc.get("custom_shift_times_effective_from") or ""),
        tuple(sorted(rows)),
    )


def generate_shift_times(doc, method=None):
    """
    AR: تنفيذ `generate` الوردية `times` ضمن وحدة `shift_type`.
    EN: Execute generate shift times within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            إضافة أيام العمل الناقصة مع الحفاظ الكامل على تعديلات المستخدم،
            واستبعاد أيام العطلة الأسبوعية المتكررة من قائمة العطلات المحددة.
            تبقى العطلات الرسمية ذات التاريخ الواحد تحت إدارة HRMS القياسية.

        EN:
            Add missing working weekdays while preserving all user edits and
            excluding recurring weekly-off days from the selected Holiday List.
            One-off official holidays remain managed by native HRMS.
    """
    if not doc.meta.has_field("custom_shift_times"):
        return

    working_days = get_working_weekdays(doc.get("holiday_list"))
    existing = {}
    for row in doc.get("custom_shift_times") or []:
        day_name = row.get("day_of_week")
        if day_name in working_days and day_name not in existing:
            existing[day_name] = row

    normalized_rows = []
    for day_name in working_days:
        row = existing.get(day_name)
        if row:
            if row.get("start_time") is None:
                row.start_time = doc.start_time
            if row.get("end_time") is None:
                row.end_time = doc.end_time
            if row.meta.has_field("shift_hours"):
                row.shift_hours = round(_duration_minutes(row.start_time, row.end_time) / 60, 4)
            normalized_rows.append(row)
            continue

        values = {
            "doctype": "Shift Time Table",
            "day_of_week": day_name,
            "start_time": doc.start_time,
            "end_time": doc.end_time,
            "shift_hours": round(_duration_minutes(doc.start_time, doc.end_time) / 60, 4),
        }
        normalized_rows.append(values)

    doc.set("custom_shift_times", normalized_rows)


def validate_shift_times(doc, method=None):
    """
    AR: تنفيذ التحقق من صحة الوردية `times` ضمن وحدة `shift_type`.
    EN: Execute validate shift times within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            التحقق من اكتمال الأيام، منع التكرار، دعم الوردية الليلية، وحماية
            البصمات غير المعالجة عند تغيير جدول نافذ.

        EN:
            Validate completeness, duplicates, overnight timing, and protect
            unprocessed checkins when an effective schedule is changed.
    """
    if not doc.meta.has_field("custom_shift_times"):
        return

    generate_shift_times(doc)
    if not _is_variable_schedule_enabled(doc):
        return

    seen = set()
    before_minutes = cint(doc.get("begin_check_in_before_shift_start_time") or 0)
    after_minutes = cint(doc.get("allow_check_out_after_shift_end_time") or 0)

    for row in doc.get("custom_shift_times") or []:
        day_name = row.get("day_of_week")
        if day_name not in DAY_NAMES:
            frappe.throw(_("Invalid day in Variable Weekday Times: {0}").format(day_name or _("Empty")))
        if day_name in seen:
            frappe.throw(_("Day {0} is repeated in Variable Weekday Times.").format(_(day_name)))
        seen.add(day_name)

        if row.get("start_time") is None or row.get("end_time") is None:
            frappe.throw(_("Start Time and End Time are required for {0}.").format(_(day_name)))
        if _time_to_seconds(row.start_time) == _time_to_seconds(row.end_time):
            frappe.throw(_("Start time and end time cannot be same for {0}.").format(_(day_name)))

        duration = _duration_minutes(row.start_time, row.end_time)
        if duration + before_minutes + after_minutes >= 1440:
            frappe.throw(
                _("The shift window for {0}, including check-in/out margins, must be less than 24 hours.").format(
                    _(day_name)
                )
            )
        if row.meta.has_field("shift_hours"):
            row.shift_hours = round(duration / 60, 4)

    working_days = get_working_weekdays(doc.get("holiday_list"))
    if not working_days:
        frappe.throw(
            _(
                "No working weekdays are available after excluding weekly-off days from Holiday List."
            )
        )

    unexpected = [day for day in seen if day not in working_days]
    if unexpected:
        frappe.throw(
            _("Weekly-off days must not appear in Variable Weekday Times: {0}").format(
                ", ".join(_(day) for day in unexpected)
            )
        )

    missing = [day for day in working_days if day not in seen]
    if missing:
        frappe.throw(
            _("Variable Weekday Times must contain all working weekdays: {0}").format(
                ", ".join(_(day) for day in missing)
            )
        )

    previous = doc.get_doc_before_save()
    if (
        previous
        and not getattr(doc.flags, "ignore_variable_shift_checkins", False)
        and _serialize_schedule(previous) != _serialize_schedule(doc)
        and frappe.db.exists(
            "Employee Checkin",
            {
                "shift": doc.name,
                "attendance": ["is", "not set"],
                "skip_auto_attendance": 0,
                "offshift": 0,
            },
        )
    ):
        frappe.throw(
            title=_("Unmarked Check-in Logs Found"),
            msg=_("Mark attendance for existing check-in/out logs before changing variable shift times."),
        )


def clear_shift_schedule_cache(doc=None, method=None):
    """
    AR: تنفيذ `clear` الوردية `schedule` `cache` ضمن وحدة `shift_type`.
    EN: Execute clear shift schedule cache within the `shift_type` module.
    """
    if doc and getattr(doc, "name", None):
        frappe.clear_cache(doctype="Shift Type")
        try:
            frappe.clear_document_cache("Shift Type", doc.name)
        except AttributeError:
            pass


def refresh_unprocessed_checkins_for_shift(shift_name: str) -> int:
    """
    AR: تنفيذ `refresh` `unprocessed` `checkins` `for` الوردية ضمن وحدة `shift_type`.
    EN: Execute refresh unprocessed checkins for shift within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            إعادة حساب نافذة الوردية للبصمات غير المرتبطة بحضور بعد تفعيل أو
            تغيير جدول الأيام. لا تمس البصمات المرتبطة بحضور معتمد.

        EN:
            Recalculate shift windows for unlinked Employee Checkins after enabling
            or changing weekday timings. Checkins linked to Attendance are untouched.
    """
    if not shift_name:
        return 0

    assigned_employees = set(
        frappe.get_all(
            "Shift Assignment",
            filters={"shift_type": shift_name, "docstatus": 1, "status": "Active"},
            pluck="employee",
        )
    )
    assigned_employees.update(
        frappe.get_all(
            "Employee",
            filters={"default_shift": shift_name, "status": "Active"},
            pluck="name",
        )
    )
    if not assigned_employees:
        return 0

    rows = frappe.get_all(
        "Employee Checkin",
        filters={
            "employee": ["in", sorted(assigned_employees)],
            "attendance": ["is", "not set"],
            "skip_auto_attendance": 0,
        },
        or_filters={"shift": shift_name, "offshift": 1},
        fields=["name"],
        order_by="time asc",
    )
    updated = 0
    for row in rows:
        checkin = frappe.get_doc("Employee Checkin", row.name)

        # AR: إزالة القيم المشتقة القديمة قبل إعادة جلب الوردية الصحيحة.
        # EN: Clear old derived values before resolving the correct shift again.
        checkin.shift = None
        checkin.offshift = 1
        checkin.shift_actual_start = None
        checkin.shift_actual_end = None
        checkin.shift_start = None
        checkin.shift_end = None
        checkin.fetch_shift()

        frappe.db.set_value(
            "Employee Checkin",
            checkin.name,
            {
                "shift": checkin.shift,
                "offshift": checkin.offshift,
                "shift_actual_start": checkin.shift_actual_start,
                "shift_actual_end": checkin.shift_actual_end,
                "shift_start": checkin.shift_start,
                "shift_end": checkin.shift_end,
            },
            update_modified=False,
        )
        updated += 1

    return updated


def resolve_employee_shift_name(employee: str, on_date, requested_shift: str | None = None):
    """
    AR: تنفيذ تحديد الموظف الوردية `name` ضمن وحدة `shift_type`.
    EN: Execute resolve employee shift name within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            تحديد الوردية الصريحة أولًا، ثم Shift Assignment النشط، ثم Default Shift.
            يمنع الغموض عند وجود أكثر من إسناد في التاريخ نفسه.

        EN:
            Resolve explicit shift, active Shift Assignment, then Employee default.
            Multiple same-day assignments are rejected as ambiguous.
    """
    if requested_shift:
        return requested_shift

    on_date = getdate(on_date)
    rows = frappe.db.sql(
        """
        SELECT shift_type
          FROM `tabShift Assignment`
         WHERE employee = %s
           AND docstatus = 1
           AND status = 'Active'
           AND start_date <= %s
           AND (end_date IS NULL OR end_date >= %s)
         ORDER BY start_date DESC, modified DESC
        """,
        (employee, on_date, on_date),
        as_dict=True,
    )
    assignments = list(dict.fromkeys(row.shift_type for row in rows if row.shift_type))
    if len(assignments) > 1:
        frappe.throw(
            _("More than one shift is assigned on {0}. Please select the Shift explicitly.").format(on_date)
        )
    if assignments:
        return assignments[0]
    return frappe.db.get_value("Employee", employee, "default_shift")


def get_shift_window_for_date(shift_type_name: str, on_date):
    """
    AR: تنفيذ استرجاع الوردية `window` `for` التاريخ ضمن وحدة `shift_type`.
    EN: Execute get shift window for date within the `shift_type` module.
    """
    shift_doc = _get_shift_doc(shift_type_name)
    if not shift_doc:
        return frappe._dict()

    window = build_shift_window_for_anchor(shift_doc, getdate(on_date))
    return frappe._dict(
        {
            "shift_type": shift_type_name,
            "start_time": window.start_time,
            "end_time": window.end_time,
            "start_datetime": window.start_datetime,
            "end_datetime": window.end_datetime,
            "actual_start": window.actual_start,
            "actual_end": window.actual_end,
            "shift_hours": round((window.end_datetime - window.start_datetime).total_seconds() / 3600, 4),
            "source": window.source,
        }
    )


def get_employee_shift_window_data(employee: str, on_date, requested_shift: str | None = None):
    """
    AR: تنفيذ استرجاع الموظف الوردية `window` `data` ضمن وحدة `shift_type`.
    EN: Execute get employee shift window data within the `shift_type` module.
    """
    shift_name = resolve_employee_shift_name(employee, on_date, requested_shift)
    if not shift_name:
        return frappe._dict()
    return get_shift_window_for_date(shift_name, on_date)


@frappe.whitelist()
def get_employee_shift_window(employee: str, date: str, shift_type: str | None = None):
    """
    AR: تنفيذ استرجاع الموظف الوردية `window` ضمن وحدة `shift_type`.
    EN: Execute get employee shift window within the `shift_type` module.
    """
    if not employee or not date:
        return None
    return get_employee_shift_window_data(employee, date, shift_type)


def _signature_is_compatible(function, required_parameters: Iterable[str]) -> bool:
    """
    AR: تنفيذ `signature` التحقق من كون `compatible` ضمن وحدة `shift_type`.
    EN: Execute signature is compatible within the `shift_type` module.
    """
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return False
    return all(parameter in parameters for parameter in required_parameters)


def apply_shift_times_patch():
    """
    AR: تنفيذ تطبيق الوردية `times` تصحيح ضمن وحدة `shift_type`.
    EN: Execute apply shift times patch within the `shift_type` module.

    DETAILS / التفاصيل:
    AR:
            تطبيق طبقة التوافق على أقل عدد ممكن من نقاط HRMS المركزية. تفحص
            التواقيع قبل التغليف، ولا تعدّل ملفات HRMS، وإذا تغيرت واجهته في
            تحديث مستقبلي يبقى السلوك القياسي فعالًا وتُعطل الميزة بأمان.

        EN:
            Patch the smallest possible set of central HRMS timing points. Function
            signatures are checked first, HRMS files are never edited, and future
            API incompatibility safely retains native behaviour while disabling
            only the variable weekday feature.
    """
    global _ORIGINAL_GET_SHIFT_DETAILS
    global _ORIGINAL_HAS_OVERLAPPING_TIMINGS
    global _ORIGINAL_GET_SHIFT_EVENTS
    global _ORIGINAL_GET_ACTUAL_SHIFT_END
    global _ORIGINAL_MARK_ABSENT_NO_CHECKIN
    global _ORIGINAL_MARK_ABSENT_HALF_DAY
    global _PATCH_APPLIED
    global _PATCH_COMPATIBLE

    if _PATCH_APPLIED:
        return _PATCH_COMPATIBLE

    try:
        hrms_package = importlib.import_module("hrms")
        shift_assignment = importlib.import_module(
            "hrms.hr.doctype.shift_assignment.shift_assignment"
        )
        shift_type_module = importlib.import_module(
            "hrms.hr.doctype.shift_type.shift_type"
        )
    except (ImportError, ModuleNotFoundError):
        LOGGER.warning(
            "HRMS shift modules are unavailable; native behaviour retained and variable weekday times disabled."
        )
        return False

    hrms_version = cstr(getattr(hrms_package, "__version__", ""))
    if hrms_version:
        try:
            installed_major = int(hrms_version.lstrip("v").split(".", 1)[0])
        except (TypeError, ValueError):
            installed_major = None
        if installed_major is not None and installed_major != SUPPORTED_HRMS_MAJOR:
            LOGGER.warning(
                "HRMS major version %s is outside the validated V21 compatibility range; native behaviour retained.",
                hrms_version,
            )
            return False

    original_details = getattr(shift_assignment, "get_shift_details", None)
    original_overlap = getattr(shift_assignment, "has_overlapping_timings", None)
    original_events = getattr(shift_assignment, "get_shift_events", None)
    original_actual_shift_end = getattr(shift_type_module, "get_actual_shift_end", None)
    shift_type_class = getattr(shift_type_module, "ShiftType", None)
    original_mark_absent = getattr(
        shift_type_class, "mark_absent_for_dates_with_no_attendance", None
    )
    original_mark_half_day = getattr(
        shift_type_class, "mark_absent_for_half_day_dates", None
    )

    # AR: get_shift_details هي النقطة المحورية للبصمة وتحديد الوردية.
    # EN: get_shift_details is the critical Employee Checkin/shift resolver point.
    if not callable(original_details) or not _signature_is_compatible(
        original_details, ("shift_type_name", "for_timestamp")
    ):
        LOGGER.warning(
            "Unsupported HRMS get_shift_details signature; native behaviour retained and variable weekday times disabled."
        )
        return False

    _ORIGINAL_GET_SHIFT_DETAILS = original_details
    _ORIGINAL_HAS_OVERLAPPING_TIMINGS = original_overlap
    _ORIGINAL_GET_SHIFT_EVENTS = original_events
    _ORIGINAL_GET_ACTUAL_SHIFT_END = original_actual_shift_end
    _ORIGINAL_MARK_ABSENT_NO_CHECKIN = original_mark_absent
    _ORIGINAL_MARK_ABSENT_HALF_DAY = original_mark_half_day

    try:
        shift_assignment.get_shift_details = custom_get_shift_details

        if callable(original_overlap) and _signature_is_compatible(
            original_overlap, ("shift_1", "shift_2")
        ):
            shift_assignment.has_overlapping_timings = custom_has_overlapping_timings

        if callable(original_events) and _signature_is_compatible(
            original_events, ("assignments",)
        ):
            shift_assignment.get_shift_events = custom_get_shift_events

        # AR: Shift Type يحتفظ بمراجع محلية لبعض الدوال؛ نحدثها عند التطابق فقط.
        # EN: Shift Type may keep local aliases; replace only exact native references.
        if getattr(shift_type_module, "get_shift_details", None) is original_details:
            shift_type_module.get_shift_details = custom_get_shift_details

        if callable(original_actual_shift_end) and _signature_is_compatible(
            original_actual_shift_end, ("shift", "current_datetime")
        ):
            shift_type_module.get_actual_shift_end = custom_get_actual_shift_end

        if shift_type_class and callable(original_mark_absent) and _signature_is_compatible(
            original_mark_absent, ("self", "employee")
        ):
            shift_type_class.mark_absent_for_dates_with_no_attendance = (
                custom_mark_absent_for_dates_with_no_attendance
            )

        if shift_type_class and callable(original_mark_half_day) and _signature_is_compatible(
            original_mark_half_day, ("self", "employee")
        ):
            shift_type_class.mark_absent_for_half_day_dates = (
                custom_mark_absent_for_half_day_dates
            )

        # AR: تحديث مراجع HRMS المحملة مسبقًا إلى الدالة الأصلية فقط.
        # EN: Update loaded HRMS aliases only when they still point to native code.
        import sys

        for module_name, module in list(sys.modules.items()):
            if not module_name.startswith("hrms.") or module is None:
                continue
            if getattr(module, "get_shift_details", None) is original_details:
                module.get_shift_details = custom_get_shift_details

        shift_assignment._masar_variable_shift_times_patch_applied = True
        _PATCH_APPLIED = True
        _PATCH_COMPATIBLE = True
        return True
    except Exception:
        # AR: إرجاع جميع المراجع التي بدأ تعديلها قبل إعادة الخطأ للتحذير فقط.
        # EN: Restore every touched reference before reporting a safe warning.
        shift_assignment.get_shift_details = original_details
        if callable(original_overlap):
            shift_assignment.has_overlapping_timings = original_overlap
        if callable(original_events):
            shift_assignment.get_shift_events = original_events
        if getattr(shift_type_module, "get_shift_details", None) is custom_get_shift_details:
            shift_type_module.get_shift_details = original_details
        if callable(original_actual_shift_end):
            shift_type_module.get_actual_shift_end = original_actual_shift_end
        if shift_type_class and callable(original_mark_absent):
            shift_type_class.mark_absent_for_dates_with_no_attendance = original_mark_absent
        if shift_type_class and callable(original_mark_half_day):
            shift_type_class.mark_absent_for_half_day_dates = original_mark_half_day

        LOGGER.warning(
            "Variable weekday shift compatibility layer failed; all native HRMS references were restored.",
            exc_info=True,
        )
        return False


def audit_shift_times_patch():
    """
    AR: تنفيذ تدقيق الوردية `times` تصحيح ضمن وحدة `shift_type`.
    EN: Execute audit shift times patch within the `shift_type` module.
    """
    status = {
        "validated_hrms_major": SUPPORTED_HRMS_MAJOR,
        "installed_hrms_version": None,
        "patch_applied": _PATCH_APPLIED,
        "patch_compatible": _PATCH_COMPATIBLE,
        "get_shift_details_wrapped": False,
        "overlap_validation_wrapped": False,
        "calendar_events_wrapped": False,
        "last_sync_calculation_wrapped": False,
        "no_checkin_absence_wrapped": False,
        "half_day_absence_wrapped": False,
    }
    try:
        hrms_package = importlib.import_module("hrms")
        status["installed_hrms_version"] = cstr(getattr(hrms_package, "__version__", "")) or None
        shift_assignment = importlib.import_module(
            "hrms.hr.doctype.shift_assignment.shift_assignment"
        )
        shift_type_module = importlib.import_module(
            "hrms.hr.doctype.shift_type.shift_type"
        )
        shift_type_class = getattr(shift_type_module, "ShiftType", None)
        status.update(
            {
                "get_shift_details_wrapped": (
                    getattr(shift_assignment, "get_shift_details", None)
                    is custom_get_shift_details
                ),
                "overlap_validation_wrapped": (
                    getattr(shift_assignment, "has_overlapping_timings", None)
                    is custom_has_overlapping_timings
                ),
                "calendar_events_wrapped": (
                    getattr(shift_assignment, "get_shift_events", None)
                    is custom_get_shift_events
                ),
                "last_sync_calculation_wrapped": (
                    getattr(shift_type_module, "get_actual_shift_end", None)
                    is custom_get_actual_shift_end
                ),
                "no_checkin_absence_wrapped": (
                    getattr(
                        shift_type_class,
                        "mark_absent_for_dates_with_no_attendance",
                        None,
                    )
                    is custom_mark_absent_for_dates_with_no_attendance
                ),
                "half_day_absence_wrapped": (
                    getattr(shift_type_class, "mark_absent_for_half_day_dates", None)
                    is custom_mark_absent_for_half_day_dates
                ),
            }
        )
    except (ImportError, ModuleNotFoundError):
        pass

    required = (
        "get_shift_details_wrapped",
        "last_sync_calculation_wrapped",
        "no_checkin_absence_wrapped",
        "half_day_absence_wrapped",
    )
    status["patch_compatible"] = bool(
        _PATCH_COMPATIBLE and all(status[key] for key in required)
    )
    return status
