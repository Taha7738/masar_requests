"""
AR: تنفيذ وظائف تطبيق مسار ضمن الوحدة `hooks`.
EN: Masar application functionality implemented by the `hooks` module.
"""

# AR: تعريف اسم التطبيق برمجياً / EN: Define the app name programmatically
app_name = "masar_requests"

# AR: تعريف العنوان الذي يظهر للمستخدمين / EN: Define the title shown to users
app_title = "Masar Requests"

# AR: تعريف اسم الناشر أو الشركة المبرمجة / EN: Define the publisher or development company name
app_publisher = "AlphaCode"

# AR: وصف التطبيق ووظيفته في النظام / EN: App description and its function in the system
app_description = "Masar Requests streamlines leave and material-request workflows for Masar."

# AR: البريد الإلكتروني للتواصل والدعم / EN: Contact and support email
app_email = "dev@alpha-code.net"

# AR: نوع رخصة استخدام التطبيق / EN: License type of the application
app_license = "mit"


# AR: ملاحظة صيانة مهمة:
# لا تُعدّل أسماء مسارات الدوال هنا إلا بعد التأكد من وجود الدالة في الملف الهدف.
#
# EN: Maintenance note:
# Do not change dotted function paths here unless the target function exists.

# AR:
# تم عمداً عدم إضافة صلاحية عامة على Employee
# حتى لا تنفتح جميع سجلات الموظفين أمام المستخدمين.
#
# EN:
# No global Employee permission hook is added,
# to avoid exposing all Employee records.


# ======================================================
# AR: قسم الأصول وملفات الواجهة
# EN: Assets and frontend files
# ======================================================

# AR:
# قائمة ملفات JavaScript العامة التي يتم تحميلها في النظام.
# القائمة فارغة لأن ملفاتنا مرتبطة مباشرة بنماذج محددة عبر doctype_js.
#
# EN:
# Global JavaScript files included in Desk.
# This list is empty because our scripts are attached to specific DocTypes.
app_include_js = []


# AR:
# ربط كل ملف JavaScript بالنموذج الذي يعمل عليه.
#
# EN:
# Attach each JavaScript file to its related DocType.
doctype_js = {
    # AR: تخصيص واجهة طلب الإجازة
    # EN: Customize the Leave Application form
    "Leave Application": "public/js/masar_requests.js",

    # AR: تخصيص نموذج نوع الوردية
    # EN: Customize the Shift Type form
    "Shift Type": "public/js/shift_type.js",

    # AR: تخصيص نموذج طلب المواد
    # EN: Customize the Material Request form
    "Material Request": "public/js/material_request.js",

    # AR:
    # Official Duty Request يحمّل ملفه القياسي الموجود داخل مجلد DocType،
    # لذلك لا يحتاج doctype_js. Attendance Request متروك كلياً لـ HRMS.
    #
    # EN:
    # Official Duty Request loads its standard DocType JavaScript file.
    # Attendance Request is intentionally left entirely to native HRMS.
}




# ======================================================
# AR: قسم التثبيت والتحديث
# EN: Installation and migration section
# ======================================================

# AR:
# تشغيل إعداد التثبيت الأولي الموجود في install.py.
#
# EN:
# Run the initial installation setup defined in install.py.
after_install = "masar_requests.install.after_install"


# AR:
# بعد كل migrate يتم تشغيل تنظيف الكاش من install.py، بينما تُطبّق
# تغييرات قاعدة البيانات مرة واحدة عبر patches.txt.
#
# EN:
# After every migration, install.py clears the relevant caches, while
# database changes are applied once through patches.txt.
after_migrate = "masar_requests.install.after_migrate"


# AR:
# تعمل هذه الدالة قبل إزالة التطبيق.
#
# EN:
# This function runs before uninstalling the app.
before_uninstall = "masar_requests.install.before_uninstall"


# ======================================================
# AR: شروط ظهور السجلات في القوائم
# EN: List-level permission query conditions
# ======================================================

# AR:
# تتحكم هذه الدالة في السجلات التي تظهر للمستخدم
# في قائمة Leave Application والتقارير والاستعلامات.
#
# EN:
# This function controls which Leave Application records
# appear in lists, reports, and database queries.
# ======================================================
# EN: List-level permission query conditions
# ======================================================
permission_query_conditions = {
    "Leave Application": (
        "masar_requests.leave_application_permissions."
        "leave_application_query"
    ),
    "Official Duty Request": (
        "masar_requests.official_duty_request_permissions."
        "official_duty_request_query"
    ),
}


# ======================================================
# AR: صلاحيات المستند الفردي
# EN: Individual document permissions
# ======================================================

# AR:
# بعد أن يحدد permission_query_conditions السجلات الظاهرة في القائمة،
# تقوم هذه الدالة بالتحقق من صلاحية فتح أو تعديل أو طباعة كل مستند.
#
# EN:
# After permission_query_conditions filters the list,
# this function validates read, write, print, delete, and other operations.
# ======================================================
# EN: Individual document permissions
# ======================================================
has_permission = {
    "Leave Application": (
        "masar_requests.leave_application_permissions."
        "leave_application_has_permission"
    ),
    "Official Duty Request": (
        "masar_requests.official_duty_request_permissions."
        "official_duty_request_has_permission"
    ),
    # AR: HR User يفتح ويطبع طلبات المواد دون تعديل أو إجراء Workflow.
    # EN: HR User may open and print Material Requests without editing/workflow actions.
    "Material Request": (
        "masar_requests.hr_user_read_only."
        "material_request_has_permission"
    ),
}


# ======================================================
# AR: استبدال فئة النموذج القياسية
# EN: Override the standard DocType class
# ======================================================

# AR:
# استبدال كلاس Leave Application القياسي بكلاس مخصص
# يدعم نصف يوم وربع يوم والإجازة بالساعات.
#
# EN:
# Replace the standard Leave Application class with a custom class
# supporting half-day, quarter-day, and hourly leave.
override_doctype_class = {
    "Leave Application": (
        "masar_requests.leave_application_partial_leave."
        "CustomLeaveApplication"
    ),

    # AR: تصحيح كسر ربع اليوم والإجازة بالساعات في Payroll مع إبقاء بقية المنطق قياسياً.
    # EN: Correct quarter-day/hourly fractions in Payroll while preserving native logic.
    "Salary Slip": (
        "masar_requests.salary_slip_partial_leave."
        "CustomSalarySlip"
    ),
}


# ======================================================
# AR: أحداث المستندات
# EN: Document events
# ======================================================

doc_events = {
    "Leave Application": {
        # AR:
        # يعمل قبل حفظ الطلب للتحقق من الصلاحيات
        # وتعبئة بيانات البديل والمسؤول والسكرتير.
        #
        # EN:
        # Runs before save to validate permissions
        # and populate substitute, manager, and secretary data.
        "validate": (
            "masar_requests.leave_application_permissions."
            "validate_leave_application"
        ),

        # AR:
        # بعد إنشاء الطلب لأول مرة تتم مشاركة المستند
        # مع الأطراف المرتبطة به.
        #
        # EN:
        # After initial insertion, share the document
        # with its related participants.
        "after_insert": (
            "masar_requests.leave_application_permissions."
            "sync_leave_application_shares"
        ),

        # AR:
        # بعد كل تحديث تتم إعادة مزامنة المشاركات
        # وإرسال إشعارات سير العمل.
        #
        # EN:
        # After each update, re-sync shares
        # and send workflow notifications.
        "on_update": (
            "masar_requests.leave_application_permissions."
            "on_update_leave_application"
        ),

        # AR:
        # نقطة مخصصة لتنظيف المشاركات عند حذف الطلب.
        #
        # EN:
        # Hook point for cleaning shares when deleting a request.
        "on_trash": (
            "masar_requests.leave_application_permissions."
            "remove_leave_application_shares"
        ),
    },

    "Shift Type": {
        # AR: استكمال أيام الأسبوع قبل التحقق دون مسح تعديلات المستخدم.
        # EN: Fill missing weekdays before validation without erasing user edits.
        "before_validate": (
            "masar_requests.overrides.shift_type."
            "generate_shift_times"
        ),
        # AR: التحقق من الأيام والأوقات والوردية الليلية والبصمات غير المعالجة.
        # EN: Validate weekdays, times, overnight shifts, and unprocessed checkins.
        "validate": (
            "masar_requests.overrides.shift_type."
            "validate_shift_times"
        ),
        # AR: مسح كاش الوردية بعد التحديث لتوحيد النتائج في كل المستندات.
        # EN: Clear Shift Type cache after update for consistent cross-document results.
        "on_update": (
            "masar_requests.overrides.shift_type."
            "clear_shift_schedule_cache"
        ),
    },

    "Employee": {
        # AR:
        # عند تغيير المستخدم أو المدير أو السكرتير، تعاد مزامنة مشاركات
        # المعاملات في الخلفية بعد نجاح الحفظ.
        #
        # EN:
        # When the user, manager, or secretary changes, request shares are
        # re-synced in the background after the save succeeds.
        "on_update": (
            "masar_requests.install."
            "schedule_workflow_share_resync_after_employee_change"
        ),
    },

    "Stock Entry": {
        # AR:
        # طلب الصرف الداخلي لا يطلب من الموظف إدخال سعر. عند إنشاء
        # Stock Entry من Material Request يسمح الخادم بالقيمة الصفرية
        # فقط عند عدم وجود تقييم سابق للصنف.
        #
        # EN:
        # Internal issues do not require requester-entered prices. When a
        # Stock Entry is mapped from a Material Request, zero valuation is
        # allowed only when no prior item valuation exists.
        "before_validate": (
            "masar_requests.material_request_engine."
            "allow_zero_valuation_for_internal_material_issue"
        ),
    },

    "Material Request": {
        # AR: قواعد الحماية والانشطار تعمل في Python أصلي قابل للاختبار.
        # EN: Protection and splitting rules run in testable native Python.
        "before_save": (
            "masar_requests.material_request_engine."
            "before_save_material_request"
        ),
        "after_insert": (
            "masar_requests.material_request_sharing."
            "sync_material_request_shares"
        ),
        "on_update": (
            "masar_requests.material_request_sharing."
            "sync_material_request_shares"
        ),
        "on_submit": (
            "masar_requests.material_request_sharing."
            "sync_material_request_shares"
        ),
        "on_update_after_submit": (
            "masar_requests.material_request_sharing."
            "sync_material_request_shares"
        ),
        "on_cancel": (
            "masar_requests.material_request_sharing."
            "sync_material_request_shares"
        ),
    },

}


# ======================================================
# AR: مهام المعالجة الدورية
# EN: Scheduled reconciliation jobs
# ======================================================

# AR:
# يعاد فحص المهام المعتمدة كل ساعة. هذا ضروري للطلبات المعتمدة قبل
# نهاية الوردية، ولا ينشئ أي سجلات Employee Checkin وهمية.
#
# EN:
# Re-check approved duties hourly. This handles requests approved before
# shift end and never fabricates Employee Checkin records.
scheduler_events = {
    "hourly": [
        # AR: تسوية المهام الرسمية بعد نهاية الوردية ومزامنة البصمات.
        # EN: Reconcile official duties after shift end and checkin synchronization.
        "masar_requests.official_duty_engine.process_pending_official_duties",

        # AR: تسجيل إجازة ربع اليوم/الساعات دون حجب Auto Attendance.
        # EN: Register quarter-day/hourly leave without blocking Auto Attendance.
        "masar_requests.leave_application_partial_leave.process_pending_partial_leave_attendance",
    ],
}


# MASAR_STRICT_REQUEST_VISIBILITY_V21_9
# Final participant/stage visibility overrides.
permission_query_conditions.update(
    {
        "Leave Application": (
            "masar_requests.strict_request_visibility."
            "leave_application_query"
        ),
        "Official Duty Request": (
            "masar_requests.strict_request_visibility."
            "official_duty_request_query"
        ),
        "Material Request": (
            "masar_requests.strict_request_visibility."
            "material_request_query"
        ),
    }
)

has_permission.update(
    {
        "Leave Application": (
            "masar_requests.strict_request_visibility."
            "leave_application_has_permission"
        ),
        "Official Duty Request": (
            "masar_requests.strict_request_visibility."
            "official_duty_request_has_permission"
        ),
        "Material Request": (
            "masar_requests.strict_request_visibility."
            "material_request_has_permission"
        ),
    }
)


# MASAR_UNIFIED_SECRETARY_ACCESS_V22
def _masar_append_doc_event(doctype, event, handler):
    """
    AR: تنفيذ `masar` `append` المستند `event` ضمن وحدة `hooks`.
    EN: Execute masar append doc event within the `hooks` module.
    """
    current = doc_events.setdefault(doctype, {}).get(event)

    if not current:
        doc_events[doctype][event] = handler
        return

    if isinstance(current, str):
        if current != handler:
            doc_events[doctype][event] = [current, handler]
        return

    if handler not in current:
        current.append(handler)


for _secretary_doctype in (
    "Leave Application",
    "Official Duty Request",
    "Material Request",
):
    for _secretary_event in (
        "after_insert",
        "on_update",
        "on_update_after_submit",
        "on_submit",
    ):
        _masar_append_doc_event(
            _secretary_doctype,
            _secretary_event,
            "masar_requests.secretary_access.sync_secretary_access",
        )

    _masar_append_doc_event(
        _secretary_doctype,
        "on_cancel",
        "masar_requests.secretary_access.revoke_secretary_access",
    )
