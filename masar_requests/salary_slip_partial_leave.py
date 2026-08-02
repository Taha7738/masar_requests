"""
AR: تنفيذ وظائف تطبيق مسار ضمن الوحدة `salary_slip_partial_leave`.
EN: Masar application functionality implemented by the `salary_slip_partial_leave` module.
"""

# ============================================================================
# AR: دعم الكسور الدقيقة للإجازة الجزئية في احتساب الرواتب
# EN: Exact partial-leave fractions in Salary Slip payroll calculations
# ============================================================================

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip


class CustomSalarySlip(SalarySlip):
    """
    AR: فئة `CustomSalarySlip` لتنظيم منطق `salary` `slip` الجزئي الإجازة.
    EN: Class `CustomSalarySlip` that organizes salary slip partial leave logic.

    DETAILS / التفاصيل:
    AR:
            يضيف فقط الفرق اللازم لربع اليوم والإجازة بالساعات، ثم يترك بقية
            احتساب Salary Slip القياسي كما هو. لا يغير منطق اليوم الكامل أو النصف.

        EN:
            Add only the exact correction required for quarter-day and hourly leave,
            while preserving the native Salary Slip logic for full and half days.
    """

    def _supports_precise_partial_leave(self):
        """
        AR: تنفيذ `supports` `precise` الجزئي الإجازة ضمن وحدة `salary_slip_partial_leave`.
        EN: Execute supports precise partial leave within the `salary_slip_partial_leave` module.
        """
        leave_meta = frappe.get_meta("Leave Application")
        attendance_meta = frappe.get_meta("Attendance")
        return (
            leave_meta.has_field("quarter_day")
            and leave_meta.has_field("is_hourly")
            and leave_meta.has_field("custom_partial_attendance_status")
            and attendance_meta.has_field("custom_partial_leave_day_fraction")
        )

    def _assert_partial_leave_attendance_reconciled(self, end_date=None):
        """
        AR: تنفيذ `assert` الجزئي الإجازة الحضور `reconciled` ضمن وحدة `salary_slip_partial_leave`.
        EN: Execute assert partial leave attendance reconciled within the `salary_slip_partial_leave` module.

        DETAILS / التفاصيل:
        AR:
                    منع اعتماد احتساب راتب قد يجمع غياب يوم كامل مع كسر إجازة جزئية
                    لم تُسوَّ بعد. لا يُسمح بالاحتساب حتى تصبح كل إجازة جزئية معتمدة
                    داخل الفترة في حالة Reconciled.

                EN:
                    Prevent payroll from combining a full-day absence with an unresolved
                    partial-leave fraction. Every approved custom partial leave in the
                    salary period must be Reconciled before payroll calculation proceeds.
        """
        if (
            not self._supports_precise_partial_leave()
            or not self.employee
            or not self.start_date
            or not (end_date or self.end_date)
        ):
            return

        unresolved = frappe.db.sql(
            """
            SELECT name, IFNULL(custom_partial_attendance_status, '') AS reconciliation_status
              FROM `tabLeave Application`
             WHERE employee = %s
               AND docstatus = 1
               AND status = 'Approved'
               AND (IFNULL(quarter_day, 0) = 1 OR IFNULL(is_hourly, 0) = 1)
               AND from_date BETWEEN %s AND %s
               AND IFNULL(custom_partial_attendance_status, '') != 'Reconciled'
             ORDER BY from_date ASC, name ASC
            """,
            (self.employee, self.start_date, end_date or self.end_date),
            as_dict=True,
        )
        if not unresolved:
            return

        references = ", ".join(
            f"{row.name} [{row.reconciliation_status or 'Pending'}]"
            for row in unresolved[:10]
        )
        if len(unresolved) > 10:
            references += _(" and {0} more").format(len(unresolved) - 10)

        frappe.throw(
            _(
                "Salary Slip cannot be calculated until partial-leave Attendance reconciliation is completed for: {0}."
            ).format(references),
            title=_("Partial Leave Attendance Pending"),
        )

    def _get_partial_leave_applications(self, end_date=None):
        """
        AR: تنفيذ استرجاع الجزئي الإجازة `applications` ضمن وحدة `salary_slip_partial_leave`.
        EN: Execute get partial leave applications within the `salary_slip_partial_leave` module.
        """
        if not self._supports_precise_partial_leave():
            return []

        return frappe.db.sql(
            """
            SELECT
                la.name,
                la.from_date AS leave_date,
                la.total_leave_days AS day_fraction,
                lt.is_lwp,
                lt.is_ppl,
                lt.fraction_of_daily_salary_per_leave,
                lt.include_holiday
            FROM `tabLeave Application` la
            INNER JOIN `tabLeave Type` lt ON lt.name = la.leave_type
            WHERE la.employee = %s
              AND la.docstatus = 1
              AND la.status = 'Approved'
              AND (IFNULL(la.quarter_day, 0) = 1 OR IFNULL(la.is_hourly, 0) = 1)
              AND la.from_date BETWEEN %s AND %s
              AND (lt.is_lwp = 1 OR lt.is_ppl = 1)
            """,
            (self.employee, self.start_date, end_date or self.end_date),
            as_dict=True,
        )

    def calculate_lwp_or_ppl_based_on_leave_application(
        self,
        holidays,
        working_days_list,
        daily_wages_fraction_for_half_day,
    ):
        """
        AR: تنفيذ حساب `lwp` `or` `ppl` `based` معالجة حدث الإجازة `application` ضمن وحدة `salary_slip_partial_leave`.
        EN: Execute calculate lwp or ppl based on leave application within the `salary_slip_partial_leave` module.

        DETAILS / التفاصيل:
        AR:
                    المنطق القياسي يعد الإجازة المخصصة يوماً كاملاً لأنها ليست Half Day.
                    نصحح فقط ذلك اليوم إلى الكسر المحفوظ في total_leave_days.

                EN:
                    Native leave-based payroll counts a custom partial leave as one full
                    day because it is not Half Day. Replace only that one-day equivalent
                    with the exact fraction stored in total_leave_days.
        """
        self._assert_partial_leave_attendance_reconciled(self.end_date)

        native_lwp = super().calculate_lwp_or_ppl_based_on_leave_application(
            holidays,
            working_days_list,
            daily_wages_fraction_for_half_day,
        )
        working_dates = {getdate(value) for value in working_days_list}

        correction = 0.0
        for row in self._get_partial_leave_applications(self.end_date):
            leave_date = getdate(row.leave_date)
            if leave_date not in working_dates:
                continue
            if self.relieving_date and leave_date > getdate(self.relieving_date):
                continue
            if not cint(row.include_holiday) and leave_date in {getdate(d) for d in holidays}:
                continue

            multiplier = 1.0
            if cint(row.is_ppl):
                paid_fraction = flt(row.fraction_of_daily_salary_per_leave)
                multiplier = (1 - paid_fraction) if paid_fraction else 1.0

            native_equivalent = multiplier
            exact_equivalent = flt(row.day_fraction, 4) * multiplier
            correction += exact_equivalent - native_equivalent

        return max(flt(native_lwp + correction, 4), 0)

    def calculate_lwp_ppl_and_absent_days_based_on_attendance(
        self,
        holidays,
        daily_wages_fraction_for_half_day,
        consider_marked_attendance_on_holidays,
    ):
        """
        AR: تنفيذ حساب `lwp` `ppl` `and` `absent` `days` `based` معالجة حدث الحضور ضمن وحدة `salary_slip_partial_leave`.
        EN: Execute calculate lwp ppl and absent days based on attendance within the `salary_slip_partial_leave` module.

        DETAILS / التفاصيل:
        AR:
                    سجل الإجازة الجزئية يبقى Present مع حقول تدقيق، ولذلك لا يراه
                    الاستعلام القياسي لحالات On Leave/Half Day. نضيف الكسر الدقيق فقط.

                EN:
                    Partial-leave Attendance remains Present with audit fields, so the
                    native On Leave/Half Day query does not count it. Add the exact
                    fraction only, without changing absent-day behavior.
        """
        self._assert_partial_leave_attendance_reconciled(
            self.get("actual_end_date") or self.end_date
        )

        native_lwp, absent = super().calculate_lwp_ppl_and_absent_days_based_on_attendance(
            holidays,
            daily_wages_fraction_for_half_day,
            consider_marked_attendance_on_holidays,
        )
        holiday_dates = {getdate(d) for d in holidays}
        precise_lwp = 0.0

        for row in self._get_partial_leave_applications(self.actual_end_date):
            leave_date = getdate(row.leave_date)
            if (
                not cint(consider_marked_attendance_on_holidays)
                and leave_date in holiday_dates
                and not cint(row.include_holiday)
            ):
                continue

            multiplier = 1.0
            if cint(row.is_ppl):
                deduction_fraction = flt(row.fraction_of_daily_salary_per_leave)
                multiplier = deduction_fraction if deduction_fraction else 1.0

            precise_lwp += flt(row.day_fraction, 4) * multiplier

        return flt(native_lwp + precise_lwp, 4), absent
