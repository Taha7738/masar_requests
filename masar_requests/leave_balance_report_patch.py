# AR: استيراد مكتبة فرابي / EN: Import frappe library
import importlib

import frappe
# AR: استيراد دوال مساعدة للتحويل إلى أرقام وتواريخ / EN: Import helper functions to convert to floats and dates
from frappe.utils import flt, getdate

# AR: دالة معدلة لاستخراج رصيد الإجازات من دفتر الأستاذ (القيود) بدقة / EN: Modified function to extract leave balance accurately from ledger
def get_leaves_for_period_from_ledger(employee, leave_type, from_date, to_date, skip_expired_leaves=True, *args, **kwargs):
    # AR: تحويل النصوص إلى كائنات تاريخ / EN: Convert strings to date objects
    from_date = getdate(from_date)
    to_date = getdate(to_date)
    
    # AR: صياغة شروط الاستعلام في قاعدة البيانات / EN: Construct query conditions for database
    conditions = "employee = %(employee)s AND leave_type = %(leave_type)s AND docstatus = 1 AND leaves < 0 AND from_date <= %(to_date)s AND to_date >= %(from_date)s"
    # AR: القيم الممررة لاستعلام الـ SQL / EN: Values passed to SQL query
    values = {"employee": employee, "leave_type": leave_type, "from_date": from_date, "to_date": to_date}

    # AR: تجاهل الإجازات منتهية الصلاحية إذا كان الحقل موجوداً بالنظام / EN: Ignore expired leaves if the field exists in system
    if skip_expired_leaves and frappe.get_meta("Leave Ledger Entry").has_field("is_expired"):
        # AR: إضافة شرط الإخفاء للاستعلام / EN: Add exclusion condition to query
        conditions += " AND IFNULL(is_expired, 0) = 0"

    # AR: تنفيذ الاستعلام لجمع أيام الإجازات المستهلكة / EN: Execute query to sum consumed leave days
    total = frappe.db.sql(f"SELECT COALESCE(SUM(leaves), 0) FROM `tabLeave Ledger Entry` WHERE {conditions}", values)[0][0]
    
    # AR: إرجاع المجموع بدقة 4 خانات عشرية / EN: Return total with 4 decimal precision
    return flt(total, 4)

# AR: دالة تطبيق الترقيع على التقرير القياسي للنظام / EN: Function to apply the patch to the standard system report
def apply_patch():
    """
    AR:
        يطبق ترقيع تقرير رصيد الإجازات فقط عندما تكون واجهة HRMS المتوقعة
        موجودة. بعض إصدارات HRMS غيّرت مسار التقرير أو اسم الدالة؛ في هذه
        الحالة نرجع False بصمت لأن حاسبة طلب الإجازة الخاصة بالتطبيق تعمل
        مستقلة عن هذا التقرير.

    EN:
        Apply the Employee Leave Balance report patch only when the expected
        HRMS API exists. Some HRMS releases changed the report path or helper
        name; return False quietly in that case because the app's Leave
        Application balance calculator works independently of this report.
    """
    try:
        employee_leave_balance = importlib.import_module(
            "hrms.hr.report.employee_leave_balance.employee_leave_balance"
        )
    except (ImportError, ModuleNotFoundError):
        return False

    original_function = getattr(
        employee_leave_balance,
        "get_leaves_for_period",
        None,
    )
    if not callable(original_function):
        return False

    if getattr(
        employee_leave_balance,
        "_masar_requests_leave_balance_patch_applied",
        False,
    ):
        return True

    employee_leave_balance.get_leaves_for_period = (
        get_leaves_for_period_from_ledger
    )
    employee_leave_balance._masar_requests_leave_balance_patch_applied = True
    return True