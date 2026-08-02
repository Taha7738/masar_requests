"""
AR: إعداد وتهيئة مكونات التطبيق ضمن الوحدة `install`.
EN: Application setup and configuration routines for the `install` module.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


# AR: استيراد إعدادات مسار للنماذج / EN: Import Masar Requests DocType setup functions
from masar_requests.setup_leave_and_shift import (
    setup_leave_and_shift_all,
    teardown_leave_and_shift,
)
from masar_requests.setup_material_request import (
    setup_material_request_all,
    teardown_material_request,
)

from masar_requests.setup_official_duty_request import (
    setup_official_duty_request_all,
    teardown_official_duty_request,
)
from masar_requests.setup_partial_leave_attendance import (
    setup_partial_leave_attendance_fields,
    teardown_partial_leave_attendance_fields,
)
from masar_requests.hr_user_read_only import setup_hr_user_read_only_permissions


def after_install(app_name=None):
    """
    AR: تنفيذ معالجة ما بعد تثبيت ضمن وحدة `install`.
    EN: Execute after install within the `install` module.
    """
    sync_custom_setup()


def after_migrate():
    """
    AR: تنفيذ معالجة ما بعد ترحيل ضمن وحدة `install`.
    EN: Execute after migrate within the `install` module.

    DETAILS / التفاصيل:
    AR:
            لا نعيد إنشاء Workflow أو الصلاحيات أو Server Scripts هنا. تشغيل
            الإعداد الكامل في كل migrate قد يمحو تخصيصات العميل. أي تغيير لاحق
            في البيانات يُنفذ عبر Patch مرقم داخل patches.txt.

        EN:
            Do not recreate Workflows, permissions, or Server Scripts here.
            Running the full setup on every migrate can overwrite customer
            customizations. Future data changes must use a numbered patch.
    """
    frappe.clear_cache(doctype="Leave Application")
    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache(doctype="Material Request Item")
    frappe.clear_cache(doctype="Attendance Request")
    frappe.clear_cache(doctype="Official Duty Request")
    frappe.clear_cache(doctype="Attendance")
    frappe.clear_cache(doctype="Salary Slip")
    frappe.clear_cache(doctype="Shift Type")
    frappe.clear_cache(doctype="Shift Assignment")
    frappe.clear_cache(doctype="Employee Checkin")


def sync_custom_setup():
    """
    AR: تنفيذ مزامنة `custom` إعداد ضمن وحدة `install`.
    EN: Execute sync custom setup within the `install` module.

    DETAILS / التفاصيل:
    AR:
            إعداد التثبيت الأولي أو Patch مرقم فقط. لا تُربط هذه الدالة مع
            after_migrate مباشرة.

        EN:
            Initial-install or numbered-patch setup only. Do not call this
            function directly from after_migrate.
    """
    core_fields = get_core_custom_fields()
    create_custom_fields(core_fields, update=True)

    setup_leave_and_shift_all()
    setup_material_request_all()
    setup_official_duty_request_all()
    setup_partial_leave_attendance_fields()

    # AR: منح HR User صلاحية عامة للعرض والطباعة فقط للطلبات الثلاثة.
    # EN: Grant HR User global read/print-only access to the three request types.
    setup_hr_user_read_only_permissions()

    for doctype in core_fields.keys():
        frappe.clear_cache(doctype=doctype)
    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache(doctype="Official Duty Request")
    frappe.clear_cache(doctype="Attendance Request")
    frappe.clear_cache(doctype="Attendance")
    frappe.clear_cache(doctype="Salary Slip")
    frappe.clear_cache(doctype="Shift Type")
    frappe.clear_cache(doctype="Shift Assignment")
    frappe.clear_cache(doctype="Employee Checkin")


def schedule_workflow_share_resync_after_employee_change(doc, method=None):
    """
    AR: تنفيذ `schedule` سير العمل مشاركة `resync` معالجة ما بعد الموظف `change` ضمن وحدة `install`.
    EN: Execute schedule workflow share resync after employee change within the `install` module.

    DETAILS / التفاصيل:
    AR:
            عند تغيير علاقة الموظف بحسابه أو مديره أو سكرتيره، نعيد مزامنة
            المشاركات بعد نجاح الحفظ. المهمة تعمل في الخلفية وتُجمع خلال دقيقة
            كي لا يبطؤ حفظ سجل Employee.

        EN:
            When a user's account, manager, or secretary relation changes,
            re-sync request sharing after the save commits. The background job is
            coalesced for one minute so saving an Employee record stays fast.
    """
    watched_fields = {
        "user_id",
        "reports_to",
        "custom_secretary_employee",
        "status",
    }
    previous = doc.get_doc_before_save()

    if previous and not any(
        previous.get(fieldname) != doc.get(fieldname)
        for fieldname in watched_fields
    ):
        return

    cache_key = "masar_requests:workflow_share_resync_queued"
    if frappe.cache().get_value(cache_key):
        return

    frappe.cache().set_value(cache_key, 1, expires_in_sec=60)
    frappe.enqueue(
        "masar_requests.install.resync_all_workflow_shares",
        queue="long",
        timeout=1800,
        enqueue_after_commit=True,
        job_name="masar_requests_workflow_share_resync",
    )


def resync_all_workflow_shares():
    """
    AR: تنفيذ `resync` `all` سير العمل `shares` ضمن وحدة `install`.
    EN: Execute resync all workflow shares within the `install` module.
    """
    from masar_requests.leave_application_permissions import (
        resync_all_leave_application_shares,
    )
    from masar_requests.official_duty_request_permissions import (
        resync_all_official_duty_request_shares,
    )
    from masar_requests.setup_material_request import (
        resync_all_material_request_shares,
        sync_material_request_secretary_roles,
    )

    secretary_roles_assigned = sync_material_request_secretary_roles()
    leave_requests = resync_all_leave_application_shares()
    official_duty_requests = resync_all_official_duty_request_shares()
    material_requests = resync_all_material_request_shares()

    frappe.cache().delete_value(
        "masar_requests:workflow_share_resync_queued"
    )
    return {
        "leave_requests": leave_requests,
        "official_duty_requests": official_duty_requests,
        "material_requests": material_requests,
        "secretary_roles_assigned": secretary_roles_assigned,
    }

# AR: تعريف الحقول الأساسية لمستخدمي النظام والتعليقات / EN: Define core fields for system users and comments
def get_core_custom_fields():
    # AR: إرجاع تعريفات الحقول الأساسية التي يديرها التطبيق.
    # EN: Return definitions for the core fields managed by the app.
    """
    AR: تنفيذ استرجاع `core` `custom` الحقول ضمن وحدة `install`.
    EN: Execute get core custom fields within the `install` module.
    """
    return {
        # "User": [
        #     {"fieldname": "custom_employment_data_tab", "fieldtype": "Tab Break", "label": "Employment Data", "insert_after": "user_image"},
        #     {"fieldname": "custom_employment_data_section", "fieldtype": "Section Break", "label": "Employment Data", "insert_after": "custom_employment_data_tab"},
        #     {"fieldname": "custom_department", "fieldtype": "Link", "label": "Department", "options": "User Group", "insert_after": "custom_employment_data_section"},
        #     {"fieldname": "custom_direct_supervisor", "fieldtype": "Link", "label": "Direct Supervisor", "options": "User", "insert_after": "custom_department"},
        #     {"fieldname": "custom_employment_column_break", "fieldtype": "Column Break", "insert_after": "custom_direct_supervisor"},
        #     {"fieldname": "custom_job_title", "fieldtype": "Data", "label": "Job Title", "insert_after": "custom_employment_column_break"},
        #     {"fieldname": "custom_employee_id", "fieldtype": "Data", "label": "Employee ID", "insert_after": "custom_job_title"},
        # ],
        # "Comment": [
        #     {"fieldname": "custom_reference_todo_name", "fieldtype": "Link", "label": "Reference ToDo Name", "options": "ToDo", "insert_after": "reference_name", "ignore_user_permissions": 1, "read_only": 1},
        # ],
    }

# AR: تنظيف قاعدة البيانات قبل إزالة التطبيق / EN: Clean DB before app uninstallation
def before_uninstall():
    # AR: تنظيف إعدادات التطبيق المملوكة له قبل إلغاء التثبيت.
    # EN: Remove app-owned configuration before uninstalling the app.
    """
    AR: تنفيذ معالجة ما قبل إلغاء تثبيت ضمن وحدة `install`.
    EN: Execute before uninstall within the `install` module.
    """
    core_fields = get_core_custom_fields()
    for doctype, fields in core_fields.items():
        frappe.db.delete(
            "Custom Field",
            {"fieldname": ("in", [field["fieldname"] for field in fields]), "dt": doctype},
        )
        frappe.clear_cache(doctype=doctype)

    teardown_material_request()
    teardown_leave_and_shift()
    teardown_partial_leave_attendance_fields()
    teardown_official_duty_request()
