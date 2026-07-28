# =======================================================================
# 🚀 محرك احتساب الإجازات الجزئية الصارم بالساعة والربع والنصف - تنظيم
# =======================================================================

from datetime import time, timedelta
import re
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, get_time
from hrms.hr.doctype.leave_application.leave_application import LeaveApplication

DAY_SECONDS = 24 * 60 * 60

class CustomLeaveApplication(LeaveApplication):
    def validate(self):
        # AR: تشغيل تحقق طلب الإجازة القياسي والتحقق الإضافي للإجازة الجزئية.
        # EN: Run standard validation plus partial-leave validation.
        self.validate_single_partial_option()
        self.normalize_partial_leave_date()
        if self.is_any_partial_leave():
            self.apply_partial_leave_time_and_days()
        super().validate()
        if self.is_any_partial_leave():
            self.apply_partial_leave_time_and_days()

    def validate_balance_leaves(self):
        # AR: التحقق من كفاية رصيد الإجازة للطلب الجزئي.
        # EN: Validate sufficient balance for a partial leave request.
        if not self.is_custom_partial_leave():
            return super().validate_balance_leaves()
        self.validate_single_partial_option()
        self.normalize_partial_leave_date()
        self.apply_partial_leave_time_and_days()
        self.validate_custom_partial_leave_balance()

    def validate_attendance(self):
        # AR: تطبيق تحقق الحضور القياسي عندما لا يكون الطلب إجازة جزئية.
        # EN: Run standard attendance validation for non-partial leave.
        if self.is_custom_partial_leave():
            return
        return super().validate_attendance()

    def update_attendance(self):
        # AR: تحديث الحضور للطلبات العادية وتجاوز التحديث للطلبات الجزئية.
        # EN: Update attendance for normal leave and skip partial leave.
        if self.is_custom_partial_leave():
            return
        return super().update_attendance()

    def is_custom_partial_leave(self):
        # AR: التحقق من أن الطلب ربع يوم أو إجازة بالساعات.
        # EN: Check whether the request is quarter-day or hourly leave.
        return cint(self.get("quarter_day")) or cint(self.get("is_hourly"))

    def is_any_partial_leave(self):
        # AR: التحقق من أن الطلب نصف يوم أو ربع يوم أو إجازة بالساعات.
        # EN: Check whether any partial-leave option is selected.
        return cint(self.get("half_day")) or cint(self.get("quarter_day")) or cint(self.get("is_hourly"))

    def validate_single_partial_option(self):
        # AR: منع اختيار أكثر من نوع إجازة جزئية في الوقت نفسه.
        # EN: Prevent selecting more than one partial-leave type.
        if (cint(self.get("half_day")) + cint(self.get("quarter_day")) + cint(self.get("is_hourly"))) > 1:
            frappe.throw(_("Only one option can be selected: Half Day, Quarter Day, or Hourly Leave."))

    def normalize_partial_leave_date(self):
        # AR: توحيد تاريخ الإجازة الجزئية مع تاريخي البداية والنهاية.
        # EN: Align the partial date with the request date range.
        if not self.is_any_partial_leave():
            return
        partial_date = self.get("custom_partial_leave_date") or self.get("half_day_date") or self.get("from_date")
        if not partial_date:
            frappe.throw(_("Partial Leave Date is required."))
        self.custom_partial_leave_date = partial_date
        self.from_date = partial_date
        self.to_date = partial_date
        self.half_day_date = partial_date if cint(self.get("half_day")) else None

    def apply_partial_leave_time_and_days(self):
        # AR: حساب وقت الإجازة الجزئية وساعاتها وعدد أيامها.
        # EN: Calculate partial-leave times, hours, and day fraction.
        if not self.employee:
            frappe.throw(_("Employee is required."))
        if not self.from_date:
            frappe.throw(_("Partial Leave Date is required."))
        if not self.get("custom_partial_from_time_ar"):
            frappe.throw(_("Start Time is required."))

        self.from_time = display_time_to_time_string(self.custom_partial_from_time_ar)
        if cint(self.get("is_hourly")):
            if not self.get("custom_partial_to_time_ar"):
                frappe.throw(_("End Time is required for Hourly Leave."))
            self.to_time = display_time_to_time_string(self.custom_partial_to_time_ar)

        shift_type = self.get_employee_shift_type()
        if not shift_type:
            frappe.throw(_("No shift is assigned to this employee on the selected date."))

        shift = frappe.get_doc("Shift Type", shift_type)
        actual_start_time = shift.start_time
        actual_end_time = shift.end_time
        day_name = getdate(self.from_date).strftime("%A")

        if shift.get("custom_shift_times"):
            for row in shift.custom_shift_times:
                if row.day_of_week == day_name:
                    actual_start_time = row.start_time
                    actual_end_time = row.end_time
                    break

        shift_start, shift_end = self.get_normalized_interval(actual_start_time, actual_end_time)
        shift_seconds = shift_end - shift_start
        shift_hours = flt(shift_seconds / 3600, 4)
        self.custom_shift_hours = shift_hours

        if cint(self.get("half_day")):
            start = self.time_to_seconds(self.from_time)
            end = start + int(shift_seconds * 0.5)
            self.to_time = self.seconds_to_time_string(end)
            self.custom_leave_hours = flt(shift_hours / 2, 4)
            self.total_leave_days = 0.5
            self.set_display_time_range(start, end)
            return

        if cint(self.get("quarter_day")):
            start = self.time_to_seconds(self.from_time)
            end = start + int(shift_seconds * 0.25)
            self.to_time = self.seconds_to_time_string(end)
            self.custom_leave_hours = flt(shift_hours / 4, 4)
            self.total_leave_days = 0.25
            self.set_display_time_range(start, end)
            return

        if cint(self.get("is_hourly")):
            leave_start, leave_end = self.get_leave_interval_inside_shift(self.from_time, self.to_time, shift_start, shift_end)
            leave_hours = flt((leave_end - leave_start) / 3600, 4)
            self.custom_leave_hours = leave_hours
            self.total_leave_days = flt(leave_hours / shift_hours, 4)
            self.set_display_time_range(leave_start, leave_end)

    def get_normalized_interval(self, start_time, end_time):
        # AR: تحويل وقتي البداية والنهاية إلى فاصل زمني يدعم الورديات الليلية.
        # EN: Normalize a time interval, including overnight shifts.
        start = self.time_to_seconds(start_time)
        end = self.time_to_seconds(end_time)
        if end <= start:
            end += DAY_SECONDS
        return start, end

    def time_to_seconds(self, value):
        # AR: تحويل قيمة الوقت إلى عدد الثواني منذ بداية اليوم.
        # EN: Convert a time value to seconds from midnight.
        if isinstance(value, timedelta):
            return int(value.total_seconds())
        t = get_time(value)
        return t.hour * 3600 + t.minute * 60 + t.second

    def seconds_to_time_string(self, seconds):
        # AR: تحويل عدد الثواني إلى وقت بصيغة 24 ساعة.
        # EN: Convert seconds to a 24-hour time string.
        seconds = int(seconds) % DAY_SECONDS
        return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

    def seconds_to_display_time(self, seconds):
        # AR: تحويل عدد الثواني إلى وقت مقروء بصيغة 12 ساعة.
        # EN: Convert seconds to a readable 12-hour time.
        seconds = int(seconds) % DAY_SECONDS
        hour_24 = seconds // 3600
        period = _("PM") if hour_24 >= 12 else _("AM")
        hour_12 = 12 if hour_24 % 12 == 0 else hour_24 % 12
        return f"{hour_12:02d}:{(seconds % 3600) // 60:02d}:{(seconds % 60):02d} {period}"

    def set_display_time_range(self, start, end):
        # AR: تحديث النص الظاهر لفترة الإجازة الجزئية.
        # EN: Update the displayed partial-leave time range.
        if frappe.get_meta(self.doctype).has_field("custom_partial_time_ar_display"):
            self.custom_partial_time_ar_display = f"{_('From')} {self.seconds_to_display_time(start)} {_('to')} {self.seconds_to_display_time(end)}"

    def get_employee_shift_type(self):
        # AR: جلب نوع الوردية المسندة إلى الموظف في التاريخ المحدد.
        # EN: Return the Employee shift assigned on a date.
        date = getdate(self.from_date)
        assignment = frappe.db.sql("""
            SELECT shift_type FROM `tabShift Assignment`
            WHERE employee = %s AND docstatus = 1 AND start_date <= %s AND (end_date IS NULL OR end_date >= %s)
            ORDER BY start_date DESC LIMIT 1
        """, (self.employee, date, date), as_dict=True)
        return assignment[0].shift_type if assignment else frappe.db.get_value("Employee", self.employee, "default_shift")

    def get_leave_interval_inside_shift(self, leave_from, leave_to, shift_start, shift_end):
        # AR: التحقق من وقوع فترة الإجازة داخل الوردية وإرجاعها.
        # EN: Validate and return a leave interval inside the shift.
        leave_start = self.time_to_seconds(leave_from)
        leave_end = self.time_to_seconds(leave_to)
        if leave_end <= leave_start:
            leave_end += DAY_SECONDS
        if shift_end > DAY_SECONDS and leave_start < shift_start:
            leave_start += DAY_SECONDS
            leave_end += DAY_SECONDS
        if leave_start < shift_start or leave_end > shift_end:
            frappe.throw(_("Leave time must be inside the employee shift."))
        return leave_start, leave_end

    def validate_custom_partial_leave_balance(self):
        # AR: التحقق من كفاية الرصيد الدقيق للإجازة الجزئية.
        # EN: Validate the precise balance for partial leave.
        if self.total_leave_days <= 0:
            return
        # AR: استدعاء داخلي أثناء التحقق بعد أن طبق Frappe صلاحية حفظ المستند.
        # EN: Internal calculation after Frappe has enforced document write permission.
        balance = _calculate_precise_leave_balance(
            self.employee,
            self.leave_type,
            self.from_date,
            self.name,
        )
        if balance < self.total_leave_days:
            frappe.throw(_("Close! Your actual precise balance ({0}) is insufficient for this partial request ({1} days).").format(flt(balance, 4), flt(self.total_leave_days, 4)))

def display_time_to_time_string(value):
    # AR: تحويل الوقت المعروض بصيغة AM أو PM إلى صيغة 24 ساعة.
    # EN: Convert an AM/PM display time to 24-hour format.
    if not value:
        return None
    if isinstance(value, timedelta):
        return f"{int(value.total_seconds()) // 3600:02d}:{(int(value.total_seconds()) % 3600) // 60:02d}:00"

    match = re.search(
        r"^\s*(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(AM|PM)?\s*$",
        str(value),
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    second = int(match.group(3) or 0)
    period = (match.group(4) or "").upper()

    if minute > 59 or second > 59:
        return None

    if period:
        if hour < 1 or hour > 12:
            return None
        hour = hour % 12 + (12 if period == "PM" else 0)
    elif hour > 23:
        return None

    return f"{hour:02d}:{minute:02d}:{second:02d}"

@frappe.whitelist()
def get_precise_leave_balance(
    employee,
    leave_type,
    date=None,
    exclude_docname=None,
):
    """
    AR:
        إرجاع رصيد الإجازة للمستخدم المخول فقط.
        عند فتح HR User لطلب موظف آخر، يبقى الرصيد مخفيًا
        دون إظهار رسالة خطأ مزعجة.

    EN:
        Return leave balance only to authorized users.
        When a read-only HR User views another employee's request,
        keep the balance hidden without raising a disruptive error.
    """
    from masar_requests.hr_user_read_only import is_hr_user_read_only
    from masar_requests.leave_application_permissions import (
        can_access_employee_leave_data,
    )

    if not can_access_employee_leave_data(employee):
        if is_hr_user_read_only():
            return None

        frappe.throw(
            _("You are not allowed to view this employee's leave balance."),
            frappe.PermissionError,
        )

    return _calculate_precise_leave_balance(
        employee,
        leave_type,
        date,
        exclude_docname,
    )


def _calculate_precise_leave_balance(employee, leave_type, date=None, exclude_docname=None):
    """Calculate a balance without exposing an unauthenticated endpoint.

    AR: دالة داخلية تستخدمها دورة حفظ المستند بعد تطبيق صلاحيات Frappe.
    EN: Internal helper used by document validation after Frappe permissions apply.
    """

    date = getdate(date or frappe.utils.today())
    allocation = frappe.db.sql("""
        SELECT from_date, to_date FROM `tabLeave Allocation`
        WHERE employee = %s AND leave_type = %s AND docstatus = 1 AND from_date <= %s AND to_date >= %s
        ORDER BY from_date DESC, creation DESC LIMIT 1
    """, (employee, leave_type, date, date), as_dict=True)
    
    if allocation:
        period_from = allocation[0].from_date
        period_to = allocation[0].to_date
    else:
        period_from = getdate(f"{date.year}-01-01")
        period_to = getdate(f"{date.year}-12-31")
        
    conds = "employee = %(employee)s AND leave_type = %(leave_type)s AND docstatus = 1 AND from_date >= %(period_from)s AND from_date <= %(period_to)s"
    vals = {"employee": employee, "leave_type": leave_type, "period_from": period_from, "period_to": period_to}
    
    if exclude_docname:
        conds += " AND IFNULL(transaction_name, '') != %(exclude_docname)s"
        vals["exclude_docname"] = exclude_docname
        
    if frappe.get_meta("Leave Ledger Entry").has_field("is_expired"):
        conds += " AND IFNULL(is_expired, 0) = 0"
        
    balance = frappe.db.sql(f"SELECT COALESCE(SUM(leaves), 0) FROM `tabLeave Ledger Entry` WHERE {conds}", vals)[0][0]
    return flt(balance, 4)
