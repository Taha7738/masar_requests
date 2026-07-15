# AR: استيراد مكتبة فرابي / EN: Import frappe library
import importlib

import frappe

# AR: استيراد دالة جلب التاريخ / EN: Import get date function
from frappe.utils import getdate


# AR: تحفظ الدالة الأصلية بعد التأكد من توافق إصدار HRMS.
# EN: Store the original function only after validating the HRMS version.
_original_get_employee_shift = None

# AR: دالة لتوليد وتحديث أوقات الوردية ديناميكياً قبل حفظها / EN: Function to dynamically generate and update shift times before save
def generate_shift_times(doc, method=None):
    # AR: إيقاف العملية إذا لم تكن هناك قائمة عطلات مرتبطة / EN: Halt process if no holiday list is linked
    if not doc.holiday_list: return
    
    # AR: جلب يوم الإجازة الأسبوعية من النظام / EN: Fetch the weekly off day from system
    weekly_off = frappe.db.get_value("Holiday List", doc.holiday_list, "weekly_off")
    # AR: قائمة بكل أيام الأسبوع / EN: List of all days of the week
    all_days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    # AR: استبعاد يوم الإجازة لتحديد أيام الدوام / EN: Exclude off day to determine working days
    active_days = [day for day in all_days if day != weekly_off]
    
    # AR: قراءة الأسطر الموجودة حالياً لحفظ أي تعديل يدوي قام به المستخدم / EN: Read currently existing rows to preserve any manual user edits
    existing_rows = {row.day_of_week: row for row in doc.get("custom_shift_times") or []}
    # AR: قائمة فارغة لجدول الأوقات الجديد / EN: Empty list for the new time table
    new_shift_times = []

    # AR: المرور على أيام الدوام / EN: Iterate through working days
    for day in active_days:
        # AR: إذا كان اليوم موجوداً سابقاً، أضفه كما هو / EN: If day already exists, append it as is
        if day in existing_rows: new_shift_times.append(existing_rows[day])
        # AR: إذا كان اليوم جديداً، قم بإنشاء سطر جديد له بأوقات افتراضية / EN: If day is new, create a new row for it with default times
        else:
            new_shift_times.append({
                # AR: تحديد نوع المستند للسطر / EN: Set doctype for row
                "doctype": "Shift Time Table", 
                # AR: تعيين اسم اليوم / EN: Set day name
                "day_of_week": day,
                # AR: تعيين وقت البدء الافتراضي / EN: Set default start time
                "start_time": doc.start_time, 
                # AR: تعيين وقت النهاية الافتراضي / EN: Set default end time
                "end_time": doc.end_time
            })
    # AR: إرسال الجدول المحدث إلى المستند لحفظه / EN: Send the updated table to the document for saving
    doc.set("custom_shift_times", new_shift_times)

def _get_standard_shift_module():
    """
    AR: استيراد API الوردية عند الحاجة بدلاً من وقت بدء التطبيق.
    EN: Import the Shift Type API lazily instead of during app startup.
    """
    try:
        return importlib.import_module(
            "hrms.hr.doctype.shift_type.shift_type"
        )
    except (ImportError, ModuleNotFoundError):
        return None

# AR: الدالة المخصصة لجلب وردية الموظف مع دعم أوقات اليوم المخصصة / EN: Custom function to fetch employee shift with custom day times support
def custom_get_employee_shift(employee, date, *args, **kwargs):
    # AR: استدعاء الدالة الأصلية لجلب بيانات الوردية الأساسية.
    # EN: Call the preserved original function for basic shift details.
    if not callable(_original_get_employee_shift):
        return None

    shift_details = _original_get_employee_shift(
        employee,
        date,
        *args,
        **kwargs,
    )
    
    # AR: العودة فوراً إذا لم توجد وردية للموظف / EN: Return immediately if no shift found for employee
    if not shift_details or not shift_details.get("shift_type"): return shift_details

    # AR: استخراج اسم اليوم الإنجليزي من التاريخ المطلوب / EN: Extract English day name from the requested date
    day_name = getdate(date).strftime("%A")
    # AR: استخراج معرف نوع الوردية / EN: Extract shift type ID
    shift_doc = shift_details.get("shift_type")
    
    # AR: التحقق مما إذا كان هناك جدول أوقات مخصص لهذه الوردية / EN: Check if there is a custom time table for this shift
    if shift_doc.get("custom_shift_times"):
        # AR: البحث داخل الجدول عن سطر يطابق اليوم الحالي / EN: Search inside the table for a row matching the current day
        for row in shift_doc.custom_shift_times:
            if row.day_of_week == day_name:
                # AR: استبدال توقيت الوردية القياسي بتوقيت اليوم المخصص / EN: Replace standard shift times with the custom day times
                shift_details["start_time"] = row.start_time; 
                shift_details["end_time"] = row.end_time; 
                # AR: الخروج من حلقة البحث بعد إيجاد التطابق / EN: Break search loop after finding match
                break
                
    # AR: إرجاع تفاصيل الوردية المحدثة / EN: Return the updated shift details
    return shift_details

# AR: دالة تطبيق الترقيع رسمياً في النظام / EN: Function to officially apply the patch in the system
def apply_shift_times_patch():
    """
    AR:
        يطبق ترقيع أوقات الوردية فقط عند توفر دالة HRMS الأصلية. بهذا لا
        يفشل استيراد التطبيق إذا تغيّر المسار الداخلي لـ HRMS في عميل آخر.

    EN:
        Apply the Shift Time patch only when the original HRMS function is
        available. This prevents app import failure if a client uses an HRMS
        release with a different internal module path.
    """
    global _original_get_employee_shift

    standard_shift = _get_standard_shift_module()
    if not standard_shift:
        return False

    if getattr(
        standard_shift,
        "_masar_requests_shift_times_patch_applied",
        False,
    ):
        return True

    original_function = getattr(
        standard_shift,
        "get_employee_shift",
        None,
    )
    if not callable(original_function):
        return False

    _original_get_employee_shift = original_function
    standard_shift.get_employee_shift = custom_get_employee_shift
    standard_shift._masar_requests_shift_times_patch_applied = True
    return True