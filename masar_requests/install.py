import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# AR: استيراد إعدادات مسار للنماذج / EN: Import Masar Requests DocType setup functions
from masar_requests.setup_leave_and_shift import (
    setup_leave_and_shift_all,
    teardown_leave_and_shift,
)
from masar_requests.setup_material_request import setup_material_request_all


def after_install(app_name=None):
    """
    AR: إنشاء إعدادات التطبيق مرة واحدة عند تثبيته على موقع جديد.
    EN: Create the application setup once when it is installed on a new site.
    """
    sync_custom_setup()


def after_migrate():
    """
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


def sync_custom_setup():
    """
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

    for doctype in core_fields.keys():
        frappe.clear_cache(doctype=doctype)
    frappe.clear_cache(doctype="Material Request")


def schedule_workflow_share_resync_after_employee_change(doc, method=None):
    """
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
    AR: تحديث مشاركات الإجازات والمواد بعد تعديل الهيكل الإداري.
    EN: Re-sync Leave and Material Request shares after hierarchy changes.
    """
    from masar_requests.leave_application_permissions import (
        resync_all_leave_application_shares,
    )
    from masar_requests.setup_material_request import (
        resync_all_material_request_shares,
        sync_material_request_secretary_roles,
    )

    secretary_roles_assigned = sync_material_request_secretary_roles()
    leave_requests = resync_all_leave_application_shares()
    material_requests = resync_all_material_request_shares()

    frappe.cache().delete_value(
        "masar_requests:workflow_share_resync_queued"
    )
    return {
        "leave_requests": leave_requests,
        "material_requests": material_requests,
        "secretary_roles_assigned": secretary_roles_assigned,
    }

# AR: تعريف الحقول الأساسية لمستخدمي النظام والتعليقات / EN: Define core fields for system users and comments
def get_core_custom_fields():
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
    core_fields = get_core_custom_fields()
    for doctype, fields in core_fields.items():
        frappe.db.delete(
            "Custom Field",
            {"fieldname": ("in", [field["fieldname"] for field in fields]), "dt": doctype},
        )
        frappe.clear_cache(doctype=doctype)
    
    teardown_leave_and_shift()