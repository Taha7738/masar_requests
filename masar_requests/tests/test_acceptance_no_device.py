"""
AR: اختبارات آلية للتحقق من منطق `test_acceptance_no_device` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_acceptance_no_device` behavior and regression prevention.

DETAILS / التفاصيل:
اختبارات قبول نظام المهمة الرسمية دون الحاجة إلى جهاز بصمة.

هذه الاختبارات:
- لا تنشئ Employee Checkin.
- لا تعدل بيانات الحضور الحقيقية.
- تستخدم سجلات دخول وخروج افتراضية داخل الذاكرة.
"""

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from masar_requests.official_duty_engine import (
    build_physical_intervals,
    interval_seconds,
    merge_intervals,
    subtract_intervals,
)
from masar_requests.overrides.shift_type import (
    _duration_minutes,
    _select_shift_window,
    get_working_weekdays,
)
from masar_requests.preflight import run_preflight


def dt(hour, minute=0):
    """
    AR: تنفيذ `dt` ضمن وحدة `test_acceptance_no_device`.
    EN: Execute dt within the `test_acceptance_no_device` module.
    """
    return datetime(2026, 7, 30, hour, minute)


def hours(intervals):
    """
    AR: تنفيذ `hours` ضمن وحدة `test_acceptance_no_device`.
    EN: Execute hours within the `test_acceptance_no_device` module.
    """
    return interval_seconds(intervals) / 3600


class TestNoBiometricAcceptance(FrappeTestCase):
    """
    AR: فئة `TestNoBiometricAcceptance` لتنظيم منطق اختبار `acceptance` `no` `device`.
    EN: Class `TestNoBiometricAcceptance` that organizes test acceptance no device logic.

    DETAILS / التفاصيل:
    اختبارات قبول محرك الحضور في بيئة لا تحتوي على جهاز بصمة.
    """

    def test_full_day_duty_without_checkins_covers_entire_shift(self):
        """
        AR: اختبار سيناريو `full` `day` المهمة `without` `checkins` `covers` `entire` الوردية والتحقق من النتيجة المتوقعة.
        EN: Verify the full day duty without checkins covers entire shift scenario and its expected result.

        DETAILS / التفاصيل:
        مهمة تغطي كامل الوردية دون أي بصمة.

                المتوقع:
                - ساعات الحضور الفعلي = صفر.
                - ساعات المهمة = 7 ساعات.
                - الساعات المحتسبة = 7 ساعات.
        """
        shift = SimpleNamespace(
            start=dt(8),
            end=dt(15),
        )
        duty = (dt(8), dt(15))

        physical, explained = build_physical_intervals(
            [],
            shift,
            duty,
        )
        credited = merge_intervals([*physical, duty])

        self.assertEqual(hours(physical), 0)
        self.assertEqual(hours(credited), 7)
        self.assertFalse(explained)

    def test_hourly_duty_without_checkins_does_not_credit_full_day(self):
        """
        AR: اختبار سيناريو `hourly` المهمة `without` `checkins` `does` `not` `credit` `full` `day` والتحقق من النتيجة المتوقعة.
        EN: Verify the hourly duty without checkins does not credit full day scenario and its expected result.

        DETAILS / التفاصيل:
        مهمة من 08:00 إلى 09:00 دون أي دليل على بقية الدوام.

                المتوقع:
                - ساعة واحدة محتسبة.
                - ست ساعات غير مغطاة.
                - لا يجوز اعتبار اليوم كاملًا تلقائيًا.
        """
        shift = SimpleNamespace(
            start=dt(8),
            end=dt(15),
        )
        duty = (dt(8), dt(9))

        physical, explained = build_physical_intervals(
            [],
            shift,
            duty,
        )
        credited = merge_intervals([*physical, duty])
        uncovered = subtract_intervals(
            [(shift.start, shift.end)],
            credited,
        )

        self.assertEqual(hours(physical), 0)
        self.assertEqual(hours(credited), 1)
        self.assertEqual(hours(uncovered), 6)
        self.assertFalse(explained)

    def test_start_of_shift_duty_with_synthetic_logs_covers_day(self):
        """
        AR: اختبار سيناريو `start` `of` الوردية المهمة `with` `synthetic` `logs` `covers` `day` والتحقق من النتيجة المتوقعة.
        EN: Verify the start of shift duty with synthetic logs covers day scenario and its expected result.

        DETAILS / التفاصيل:
        المهمة 08:00–09:00 ثم وجود افتراضي 09:00–15:00.

                البصمات هنا كائنات اختبار داخل الذاكرة وليست سجلات في النظام.
        """
        shift = SimpleNamespace(
            start=dt(8),
            end=dt(15),
        )
        duty = (dt(8), dt(9))

        logs = [
            SimpleNamespace(time=dt(9), log_type="IN"),
            SimpleNamespace(time=dt(15), log_type="OUT"),
        ]

        physical, explained = build_physical_intervals(
            logs,
            shift,
            duty,
        )
        credited = merge_intervals([*physical, duty])

        self.assertEqual(hours(physical), 6)
        self.assertEqual(hours(credited), 7)
        self.assertFalse(explained)

    def test_mid_shift_duty_is_not_double_counted(self):
        """
        AR: اختبار سيناريو `mid` الوردية المهمة التحقق من كون `not` `double` `counted` والتحقق من النتيجة المتوقعة.
        EN: Verify the mid shift duty is not double counted scenario and its expected result.

        DETAILS / التفاصيل:
        وجود افتراضي 08:00–15:00 مع مهمة 11:00–13:00.

                يجب ألا تحسب ساعتَا المهمة مرتين.
        """
        shift = SimpleNamespace(
            start=dt(8),
            end=dt(15),
        )
        duty = (dt(11), dt(13))

        logs = [
            SimpleNamespace(time=dt(8), log_type="IN"),
            SimpleNamespace(time=dt(15), log_type="OUT"),
        ]

        physical, explained = build_physical_intervals(
            logs,
            shift,
            duty,
        )

        physical_inside_company = subtract_intervals(
            physical,
            [duty],
        )
        credited = merge_intervals([*physical, duty])

        self.assertEqual(hours(physical_inside_company), 5)
        self.assertEqual(hours(credited), 7)
        self.assertFalse(explained)

    def test_shift_duration_supports_day_and_night_shifts(self):
        """
        AR: اختبار سيناريو الوردية `duration` `supports` `day` `and` `night` `shifts` والتحقق من النتيجة المتوقعة.
        EN: Verify the shift duration supports day and night shifts scenario and its expected result.

        DETAILS / التفاصيل:
        الوردية اليومية والليلية تحسبان بشكل صحيح.
        """
        self.assertEqual(
            _duration_minutes("08:00:00", "15:00:00"),
            420,
        )
        self.assertEqual(
            _duration_minutes("22:00:00", "06:00:00"),
            480,
        )

    def test_post_midnight_time_uses_previous_night_shift(self):
        """
        AR: اختبار سيناريو `post` `midnight` الوقت `uses` `previous` `night` الوردية والتحقق من النتيجة المتوقعة.
        EN: Verify the post midnight time uses previous night shift scenario and its expected result.

        DETAILS / التفاصيل:
        الوقت بعد منتصف الليل يرتبط بالوردية الليلية السابقة.
        """
        previous = SimpleNamespace(
            anchor_date=date(2026, 7, 30),
            start_datetime=datetime(2026, 7, 30, 22, 0),
            end_datetime=datetime(2026, 7, 31, 6, 0),
            actual_start=datetime(2026, 7, 30, 21, 0),
            actual_end=datetime(2026, 7, 31, 7, 0),
        )

        current = SimpleNamespace(
            anchor_date=date(2026, 7, 31),
            start_datetime=datetime(2026, 7, 31, 22, 0),
            end_datetime=datetime(2026, 8, 1, 6, 0),
            actual_start=datetime(2026, 7, 31, 21, 0),
            actual_end=datetime(2026, 8, 1, 7, 0),
        )

        selected = _select_shift_window(
            [previous, current],
            datetime(2026, 7, 31, 2, 0),
            native_anchor=date(2026, 7, 30),
        )

        self.assertEqual(
            selected.anchor_date,
            date(2026, 7, 30),
        )

    def test_variable_shifts_have_all_required_working_days(self):
        """
        AR: اختبار سيناريو `variable` `shifts` `have` `all` `required` `working` `days` والتحقق من النتيجة المتوقعة.
        EN: Verify the variable shifts have all required working days scenario and its expected result.

        DETAILS / التفاصيل:
        جدول الوردية يجب أن يحتوي أيام العمل فقط،
                وليس أيام العطلات الأسبوعية.
        """
        shifts = frappe.get_all(
            "Shift Type",
            filters={"custom_enable_variable_shift_times": 1},
            pluck="name",
        )

        for shift_name in shifts:
            shift = frappe.get_doc(
                "Shift Type",
                shift_name,
            )

            required_days = set(
                get_working_weekdays(
                    shift.get("holiday_list")
                )
            )

            configured_days = {
                row.day_of_week
                for row in shift.get("custom_shift_times") or []
                if (
                    row.day_of_week
                    and row.start_time is not None
                    and row.end_time is not None
                )
            }

            self.assertTrue(
                required_days.issubset(configured_days),
                msg={
                    "shift": shift_name,
                    "required_days": sorted(required_days),
                    "configured_days": sorted(configured_days),
                },
            )

    def test_preflight_is_ready(self):
        """
        AR: اختبار سيناريو `preflight` التحقق من كون `ready` والتحقق من النتيجة المتوقعة.
        EN: Verify the preflight is ready scenario and its expected result.

        DETAILS / التفاصيل:
        فحص الجاهزية العام يجب أن يبقى ناجحًا.
        """
        result = run_preflight()

        self.assertTrue(
            result.get("ready"),
            msg=result,
        )
        self.assertEqual(
            result.get("errors"),
            [],
            msg=result,
        )

    def test_engine_does_not_create_employee_checkins(self):
        """
        AR: اختبار سيناريو `engine` `does` `not` إنشاء الموظف `checkins` والتحقق من النتيجة المتوقعة.
        EN: Verify the engine does not create employee checkins scenario and its expected result.
        """
        engine_path = (
            Path(__file__).parents[1]
            / "official_duty_engine.py"
        )

        source = engine_path.read_text(
            encoding="utf-8"
        )

        forbidden_patterns = (
            'new_doc("Employee Checkin")',
            "new_doc('Employee Checkin')",
            'get_doc({"doctype": "Employee Checkin"',
            "get_doc({'doctype': 'Employee Checkin'",
            "INSERT INTO `tabEmployee Checkin`",
        )

        for pattern in forbidden_patterns:
            self.assertNotIn(
                pattern,
                source,
                msg=f"Found synthetic checkin creation pattern: {pattern}",
            )

    def test_nonlegacy_attendance_links_use_matching_dates(self):
        """
        AR: اختبار سيناريو `nonlegacy` الحضور `links` `use` `matching` `dates` والتحقق من النتيجة المتوقعة.
        EN: Verify the nonlegacy attendance links use matching dates scenario and its expected result.
        """
        rows = frappe.db.sql(
            """
            SELECT
                attendance.name AS attendance,
                attendance.attendance_date,
                duty.name AS official_duty,
                duty.from_date,
                duty.to_date,
                duty.processing_status
            FROM `tabAttendance` attendance
            INNER JOIN `tabOfficial Duty Request` duty
                ON duty.name = attendance.custom_official_duty_request
            WHERE
                attendance.custom_official_duty_request IS NOT NULL
                AND COALESCE(duty.processing_status, '') != 'Legacy Linked'
                AND (
                    attendance.attendance_date < duty.from_date
                    OR attendance.attendance_date > duty.to_date
                )
            """,
            as_dict=True,
        )

        self.assertEqual(
            rows,
            [],
            msg={
                "message": (
                    "وجد ارتباط حضور خارج تواريخ المهمة "
                    "في طلب غير تاريخي."
                ),
                "rows": rows,
            },
        )

    def test_legacy_requests_are_not_in_pending_scheduler_states(self):
        """
        AR: اختبار سيناريو القديم `requests` `are` `not` `in` `pending` `scheduler` `states` والتحقق من النتيجة المتوقعة.
        EN: Verify the legacy requests are not in pending scheduler states scenario and its expected result.
        """
        engine_path = (
            Path(__file__).parents[1]
            / "official_duty_engine.py"
        )

        source = engine_path.read_text(
            encoding="utf-8"
        )

        function_start = source.find(
            "def process_pending_official_duties"
        )

        self.assertNotEqual(
            function_start,
            -1,
            msg="Pending processor function was not found.",
        )

        next_function = source.find(
            "\ndef ",
            function_start + 10,
        )

        if next_function == -1:
            function_source = source[function_start:]
        else:
            function_source = source[
                function_start:next_function
            ]

        self.assertNotIn(
            "STATUS_LEGACY",
            function_source,
            msg=(
                "Legacy Linked must not be included "
                "in scheduled reconciliation."
            ),
        )
