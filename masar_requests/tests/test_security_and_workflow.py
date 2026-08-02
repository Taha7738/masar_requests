"""
AR: اختبارات آلية للتحقق من منطق `test_security_and_workflow` ومنع الانحدارات البرمجية.
EN: Automated tests for `test_security_and_workflow` behavior and regression prevention.
"""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from masar_requests import hooks
from masar_requests.constants import (
    ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE,
    ATTENDANCE_ACTION_REJECT,
    ATTENDANCE_STATE_DRAFT,
    ATTENDANCE_STATE_WAITING_HR_MANAGER,
    ATTENDANCE_STATE_WAITING_SUBSTITUTE,
)
from masar_requests.hr_user_read_only import (
    READ_ONLY_DOCTYPES,
    is_hr_user_read_only,
    material_request_has_permission,
)
from masar_requests.material_request_engine import (
    allow_zero_valuation_for_internal_material_issue,
)
from masar_requests.official_duty_engine import (
    build_physical_intervals,
    interval_seconds,
    merge_intervals,
    subtract_intervals,
)
from masar_requests.overrides.shift_type import (
    DAY_NAMES,
    _duration_minutes,
    _select_shift_window,
    get_working_weekdays,
)
from masar_requests.setup_official_duty_request import (
    _hr_override_transitions,
    _system_manager_transitions,
    get_official_duty_integration_fields,
)
from masar_requests.setup_partial_leave_attendance import (
    get_partial_leave_attendance_fields,
)


class TestUnifiedRequestWorkflow(FrappeTestCase):
    """
    AR: فئة `TestUnifiedRequestWorkflow` لتنظيم منطق اختبار `security` `and` سير العمل.
    EN: Class `TestUnifiedRequestWorkflow` that organizes test security and workflow logic.
    """

    def test_material_request_hr_permission_hook_is_registered(self):
        # AR: طلب المواد يستخدم حماية HR User الخادمية.
        # EN: Material Request uses the server-side HR User permission guard.
        """
        AR: اختبار سيناريو المواد الطلب `hr` صلاحية `hook` التحقق من كون `registered` والتحقق من النتيجة المتوقعة.
        EN: Verify the material request hr permission hook is registered scenario and its expected result.
        """
        self.assertIn("Material Request", hooks.has_permission)
        self.assertEqual(
            hooks.has_permission["Material Request"],
            "masar_requests.strict_request_visibility.material_request_has_permission",
        )

    def test_stock_entry_zero_valuation_hook_is_registered(self):
        # AR: حركة الصرف المرتبطة بطلب المواد تمر عبر الحماية المقيدة.
        # EN: Linked material issues use the guarded zero-valuation hook.
        """
        AR: اختبار سيناريو المخزون `entry` `zero` `valuation` `hook` التحقق من كون `registered` والتحقق من النتيجة المتوقعة.
        EN: Verify the stock entry zero valuation hook is registered scenario and its expected result.
        """
        self.assertIn("Stock Entry", hooks.doc_events)
        self.assertEqual(
            hooks.doc_events["Stock Entry"]["before_validate"],
            "masar_requests.material_request_engine."
            "allow_zero_valuation_for_internal_material_issue",
        )

    @patch("masar_requests.material_request_engine.frappe.db.get_value")
    def test_zero_valuation_is_limited_to_linked_internal_issues(self, get_value):
        # AR: التفعيل لا يشمل إلا سطر صرف مرتبط بطلب Material Issue.
        # EN: Only a row linked to a Material Issue request is enabled.
        """
        AR: اختبار سيناريو `zero` `valuation` التحقق من كون `limited` `to` `linked` `internal` `issues` والتحقق من النتيجة المتوقعة.
        EN: Verify the zero valuation is limited to linked internal issues scenario and its expected result.
        """
        get_value.return_value = "Material Issue"
        linked_row = SimpleNamespace(
            material_request="MAT-MR-TEST-0001",
            allow_zero_valuation_rate=0,
        )
        unrelated_row = SimpleNamespace(
            material_request=None,
            allow_zero_valuation_rate=0,
        )
        doc = SimpleNamespace(
            purpose="Material Issue",
            items=[linked_row, unrelated_row],
        )

        allow_zero_valuation_for_internal_material_issue(doc)

        self.assertEqual(linked_row.allow_zero_valuation_rate, 1)
        self.assertEqual(unrelated_row.allow_zero_valuation_rate, 0)
        get_value.assert_called_once_with(
            "Material Request",
            "MAT-MR-TEST-0001",
            "material_request_type",
        )

    @patch("masar_requests.material_request_engine.frappe.db.get_value")
    def test_zero_valuation_does_not_apply_to_other_stock_entries(self, get_value):
        # AR: الاستلام والتحويل لا يتأثران بالتعديل.
        # EN: Receipts and transfers remain unaffected.
        """
        AR: اختبار سيناريو `zero` `valuation` `does` `not` تطبيق `to` `other` المخزون `entries` والتحقق من النتيجة المتوقعة.
        EN: Verify the zero valuation does not apply to other stock entries scenario and its expected result.
        """
        row = SimpleNamespace(
            material_request="MAT-MR-TEST-0001",
            allow_zero_valuation_rate=0,
        )
        doc = SimpleNamespace(
            purpose="Material Receipt",
            items=[row],
        )

        allow_zero_valuation_for_internal_material_issue(doc)

        self.assertEqual(row.allow_zero_valuation_rate, 0)
        get_value.assert_not_called()

    def test_native_attendance_request_has_no_custom_hooks(self):
        # AR: Attendance Request عاد إلى HRMS دون JS/صلاحية/Controller/Events من التطبيق.
        # EN: Attendance Request is restored to native HRMS without app hooks.
        """
        AR: اختبار سيناريو `native` الحضور الطلب التحقق من وجود `no` `custom` `hooks` والتحقق من النتيجة المتوقعة.
        EN: Verify the native attendance request has no custom hooks scenario and its expected result.
        """
        self.assertNotIn("Attendance Request", hooks.doctype_js)
        self.assertNotIn("Attendance Request", hooks.permission_query_conditions)
        self.assertNotIn("Attendance Request", hooks.has_permission)
        self.assertNotIn("Attendance Request", hooks.override_doctype_class)
        self.assertNotIn("Attendance Request", hooks.doc_events)

    def test_official_duty_permission_hooks_are_registered(self):
        # AR: الصلاحيات المخصصة نُقلت إلى المستند المستقل فقط.
        # EN: Custom permissions are attached only to the independent DocType.
        """
        AR: اختبار سيناريو الرسمية المهمة صلاحية `hooks` `are` `registered` والتحقق من النتيجة المتوقعة.
        EN: Verify the official duty permission hooks are registered scenario and its expected result.
        """
        self.assertEqual(
            hooks.permission_query_conditions["Official Duty Request"],
            "masar_requests.strict_request_visibility.official_duty_request_query",
        )
        self.assertEqual(
            hooks.has_permission["Official Duty Request"],
            "masar_requests.strict_request_visibility.official_duty_request_has_permission",
        )
        self.assertIn("Official Duty Request", READ_ONLY_DOCTYPES)
        self.assertNotIn("Attendance Request", READ_ONLY_DOCTYPES)

    def test_salary_slip_precise_partial_leave_override_is_registered(self):
        # AR: Payroll يقرأ كسر ربع اليوم والساعات بدقة.
        # EN: Payroll uses the exact quarter-day/hourly fraction override.
        """
        AR: اختبار سيناريو `salary` `slip` `precise` الجزئي الإجازة `override` التحقق من كون `registered` والتحقق من النتيجة المتوقعة.
        EN: Verify the salary slip precise partial leave override is registered scenario and its expected result.
        """
        self.assertEqual(
            hooks.override_doctype_class["Salary Slip"],
            "masar_requests.salary_slip_partial_leave.CustomSalarySlip",
        )

    def test_official_duty_report_is_required_at_creation(self):
        # AR: التقرير مطلوب في المستند الجديد وليس في Attendance Request.
        # EN: The report is required on the new DocType, not Attendance Request.
        """
        AR: اختبار سيناريو الرسمية المهمة التقرير التحقق من كون `required` `at` `creation` والتحقق من النتيجة المتوقعة.
        EN: Verify the official duty report is required at creation scenario and its expected result.
        """
        import json
        from pathlib import Path

        path = (
            Path(__file__).parents[1]
            / "masar_requests"
            / "doctype"
            / "official_duty_request"
            / "official_duty_request.json"
        )
        fields = {
            field["fieldname"]: field
            for field in json.loads(path.read_text(encoding="utf-8"))["fields"]
        }
        self.assertEqual(fields["custom_achievement_report"]["fieldtype"], "Text Editor")
        self.assertEqual(fields["custom_achievement_report"]["reqd"], 1)
        self.assertIn("custom_achievement_report_attachment", fields)

    def test_manager_can_approve_while_substitute_is_pending(self):
        # AR: مدير النظام يستطيع تمرير اعتماد المدير أثناء انتظار البديل.
        # EN: System Manager transitions preserve manager approval during substitute wait.
        """
        AR: اختبار سيناريو المدير التحقق من إمكانية `approve` `while` `substitute` التحقق من كون `pending` والتحقق من النتيجة المتوقعة.
        EN: Verify the manager can approve while substitute is pending scenario and its expected result.
        """
        transitions = _system_manager_transitions()
        self.assertTrue(
            any(
                row["state"] == ATTENDANCE_STATE_WAITING_SUBSTITUTE
                and row["action"] == ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE
                and row["next_state"] == ATTENDANCE_STATE_WAITING_HR_MANAGER
                for row in transitions
            )
        )

    def test_hr_manager_can_finally_decide_from_active_stages(self):
        # AR: مدير الموارد البشرية يحسم الطلب من أي مرحلة نشطة.
        # EN: HR Manager can finally decide from every active stage.
        """
        AR: اختبار سيناريو `hr` المدير التحقق من إمكانية `finally` `decide` `from` النشط `stages` والتحقق من النتيجة المتوقعة.
        EN: Verify the hr manager can finally decide from active stages scenario and its expected result.
        """
        transitions = _hr_override_transitions()
        covered = {(row["state"], row["action"]) for row in transitions}
        self.assertIn((ATTENDANCE_STATE_DRAFT, ATTENDANCE_ACTION_REJECT), covered)
        self.assertIn((ATTENDANCE_STATE_WAITING_SUBSTITUTE, ATTENDANCE_ACTION_REJECT), covered)

    def test_official_duty_fields_are_technical_only_on_attendance_request(self):
        # AR: Attendance Request يحمل رابطاً مخفياً واحداً فقط لمنع التكرار.
        # EN: Attendance Request gets only one hidden technical link.
        """
        AR: اختبار سيناريو الرسمية المهمة الحقول `are` `technical` `only` معالجة حدث الحضور الطلب والتحقق من النتيجة المتوقعة.
        EN: Verify the official duty fields are technical only on attendance request scenario and its expected result.
        """
        fields = get_official_duty_integration_fields()["Attendance Request"]
        self.assertEqual([field["fieldname"] for field in fields], ["custom_official_duty_request"])
        self.assertEqual(fields[0]["hidden"], 1)
        self.assertEqual(fields[0]["read_only"], 1)

    def test_partial_leave_attendance_fields_include_exact_fraction(self):
        # AR: سجل الحضور يحفظ الساعات وكسر اليوم ومصدر الطلب.
        # EN: Attendance stores hours, exact fraction, and source request.
        """
        AR: اختبار سيناريو الجزئي الإجازة الحضور الحقول `include` `exact` `fraction` والتحقق من النتيجة المتوقعة.
        EN: Verify the partial leave attendance fields include exact fraction scenario and its expected result.
        """
        fields = {
            field["fieldname"]: field
            for field in get_partial_leave_attendance_fields()["Attendance"]
        }
        self.assertIn("custom_partial_leave_application", fields)
        self.assertIn("custom_partial_leave_hours", fields)
        self.assertIn("custom_partial_leave_day_fraction", fields)
        self.assertEqual(fields["custom_partial_leave_day_fraction"]["precision"], 4)

    def test_partial_leave_application_tracks_deferred_attendance_processing(self):
        # AR: الطلب يعرض حالة انتظار نهاية الوردية ورابط سجل الحضور الناتج.
        # EN: The request exposes shift-wait status and the resulting Attendance link.
        """
        AR: اختبار سيناريو الجزئي الإجازة `application` `tracks` `deferred` الحضور `processing` والتحقق من النتيجة المتوقعة.
        EN: Verify the partial leave application tracks deferred attendance processing scenario and its expected result.
        """
        fields = {
            field["fieldname"]: field
            for field in get_partial_leave_attendance_fields()["Leave Application"]
        }
        self.assertIn("custom_partial_attendance_status", fields)
        self.assertIn("custom_partial_attendance", fields)
        self.assertIn("Waiting for Shift End", fields["custom_partial_attendance_status"]["options"])
        self.assertIn("Manual Review", fields["custom_partial_attendance_status"]["options"])
        self.assertEqual(fields["custom_partial_attendance"]["options"], "Attendance")

        attendance_fields = {
            field["fieldname"]: field
            for field in get_partial_leave_attendance_fields()["Attendance"]
        }
        self.assertIn(
            "Manual Review",
            attendance_fields["custom_partial_leave_reconciliation_status"]["options"],
        )

    def test_hourly_scheduler_reconciles_duties_and_partial_leave(self):
        # AR: كلا النوعين ينتظر نهاية الوردية دون تعطيل Auto Attendance.
        # EN: Both workflows wait for shift completion without blocking Auto Attendance.
        """
        AR: اختبار سيناريو `hourly` `scheduler` `reconciles` `duties` `and` الجزئي الإجازة والتحقق من النتيجة المتوقعة.
        EN: Verify the hourly scheduler reconciles duties and partial leave scenario and its expected result.
        """
        hourly = hooks.scheduler_events["hourly"]
        self.assertIn(
            "masar_requests.official_duty_engine.process_pending_official_duties",
            hourly,
        )
        self.assertIn(
            "masar_requests.leave_application_partial_leave."
            "process_pending_partial_leave_attendance",
            hourly,
        )

    def test_interval_merge_prevents_double_counting(self):
        # AR: تداخل البصمة مع المهمة لا يضاعف الساعات.
        # EN: Overlap between physical time and duty is never double-counted.
        """
        AR: اختبار سيناريو `interval` `merge` `prevents` `double` `counting` والتحقق من النتيجة المتوقعة.
        EN: Verify the interval merge prevents double counting scenario and its expected result.
        """
        start = datetime(2026, 7, 30, 8, 0)
        end = datetime(2026, 7, 30, 16, 0)
        duty_start = datetime(2026, 7, 30, 11, 0)
        duty_end = datetime(2026, 7, 30, 13, 0)
        merged = merge_intervals([(start, end), (duty_start, duty_end)])
        physical_only = subtract_intervals([(start, end)], [(duty_start, duty_end)])
        self.assertEqual(interval_seconds(merged), 8 * 3600)
        self.assertEqual(interval_seconds(physical_only), 6 * 3600)

    def test_single_in_is_closed_at_duty_start_when_duty_covers_shift_end(self):
        # AR: بصمة دخول واحدة + مهمة حتى نهاية الدوام تفسر غياب بصمة الانصراف.
        # EN: One IN plus end-of-shift duty explains the missing checkout.
        """
        AR: اختبار سيناريو `single` `in` التحقق من كون `closed` `at` المهمة `start` `when` المهمة `covers` الوردية `end` والتحقق من النتيجة المتوقعة.
        EN: Verify the single in is closed at duty start when duty covers shift end scenario and its expected result.
        """
        shift = SimpleNamespace(
            start=datetime(2026, 7, 30, 8, 0),
            end=datetime(2026, 7, 30, 16, 0),
        )
        logs = [SimpleNamespace(time=datetime(2026, 7, 30, 8, 0), log_type="IN")]
        intervals, explained = build_physical_intervals(
            logs,
            shift,
            (datetime(2026, 7, 30, 14, 0), datetime(2026, 7, 30, 16, 0)),
        )
        self.assertTrue(explained)
        self.assertEqual(interval_seconds(intervals), 6 * 3600)

    def test_single_in_before_mid_shift_duty_credits_only_pre_duty_time(self):
        # AR: الطلب يغلق الحضور عند بداية المهمة، لكن ما بعد عودتها يبقى غير مثبت.
        # EN: Duty start closes pre-duty presence, while the post-duty segment stays unproven.
        """
        AR: اختبار سيناريو `single` `in` معالجة ما قبل `mid` الوردية المهمة `credits` `only` `pre` المهمة الوقت والتحقق من النتيجة المتوقعة.
        EN: Verify the single in before mid shift duty credits only pre duty time scenario and its expected result.
        """
        shift = SimpleNamespace(
            start=datetime(2026, 7, 30, 8, 0),
            end=datetime(2026, 7, 30, 16, 0),
        )
        logs = [SimpleNamespace(time=datetime(2026, 7, 30, 8, 0), log_type="IN")]
        duty = (datetime(2026, 7, 30, 11, 0), datetime(2026, 7, 30, 13, 0))
        physical, explained = build_physical_intervals(logs, shift, duty)
        credited = merge_intervals([*physical, duty])
        self.assertFalse(explained)
        self.assertEqual(interval_seconds(physical), 3 * 3600)
        self.assertEqual(interval_seconds(credited), 5 * 3600)

    def test_duty_from_shift_start_uses_first_arrival_and_final_checkout(self):
        # AR: مهمة بداية الدوام + IN عند الوصول + OUT النهائي تغطي اليوم بلا بصمة مهمة خاصة.
        # EN: Start-of-shift duty plus arrival IN/final OUT covers the day without special duty punches.
        """
        AR: اختبار سيناريو المهمة `from` الوردية `start` `uses` `first` `arrival` `and` `final` `checkout` والتحقق من النتيجة المتوقعة.
        EN: Verify the duty from shift start uses first arrival and final checkout scenario and its expected result.
        """
        shift = SimpleNamespace(
            start=datetime(2026, 7, 30, 8, 0),
            end=datetime(2026, 7, 30, 16, 0),
        )
        logs = [
            SimpleNamespace(time=datetime(2026, 7, 30, 12, 0), log_type="IN"),
            SimpleNamespace(time=datetime(2026, 7, 30, 16, 0), log_type="OUT"),
        ]
        physical, explained = build_physical_intervals(
            logs,
            shift,
            (datetime(2026, 7, 30, 8, 0), datetime(2026, 7, 30, 12, 0)),
        )
        credited = merge_intervals(
            [*physical, (datetime(2026, 7, 30, 8, 0), datetime(2026, 7, 30, 12, 0))]
        )
        self.assertFalse(explained)
        self.assertEqual(interval_seconds(physical), 4 * 3600)
        self.assertEqual(interval_seconds(credited), 8 * 3600)

    def test_mid_shift_duty_uses_normal_first_and_last_checkins_without_double_count(self):
        # AR: بصمتا بداية/نهاية الدوام تكفيان، وتطرح ساعات المهمة من الحضور الفعلي.
        # EN: Normal first/final checkins are sufficient and duty time is removed from physical hours.
        """
        AR: اختبار سيناريو `mid` الوردية المهمة `uses` `normal` `first` `and` `last` `checkins` `without` `double` `count` والتحقق من النتيجة المتوقعة.
        EN: Verify the mid shift duty uses normal first and last checkins without double count scenario and its expected result.
        """
        shift = SimpleNamespace(
            start=datetime(2026, 7, 30, 8, 0),
            end=datetime(2026, 7, 30, 16, 0),
        )
        logs = [
            SimpleNamespace(time=datetime(2026, 7, 30, 8, 0), log_type="IN"),
            SimpleNamespace(time=datetime(2026, 7, 30, 16, 0), log_type="OUT"),
        ]
        duty = (datetime(2026, 7, 30, 11, 0), datetime(2026, 7, 30, 13, 0))
        physical, explained = build_physical_intervals(logs, shift, duty)
        physical_only = subtract_intervals(physical, [duty])
        credited = merge_intervals([*physical, duty])
        self.assertFalse(explained)
        self.assertEqual(interval_seconds(physical_only), 6 * 3600)
        self.assertEqual(interval_seconds(credited), 8 * 3600)

    def test_alternating_first_last_matches_shift_configuration(self):
        # AR: وضع أول بصمة/آخر بصمة يحتسب كامل النطاق حتى مع وجود بصمات وسطية.
        # EN: First/last mode credits the full span even when middle logs exist.
        """
        AR: اختبار سيناريو `alternating` `first` `last` `matches` الوردية `configuration` والتحقق من النتيجة المتوقعة.
        EN: Verify the alternating first last matches shift configuration scenario and its expected result.
        """
        shift = SimpleNamespace(
            start=datetime(2026, 7, 30, 8, 0),
            end=datetime(2026, 7, 30, 16, 0),
            doc={
                "determine_check_in_and_check_out": (
                    "Alternating entries as IN and OUT during the same shift"
                ),
                "working_hours_calculation_based_on": "First Check-in and Last Check-out",
            },
        )
        logs = [
            {"time": datetime(2026, 7, 30, 8, 0), "log_type": ""},
            {"time": datetime(2026, 7, 30, 10, 0), "log_type": ""},
            {"time": datetime(2026, 7, 30, 11, 0), "log_type": ""},
            {"time": datetime(2026, 7, 30, 16, 0), "log_type": ""},
        ]
        physical, _ = build_physical_intervals(logs, shift, None)
        self.assertEqual(interval_seconds(physical), 8 * 3600)

    def test_alternating_every_valid_matches_shift_configuration(self):
        # AR: وضع كل زوج صحيح يحتسب 08-10 و11-16 فقط.
        # EN: Every-valid mode credits only the 08-10 and 11-16 pairs.
        """
        AR: اختبار سيناريو `alternating` `every` `valid` `matches` الوردية `configuration` والتحقق من النتيجة المتوقعة.
        EN: Verify the alternating every valid matches shift configuration scenario and its expected result.
        """
        shift = SimpleNamespace(
            start=datetime(2026, 7, 30, 8, 0),
            end=datetime(2026, 7, 30, 16, 0),
            doc={
                "determine_check_in_and_check_out": (
                    "Alternating entries as IN and OUT during the same shift"
                ),
                "working_hours_calculation_based_on": (
                    "Every Valid Check-in and Check-out"
                ),
            },
        )
        logs = [
            {"time": datetime(2026, 7, 30, 8, 0), "log_type": ""},
            {"time": datetime(2026, 7, 30, 10, 0), "log_type": ""},
            {"time": datetime(2026, 7, 30, 11, 0), "log_type": ""},
            {"time": datetime(2026, 7, 30, 16, 0), "log_type": ""},
        ]
        physical, _ = build_physical_intervals(logs, shift, None)
        self.assertEqual(interval_seconds(physical), 7 * 3600)

    def test_strict_first_last_matches_shift_configuration(self):
        # AR: الوضع الصارم يستخدم أول IN وآخر OUT كما في HRMS القياسي.
        # EN: Strict first/last mode uses the first IN and final OUT like native HRMS.
        """
        AR: اختبار سيناريو الصارم `first` `last` `matches` الوردية `configuration` والتحقق من النتيجة المتوقعة.
        EN: Verify the strict first last matches shift configuration scenario and its expected result.
        """
        shift = SimpleNamespace(
            start=datetime(2026, 7, 30, 8, 0),
            end=datetime(2026, 7, 30, 16, 0),
            doc={
                "determine_check_in_and_check_out": (
                    "Strictly based on Log Type in Employee Checkin"
                ),
                "working_hours_calculation_based_on": "First Check-in and Last Check-out",
            },
        )
        logs = [
            {"time": datetime(2026, 7, 30, 8, 0), "log_type": "IN"},
            {"time": datetime(2026, 7, 30, 10, 0), "log_type": "OUT"},
            {"time": datetime(2026, 7, 30, 11, 0), "log_type": "IN"},
            {"time": datetime(2026, 7, 30, 16, 0), "log_type": "OUT"},
        ]
        physical, _ = build_physical_intervals(logs, shift, None)
        self.assertEqual(interval_seconds(physical), 8 * 3600)

    def test_attendance_audit_fields_preserve_original_state(self):
        # AR: حقول الحالة السابقة موجودة لضمان سلامة الإعادة والإلغاء.
        # EN: Previous-state fields exist so retries and cancellation remain safe.
        """
        AR: اختبار سيناريو الحضور تدقيق الحقول `preserve` `original` الحالة والتحقق من النتيجة المتوقعة.
        EN: Verify the attendance audit fields preserve original state scenario and its expected result.
        """
        fields = {
            field["fieldname"]: field
            for field in get_official_duty_integration_fields()["Attendance"]
        }
        for fieldname in (
            "custom_official_duty_previous_status",
            "custom_official_duty_previous_half_day_status",
            "custom_official_duty_previous_late_entry",
            "custom_official_duty_previous_early_exit",
        ):
            self.assertIn(fieldname, fields)
            self.assertEqual(fields[fieldname]["hidden"], 1)

    @patch("masar_requests.hr_user_read_only.frappe.get_roles")
    def test_hr_user_is_read_print_only(self, get_roles):
        # AR: HR User لا يكتسب تعديل الطلب حتى لو حمل Employee.
        # EN: HR User stays read/print-only even when also assigned Employee.
        """
        AR: اختبار سيناريو `hr` المستخدم التحقق من كون القراءة طباعة `only` والتحقق من النتيجة المتوقعة.
        EN: Verify the hr user is read print only scenario and its expected result.
        """
        get_roles.return_value = ["HR User", "Employee"]
        self.assertTrue(is_hr_user_read_only("hr.user@example.com"))
        self.assertTrue(material_request_has_permission(None, "read", "hr.user@example.com"))
        self.assertTrue(material_request_has_permission(None, "print", "hr.user@example.com"))
        self.assertFalse(material_request_has_permission(None, "write", "hr.user@example.com"))
        self.assertFalse(material_request_has_permission(None, "submit", "hr.user@example.com"))


    def test_variable_shift_hooks_are_registered(self):
        # AR: توليد الجدول والتحقق ومسح الكاش مرتبطة بـ Shift Type.
        # EN: Generation, validation, and cache clearing are hooked to Shift Type.
        """
        AR: اختبار سيناريو `variable` الوردية `hooks` `are` `registered` والتحقق من النتيجة المتوقعة.
        EN: Verify the variable shift hooks are registered scenario and its expected result.
        """
        events = hooks.doc_events["Shift Type"]
        self.assertEqual(
            events["before_validate"],
            "masar_requests.overrides.shift_type.generate_shift_times",
        )
        self.assertEqual(
            events["validate"],
            "masar_requests.overrides.shift_type.validate_shift_times",
        )
        self.assertEqual(
            events["on_update"],
            "masar_requests.overrides.shift_type.clear_shift_schedule_cache",
        )

    def test_shift_duration_supports_day_and_night_shifts(self):
        # AR: 08-16 ثماني ساعات، و22-06 وردية ليلية ثماني ساعات.
        # EN: 08-16 is eight hours and 22-06 is an eight-hour night shift.
        """
        AR: اختبار سيناريو الوردية `duration` `supports` `day` `and` `night` `shifts` والتحقق من النتيجة المتوقعة.
        EN: Verify the shift duration supports day and night shifts scenario and its expected result.
        """
        self.assertEqual(_duration_minutes("08:00:00", "16:00:00"), 480)
        self.assertEqual(_duration_minutes("22:00:00", "06:00:00"), 480)

    def test_shift_candidate_prefers_window_containing_timestamp(self):
        # AR: بصمة بعد منتصف الليل ترتبط بالوردية الليلية التي بدأت في اليوم السابق.
        # EN: A post-midnight checkin resolves to the night shift anchored on the prior day.
        """
        AR: اختبار سيناريو الوردية `candidate` `prefers` `window` `containing` `timestamp` والتحقق من النتيجة المتوقعة.
        EN: Verify the shift candidate prefers window containing timestamp scenario and its expected result.
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
        self.assertEqual(selected.anchor_date, date(2026, 7, 30))

    def test_variable_shift_day_contract_defines_all_weekdays(self):
        # AR: أسماء الأيام القياسية ثابتة، ثم تُستبعد منها العطلات الأسبوعية فقط.
        # EN: Canonical day names stay fixed before recurring weekly offs are excluded.
        """
        AR: اختبار سيناريو `variable` الوردية `day` `contract` `defines` `all` `weekdays` والتحقق من النتيجة المتوقعة.
        EN: Verify the variable shift day contract defines all weekdays scenario and its expected result.
        """
        self.assertEqual(len(DAY_NAMES), 7)
        self.assertEqual(set(DAY_NAMES), {
            "Sunday", "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday",
        })

    @patch(
        "masar_requests.overrides.shift_type.get_weekly_off_days",
        return_value={"Friday", "Saturday"},
    )
    def test_variable_shift_excludes_recurring_weekly_off_days(self, _weekly_off_days):
        # AR: جدول الوردية يعرض أيام العمل فقط ولا يجلب الجمعة والسبت في المثال.
        # EN: The variable table includes working days only in this Fri/Sat-off example.
        """
        AR: اختبار سيناريو `variable` الوردية `excludes` `recurring` `weekly` `off` `days` والتحقق من النتيجة المتوقعة.
        EN: Verify the variable shift excludes recurring weekly off days scenario and its expected result.
        """
        self.assertEqual(
            get_working_weekdays("TEST-HOLIDAY-LIST"),
            ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"),
        )

    def test_preflight_requires_working_days_not_weekly_off_days(self):
        # AR: فحص الجاهزية يستخدم أيام العمل بعد استبعاد العطلات الأسبوعية.
        # EN: Preflight validates working weekdays after weekly-off exclusion.
        """
        AR: اختبار سيناريو `preflight` `requires` `working` `days` `not` `weekly` `off` `days` والتحقق من النتيجة المتوقعة.
        EN: Verify the preflight requires working days not weekly off days scenario and its expected result.
        """
        from pathlib import Path

        path = Path(__file__).parents[1] / "preflight.py"
        content = path.read_text(encoding="utf-8")
        self.assertIn("get_working_weekdays", content)
        self.assertIn(
            'required_days = get_working_weekdays(shift_doc.get("holiday_list"))',
            content,
        )

    def test_v21_2_weekly_off_patch_is_registered(self):
        # AR: Patch V21.2 مسجل لتنظيف صفوف أيام العطلة الأسبوعية.
        # EN: V21.2 migration is registered to remove recurring weekly-off rows.
        """
        AR: اختبار سيناريو `v21` `2` `weekly` `off` تصحيح التحقق من كون `registered` والتحقق من النتيجة المتوقعة.
        EN: Verify the v21 2 weekly off patch is registered scenario and its expected result.
        """
        from pathlib import Path

        patches = (Path(__file__).parents[1] / "patches.txt").read_text(encoding="utf-8")
        self.assertIn(
            "masar_requests.patches.apply_variable_shift_holiday_exclusions_v21_2",
            patches,
        )

    def test_shift_type_script_syncs_holiday_list_working_days(self):
        # AR: واجهة Shift Type تستدعي الخادم عند تغيير قائمة العطلات.
        # EN: Shift Type UI resolves working weekdays when Holiday List changes.
        """
        AR: اختبار سيناريو الوردية `type` `script` `syncs` العطلة `list` `working` `days` والتحقق من النتيجة المتوقعة.
        EN: Verify the shift type script syncs holiday list working days scenario and its expected result.
        """
        from pathlib import Path

        path = Path(__file__).parents[1] / "public" / "js" / "shift_type.js"
        content = path.read_text(encoding="utf-8")
        self.assertIn("async holiday_list(frm)", content)
        self.assertIn("get_variable_shift_working_days", content)

    def test_v21_variable_shift_patch_is_registered(self):
        # AR: Patch V21 مسجل في patches.txt لتنفيذ الترقية مرة واحدة.
        # EN: The V21 migration is registered once through patches.txt.
        """
        AR: اختبار سيناريو `v21` `variable` الوردية تصحيح التحقق من كون `registered` والتحقق من النتيجة المتوقعة.
        EN: Verify the v21 variable shift patch is registered scenario and its expected result.
        """
        from pathlib import Path

        patches = (Path(__file__).parents[1] / "patches.txt").read_text(encoding="utf-8")
        self.assertIn(
            "masar_requests.patches.apply_variable_shift_times_v21",
            patches,
        )

    def test_variable_shift_custom_fields_are_complete(self):
        # AR: التفعيل وتاريخ النفاذ والجدول موجودة ضمن إعداد Shift Type.
        # EN: Enable flag, effective date, and weekday table are part of Shift Type setup.
        """
        AR: اختبار سيناريو `variable` الوردية `custom` الحقول `are` `complete` والتحقق من النتيجة المتوقعة.
        EN: Verify the variable shift custom fields are complete scenario and its expected result.
        """
        from masar_requests.setup_leave_and_shift import get_leave_and_shift_custom_fields

        fields = {
            field["fieldname"]: field
            for field in get_leave_and_shift_custom_fields()["Shift Type"]
        }
        self.assertIn("custom_enable_variable_shift_times", fields)
        self.assertIn("custom_shift_times_effective_from", fields)
        self.assertEqual(fields["custom_shift_times"]["options"], "Shift Time Table")


    def test_material_request_script_is_not_leave_script(self):
        # AR: منع رجوع خطأ V20 الذي حمّل كود Leave Application داخل Material Request.
        # EN: Prevent regression where V20 loaded Leave Application code as Material Request JS.
        """
        AR: اختبار سيناريو المواد الطلب `script` التحقق من كون `not` الإجازة `script` والتحقق من النتيجة المتوقعة.
        EN: Verify the material request script is not leave script scenario and its expected result.
        """
        from pathlib import Path

        path = Path(__file__).parents[1] / "public" / "js" / "material_request.js"
        content = path.read_text(encoding="utf-8")
        self.assertIn("frappe.ui.form.on('Material Request'", content)
        self.assertNotIn('frappe.ui.form.on("Leave Application"', content)
