"""
AR: تنفيذ وظائف تطبيق مسار ضمن الوحدة `leave_application_partial_leave`.
EN: Masar application functionality implemented by the `leave_application_partial_leave` module.
"""

# =======================================================================
# 🚀 محرك احتساب الإجازات الجزئية الصارم بالساعة والربع والنصف - تنظيم
# =======================================================================

from datetime import datetime, time, timedelta
import re
import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, get_time, now_datetime
from hrms.hr.doctype.leave_application.leave_application import LeaveApplication

from masar_requests.official_duty_engine import (
    COVERAGE_TOLERANCE_SECONDS,
    build_physical_intervals,
    get_checkins,
    get_shift_window,
    interval_seconds,
    merge_intervals,
    subtract_intervals,
)
from masar_requests.overrides.shift_type import resolve_employee_shift_name

DAY_SECONDS = 24 * 60 * 60

class CustomLeaveApplication(LeaveApplication):
    """
    AR: فئة `CustomLeaveApplication` لتنظيم منطق الإجازة `application` الجزئي الإجازة.
    EN: Class `CustomLeaveApplication` that organizes leave application partial leave logic.
    """
    def validate(self):
        # AR: تشغيل تحقق طلب الإجازة القياسي والتحقق الإضافي للإجازة الجزئية.
        # EN: Run standard validation plus partial-leave validation.
        """
        AR: تنفيذ التحقق من صحة ضمن وحدة `leave_application_partial_leave`.
        EN: Execute validate within the `leave_application_partial_leave` module.
        """
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
        """
        AR: تنفيذ التحقق من صحة الرصيد `leaves` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute validate balance leaves within the `leave_application_partial_leave` module.
        """
        if not self.is_custom_partial_leave():
            return super().validate_balance_leaves()
        self.validate_single_partial_option()
        self.normalize_partial_leave_date()
        self.apply_partial_leave_time_and_days()
        self.validate_custom_partial_leave_balance()

    def validate_attendance(self):
        # AR: الإجازات العادية تستخدم تحقق HRMS القياسي دون تغيير.
        # EN: Normal leaves keep the native HRMS attendance validation unchanged.
        """
        AR: تنفيذ التحقق من صحة الحضور ضمن وحدة `leave_application_partial_leave`.
        EN: Execute validate attendance within the `leave_application_partial_leave` module.
        """
        if not self.is_custom_partial_leave():
            return super().validate_attendance()

        # AR:
        # ربع اليوم والإجازة بالساعات مسموحان مع Present/Work From Home لأنهما
        # يوثقان جزءاً مأذوناً داخل يوم عمل. يمنع ربط طلبين جزئيين بالسجل نفسه.
        #
        # EN:
        # Quarter-day/hourly leave may coexist with Present/Work From Home because
        # they document an authorized segment inside a working day. A second
        # partial-leave link on the same Attendance record is rejected.
        attendance = self._get_partial_attendance()
        if not attendance:
            return

        linked_application = attendance.get("custom_partial_leave_application")
        if linked_application and linked_application != self.name:
            frappe.throw(
                _("Attendance {0} is already linked to Partial Leave Application {1}.").format(
                    frappe.bold(attendance.name),
                    frappe.bold(linked_application),
                )
            )

        if attendance.status in {"On Leave"} and attendance.get("leave_application") != self.name:
            frappe.throw(
                _("Attendance {0} is already marked On Leave and requires HR review.").format(
                    frappe.bold(attendance.name)
                )
            )

    def update_attendance(self):
        # AR: الإجازات العادية (يوم/نصف يوم) تبقى على منطق HRMS القياسي.
        # EN: Full-day and half-day leave keep the native HRMS behavior.
        """
        AR: تنفيذ تحديث الحضور ضمن وحدة `leave_application_partial_leave`.
        EN: Execute update attendance within the `leave_application_partial_leave` module.
        """
        if not self.is_custom_partial_leave():
            return super().update_attendance()

        if self.status != "Approved":
            return

        attendance = self._get_partial_attendance()

        # AR:
        # لا ننشئ Attendance مبكراً قبل انتهاء الوردية/مزامنة الحضور التلقائي؛
        # لأن سجل Submitted مبكر قد يمنع Auto Attendance من ربط البصمات.
        #
        # EN:
        # Never create Attendance before shift completion/auto-attendance sync;
        # an early submitted record could prevent Auto Attendance from linking
        # the real checkins.
        if not attendance and not self._partial_attendance_is_ready():
            self._set_partial_attendance_processing(
                "Waiting for Shift End",
                _(
                    "Partial leave is approved and will be registered in Attendance after the shift and checkin synchronization finish."
                ),
            )
            return

        coverage = self._get_partial_leave_coverage()

        # AR:
        # الإجازة الجزئية تبرر فترتها فقط. إذا لم تغطِّ البصمات مع الإجازة
        # كامل الوردية، لا نحول Absent/Half Day إلى Present تلقائياً.
        # نسجل البيانات المتاحة ونطلب مراجعة HR.
        #
        # EN:
        # Partial leave authorizes only its exact interval. If real checkins plus
        # leave do not cover the shift, never promote Absent/Half Day to Present.
        # Store available audit data and require HR review.
        if not coverage.is_fully_covered:
            attendance_name = None
            if attendance:
                self._write_partial_attendance_fields(
                    attendance,
                    coverage,
                    reconciliation_status="Manual Review",
                    change_daily_status=False,
                )
                attendance_name = attendance.name

            self._set_partial_attendance_processing(
                "Manual Review",
                _(
                    "The partial leave and available checkins leave {0} uncovered hour(s); HR review is required."
                ).format(coverage.uncovered_hours),
                attendance_name,
            )
            return

        created = not bool(attendance)
        if created:
            attendance = frappe.new_doc("Attendance")
            attendance.employee = self.employee
            attendance.employee_name = self.employee_name
            attendance.attendance_date = self.from_date
            attendance.company = self.company
            attendance.shift = coverage.shift
            attendance.status = "Present"
            attendance.flags.ignore_validate = True
        else:
            linked_application = attendance.get("custom_partial_leave_application")
            if linked_application and linked_application != self.name:
                frappe.throw(
                    _("Attendance {0} is already linked to Partial Leave Application {1}.").format(
                        frappe.bold(attendance.name),
                        frappe.bold(linked_application),
                    )
                )

        self._write_partial_attendance_fields(
            attendance,
            coverage,
            reconciliation_status="Reconciled",
            created=created,
        )

        if created:
            attendance.insert(ignore_permissions=True)
            attendance.submit()
            attendance.add_comment(
                comment_type="Info",
                text=self._get_partial_leave_coverage_note(coverage),
            )
        else:
            attendance.save(ignore_permissions=True)

        self._set_partial_attendance_processing(
            "Reconciled",
            _("Partial leave was registered in Attendance with the exact hour/day fraction."),
            attendance.name,
        )

    def _get_partial_leave_coverage(self):
        """
        AR: تنفيذ استرجاع الجزئي الإجازة `coverage` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute get partial leave coverage within the `leave_application_partial_leave` module.

        DETAILS / التفاصيل:
        AR:
                    دمج البصمات الفعلية مع فترة الإجازة المأذونة دون احتساب مزدوج،
                    ثم تحديد الساعات غير المغطاة من الوردية.

                EN:
                    Merge real checkins with the authorized leave interval without
                    double-counting, then calculate uncovered shift time.
        """
        shift_name = self.get_employee_shift_type()
        shift_window = get_shift_window(self.employee, self.from_date, shift_name)

        leave_start = datetime.combine(getdate(self.from_date), get_time(self.from_time))
        leave_end = datetime.combine(getdate(self.from_date), get_time(self.to_time))
        if leave_end <= leave_start:
            leave_end += timedelta(days=1)

        # AR: إزاحة أوقات ما بعد منتصف الليل داخل نافذة الوردية الليلية.
        # EN: Move post-midnight values into the overnight shift window.
        if shift_window.end.date() > shift_window.start.date() and leave_start < shift_window.start:
            leave_start += timedelta(days=1)
            leave_end += timedelta(days=1)

        if leave_start < shift_window.start or leave_end > shift_window.end:
            frappe.throw(_("Leave time must be inside the employee shift."))

        leave_interval = (leave_start, leave_end)
        checkins = get_checkins(self.employee, shift_window)
        physical_intervals, missing_checkout_explained = build_physical_intervals(
            checkins,
            shift_window,
            leave_interval,
        )
        credited_intervals = merge_intervals([*physical_intervals, leave_interval])
        physical_excluding_leave = subtract_intervals(physical_intervals, [leave_interval])

        shift_seconds = (shift_window.end - shift_window.start).total_seconds()
        leave_seconds = interval_seconds([leave_interval])
        physical_seconds = interval_seconds(physical_excluding_leave)
        credited_seconds = interval_seconds(credited_intervals)
        uncovered_seconds = max(shift_seconds - credited_seconds, 0)

        return frappe._dict(
            {
                "shift": shift_window.name,
                "shift_start": shift_window.start,
                "shift_end": shift_window.end,
                "leave_start": leave_start,
                "leave_end": leave_end,
                "leave_hours": flt(leave_seconds / 3600, 4),
                "physical_working_hours": flt(physical_seconds / 3600, 4),
                "credited_working_hours": flt(credited_seconds / 3600, 4),
                "uncovered_hours": flt(uncovered_seconds / 3600, 4),
                "is_fully_covered": uncovered_seconds <= COVERAGE_TOLERANCE_SECONDS,
                "missing_checkout_explained": missing_checkout_explained,
            }
        )

    def _write_partial_attendance_fields(
        self,
        attendance,
        coverage,
        reconciliation_status,
        created=False,
        change_daily_status=True,
    ):
        """
        AR: تنفيذ الكتابة الجزئي الحضور الحقول ضمن وحدة `leave_application_partial_leave`.
        EN: Execute write partial attendance fields within the `leave_application_partial_leave` module.
        """
        linked_application = attendance.get("custom_partial_leave_application")
        previous_reconciliation_status = attendance.get(
            "custom_partial_leave_reconciliation_status"
        )
        if linked_application and linked_application != self.name:
            frappe.throw(
                _("Attendance {0} is already linked to Partial Leave Application {1}.").format(
                    frappe.bold(attendance.name),
                    frappe.bold(linked_application),
                )
            )

        if not linked_application and not created:
            attendance.custom_partial_leave_previous_status = attendance.status
            attendance.custom_partial_leave_previous_half_day_status = attendance.half_day_status
            attendance.custom_partial_leave_previous_leave_type = attendance.leave_type
            attendance.custom_partial_leave_previous_leave_application = attendance.leave_application

        if change_daily_status and attendance.status not in {"Present", "Work From Home"}:
            attendance.status = "Present"
            attendance.half_day_status = None
            attendance.leave_type = None
            attendance.leave_application = None

        attendance.custom_partial_leave_application = self.name
        attendance.custom_partial_leave_type = self.leave_type
        attendance.custom_partial_leave_hours = flt(self.custom_leave_hours, 4)
        attendance.custom_partial_leave_day_fraction = flt(self.total_leave_days, 4)
        attendance.custom_partial_leave_from_time = self.from_time
        attendance.custom_partial_leave_to_time = self.to_time
        attendance.custom_partial_leave_reconciliation_status = reconciliation_status
        if created:
            attendance.custom_partial_leave_attendance_created = 1
        elif not linked_application:
            attendance.custom_partial_leave_attendance_created = 0
        attendance.flags.ignore_validate = True
        attendance.flags.ignore_validate_update_after_submit = True

        # AR: إضافة تعليق واحد فقط عند انتقال حالة التسوية على سجل موجود.
        # EN: Add one audit comment only when reconciliation status changes.
        if (
            attendance.name
            and previous_reconciliation_status != reconciliation_status
        ):
            attendance.add_comment(
                comment_type="Info",
                text=self._get_partial_leave_coverage_note(coverage),
            )

        # AR: في Manual Review نحفظ التوثيق على السجل الموجود فقط دون Submit جديد.
        # EN: Manual Review annotates an existing record only; it never creates one.
        if reconciliation_status == "Manual Review" and not created:
            attendance.save(ignore_permissions=True)

    def _get_partial_leave_coverage_note(self, coverage):
        """
        AR: تنفيذ استرجاع الجزئي الإجازة `coverage` `note` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute get partial leave coverage note within the `leave_application_partial_leave` module.
        """
        return _(
            "Partial leave coverage: {0} physical hour(s) + {1} leave hour(s) = {2} credited hour(s); {3} uncovered hour(s)."
        ).format(
            coverage.physical_working_hours,
            coverage.leave_hours,
            coverage.credited_working_hours,
            coverage.uncovered_hours,
        )

    def _partial_attendance_is_ready(self):
        """
        AR: تنفيذ الجزئي الحضور التحقق من كون `ready` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute partial attendance is ready within the `leave_application_partial_leave` module.

        DETAILS / التفاصيل:
        AR:
                    التحقق من انتهاء الوردية ووصول Last Sync عند تفعيل Auto Attendance.
                    هذا يمنع طلب الإجازة من حجب معالجة البصمات القياسية.

                EN:
                    Check shift completion and Last Sync when Auto Attendance is enabled.
                    This prevents partial leave from blocking native checkin processing.
        """
        shift_type = self.get_employee_shift_type()
        if not shift_type:
            return False

        shift_window = get_shift_window(self.employee, self.from_date, shift_type)
        shift = shift_window.doc
        shift_end = shift_window.end + timedelta(
            minutes=cint(shift.get("allow_check_out_after_shift_end_time") or 0)
        )
        if now_datetime() < shift_end:
            return False

        if cint(shift.get("enable_auto_attendance")):
            last_sync = shift.get("last_sync_of_checkin")
            if not last_sync or get_datetime(last_sync) < shift_end:
                return False

        return True

    def _set_partial_attendance_processing(self, status, message, attendance=None):
        """
        AR: تنفيذ تعيين الجزئي الحضور `processing` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute set partial attendance processing within the `leave_application_partial_leave` module.
        """
        if not self.name or not frappe.db.exists("Leave Application", self.name):
            return

        values = {}
        for fieldname, value in {
            "custom_partial_attendance_status": status,
            "custom_partial_attendance_message": message,
            "custom_partial_attendance": attendance,
            "custom_partial_attendance_last_processed_on": now_datetime(),
        }.items():
            if self.meta.has_field(fieldname):
                values[fieldname] = value
        if values:
            frappe.db.set_value(
                "Leave Application",
                self.name,
                values,
                update_modified=False,
            )

    def cancel_attendance(self):
        # AR: الإجازات العادية تستخدم الإلغاء القياسي.
        # EN: Normal leave cancellation keeps the native HRMS logic.
        """
        AR: تنفيذ إلغاء الحضور ضمن وحدة `leave_application_partial_leave`.
        EN: Execute cancel attendance within the `leave_application_partial_leave` module.
        """
        if not self.is_custom_partial_leave():
            return super().cancel_attendance()

        attendance = self._get_partial_attendance(require_link=True)
        if not attendance:
            # AR: قد يلغى الطلب أثناء انتظار نهاية الوردية قبل إنشاء Attendance.
            # EN: The request may be cancelled while waiting before Attendance exists.
            self._set_partial_attendance_processing(
                "Cancelled",
                _("Partial-leave Attendance reconciliation was cancelled."),
            )
            return

        if cint(attendance.get("custom_partial_leave_attendance_created")):
            # AR: السجل أنشئ خصيصاً لهذا الطلب، لذلك يلغى كاملاً.
            # EN: The record was created only for this request, so cancel it.
            if attendance.docstatus == 1:
                attendance.flags.ignore_permissions = True
                attendance.cancel()
            self._set_partial_attendance_processing(
                "Cancelled",
                _("Partial-leave Attendance reconciliation was cancelled."),
                attendance.name,
            )
            return

        # AR: السجل كان موجوداً مسبقاً؛ نعيد حالته الأصلية ونمسح حقولنا فقط.
        # EN: Restore the pre-existing record and clear only app-owned fields.
        attendance.status = attendance.get("custom_partial_leave_previous_status") or "Present"
        attendance.half_day_status = attendance.get("custom_partial_leave_previous_half_day_status")
        attendance.leave_type = attendance.get("custom_partial_leave_previous_leave_type")
        attendance.leave_application = attendance.get("custom_partial_leave_previous_leave_application")
        for fieldname in (
            "custom_partial_leave_application",
            "custom_partial_leave_type",
            "custom_partial_leave_hours",
            "custom_partial_leave_day_fraction",
            "custom_partial_leave_from_time",
            "custom_partial_leave_to_time",
            "custom_partial_leave_reconciliation_status",
            "custom_partial_leave_attendance_created",
            "custom_partial_leave_previous_status",
            "custom_partial_leave_previous_half_day_status",
            "custom_partial_leave_previous_leave_type",
            "custom_partial_leave_previous_leave_application",
        ):
            attendance.set(fieldname, None)
        attendance.flags.ignore_validate = True
        attendance.flags.ignore_validate_update_after_submit = True
        attendance.save(ignore_permissions=True)
        self._set_partial_attendance_processing(
            "Cancelled",
            _("Partial-leave Attendance reconciliation was cancelled."),
            attendance.name,
        )

    def _get_partial_attendance(self, require_link=False):
        """
        AR: تنفيذ استرجاع الجزئي الحضور ضمن وحدة `leave_application_partial_leave`.
        EN: Execute get partial attendance within the `leave_application_partial_leave` module.
        """
        filters = {
            "employee": self.employee,
            "attendance_date": self.from_date,
            "docstatus": ("!=", 2),
        }
        if require_link:
            filters["custom_partial_leave_application"] = self.name

        attendance_name = frappe.db.get_value("Attendance", filters, "name")
        return frappe.get_doc("Attendance", attendance_name) if attendance_name else None

    def is_custom_partial_leave(self):
        # AR: التحقق من أن الطلب ربع يوم أو إجازة بالساعات.
        # EN: Check whether the request is quarter-day or hourly leave.
        """
        AR: تنفيذ التحقق من كون `custom` الجزئي الإجازة ضمن وحدة `leave_application_partial_leave`.
        EN: Execute is custom partial leave within the `leave_application_partial_leave` module.
        """
        return cint(self.get("quarter_day")) or cint(self.get("is_hourly"))

    def is_any_partial_leave(self):
        # AR: التحقق من أن الطلب نصف يوم أو ربع يوم أو إجازة بالساعات.
        # EN: Check whether any partial-leave option is selected.
        """
        AR: تنفيذ التحقق من كون `any` الجزئي الإجازة ضمن وحدة `leave_application_partial_leave`.
        EN: Execute is any partial leave within the `leave_application_partial_leave` module.
        """
        return cint(self.get("half_day")) or cint(self.get("quarter_day")) or cint(self.get("is_hourly"))

    def validate_single_partial_option(self):
        # AR: منع اختيار أكثر من نوع إجازة جزئية في الوقت نفسه.
        # EN: Prevent selecting more than one partial-leave type.
        """
        AR: تنفيذ التحقق من صحة `single` الجزئي `option` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute validate single partial option within the `leave_application_partial_leave` module.
        """
        if (cint(self.get("half_day")) + cint(self.get("quarter_day")) + cint(self.get("is_hourly"))) > 1:
            frappe.throw(_("Only one option can be selected: Half Day, Quarter Day, or Hourly Leave."))

    def normalize_partial_leave_date(self):
        # AR: توحيد تاريخ الإجازة الجزئية مع تاريخي البداية والنهاية.
        # EN: Align the partial date with the request date range.
        """
        AR: تنفيذ توحيد الجزئي الإجازة التاريخ ضمن وحدة `leave_application_partial_leave`.
        EN: Execute normalize partial leave date within the `leave_application_partial_leave` module.
        """
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
        """
        AR: تنفيذ تطبيق الجزئي الإجازة الوقت `and` `days` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute apply partial leave time and days within the `leave_application_partial_leave` module.
        """
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

        shift_window = get_shift_window(self.employee, self.from_date, shift_type)
        actual_start_time = shift_window.start.time()
        actual_end_time = shift_window.end.time()
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
        """
        AR: تنفيذ استرجاع `normalized` `interval` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute get normalized interval within the `leave_application_partial_leave` module.
        """
        start = self.time_to_seconds(start_time)
        end = self.time_to_seconds(end_time)
        if end <= start:
            end += DAY_SECONDS
        return start, end

    def time_to_seconds(self, value):
        # AR: تحويل قيمة الوقت إلى عدد الثواني منذ بداية اليوم.
        # EN: Convert a time value to seconds from midnight.
        """
        AR: تنفيذ الوقت `to` `seconds` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute time to seconds within the `leave_application_partial_leave` module.
        """
        if isinstance(value, timedelta):
            return int(value.total_seconds())
        t = get_time(value)
        return t.hour * 3600 + t.minute * 60 + t.second

    def seconds_to_time_string(self, seconds):
        # AR: تحويل عدد الثواني إلى وقت بصيغة 24 ساعة.
        # EN: Convert seconds to a 24-hour time string.
        """
        AR: تنفيذ `seconds` `to` الوقت `string` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute seconds to time string within the `leave_application_partial_leave` module.
        """
        seconds = int(seconds) % DAY_SECONDS
        return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

    def seconds_to_display_time(self, seconds):
        # AR: تحويل عدد الثواني إلى وقت مقروء بصيغة 12 ساعة.
        # EN: Convert seconds to a readable 12-hour time.
        """
        AR: تنفيذ `seconds` `to` `display` الوقت ضمن وحدة `leave_application_partial_leave`.
        EN: Execute seconds to display time within the `leave_application_partial_leave` module.
        """
        seconds = int(seconds) % DAY_SECONDS
        hour_24 = seconds // 3600
        period = _("PM") if hour_24 >= 12 else _("AM")
        hour_12 = 12 if hour_24 % 12 == 0 else hour_24 % 12
        return f"{hour_12:02d}:{(seconds % 3600) // 60:02d}:{(seconds % 60):02d} {period}"

    def set_display_time_range(self, start, end):
        # AR: تحديث النص الظاهر لفترة الإجازة الجزئية.
        # EN: Update the displayed partial-leave time range.
        """
        AR: تنفيذ تعيين `display` الوقت `range` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute set display time range within the `leave_application_partial_leave` module.
        """
        if frappe.get_meta(self.doctype).has_field("custom_partial_time_ar_display"):
            self.custom_partial_time_ar_display = f"{_('From')} {self.seconds_to_display_time(start)} {_('to')} {self.seconds_to_display_time(end)}"

    def get_employee_shift_type(self):
        # AR: استخدام محلل الوردية المركزي لمنع اختلاف النتائج بين المستندات.
        # EN: Use the central resolver to keep all shift-linked documents consistent.
        """
        AR: تنفيذ استرجاع الموظف الوردية `type` ضمن وحدة `leave_application_partial_leave`.
        EN: Execute get employee shift type within the `leave_application_partial_leave` module.
        """
        return resolve_employee_shift_name(self.employee, self.from_date)

    def get_leave_interval_inside_shift(self, leave_from, leave_to, shift_start, shift_end):
        # AR: التحقق من وقوع فترة الإجازة داخل الوردية وإرجاعها.
        # EN: Validate and return a leave interval inside the shift.
        """
        AR: تنفيذ استرجاع الإجازة `interval` `inside` الوردية ضمن وحدة `leave_application_partial_leave`.
        EN: Execute get leave interval inside shift within the `leave_application_partial_leave` module.
        """
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
        """
        AR: تنفيذ التحقق من صحة `custom` الجزئي الإجازة الرصيد ضمن وحدة `leave_application_partial_leave`.
        EN: Execute validate custom partial leave balance within the `leave_application_partial_leave` module.
        """
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

def process_pending_partial_leave_attendance():
    """
    AR: تنفيذ `process` `pending` الجزئي الإجازة الحضور ضمن وحدة `leave_application_partial_leave`.
    EN: Execute process pending partial leave attendance within the `leave_application_partial_leave` module.

    DETAILS / التفاصيل:
    AR:
            إعادة فحص الإجازات الجزئية المعتمدة التي انتظرت نهاية الوردية أو
            مزامنة البصمات. لا يغيّر اليوم الكامل أو نصف اليوم القياسي.

        EN:
            Retry approved quarter-day/hourly leaves that waited for shift end or
            checkin synchronization. Native full-day/half-day leave is untouched.
    """
    if not frappe.db.exists("DocType", "Leave Application"):
        return 0

    # AR:
    # أثناء نشر الكود قد تعمل المجدولة قبل bench migrate. نخرج بهدوء حتى
    # لا يفشل العامل بسبب أعمدة لم تُنشأ بعد.
    #
    # EN:
    # A scheduler may run after code deployment but before bench migrate. Exit
    # safely until the V20 Custom Fields exist instead of querying missing columns.
    meta = frappe.get_meta("Leave Application")
    required_fields = (
        "quarter_day",
        "is_hourly",
        "custom_partial_attendance_status",
    )
    if not all(meta.has_field(fieldname) for fieldname in required_fields):
        return 0

    rows = frappe.db.sql(
        """
        SELECT name
          FROM `tabLeave Application`
         WHERE docstatus = 1
           AND status = 'Approved'
           AND (IFNULL(quarter_day, 0) = 1 OR IFNULL(is_hourly, 0) = 1)
           AND (
                IFNULL(custom_partial_attendance_status, '') IN ('', 'Waiting for Shift End', 'Manual Review', 'Failed')
           )
         ORDER BY from_date ASC, modified ASC
         LIMIT 500
        """,
        as_dict=True,
    )

    processed = 0
    for row in rows:
        try:
            doc = frappe.get_doc("Leave Application", row.name)
            doc.update_attendance()
            processed += 1
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Partial leave Attendance reconciliation failed: {row.name}",
            )
            meta = frappe.get_meta("Leave Application")
            values = {}
            if meta.has_field("custom_partial_attendance_status"):
                values["custom_partial_attendance_status"] = "Failed"
            if meta.has_field("custom_partial_attendance_message"):
                values["custom_partial_attendance_message"] = _(
                    "Partial-leave Attendance reconciliation failed. See Error Log."
                )
            if meta.has_field("custom_partial_attendance_last_processed_on"):
                values["custom_partial_attendance_last_processed_on"] = now_datetime()
            if values:
                frappe.db.set_value(
                    "Leave Application", row.name, values, update_modified=False
                )
    return processed


def display_time_to_time_string(value):
    # AR: تحويل الوقت المعروض بصيغة AM أو PM إلى صيغة 24 ساعة.
    # EN: Convert an AM/PM display time to 24-hour format.
    """
    AR: تنفيذ `display` الوقت `to` الوقت `string` ضمن وحدة `leave_application_partial_leave`.
    EN: Execute display time to time string within the `leave_application_partial_leave` module.
    """
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
    AR: تنفيذ استرجاع `precise` الإجازة الرصيد ضمن وحدة `leave_application_partial_leave`.
    EN: Execute get precise leave balance within the `leave_application_partial_leave` module.

    DETAILS / التفاصيل:
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
    """
    AR: تنفيذ حساب `precise` الإجازة الرصيد ضمن وحدة `leave_application_partial_leave`.
    EN: Execute calculate precise leave balance within the `leave_application_partial_leave` module.

    DETAILS / التفاصيل:
    Calculate a balance without exposing an unauthenticated endpoint.

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
