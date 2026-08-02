"""
AR: محرك قواعد الأعمال والمعالجة ضمن الوحدة `official_duty_engine`.
EN: Business-rule and processing engine for the `official_duty_engine` module.
"""

# ============================================================================
# AR: محرك تسوية الحضور للمهمة الرسمية بالساعات أو اليوم الكامل
# EN: Hourly and full-day Official Duty attendance reconciliation engine
# ============================================================================

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, get_time, getdate, now_datetime

from masar_requests.overrides.shift_type import (
    get_employee_shift_window_data,
    resolve_employee_shift_name,
)

OFFICIAL_DUTY_DOCTYPE = "Official Duty Request"
DETAIL_DOCTYPE = "Official Duty Attendance Detail"

DUTY_TYPE_HOURLY = "Hourly"
DUTY_TYPE_FULL_DAY = "Full Day"
DUTY_TYPE_NO_ADJUSTMENT = "No Attendance Adjustment"

STATUS_PENDING = "Pending"
STATUS_WAITING = "Waiting for Shift End"
STATUS_PARTIAL = "Partially Reconciled"
STATUS_RECONCILED = "Reconciled"
STATUS_MANUAL_REVIEW = "Manual Review"
STATUS_NO_ADJUSTMENT = "No Attendance Adjustment"
STATUS_FAILED = "Failed"
STATUS_LEGACY = "Legacy Linked"

DETAIL_PENDING = "Pending"
DETAIL_WAITING = "Waiting for Shift End"
DETAIL_RECONCILED = "Reconciled"
DETAIL_MANUAL_REVIEW = "Manual Review"
DETAIL_NO_ADJUSTMENT = "No Attendance Adjustment"
DETAIL_FAILED = "Failed"

# AR: القيم الأصلية المستخدمة في إعدادات Shift Type داخل HRMS v15.
# EN: Native Shift Type option values used by HRMS v15.
CHECKIN_MODE_ALTERNATING = "Alternating entries as IN and OUT during the same shift"
CHECKIN_MODE_STRICT = "Strictly based on Log Type in Employee Checkin"
HOURS_MODE_FIRST_LAST = "First Check-in and Last Check-out"
HOURS_MODE_EVERY_VALID = "Every Valid Check-in and Check-out"

# AR: سماحية دقيقة واحدة للفرق الناتج عن ثواني البصمة أو التقريب.
# EN: One-minute tolerance for checkin seconds and rounding differences.
COVERAGE_TOLERANCE_SECONDS = 60


def _as_time(value) -> time:
    """
    AR: تنفيذ `as` الوقت ضمن وحدة `official_duty_engine`.
    EN: Execute as time within the `official_duty_engine` module.
    """
    if isinstance(value, time):
        return value
    if isinstance(value, timedelta):
        total = int(value.total_seconds()) % (24 * 60 * 60)
        return time(total // 3600, (total % 3600) // 60, total % 60)
    return get_time(value)


def _combine(day: date, value) -> datetime:
    """
    AR: تنفيذ `combine` ضمن وحدة `official_duty_engine`.
    EN: Execute combine within the `official_duty_engine` module.
    """
    return datetime.combine(getdate(day), _as_time(value))


def _hours(seconds: float) -> float:
    """
    AR: تنفيذ `hours` ضمن وحدة `official_duty_engine`.
    EN: Execute hours within the `official_duty_engine` module.
    """
    return flt(max(seconds, 0) / 3600, 4)


def _clip_interval(start: datetime, end: datetime, lower: datetime, upper: datetime):
    """
    AR: تنفيذ `clip` `interval` ضمن وحدة `official_duty_engine`.
    EN: Execute clip interval within the `official_duty_engine` module.
    """
    start = max(start, lower)
    end = min(end, upper)
    return (start, end) if end > start else None


def merge_intervals(intervals: Iterable[tuple[datetime, datetime]]):
    """
    AR: تنفيذ `merge` `intervals` ضمن وحدة `official_duty_engine`.
    EN: Execute merge intervals within the `official_duty_engine` module.
    """
    clean = sorted((start, end) for start, end in intervals if start and end and end > start)
    if not clean:
        return []

    merged = [list(clean[0])]
    for start, end in clean[1:]:
        previous = merged[-1]
        if start <= previous[1]:
            previous[1] = max(previous[1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def interval_seconds(intervals: Iterable[tuple[datetime, datetime]]) -> float:
    """
    AR: تنفيذ `interval` `seconds` ضمن وحدة `official_duty_engine`.
    EN: Execute interval seconds within the `official_duty_engine` module.
    """
    return sum((end - start).total_seconds() for start, end in merge_intervals(intervals))


def subtract_intervals(
    source_intervals: Iterable[tuple[datetime, datetime]],
    excluded_intervals: Iterable[tuple[datetime, datetime]],
):
    """
    AR: تنفيذ `subtract` `intervals` ضمن وحدة `official_duty_engine`.
    EN: Execute subtract intervals within the `official_duty_engine` module.
    """
    result = merge_intervals(source_intervals)
    for excluded_start, excluded_end in merge_intervals(excluded_intervals):
        next_result = []
        for start, end in result:
            if excluded_end <= start or excluded_start >= end:
                next_result.append((start, end))
                continue
            if start < excluded_start:
                next_result.append((start, excluded_start))
            if excluded_end < end:
                next_result.append((excluded_end, end))
        result = next_result
    return merge_intervals(result)


def _get_shift_name(employee: str, attendance_date, requested_shift: str | None = None):
    """
    AR: تنفيذ استرجاع الوردية `name` ضمن وحدة `official_duty_engine`.
    EN: Execute get shift name within the `official_duty_engine` module.
    """
    return resolve_employee_shift_name(employee, attendance_date, requested_shift)


def get_shift_window(employee: str, attendance_date, requested_shift: str | None = None):
    """
    AR: تنفيذ استرجاع الوردية `window` ضمن وحدة `official_duty_engine`.
    EN: Execute get shift window within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            إرجاع اسم الوردية وبدايتها ونهايتها حسب جدول يوم الأسبوع، مع دعم
            الورديات الليلية دون تكرار منطق أوقات الوردية داخل هذا المحرك.

        EN:
            Return the weekday-specific shift window, including overnight shifts,
            without duplicating timing logic inside the duty engine.
    """
    resolved = get_employee_shift_window_data(employee, attendance_date, requested_shift)
    if not resolved:
        frappe.throw(
            _("No shift is assigned to employee {0} on {1}.").format(employee, attendance_date)
        )

    shift_doc = frappe.get_cached_doc("Shift Type", resolved.shift_type)
    return frappe._dict(
        {
            "name": resolved.shift_type,
            "doc": shift_doc,
            "start": resolved.start_datetime,
            "end": resolved.end_datetime,
            "hours": resolved.shift_hours,
            "source": resolved.source,
        }
    )


def _get_holiday_list(employee: str, shift_window):
    """
    AR: تنفيذ استرجاع العطلة `list` ضمن وحدة `official_duty_engine`.
    EN: Execute get holiday list within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            تحديد قائمة العطلات بنفس أولوية تشغيل الحضور: قائمة الوردية ثم
            الموظف ثم القائمة الافتراضية للشركة.

        EN:
            Resolve the holiday list using the attendance-oriented priority:
            Shift Type, then Employee, then the Company default.
    """
    shift_holiday_list = (
        shift_window.doc.get("holiday_list")
        if shift_window and shift_window.doc.meta.has_field("holiday_list")
        else None
    )
    if shift_holiday_list:
        return shift_holiday_list

    employee_data = frappe.db.get_value(
        "Employee", employee, ["holiday_list", "company"], as_dict=True
    )
    if not employee_data:
        return None
    return employee_data.holiday_list or frappe.db.get_value(
        "Company", employee_data.company, "default_holiday_list"
    )


def _is_holiday(employee: str, attendance_date, shift_window) -> bool:
    """
    AR: تنفيذ التحقق من كون العطلة ضمن وحدة `official_duty_engine`.
    EN: Execute is holiday within the `official_duty_engine` module.
    """
    holiday_list = _get_holiday_list(employee, shift_window)
    return bool(
        holiday_list
        and frappe.db.exists(
            "Holiday",
            {"parent": holiday_list, "holiday_date": getdate(attendance_date)},
        )
    )


def get_duty_interval(doc, attendance_date, shift_window):
    """
    AR: تنفيذ استرجاع المهمة `interval` ضمن وحدة `official_duty_engine`.
    EN: Execute get duty interval within the `official_duty_engine` module.
    """
    if doc.duty_type == DUTY_TYPE_FULL_DAY:
        return shift_window.start, shift_window.end

    if doc.duty_type != DUTY_TYPE_HOURLY:
        return None

    duty_start = _combine(getdate(attendance_date), doc.custom_leaving_time)
    duty_end = _combine(getdate(attendance_date), doc.custom_return_time)
    if duty_end <= duty_start:
        duty_end = duty_end + timedelta(days=1)

    # AR: في الوردية الليلية قد يكون وقت المهمة بعد منتصف الليل.
    # EN: For overnight shifts, move post-midnight duty times into the next day.
    if shift_window.end.date() > shift_window.start.date() and duty_start < shift_window.start:
        duty_start = add_days(duty_start, 1)
        duty_end = duty_end + timedelta(days=1)

    if duty_start < shift_window.start or duty_end > shift_window.end:
        frappe.throw(
            _("Official Duty time must be inside the employee shift on {0}.").format(attendance_date)
        )
    return duty_start, duty_end


def get_checkins(employee: str, shift_window):
    """
    AR: تنفيذ استرجاع `checkins` ضمن وحدة `official_duty_engine`.
    EN: Execute get checkins within the `official_duty_engine` module.
    """
    shift_doc = shift_window.doc
    before_minutes = cint(shift_doc.get("begin_check_in_before_shift_start_time") or 0)
    after_minutes = cint(shift_doc.get("allow_check_out_after_shift_end_time") or 0)
    lower = shift_window.start - timedelta(minutes=before_minutes)
    upper = shift_window.end + timedelta(minutes=after_minutes)

    filters = {
        "employee": employee,
        "time": ("between", [lower, upper]),
        "skip_auto_attendance": 0,
    }
    if frappe.get_meta("Employee Checkin").has_field("offshift"):
        filters["offshift"] = 0

    return frappe.get_all(
        "Employee Checkin",
        filters=filters,
        fields=["name", "time", "log_type", "shift", "attendance"],
        order_by="time asc, creation asc",
        limit_page_length=0,
    )


def _shift_checkin_modes(shift_window, logs):
    """
    AR: تنفيذ الوردية `checkin` `modes` ضمن وحدة `official_duty_engine`.
    EN: Execute shift checkin modes within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            قراءة طريقتي تفسير البصمات وحساب الساعات من Shift Type. عند استدعاء
            الدالة في اختبار أو بيئة قديمة بلا مستند وردية، نستخدم قيماً احتياطية
            تحافظ على السلوك السابق دون تخمين نوع بصمة غير موجود.

        EN:
            Read checkin interpretation and working-hours modes from Shift Type.
            Tests or legacy callers without a shift document use compatibility
            fallbacks rather than inventing an unavailable log type.
    """
    shift_doc = getattr(shift_window, "doc", None)
    checkin_mode = shift_doc.get("determine_check_in_and_check_out") if shift_doc else None
    hours_mode = shift_doc.get("working_hours_calculation_based_on") if shift_doc else None

    valid_checkin_modes = {CHECKIN_MODE_ALTERNATING, CHECKIN_MODE_STRICT}
    valid_hours_modes = {HOURS_MODE_FIRST_LAST, HOURS_MODE_EVERY_VALID}

    if checkin_mode not in valid_checkin_modes:
        has_explicit_types = any(
            (row.log_type or "").upper() in {"IN", "OUT"} for row in logs
        )
        checkin_mode = CHECKIN_MODE_STRICT if has_explicit_types else CHECKIN_MODE_ALTERNATING

    if hours_mode not in valid_hours_modes:
        # AR: هذا يطابق سلوك محركنا السابق عند غياب الإعداد صراحةً.
        # EN: This preserves the previous engine behavior when the option is unset.
        hours_mode = HOURS_MODE_EVERY_VALID

    return checkin_mode, hours_mode


def build_physical_intervals(checkins, shift_window, duty_interval):
    """
    AR: تنفيذ بناء `physical` `intervals` ضمن وحدة `official_duty_engine`.
    EN: Execute build physical intervals within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            بناء فترات الحضور الفعلي من البصمات الحقيقية وفق خياري Shift Type:
            طريقة تحديد IN/OUT وطريقة حساب ساعات العمل. لا تُنشأ بصمات وهمية.
            عندما تبقى بصمة دخول مفتوحة ويبدأ بعدها طلب مهمة معتمد، يمكن إنهاء
            الحضور الفعلي عند بداية المهمة فقط؛ وما بعد انتهاء المهمة لا يحتسب
            إلا إذا أثبتته بصمات الدوام العادية أو راجعته الموارد البشرية.

        EN:
            Build real physical-presence intervals using the Shift Type checkin and
            working-hours modes. No synthetic Employee Checkin is created. When an
            IN remains open and an approved duty starts afterwards, physical presence
            may end at duty start only; time after duty remains uncovered unless normal
            shift checkins or HR review prove it.
    """
    # AR: تدعم الدالة صفوف Frappe والقواميس وكائنات الاختبار البسيطة.
    # EN: Accept Frappe rows, dictionaries, and lightweight test objects.
    logs = [
        row
        if isinstance(row, frappe._dict)
        else frappe._dict(vars(row) if hasattr(row, "__dict__") else row)
        for row in checkins
    ]
    if not logs:
        return [], False

    intervals = []
    pending_in = None
    checkin_mode, hours_mode = _shift_checkin_modes(shift_window, logs)

    if checkin_mode == CHECKIN_MODE_ALTERNATING:
        if hours_mode == HOURS_MODE_FIRST_LAST:
            first_time = get_datetime(logs[0].time)
            if len(logs) >= 2:
                last_time = get_datetime(logs[-1].time)
                interval = _clip_interval(
                    first_time, last_time, shift_window.start, shift_window.end
                )
                if interval:
                    intervals.append(interval)
            else:
                pending_in = first_time
        else:
            # AR: البصمة الأولى IN والثانية OUT، ثم يتكرر الزوج.
            # EN: First log is IN, second is OUT, then the pair repeats.
            for index in range(0, len(logs) - 1, 2):
                start = get_datetime(logs[index].time)
                end = get_datetime(logs[index + 1].time)
                interval = _clip_interval(start, end, shift_window.start, shift_window.end)
                if interval:
                    intervals.append(interval)
            if len(logs) % 2:
                pending_in = get_datetime(logs[-1].time)

    elif hours_mode == HOURS_MODE_FIRST_LAST:
        # AR: أول IN وآخر OUT كما يفعل HRMS في هذا الوضع.
        # EN: Use the first IN and last OUT, matching native HRMS behavior.
        first_in = next(
            (get_datetime(row.time) for row in logs if (row.log_type or "").upper() == "IN"),
            None,
        )
        last_out = next(
            (
                get_datetime(row.time)
                for row in reversed(logs)
                if (row.log_type or "").upper() == "OUT"
            ),
            None,
        )
        if first_in and last_out and last_out > first_in:
            interval = _clip_interval(first_in, last_out, shift_window.start, shift_window.end)
            if interval:
                intervals.append(interval)
        elif first_in:
            pending_in = first_in

    else:
        # AR: أزواج IN/OUT الصحيحة فقط؛ IN المتكرر لا يستبدل IN المفتوح.
        # EN: Use valid IN/OUT pairs only; repeated IN does not replace an open IN.
        for row in logs:
            log_type = (row.log_type or "").upper()
            current = get_datetime(row.time)
            if pending_in is None and log_type == "IN":
                pending_in = current
            elif pending_in is not None and log_type == "OUT" and current > pending_in:
                interval = _clip_interval(
                    pending_in, current, shift_window.start, shift_window.end
                )
                if interval:
                    intervals.append(interval)
                pending_in = None

    missing_checkout_explained = False
    if duty_interval and pending_in:
        duty_start, duty_end = duty_interval

        # AR:
        # الطلب المعتمد نفسه يحدد لحظة مغادرة الموظف للمهمة؛ لذلك يمكن إغلاق
        # فترة الحضور المفتوحة عند بداية المهمة حتى لو لم يبصم OUT خاصاً بها.
        # إذا انتهت المهمة قبل نهاية الوردية، تبقى المدة اللاحقة غير مغطاة حتى
        # تثبت ببصمة عودة/انصراف عادية أو بمعالجة الموارد البشرية.
        #
        # EN:
        # The approved request establishes the duty departure time, so an open
        # physical interval may end at duty start without a special duty OUT.
        # If duty ends before shift end, the later segment remains uncovered until
        # normal return/final checkins or HR review prove it.
        if pending_in <= duty_start:
            interval = _clip_interval(
                pending_in, duty_start, shift_window.start, shift_window.end
            )
            if interval:
                intervals.append(interval)

            duty_covers_shift_end = abs(
                (shift_window.end - duty_end).total_seconds()
            ) <= COVERAGE_TOLERANCE_SECONDS
            missing_checkout_explained = duty_covers_shift_end

    return merge_intervals(intervals), missing_checkout_explained


def calculate_daily_coverage(doc, attendance_date):
    """
    AR: تنفيذ حساب `daily` `coverage` ضمن وحدة `official_duty_engine`.
    EN: Execute calculate daily coverage within the `official_duty_engine` module.
    """
    shift_window = get_shift_window(doc.employee, attendance_date, doc.shift)
    duty_interval = get_duty_interval(doc, attendance_date, shift_window)
    duty_intervals = [duty_interval] if duty_interval else []
    checkins = get_checkins(doc.employee, shift_window)
    physical_intervals, missing_checkout_explained = build_physical_intervals(
        checkins, shift_window, duty_interval
    )

    credited_intervals = merge_intervals([*physical_intervals, *duty_intervals])
    physical_excluding_duty = subtract_intervals(physical_intervals, duty_intervals)

    shift_seconds = (shift_window.end - shift_window.start).total_seconds()
    duty_seconds = interval_seconds(duty_intervals)
    physical_seconds = interval_seconds(physical_excluding_duty)
    credited_seconds = interval_seconds(credited_intervals)
    uncovered_seconds = max(shift_seconds - credited_seconds, 0)

    return frappe._dict(
        {
            "attendance_date": getdate(attendance_date),
            "shift": shift_window.name,
            "shift_start": shift_window.start,
            "shift_end": shift_window.end,
            "duty_start": duty_interval[0] if duty_interval else None,
            "duty_end": duty_interval[1] if duty_interval else None,
            "shift_hours": _hours(shift_seconds),
            "official_duty_hours": _hours(duty_seconds),
            "physical_working_hours": _hours(physical_seconds),
            "credited_working_hours": _hours(credited_seconds),
            "uncovered_hours": _hours(uncovered_seconds),
            "is_fully_covered": uncovered_seconds <= COVERAGE_TOLERANCE_SECONDS,
            "checkins": checkins,
            "checkin_count": len(checkins),
            "first_checkin": get_datetime(checkins[0].time) if checkins else None,
            "last_checkin": get_datetime(checkins[-1].time) if checkins else None,
            "missing_checkout_explained": missing_checkout_explained,
        }
    )


def _attendance_data_is_ready(coverage):
    """
    AR: تنفيذ الحضور `data` التحقق من كون `ready` ضمن وحدة `official_duty_engine`.
    EN: Execute attendance data is ready within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            انتظار نهاية نافذة الانصراف ووصول Last Sync عند تفعيل Auto Attendance.
            هذا يمنع التسوية من الحكم على يوم ناقص قبل وصول البصمات القياسية.

        EN:
            Wait for the checkout buffer and Last Sync when Auto Attendance is enabled.
            This prevents reconciliation from judging an incomplete day before native
            checkins have finished synchronizing.
    """
    shift_doc = frappe.get_cached_doc("Shift Type", coverage.shift)
    processing_end = coverage.shift_end + timedelta(
        minutes=cint(shift_doc.get("allow_check_out_after_shift_end_time") or 0)
    )
    if now_datetime() < processing_end:
        return False

    if cint(shift_doc.get("enable_auto_attendance")):
        last_sync = shift_doc.get("last_sync_of_checkin")
        if not last_sync or get_datetime(last_sync) < processing_end:
            return False

    return True


def _attendance_for_date(employee, attendance_date, shift=None):
    """
    AR: تنفيذ الحضور `for` التاريخ ضمن وحدة `official_duty_engine`.
    EN: Execute attendance for date within the `official_duty_engine` module.
    """
    filters = {
        "employee": employee,
        "attendance_date": attendance_date,
        "docstatus": ("!=", 2),
    }
    rows = frappe.get_all(
        "Attendance",
        filters=filters,
        fields=[
            "name",
            "status",
            "half_day_status",
            "shift",
            "late_entry",
            "early_exit",
            "attendance_request",
        ],
        order_by="modified desc",
        limit_page_length=2,
    )
    if not rows:
        return None

    if shift:
        exact = [row for row in rows if row.shift == shift]
        if exact:
            return frappe._dict(exact[0])
    if len(rows) > 1:
        return frappe._dict(rows[0])
    return frappe._dict(rows[0])


def _approved_leave_exists(employee, attendance_date):
    """
    AR: تنفيذ `approved` الإجازة `exists` ضمن وحدة `official_duty_engine`.
    EN: Execute approved leave exists within the `official_duty_engine` module.
    """
    return frappe.db.exists(
        "Leave Application",
        {
            "employee": employee,
            "docstatus": 1,
            "status": "Approved",
            "from_date": ("<=", attendance_date),
            "to_date": (">=", attendance_date),
        },
    )


def _find_linked_attendance_request(docname, attendance_date):
    """
    AR: تنفيذ البحث عن `linked` الحضور الطلب ضمن وحدة `official_duty_engine`.
    EN: Execute find linked attendance request within the `official_duty_engine` module.
    """
    if not frappe.get_meta("Attendance Request").has_field("custom_official_duty_request"):
        return None
    row = frappe.db.get_value(
        "Attendance Request",
        {
            "custom_official_duty_request": docname,
            "from_date": attendance_date,
            "to_date": attendance_date,
            "docstatus": ("!=", 2),
        },
        ["name", "docstatus"],
        as_dict=True,
    )
    return frappe._dict(row) if row else None


def _has_unrelated_attendance_request(employee, attendance_date, shift=None):
    """
    AR: تنفيذ التحقق من وجود `unrelated` الحضور الطلب ضمن وحدة `official_duty_engine`.
    EN: Execute has unrelated attendance request within the `official_duty_engine` module.
    """
    filters = {
        "employee": employee,
        "docstatus": ("<", 2),
        "from_date": ("<=", attendance_date),
        "to_date": (">=", attendance_date),
    }
    if shift:
        filters["shift"] = shift
    return frappe.db.get_value("Attendance Request", filters, "name")


def _create_standard_attendance_request(doc, coverage, existing_attendance=None):
    """
    AR: تنفيذ إنشاء `standard` الحضور الطلب ضمن وحدة `official_duty_engine`.
    EN: Execute create standard attendance request within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            إنشاء Attendance Request قياسي لليوم الذي يحتاج إنشاء/تصحيح حضور.
            لا يُستخدم هذا المستند لتخزين ساعات المهمة، بل لتطبيق حالة Present القياسية.

        EN:
            Create a native Attendance Request when a daily Attendance record must be
            created or corrected. Hour details remain on Official Duty/Attendance fields.
    """
    linked = _find_linked_attendance_request(doc.name, coverage.attendance_date)
    if linked:
        # AR: إذا توقف تنفيذ سابق بعد Insert وقبل Submit نكمل نفس المستند.
        # EN: If a previous run stopped after Insert, submit the same draft safely.
        linked_doc = frappe.get_doc("Attendance Request", linked.name)
        if linked_doc.docstatus == 0:
            linked_doc.flags.ignore_permissions = True
            linked_doc.submit()
        return linked_doc.name

    unrelated = _has_unrelated_attendance_request(
        doc.employee,
        coverage.attendance_date,
        existing_attendance.shift if existing_attendance else coverage.shift,
    )
    if unrelated:
        frappe.throw(
            _("Attendance Request {0} already covers {1}.").format(
                frappe.bold(unrelated), coverage.attendance_date
            )
        )

    attendance_request = frappe.new_doc("Attendance Request")
    attendance_request.employee = doc.employee
    attendance_request.from_date = coverage.attendance_date
    attendance_request.to_date = coverage.attendance_date
    attendance_request.reason = "On Duty"
    attendance_request.explanation = _(
        "Created from Official Duty Request {0}: {1}"
    ).format(doc.name, doc.custom_assignment_explanation or "")
    if attendance_request.meta.has_field("shift"):
        attendance_request.shift = (
            existing_attendance.shift
            if existing_attendance and existing_attendance.shift
            else coverage.shift
        )
    if attendance_request.meta.has_field("include_holidays"):
        attendance_request.include_holidays = cint(doc.include_holidays)
    if attendance_request.meta.has_field("custom_official_duty_request"):
        attendance_request.custom_official_duty_request = doc.name
    attendance_request.flags.ignore_permissions = True
    attendance_request.insert(ignore_permissions=True)
    attendance_request.submit()
    return attendance_request.name


def _annotate_attendance(doc, coverage, attendance_name, previous=None):
    """
    AR: تنفيذ `annotate` الحضور ضمن وحدة `official_duty_engine`.
    EN: Execute annotate attendance within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            حفظ نتيجة الساعات على Attendance دون اختلاق بصمات أو تغيير
            in_time/out_time. تحفظ الحالة السابقة مرة واحدة كي تبقى إعادة التشغيل
            والإلغاء آمنين.

        EN:
            Store credited-hour results without synthetic checkins or changes to
            in_time/out_time. Capture the original state once so retries and
            cancellation remain idempotent.
    """
    attendance_meta = frappe.get_meta("Attendance")
    current = frappe.db.get_value(
        "Attendance",
        attendance_name,
        [
            "custom_official_duty_request",
            "status",
            "half_day_status",
            "late_entry",
            "early_exit",
        ],
        as_dict=True,
    )
    values = {
        "custom_official_duty_request": doc.name,
        "custom_official_duty_hours": coverage.official_duty_hours,
        "custom_physical_working_hours": coverage.physical_working_hours,
        "custom_credited_working_hours": coverage.credited_working_hours,
        "custom_uncovered_hours": coverage.uncovered_hours,
        "custom_missing_checkout_explained": cint(coverage.missing_checkout_explained),
        "custom_official_duty_reconciliation_status": DETAIL_RECONCILED,
        "custom_official_duty_note": _(
            "Attendance reconciled from Official Duty Request {0}. No Employee Checkin was fabricated."
        ).format(doc.name),
    }

    # AR: لا نكتب الحالة الأصلية فوق نفسها عند إعادة تشغيل التسوية.
    # EN: Never overwrite the original state during a reconciliation retry.
    already_linked = current and current.custom_official_duty_request == doc.name
    if not already_linked:
        original = previous or current or frappe._dict()
        audit_values = {
            "custom_official_duty_previous_status": original.get("status"),
            "custom_official_duty_previous_half_day_status": original.get("half_day_status"),
            "custom_official_duty_previous_late_entry": cint(original.get("late_entry")),
            "custom_official_duty_previous_early_exit": cint(original.get("early_exit")),
        }
        for fieldname, value in audit_values.items():
            if attendance_meta.has_field(fieldname):
                values[fieldname] = value

    # AR: إذا غطت المهمة بداية الدوام أو نهايته نزيل إشارات التأخير/الخروج المبكر.
    # EN: Clear late/early flags only when the approved duty covers that shift edge.
    if coverage.duty_start and abs(
        (coverage.duty_start - coverage.shift_start).total_seconds()
    ) <= COVERAGE_TOLERANCE_SECONDS:
        values["late_entry"] = 0
    if coverage.duty_end and abs(
        (coverage.shift_end - coverage.duty_end).total_seconds()
    ) <= COVERAGE_TOLERANCE_SECONDS:
        values["early_exit"] = 0

    frappe.db.set_value("Attendance", attendance_name, values, update_modified=False)



def _normalize_previous_detail(previous_detail):
    """
    AR: تنفيذ توحيد `previous` `detail` ضمن وحدة `official_duty_engine`.
    EN: Execute normalize previous detail within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            تحويل صف التسوية السابق إلى frappe._dict بطريقة آمنة. عند إعادة
            المعالجة يكون الصف مستند Child Document وليس dict عادياً.

        EN:
            Safely normalize a previous reconciliation child row. On retries the
            value is a child Document, so it must pass through as_dict() first.
    """
    if not previous_detail:
        return frappe._dict()

    if isinstance(previous_detail, frappe._dict):
        return previous_detail.copy()

    if isinstance(previous_detail, dict):
        return frappe._dict(previous_detail)

    if hasattr(previous_detail, "as_dict"):
        return frappe._dict(previous_detail.as_dict())

    return frappe._dict(previous_detail)


def reconcile_day(doc, attendance_date, previous_detail=None):
    """
    AR: تنفيذ `reconcile` `day` ضمن وحدة `official_duty_engine`.
    EN: Execute reconcile day within the `official_duty_engine` module.
    """
    if doc.duty_type == DUTY_TYPE_NO_ADJUSTMENT:
        return frappe._dict(
            {
                "attendance_date": attendance_date,
                "reconciliation_status": DETAIL_NO_ADJUSTMENT,
                "message": _("No attendance adjustment was requested."),
            }
        )

    # AR: نحدد الوردية قبل الحساب كي نتجاوز العطلة فقط عندما لم يطلب إدراجها.
    # EN: Resolve the shift first so holidays are skipped only when not requested.
    shift_window = get_shift_window(doc.employee, attendance_date, doc.shift)
    if not cint(doc.include_holidays) and _is_holiday(doc.employee, attendance_date, shift_window):
        return frappe._dict(
            {
                "attendance_date": attendance_date,
                "shift": shift_window.name,
                "shift_start": shift_window.start,
                "shift_end": shift_window.end,
                "shift_hours": shift_window.hours,
                "reconciliation_status": DETAIL_NO_ADJUSTMENT,
                "message": _("The date is a holiday and Include Holidays is not enabled."),
            }
        )

    coverage = calculate_daily_coverage(doc, attendance_date)
    detail = frappe._dict(coverage.copy())
    detail.pop("checkins", None)
    detail.reconciliation_status = DETAIL_PENDING
    detail.message = ""
    previous_detail = _normalize_previous_detail(previous_detail)
    # MASAR_MANUAL_RECONCILIATION_PRESERVE
    # Keep an HR-confirmed daily row intact when another date in the same
    # multi-day request still requires scheduler processing.
    if (
        previous_detail.get("custom_manual_resolution")
        == "Confirmed Remaining Hours"
        and previous_detail.get("reconciliation_status") == DETAIL_RECONCILED
    ):
        preserved = frappe._dict(previous_detail.copy())
        for fieldname in (
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
        ):
            preserved.pop(fieldname, None)
        return preserved
    detail.attendance = previous_detail.get("attendance")
    detail.attendance_request = previous_detail.get("attendance_request")
    detail.attendance_created_by_request = cint(
        previous_detail.get("attendance_created_by_request")
    )
    detail.previous_status = previous_detail.get("previous_status")
    detail.previous_half_day_status = previous_detail.get("previous_half_day_status")
    detail.previous_late_entry = cint(previous_detail.get("previous_late_entry"))
    detail.previous_early_exit = cint(previous_detail.get("previous_early_exit"))

    if not _attendance_data_is_ready(coverage):
        detail.reconciliation_status = DETAIL_WAITING
        detail.message = _(
            "Attendance will be reconciled after the shift and checkin synchronization finish."
        )
        return detail

    if _approved_leave_exists(doc.employee, attendance_date):
        detail.reconciliation_status = DETAIL_MANUAL_REVIEW
        detail.message = _("An approved Leave Application overlaps this Official Duty date.")
        return detail

    if not coverage.is_fully_covered:
        detail.reconciliation_status = DETAIL_MANUAL_REVIEW
        detail.message = _(
            "The request and available checkins leave {0} uncovered hour(s); HR review is required."
        ).format(coverage.uncovered_hours)
        return detail

    existing = _attendance_for_date(doc.employee, attendance_date, coverage.shift)
    linked_request = _find_linked_attendance_request(doc.name, attendance_date)
    if existing:
        detail.attendance = existing.name
        # AR: الحالة السابقة تسجل مرة واحدة ولا تستبدل بحالة Present في إعادة التشغيل.
        # EN: Preserve the first original state instead of replacing it with Present on retries.
        if not previous_detail:
            detail.previous_status = existing.status
            detail.previous_half_day_status = existing.half_day_status
            detail.previous_late_entry = cint(existing.late_entry)
            detail.previous_early_exit = cint(existing.early_exit)
    if linked_request:
        detail.attendance_request = linked_request.name
        detail.attendance_created_by_request = 1

    if existing and existing.status in {"On Leave", "Work From Home"}:
        detail.reconciliation_status = DETAIL_MANUAL_REVIEW
        detail.message = _("Existing Attendance status {0} requires HR review.").format(existing.status)
        return detail

    # AR:
    # لا نربط المهمة آلياً بسجل حضور أنشأه طلب حضور مستقل؛ لأن إلغاء أو تعديل
    # أحد المستندين قد يؤثر في الآخر. يراجع HR الحالة ويحدد المستند الصحيح.
    #
    # EN:
    # Never attach duty reconciliation automatically to Attendance owned by an
    # unrelated Attendance Request. Cancellation or amendment could otherwise
    # make the two independent corrections affect each other.
    if (
        existing
        and existing.attendance_request
        and (
            not linked_request
            or existing.attendance_request != linked_request.name
        )
    ):
        detail.reconciliation_status = DETAIL_MANUAL_REVIEW
        detail.message = _(
            "Attendance is linked to another Attendance Request {0}; HR review is required."
        ).format(frappe.bold(existing.attendance_request))
        return detail

    if existing:
        # AR:
        # تحديث السجل الموجود مباشرة يحافظ على in_time/out_time/working_hours
        # وروابط البصمات. استخدام Attendance Request القياسي لتعديل سجل موجود
        # سيؤدي عند إلغائه إلى إلغاء السجل كاملاً، وهو غير مرغوب هنا.
        #
        # EN:
        # Update an existing record directly to preserve in_time/out_time,
        # working_hours, and checkin links. A native Attendance Request would
        # cancel the whole existing record when later cancelled.
        attendance_name = existing.name
        if existing.status != "Present":
            frappe.db.set_value(
                "Attendance",
                attendance_name,
                {
                    "status": "Present",
                    "half_day_status": None,
                },
                update_modified=False,
            )
    else:
        try:
            request_name = _create_standard_attendance_request(doc, coverage)
        except Exception as exc:
            detail.reconciliation_status = DETAIL_MANUAL_REVIEW
            detail.message = str(exc)
            return detail

        detail.attendance_request = request_name
        detail.attendance_created_by_request = 1
        attendance_name = frappe.db.get_value(
            "Attendance",
            {
                "employee": doc.employee,
                "attendance_date": attendance_date,
                "attendance_request": request_name,
                "docstatus": ("!=", 2),
            },
            "name",
        )
        if not attendance_name:
            detail.reconciliation_status = DETAIL_FAILED
            detail.message = _("Attendance Request was submitted but no Attendance record was found.")
            return detail
        detail.attendance = attendance_name

    _annotate_attendance(doc, coverage, attendance_name, previous=existing)
    detail.reconciliation_status = DETAIL_RECONCILED
    detail.message = _(
        "Attendance is Present: {0} physical hour(s) + {1} official-duty hour(s) = {2} credited hour(s)."
    ).format(
        coverage.physical_working_hours,
        coverage.official_duty_hours,
        coverage.credited_working_hours,
    )
    return detail


def _date_range(from_date, to_date):
    """
    AR: تنفيذ التاريخ `range` ضمن وحدة `official_duty_engine`.
    EN: Execute date range within the `official_duty_engine` module.
    """
    current = getdate(from_date)
    end = getdate(to_date)
    while current <= end:
        yield current
        current = add_days(current, 1)


def _summarize_status(details, duty_type):
    """
    AR: تنفيذ `summarize` الحالة ضمن وحدة `official_duty_engine`.
    EN: Execute summarize status within the `official_duty_engine` module.
    """
    statuses = {row.get("reconciliation_status") for row in details}
    if duty_type == DUTY_TYPE_NO_ADJUSTMENT:
        return STATUS_NO_ADJUSTMENT
    if statuses and statuses.issubset({DETAIL_RECONCILED, DETAIL_NO_ADJUSTMENT}):
        return STATUS_RECONCILED if DETAIL_RECONCILED in statuses else STATUS_NO_ADJUSTMENT
    if DETAIL_FAILED in statuses:
        return STATUS_FAILED
    if DETAIL_MANUAL_REVIEW in statuses:
        return STATUS_MANUAL_REVIEW
    if DETAIL_WAITING in statuses and DETAIL_RECONCILED in statuses:
        return STATUS_PARTIAL
    if DETAIL_WAITING in statuses:
        return STATUS_WAITING
    return STATUS_PENDING


def _save_processing_result(doc, detail_rows, status, message=""):
    """
    AR: تنفيذ حفظ `processing` `result` ضمن وحدة `official_duty_engine`.
    EN: Execute save processing result within the `official_duty_engine` module.
    """
    doc.set("attendance_details", [])
    for row in detail_rows:
        doc.append("attendance_details", row)

    doc.processing_status = status
    doc.processing_message = message
    doc.total_official_duty_hours = flt(sum(row.get("official_duty_hours") or 0 for row in detail_rows), 4)
    doc.total_physical_working_hours = flt(
        sum(row.get("physical_working_hours") or 0 for row in detail_rows), 4
    )
    doc.total_credited_working_hours = flt(
        sum(row.get("credited_working_hours") or 0 for row in detail_rows), 4
    )
    doc.total_uncovered_hours = flt(sum(row.get("uncovered_hours") or 0 for row in detail_rows), 4)
    doc.last_reconciliation_on = now_datetime()

    doc.flags.ignore_validate_update_after_submit = True
    doc.flags.skip_reconciliation = True
    doc.save(ignore_permissions=True)


def process_official_duty_request(name: str, force: bool = False):
    """
    AR: تنفيذ `process` الرسمية المهمة الطلب ضمن وحدة `official_duty_engine`.
    EN: Execute process official duty request within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            معالجة طلب مهمة معتمد بأثر رجعي أو بعد نهاية الوردية. الدالة قابلة
            لإعادة التشغيل؛ الروابط التقنية تمنع تكرار Attendance Request.

        EN:
            Reconcile an approved request retrospectively or after shift end. The
            operation is idempotent; technical links prevent duplicate Attendance Requests.
    """
    if not frappe.db.exists(OFFICIAL_DUTY_DOCTYPE, name):
        return None

    # AR: قفل صف الطلب يمنع تشغيل مهمتين متزامنتين من إنشاء تسوية مكررة.
    # EN: Row locking prevents concurrent workers from creating duplicate reconciliation.
    frappe.db.sql(
        f"SELECT name FROM `tab{OFFICIAL_DUTY_DOCTYPE}` WHERE name = %s FOR UPDATE",
        name,
    )
    doc = frappe.get_doc(OFFICIAL_DUTY_DOCTYPE, name)
    if doc.docstatus != 1 or doc.workflow_state != "Approved":
        return None
    if getattr(doc.flags, "skip_reconciliation", False):
        return None

    previous_details = {
        getdate(row.attendance_date): row
        for row in (doc.get("attendance_details") or [])
        if row.get("attendance_date")
    }
    detail_rows = []
    errors = []
    for attendance_date in _date_range(doc.from_date, doc.to_date):
        try:
            detail_rows.append(
                reconcile_day(doc, attendance_date, previous_details.get(getdate(attendance_date)))
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Official Duty reconciliation failed: {doc.name} / {attendance_date}",
            )
            errors.append(str(attendance_date))
            detail_rows.append(
                frappe._dict(
                    {
                        "attendance_date": attendance_date,
                        "reconciliation_status": DETAIL_FAILED,
                        "message": _("Unexpected reconciliation error. See Error Log."),
                    }
                )
            )

    status = _summarize_status(detail_rows, doc.duty_type)
    message = ""
    if errors:
        message = _("Reconciliation failed for: {0}").format(", ".join(errors))
    elif status == STATUS_MANUAL_REVIEW:
        message = _("One or more dates require HR review because some shift time is not covered.")
    elif status == STATUS_WAITING:
        message = _("The request is approved and will be processed after the shift ends.")
    elif status == STATUS_RECONCILED:
        message = _("Attendance reconciliation completed successfully without creating synthetic checkins.")
    elif status == STATUS_NO_ADJUSTMENT:
        message = _("No attendance adjustment was applied for the selected date range.")

    _save_processing_result(doc, detail_rows, status, message)
    return {
        "name": doc.name,
        "processing_status": status,
        "details": [dict(row) for row in detail_rows],
    }


def enqueue_official_duty_reconciliation(doc, method=None):
    """
    AR: تنفيذ `enqueue` الرسمية المهمة التسوية ضمن وحدة `official_duty_engine`.
    EN: Execute enqueue official duty reconciliation within the `official_duty_engine` module.
    """
    if doc.docstatus != 1 or doc.workflow_state != "Approved":
        return
    frappe.enqueue(
        "masar_requests.official_duty_engine.process_official_duty_request",
        name=doc.name,
        queue="short",
        timeout=600,
        enqueue_after_commit=True,
        job_name=f"official_duty_reconciliation_{doc.name}",
    )


def process_pending_official_duties():
    """
    AR: تنفيذ `process` `pending` الرسمية `duties` ضمن وحدة `official_duty_engine`.
    EN: Execute process pending official duties within the `official_duty_engine` module.
    """
    names = frappe.get_all(
        OFFICIAL_DUTY_DOCTYPE,
        filters={
            "docstatus": 1,
            "workflow_state": "Approved",
            "processing_status": (
                "in",
                [
                    STATUS_PENDING,
                    STATUS_WAITING,
                    STATUS_PARTIAL,
                    STATUS_MANUAL_REVIEW,
                    STATUS_FAILED,
                ],
            ),
        },
        pluck="name",
        limit_page_length=500,
    )
    for name in names:
        try:
            process_official_duty_request(name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Scheduled Official Duty reconciliation failed: {name}",
            )
    return len(names)


def _clear_attendance_annotations(attendance_name):
    """
    AR: تنفيذ `clear` الحضور `annotations` ضمن وحدة `official_duty_engine`.
    EN: Execute clear attendance annotations within the `official_duty_engine` module.
    """
    if not attendance_name or not frappe.db.exists("Attendance", attendance_name):
        return
    frappe.db.set_value(
        "Attendance",
        attendance_name,
        {
            "custom_official_duty_request": None,
            "custom_official_duty_hours": 0,
            "custom_physical_working_hours": 0,
            "custom_credited_working_hours": 0,
            "custom_uncovered_hours": 0,
            "custom_missing_checkout_explained": 0,
            "custom_official_duty_reconciliation_status": None,
            "custom_official_duty_note": None,
            "custom_official_duty_previous_status": None,
            "custom_official_duty_previous_half_day_status": None,
            "custom_official_duty_previous_late_entry": 0,
            "custom_official_duty_previous_early_exit": 0,
            "custom_manual_confirmed_working_hours": 0,
            "custom_manual_reconciliation_decision": None,
            "custom_manual_reconciled_by": None,
            "custom_manual_reconciled_on": None,
            "custom_manual_reconciliation_note": None,
        },
        update_modified=False,
    )


def cancel_official_duty_reconciliation(doc, method=None):
    """
    AR: تنفيذ إلغاء الرسمية المهمة التسوية ضمن وحدة `official_duty_engine`.
    EN: Execute cancel official duty reconciliation within the `official_duty_engine` module.

    DETAILS / التفاصيل:
    AR:
            إلغاء آثار التسوية المرتبطة بالطلب. لا يتم حذف Employee Checkin لأنه
            لم يتم إنشاؤه أو تعديله أساساً.

        EN:
            Reverse linked reconciliation effects. Employee Checkin records are untouched
            because this engine never creates or modifies them.
    """
    details = list(doc.get("attendance_details") or [])
    for row in details:
        request_name = row.get("attendance_request")
        if request_name and frappe.db.exists("Attendance Request", request_name):
            request_doc = frappe.get_doc("Attendance Request", request_name)
            if request_doc.docstatus == 1:
                request_doc.flags.ignore_permissions = True
                request_doc.cancel()

        attendance_name = row.get("attendance")
        if not attendance_name or not frappe.db.exists("Attendance", attendance_name):
            continue

        # AR: السجل الذي أنشأه Attendance Request أُلغي معه ولا يجب إعادة إنشائه.
        # EN: Attendance created by the linked request is cancelled with it and must stay cancelled.
        if cint(row.get("attendance_created_by_request")):
            continue

        attendance_doc = frappe.get_doc("Attendance", attendance_name)
        previous_status = (
            row.get("previous_status")
            or attendance_doc.get("custom_official_duty_previous_status")
        )
        previous_half_day_status = (
            row.get("previous_half_day_status")
            or attendance_doc.get("custom_official_duty_previous_half_day_status")
        )
        previous_late_entry = cint(
            row.get("previous_late_entry")
            or attendance_doc.get("custom_official_duty_previous_late_entry")
        )
        previous_early_exit = cint(
            row.get("previous_early_exit")
            or attendance_doc.get("custom_official_duty_previous_early_exit")
        )
        if attendance_doc.docstatus == 2 and previous_status:
            # AR: Attendance Request القياسي يلغي السجل عند إلغائه؛ نعيد الحالة السابقة كسجل جديد.
            # EN: Native Attendance Request cancels its linked record; restore the pre-existing state.
            restored = frappe.new_doc("Attendance")
            restored.employee = doc.employee
            restored.employee_name = doc.employee_name
            restored.attendance_date = row.attendance_date
            restored.company = doc.company
            restored.shift = row.shift
            restored.status = previous_status
            restored.half_day_status = previous_half_day_status
            restored.late_entry = previous_late_entry
            restored.early_exit = previous_early_exit
            restored.flags.ignore_validate = True
            restored.insert(ignore_permissions=True)
            restored.submit()
        elif attendance_doc.docstatus != 2:
            _clear_attendance_annotations(attendance_name)
            frappe.db.set_value(
                "Attendance",
                attendance_name,
                {
                    "status": previous_status or attendance_doc.status,
                    "half_day_status": previous_half_day_status,
                    "late_entry": previous_late_entry,
                    "early_exit": previous_early_exit,
                },
                update_modified=False,
            )

    frappe.db.set_value(
        OFFICIAL_DUTY_DOCTYPE,
        doc.name,
        {
            "processing_status": STATUS_PENDING,
            "processing_message": _("Attendance reconciliation was reversed after cancellation."),
            "custom_total_manual_confirmed_hours": 0,
            "custom_last_manual_reconciled_by": None,
            "custom_last_manual_reconciled_on": None,
            "custom_manual_reconciliation_summary": None,
        },
        update_modified=False,
    )


@frappe.whitelist()
def reconcile_official_duty_now(name: str):
    """
    AR: تنفيذ `reconcile` الرسمية المهمة `now` ضمن وحدة `official_duty_engine`.
    EN: Execute reconcile official duty now within the `official_duty_engine` module.
    """
    roles = set(frappe.get_roles())
    if frappe.session.user != "Administrator" and not roles.intersection({"HR Manager", "System Manager"}):
        frappe.throw(_("Only HR Manager or System Manager can reconcile attendance."), frappe.PermissionError)
    return process_official_duty_request(name, force=True)
