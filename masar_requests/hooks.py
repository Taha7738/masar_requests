# AR: تعريف اسم التطبيق برمجياً / EN: Define the app name programmatically
app_name = "masar_requests"

# AR: تعريف العنوان الذي يظهر للمستخدمين / EN: Define the title shown to users
app_title = "Masar Requests"

# AR: تعريف اسم الناشر أو الشركة المبرمجة / EN: Define the publisher or development company name
app_publisher = "AlphaCode"

# AR: وصف التطبيق ووظيفته في النظام / EN: App description and its function in the system
app_description = "Masar Requests is an application to streamline workflow and paper transactions for."

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
app_include_js = [

]


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
}


# ======================================================
# AR: قسم التثبيت والتحديث
# EN: Installation and migration section
# ======================================================

# AR:
# تعمل هذه الدالة مباشرة بعد تثبيت التطبيق.
#
# EN:
# This function runs immediately after installing the app.
after_install = "masar_requests.install.after_install"


# AR:
# تعمل هذه الدالة بعد تنفيذ migrate.
#
# EN:
# This function runs after migration.
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
permission_query_conditions = {
    "Leave Application":
        "masar_requests.leave_application_permissions.leave_application_query",
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
has_permission = {
    "Leave Application":
        "masar_requests.leave_application_permissions.leave_application_has_permission",
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
    "Leave Application":
        "masar_requests.leave_application_partial_leave.CustomLeaveApplication",
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
        "validate":
            "masar_requests.leave_application_permissions.validate_leave_application",

        # AR:
        # بعد إنشاء الطلب لأول مرة تتم مشاركة المستند
        # مع الأطراف المرتبطة به.
        #
        # EN:
        # After initial insertion, share the document
        # with its related participants.
        "after_insert":
            "masar_requests.leave_application_permissions.sync_leave_application_shares",

        # AR:
        # بعد كل تحديث تتم إعادة مزامنة المشاركات
        # وإرسال إشعارات سير العمل.
        #
        # EN:
        # After each update, re-sync shares
        # and send workflow notifications.
        "on_update":
            "masar_requests.leave_application_permissions.on_update_leave_application",

        # AR:
        # نقطة مخصصة لتنظيف المشاركات عند حذف الطلب.
        #
        # EN:
        # Hook point for cleaning shares when deleting a request.
        "on_trash":
            "masar_requests.leave_application_permissions.remove_leave_application_shares",
    },

    "Shift Type": {
        # AR:
        # توليد أو معالجة أوقات الوردية قبل حفظ Shift Type.
        #
        # EN:
        # Generate or process shift times before saving Shift Type.
        "before_save":
            "masar_requests.overrides.shift_type.generate_shift_times",
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
    
    "Material Request": {
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