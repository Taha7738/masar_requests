"""
AR: إعداد وتهيئة مكونات التطبيق ضمن الوحدة `setup_leave_and_shift`.
EN: Application setup and configuration routines for the `setup_leave_and_shift` module.
"""

import json
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import cint





# ==========================================
# ثوابت سير العمل / Workflow Constants
# ==========================================
WORKFLOW_NAME = "Custom Leave Application Workflow"
LEAVE_APPLICATION_DOCTYPE = "Leave Application"

# الأدوار / Roles
EMPLOYEE_ROLE = "Employee"
HR_MANAGER_ROLE = "HR Manager"
SYSTEM_MANAGER_ROLE = "System Manager"
ALL_ROLE = "All"

# حالات سير العمل / Workflow States
STATE_DRAFT = "Draft"
STATE_WAITING_SUBSTITUTE = "Waiting for Substitute Approval"
STATE_WAITING_DIRECT_MANAGER = "Waiting for Direct Manager Approval"
STATE_WAITING_HR_MANAGER = "Waiting for HR Manager Approval"
STATE_APPROVED = "Approved"
STATE_REJECTED = "Rejected"

# إجراءات سير العمل / Workflow Actions
ACTION_SEND_TO_SUBSTITUTE = "Send to Substitute"
ACTION_SEND_TO_DIRECT_MANAGER = "Send to Direct Manager"
ACTION_SUBSTITUTE_APPROVE = "Substitute Approve"
ACTION_DIRECT_MANAGER_APPROVE = "Direct Manager Approve"
ACTION_FINAL_APPROVE = "Final Approve"
ACTION_REJECT = "Reject"

# ==========================================
# الدوال الرئيسية / Main Functions
# ==========================================

def setup_leave_and_shift_all():
    # AR: إعداد حقول الإجازة والورديات والواجهة وسير العمل عند التثبيت.
    # EN: Configure leave and shift fields, layout, and workflow on install.
    """
    AR: تنفيذ إعداد الإجازة `and` الوردية `all` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute setup leave and shift all within the `setup_leave_and_shift` module.
    """
    # 1. إعادة ضبط حقول الوقت إذا لزم الأمر / Reset partial time fields if needed
    reset_partial_time_custom_fields_if_needed()

    # 2. إنشاء جدول أوقات المناوبة / Create shift time child table
    create_shift_time_child_table()

    set_employee_link_fields_to_show_employee_name()

    # 3. إحضار وإنشاء الحقول / Fetch and create custom fields
    custom_fields = get_leave_and_shift_custom_fields()
    secretary_fields = get_direct_manager_secretary_fields()

    create_custom_fields(custom_fields, update=True)
    create_custom_fields(secretary_fields, update=True)

    # 4. إصلاح الصلاحيات والكسور العشرية / Fix permissions and decimal precision
    fix_leave_application_link_permissions()
    fix_leave_decimal_precision()

    # 5. تطبيق ترتيب وواجهة نموذج الإجازة حسب متطلبات المشروع
    # 5. Apply the Leave Application layout and ordering preferences
    apply_leave_application_layout_preferences()

    # 6. إنشاء سير عمل الإجازات / Create leave application workflow
    create_leave_application_workflow()

    # تنظيف الكاش / Clear cache
    for doctype in set(custom_fields.keys()) | set(secretary_fields.keys()):
        frappe.clear_cache(doctype=doctype)
    frappe.clear_cache(doctype=LEAVE_APPLICATION_DOCTYPE)


def teardown_leave_and_shift():
    # AR: إزالة إعدادات الإجازة والورديات التابعة للتطبيق.
    # EN: Remove app-owned leave and shift configuration.
    """
    AR: تنفيذ `teardown` الإجازة `and` الوردية ضمن وحدة `setup_leave_and_shift`.
    EN: Execute teardown leave and shift within the `setup_leave_and_shift` module.

    DETAILS / التفاصيل:
    AR:
            حذف الحقول وسير العمل وجدول الأوقات الفرعي المملوك للتطبيق فقط.

        EN:
            Remove app-owned fields, workflow, and the variable-time child table.
    """
    delete_custom_fields(get_leave_and_shift_custom_fields())
    delete_custom_fields(get_direct_manager_secretary_fields())
    delete_leave_application_workflow()

    if frappe.db.exists("DocType", "Shift Time Table"):
        child_doctype = frappe.get_doc("DocType", "Shift Time Table")
        if cint(child_doctype.get("custom")) and child_doctype.get("module") == "Masar Requests":
            frappe.delete_doc(
                "DocType",
                "Shift Time Table",
                ignore_permissions=True,
                force=True,
            )


# ==========================================
# إعدادات الجداول والحقول / Tables & Fields Setup
# ==========================================

def create_shift_time_child_table():
    """
    AR: تنفيذ إنشاء الوردية الوقت `child` `table` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute create shift time child table within the `setup_leave_and_shift` module.

    DETAILS / التفاصيل:
    AR:
            إنشاء أو تحديث جدول أوقات الوردية الأسبوعية. يتم تحديث الحقول
            بطريقة تراكمية حتى لا تضيع البيانات الموجودة في المواقع السابقة.

        EN:
            Create or update the weekday Shift Time child table incrementally,
            preserving existing site data across upgrades.
    """
    days_options = "\n".join(
        [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]
    )

    field_definitions = [
        {
            "fieldname": "day_of_week",
            "label": "Day of Week",
            "fieldtype": "Select",
            "options": days_options,
            "reqd": 1,
            "in_list_view": 1,
            "columns": 3,
        },
        {
            "fieldname": "start_time",
            "label": "Start Time",
            "fieldtype": "Time",
            "reqd": 1,
            "in_list_view": 1,
            "columns": 3,
        },
        {
            "fieldname": "end_time",
            "label": "End Time",
            "fieldtype": "Time",
            "reqd": 1,
            "in_list_view": 1,
            "columns": 3,
        },
        {
            "fieldname": "shift_hours",
            "label": "Shift Hours",
            "fieldtype": "Float",
            "read_only": 1,
            "precision": "4",
            "in_list_view": 1,
            "columns": 3,
        },
    ]

    if not frappe.db.exists("DocType", "Shift Time Table"):
        doc = frappe.get_doc(
            {
                "doctype": "DocType",
                "name": "Shift Time Table",
                "module": "Masar Requests",
                "custom": 1,
                "istable": 1,
                "fields": field_definitions,
            }
        )
        doc.insert(ignore_permissions=True)
        return

    doc = frappe.get_doc("DocType", "Shift Time Table")
    updated = False
    if doc.module != "Masar Requests":
        doc.module = "Masar Requests"
        updated = True
    if not cint(doc.istable):
        doc.istable = 1
        updated = True

    existing = {field.fieldname: field for field in doc.fields}
    for definition in field_definitions:
        field = existing.get(definition["fieldname"])
        if not field:
            doc.append("fields", definition)
            updated = True
            continue

        for property_name, value in definition.items():
            if property_name == "fieldname":
                continue
            if field.get(property_name) != value:
                field.set(property_name, value)
                updated = True

    if updated:
        doc.save(ignore_permissions=True)


def reset_partial_time_custom_fields_if_needed():
    # AR: إعادة إنشاء حقول وقت الإجازة الجزئية إذا كان نوعها غير صحيح.
    # EN: Recreate partial-time fields when their field type is invalid.
    """
    AR: تنفيذ `reset` الجزئي الوقت `custom` الحقول `if` `needed` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute reset partial time custom fields if needed within the `setup_leave_and_shift` module.
    """
    fieldnames = [
        "custom_partial_from_time_ar",
        "custom_partial_to_time_ar",
    ]

    for fieldname in fieldnames:
        custom_field = frappe.db.get_value(
            "Custom Field",
            {"dt": LEAVE_APPLICATION_DOCTYPE, "fieldname": fieldname},
            ["name", "fieldtype"],
            as_dict=True,
        )

        if custom_field and custom_field.fieldtype != "Time":
            frappe.delete_doc(
                "Custom Field",
                custom_field.name,
                ignore_permissions=True,
                force=True,
            )

    frappe.clear_cache(doctype=LEAVE_APPLICATION_DOCTYPE)


def get_leave_and_shift_custom_fields():
    # AR: إرجاع تعريفات الحقول المخصصة للإجازة والورديات.
    # EN: Return custom field definitions for leave and shift.
    """
    AR: تنفيذ استرجاع الإجازة `and` الوردية `custom` الحقول ضمن وحدة `setup_leave_and_shift`.
    EN: Execute get leave and shift custom fields within the `setup_leave_and_shift` module.
    """
    return {
        "Leave Application": [
            {
                "fieldname": "custom_substitute_section",
                "fieldtype": "Section Break",
                "label": "Substitute Approval",
                "insert_after": "employee",
            },
            {
                "fieldname": "custom_substitute_employee",
                "fieldtype": "Link",
                "label": "Substitute Employee",
                "options": "Employee",
                "insert_after": "custom_substitute_section",
                "reqd": 0,
                "ignore_user_permissions": 1,
                "description": "Select the employee who will handle duties during the leave period.",
            },
            {
                "fieldname": "custom_substitute_user",
                "fieldtype": "Link",
                "label": "Substitute User",
                "options": "User",
                "insert_after": "custom_substitute_employee",
                "read_only": 1,
                "hidden": 1,
                "ignore_user_permissions": 1,
                "description": "User account linked to the substitute employee.",
            },
            {
                "fieldname": "custom_substitute_approval",
                "fieldtype": "Select",
                "label": "Substitute Approval Status",
                "options": "\nPending\nApproved\nRejected\nBypassed",
                "default": "",
                "insert_after": "custom_substitute_user",
                "read_only": 1,
                "ignore_user_permissions": 1,
            },
            {
                "fieldname": "custom_direct_manager_section",
                "fieldtype": "Section Break",
                "label": "Direct Manager Approval",
                "insert_after": "custom_substitute_approval",
            },
            {
                "fieldname": "custom_direct_manager_employee",
                "fieldtype": "Link",
                "label": "Direct Manager",
                "options": "Employee",
                "insert_after": "custom_direct_manager_section",
                "read_only": 1,
                "hidden": 1,
                "ignore_user_permissions": 1,
                "description": "Direct manager fetched automatically from the employee reports_to field.",
            },
            {
                "fieldname": "custom_direct_manager_user",
                "fieldtype": "Link",
                "label": "Direct Manager User",
                "options": "User",
                "insert_after": "custom_direct_manager_employee",
                "read_only": 1,
                "hidden": 1,
                "ignore_user_permissions": 1,
                "description": "User account linked to the direct manager.",
            },
            {
                "fieldname": "custom_direct_manager_approval",
                "fieldtype": "Select",
                "label": "Direct Manager Approval Status",
                "options": "\nPending\nApproved\nRejected\nBypassed",
                "default": "Pending",
                "insert_after": "custom_direct_manager_user",
                "read_only": 1,
                "ignore_user_permissions": 1,
            },
            {
                "fieldname": "custom_balance_section",
                "fieldtype": "Section Break",
                "label": "Actual Leave Balance",
                "insert_after": "custom_direct_manager_approval",
            },
            {
                "fieldname": "custom_actual_leave_balance",
                "label": "Actual Leave Balance",
                "fieldtype": "Float",
                "insert_after": "custom_balance_section",
                "read_only": 1,
                "precision": "4",
                "description": "Current balance from leave ledger before this request.",
            },
            {
                "fieldname": "custom_balance_after_this_request",
                "label": "Balance After This Request",
                "fieldtype": "Float",
                "insert_after": "custom_actual_leave_balance",
                "read_only": 1,
                "precision": "4",
                "description": "Estimated balance after this request.",
            },
            {
                # AR:
                # فاصل أعمدة مساعد لعرض رصيد الإجازة الفعلي واعتماد المسؤول المباشر
                # في نفس السطر داخل عمودين متجاورين.
                #
                # EN:
                # Helper column break used to render Actual Leave Balance and
                # Direct Manager approval side by side on the same row.
                "fieldname": "custom_balance_manager_column_break",
                "fieldtype": "Column Break",
                "insert_after": "custom_balance_after_this_request",
            },
            {
                "fieldname": "quarter_day",
                "label": "Quarter Day",
                "fieldtype": "Check",
                "insert_after": "half_day",
                "description": "Deduct a quarter day from the leave balance.",
            },
            {
                "fieldname": "is_hourly",
                "label": "Hourly Leave",
                "fieldtype": "Check",
                "insert_after": "quarter_day",
                "description": "Calculate leave based on the selected hours and the employee shift.",
            },
            {
                "fieldname": "custom_partial_leave_date",
                "label": "Partial Leave Date",
                "fieldtype": "Date",
                "insert_after": "to_date",
                "description": "Used for half-day, quarter-day, and hourly leave requests.",
            },
            {
                "fieldname": "custom_partial_from_time_ar",
                "label": "Start Time",
                "fieldtype": "Time",
                "insert_after": "custom_partial_leave_date",
                "description": "Select the leave start time.",
            },
            {
                "fieldname": "custom_partial_to_time_ar",
                "label": "End Time",
                "fieldtype": "Time",
                "insert_after": "custom_partial_from_time_ar",
                "description": "Required only for hourly leave.",
            },
            {
                "fieldname": "custom_partial_time_ar_display",
                "label": "Leave Time",
                "fieldtype": "Data",
                "insert_after": "custom_partial_to_time_ar",
                "read_only": 1,
                "description": "Displays the calculated leave time range.",
            },
            {
                "fieldname": "from_time",
                "label": "Start Time Internal",
                "fieldtype": "Time",
                "insert_after": "custom_partial_time_ar_display",
                "read_only": 1,
                "hidden": 1,
                "description": "Internal time value used by the system.",
            },
            {
                "fieldname": "to_time",
                "label": "End Time Internal",
                "fieldtype": "Time",
                "insert_after": "from_time",
                "read_only": 1,
                "hidden": 1,
                "description": "Internal time value used by the system.",
            },
            {
                "fieldname": "custom_leave_hours",
                "label": "Leave Hours",
                "fieldtype": "Float",
                "insert_after": "to_time",
                "read_only": 1,
                "depends_on": "eval:doc.half_day == 1 || doc.quarter_day == 1 || doc.is_hourly == 1",
                "description": "Calculated leave hours.",
            },
            {
                "fieldname": "custom_shift_hours",
                "label": "Shift Hours",
                "fieldtype": "Float",
                "insert_after": "custom_leave_hours",
                "read_only": 1,
                "depends_on": "eval:doc.half_day == 1 || doc.quarter_day == 1 || doc.is_hourly == 1",
                "description": "Employee shift hours on the selected leave date.",
            },
            {
                "fieldname": "custom_leave_period",
                "label": "Leave Period",
                "fieldtype": "Select",
                "options": "\nMorning\nEvening",
                "insert_after": "custom_shift_hours",
                "hidden": 1,
                "description": "Legacy field kept for backward compatibility.",
            },
        ],
        "Shift Type": [
            {
                "fieldname": "custom_enable_variable_shift_times",
                "fieldtype": "Check",
                "label": "Enable Variable Weekday Times",
                "insert_after": "end_time",
                "default": "0",
                "description": (
                    "Use a different start and end time for each weekday. "
                    "Holiday dates remain controlled by the standard Holiday List."
                ),
            },
            {
                "fieldname": "custom_shift_times_section",
                "fieldtype": "Section Break",
                "label": "Variable Weekday Times",
                "insert_after": "custom_enable_variable_shift_times",
                "depends_on": "eval:doc.custom_enable_variable_shift_times == 1",
            },
            {
                "fieldname": "custom_shift_times_effective_from",
                "fieldtype": "Date",
                "label": "Variable Times Effective From",
                "insert_after": "custom_shift_times_section",
                "depends_on": "eval:doc.custom_enable_variable_shift_times == 1",
                "description": (
                    "Optional. Before this date the standard Start Time and End Time are used. "
                    "Leave blank to apply the weekday table to all dates."
                ),
            },
            {
                "fieldname": "custom_shift_times",
                "fieldtype": "Table",
                "label": "Weekday Time Table",
                "options": "Shift Time Table",
                "insert_after": "custom_shift_times_effective_from",
                "depends_on": "eval:doc.custom_enable_variable_shift_times == 1",
                "ignore_user_permissions": 1,
                "description": (
                    "Set one row for every weekday. Weekly offs and official holidays "
                    "must continue to be configured in Holiday List."
                ),
            },
        ],
    }


def get_direct_manager_secretary_fields():
    # AR: إرجاع تعريفات حقول المدير المباشر والسكرتير.
    # EN: Return direct-manager and secretary field definitions.
    """
    AR: تنفيذ استرجاع `direct` المدير السكرتير الحقول ضمن وحدة `setup_leave_and_shift`.
    EN: Execute get direct manager secretary fields within the `setup_leave_and_shift` module.
    """
    return {
        "Employee": [
            {
                "fieldname": "custom_secretary_employee",
                "fieldtype": "Link",
                "label": "Secretary",
                "options": "Employee",
                "insert_after": "reports_to",
                "ignore_user_permissions": 1,
            }
        ],
        "Leave Application": [
            {
                "fieldname": "custom_direct_manager_secretary_employee",
                "fieldtype": "Link",
                "label": "Direct Manager Secretary Employee",
                "options": "Employee",
                "insert_after": "custom_direct_manager_user",
                "read_only": 1,
                "hidden": 1,
                "ignore_user_permissions": 1,
            },
            {
                "fieldname": "custom_direct_manager_secretary_user",
                "fieldtype": "Link",
                "label": "Direct Manager Secretary User",
                "options": "User",
                "insert_after": "custom_direct_manager_secretary_employee",
                "read_only": 1,
                "hidden": 1,
                "ignore_user_permissions": 1,
            },
        ],
    }


def create_direct_manager_secretary_fields():
    # AR: إنشاء أو تحديث حقول المدير المباشر والسكرتير.
    # EN: Create or update direct-manager and secretary fields.
    """
    AR: تنفيذ إنشاء `direct` المدير السكرتير الحقول ضمن وحدة `setup_leave_and_shift`.
    EN: Execute create direct manager secretary fields within the `setup_leave_and_shift` module.
    """
    create_custom_fields(get_direct_manager_secretary_fields(), update=True)


def apply_leave_application_layout_preferences():
    """
    AR: تنفيذ تطبيق الإجازة `application` `layout` `preferences` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute apply leave application layout preferences within the `setup_leave_and_shift` module.

    DETAILS / التفاصيل:
    AR:
            تطبيق ترتيب وواجهة نموذج طلب الإجازة وفق المتطلبات التالية:
            1) تنظيم حقول نصف يوم وربع يوم والإجازة بالساعات.
            2) عرض رصيد الإجازة الفعلي واعتماد المسؤول المباشر في نفس السطر
               داخل عمودين متجاورين.
            3) إخفاء اسم الموظف وإظهار الموظف البديل مكانه في الجزء العلوي.
            4) إخفاء قسم الاعتماد/الموافقة القياسي وقسم تفاصيل أخرى.

            هذه الدالة لا تغيّر منطق سير العمل ولا صلاحيات الحقول؛
            هي مسؤولة فقط عن ترتيب الواجهة وخصائص الإظهار.

        EN:
            Apply the Leave Application form layout according to the following requirements:
            1) Organize the Half Day, Quarter Day, and Hourly Leave fields.
            2) Show Actual Leave Balance and Direct Manager approval on the same row
               in two adjacent columns.
            3) Hide Employee Name and show Substitute Employee in its place near the top.
            4) Hide the standard Approval section and the Other Details section.

            This function does not change workflow logic or field permissions;
            it only controls the visual layout and visibility properties.
    """

    doctype = LEAVE_APPLICATION_DOCTYPE

    # ------------------------------------------------------------------
    # AR: ترتيب الحقول النهائي داخل النموذج.
    # EN: Final field order inside the form.
    # ------------------------------------------------------------------
    preferred_order = [
        # ==============================================================
        # AR: الحقول الإدارية الأساسية.
        # EN: Core administrative fields.
        # ==============================================================
        "workflow_state",
        "naming_series",

        # ==============================================================
        # AR:
        # ترتيب الجزء العلوي من النموذج:
        # - الموظف في العمود الأيمن.
        # - الموظف البديل تحت الموظف مباشرة في العمود نفسه.
        # - نوع الإجازة في العمود الأيسر.
        #
        # EN:
        # Top form layout order:
        # - Employee appears in the right column.
        # - Substitute Employee appears directly below Employee
        #   in the same column.
        # - Leave Type appears in the left column.
        # ==============================================================
        "employee",
        "custom_substitute_employee",
        "column_break_4",
        "leave_type",

        # AR: هذه الحقول ستبقى موجودة في الترتيب لكن سيتم إخفاؤها.
        # EN: These fields remain in the order but will be hidden.
        "company",
        "department",
        "employee_name",

        # ==============================================================
        # AR:
        # ترتيب قسم التواريخ والإجازة الجزئية والسبب:
        # - العمود الأيمن: من تاريخ، إلى تاريخ، ثم خيارات الإجازة الجزئية
        #   وحقولها التابعة.
        # - العمود الأيسر: السبب وعدد أيام الإجازة.
        #
        # بهذه الطريقة يعود حقلا من تاريخ وإلى تاريخ إلى العمود الأيمن،
        # بينما يبقى حقل السبب في العمود الأيسر كما هو مطلوب.
        #
        # EN:
        # Arrange the date, partial-leave, and reason section:
        # - Right column: From Date, To Date, then partial-leave options
        #   and their dependent fields.
        # - Left column: Reason and Total Leave Days.
        #
        # This moves From Date and To Date back to the right column while
        # keeping the Reason field in the left column.
        # ==============================================================
        "section_break_5",
        "half_day",
        "quarter_day",
        "is_hourly",
        "custom_partial_leave_date",
        "custom_partial_from_time_ar",
        "custom_partial_to_time_ar",
        "custom_partial_time_ar_display",
        "custom_leave_hours",
        "custom_shift_hours",
        "from_date",
        "to_date",
        "column_break1",
        "description",
        "total_leave_days",
        "half_day_date",
        "custom_leave_period",
        "from_time",
        "to_time",
        "leave_balance",

        # ==============================================================
        # AR: رصيد الإجازة واعتماد المسؤول المباشر.
        # EN: Leave balance and direct manager approval.
        # ==============================================================
        "custom_balance_section",
        "custom_actual_leave_balance",
        "custom_balance_after_this_request",
        "custom_balance_manager_column_break",
        "custom_direct_manager_employee",
        "custom_direct_manager_approval",
        "custom_direct_manager_user",
        "custom_direct_manager_secretary_employee",
        "custom_direct_manager_secretary_user",
        "custom_direct_manager_section",

        # ==============================================================
        # AR: بيانات الموظف البديل الإضافية.
        # EN: Additional substitute-related fields.
        # ==============================================================
        "custom_substitute_section",
        "custom_substitute_approval",
        "custom_substitute_user",

        # ==============================================================
        # AR: الأقسام المخفية لاحقًا.
        # EN: Sections hidden later.
        # ==============================================================
        "section_break_7",
        "leave_approver",
        "leave_approver_name",
        "follow_via_email",
        "column_break_18",
        "posting_date",
        "status",
        "sb_other_details",
        "salary_slip",
        "color",
        "column_break_17",
        "letter_head",
        "amended_from",
    ]
    meta = frappe.get_meta(doctype, cached=False)
    existing_fields = [field.fieldname for field in meta.fields if field.fieldname]
    existing_fields_set = set(existing_fields)

    final_order = [
        fieldname
        for fieldname in preferred_order
        if fieldname in existing_fields_set
    ]

    # ------------------------------------------------------------------
    # AR:
    # يجب تعيين قيمة افتراضية صحيحة للشركة قبل إخفائها؛ لأن حقل
    # Company إلزامي في Leave Application، وFrappe يمنع إخفاء أي
    # حقل إلزامي لا يملك قيمة افتراضية.
    #
    # EN:
    # A valid default Company must be assigned before hiding the field,
    # because Company is mandatory in Leave Application and Frappe does
    # not allow a mandatory field to be hidden without a default value.
    # ------------------------------------------------------------------
    company_field = meta.get_field("company")

    if company_field:
        company_candidates = [
            company_field.default,
            frappe.db.get_single_value(
                "Global Defaults",
                "default_company",
            ),
            frappe.db.get_value(
                "Company",
                {},
                "name",
            ),
        ]

        default_company = next(
            (
                company
                for company in company_candidates
                if company and frappe.db.exists("Company", company)
            ),
            None,
        )

        if not default_company:
            frappe.throw(
                "Unable to hide Company because no default Company "
                "is configured in Global Defaults and no Company "
                "record exists."
            )

        make_property_setter(
            doctype=doctype,
            fieldname="company",
            property="default",
            value=default_company,
            property_type="Data",
        )

        make_property_setter(
            doctype=doctype,
            fieldname="company",
            property="hidden",
            value=1,
            property_type="Check",
        )

    # ------------------------------------------------------------------
    # AR:
    # إضافة سلسلة التسمية المطلوبة إلى خيارات الحقل عند عدم وجودها،
    # ثم اعتمادها كقيمة افتراضية وإخفاء الحقل من الواجهة.
    #
    # EN:
    # Add the required naming series to the field options when missing,
    # then set it as the default value and hide the field from the form.
    # ------------------------------------------------------------------
    required_naming_series = "HR-LAP-.YYYY.-"
    naming_series_field = meta.get_field("naming_series")

    if naming_series_field:
        naming_series_options = [
            option.strip()
            for option in (naming_series_field.options or "").splitlines()
            if option.strip()
        ]

        if required_naming_series not in naming_series_options:
            naming_series_options.insert(0, required_naming_series)

            make_property_setter(
                doctype=doctype,
                fieldname="naming_series",
                property="options",
                value="\n".join(naming_series_options),
                property_type="Text",
            )

        make_property_setter(
            doctype=doctype,
            fieldname="naming_series",
            property="default",
            value=required_naming_series,
            property_type="Text",
        )

        make_property_setter(
            doctype=doctype,
            fieldname="naming_series",
            property="hidden",
            value=1,
            property_type="Check",
        )

    # AR: الاحتفاظ بأي حقول إضافية مستقبلية بدل فقدانها من الواجهة.
    # EN: Preserve any future extra fields instead of dropping them from the UI.
    for fieldname in existing_fields:
        if fieldname not in final_order:
            final_order.append(fieldname)

    make_property_setter(
        doctype=doctype,
        fieldname=None,
        property="field_order",
        value=json.dumps(final_order),
        property_type="Text",
        for_doctype=True,
    )

    # ------------------------------------------------------------------
    # AR: إخفاء الحقول والأقسام غير المطلوبة في الواجهة النهائية.
    # EN: Hide fields and sections that should not appear in the final UI.
    # ------------------------------------------------------------------
    fields_to_hide = [
        # AR: naming_series وcompany تمت معالجتهما أعلاه بعد ضبط القيم الافتراضية.
        # EN: naming_series and company are handled above after setting defaults.
        "department",
        "employee_name",

        # AR: إخفاء حقل المسؤول المباشر من الواجهة مع إبقائه داخليًا.
        # EN: Hide the reports_to field from the UI while preserving it internally.
        "reports_to",

        "section_break_7",
        "leave_approver",
        "leave_approver_name",
        "follow_via_email",
        "column_break_18",
        "posting_date",
        "status",

        "sb_other_details",
        "salary_slip",
        "color",
        "column_break_17",
        "letter_head",
        "amended_from",

        "custom_direct_manager_section",
        # AR: إخفاء حالة اعتماد المسؤول المباشر من واجهة الموظف.
        # EN: Hide Direct Manager Approval Status from the employee-facing form.
        "custom_direct_manager_approval",
        "custom_substitute_section",
        "custom_substitute_user",
        "custom_direct_manager_user",
        "custom_direct_manager_secretary_employee",
        "custom_direct_manager_secretary_user",

        "half_day_date",
        "leave_balance",
        "custom_leave_period",
        "from_time",
        "to_time",
    ]

    for fieldname in fields_to_hide:
        if meta.has_field(fieldname):
            make_property_setter(
                doctype=doctype,
                fieldname=fieldname,
                property="hidden",
                value=1,
                property_type="Check",
            )

    # ------------------------------------------------------------------
    # AR: إظهار الحقول التي نحتاجها صراحةً في الواجهة الجديدة.
    # EN: Explicitly show the fields needed in the new layout.
    # ------------------------------------------------------------------
    fields_to_show = [
        "custom_substitute_employee",
        "custom_substitute_approval",
        "custom_balance_section",
        "custom_actual_leave_balance",
        "custom_balance_after_this_request",
        "custom_balance_manager_column_break",
        "custom_direct_manager_employee",
        "custom_partial_leave_date",
        "custom_partial_from_time_ar",
        "custom_partial_to_time_ar",
        "custom_partial_time_ar_display",
        "custom_leave_hours",
        "custom_shift_hours",
        "half_day",
        "quarter_day",
        "is_hourly",
        "description",
        "from_date",
        "to_date",
        "total_leave_days",
    ]

    for fieldname in fields_to_show:
        if meta.has_field(fieldname):
            make_property_setter(
                doctype=doctype,
                fieldname=fieldname,
                property="hidden",
                value=0,
                property_type="Check",
            )

    # ------------------------------------------------------------------
    # AR:
    # تنظيم الحقول الشرطية الخاصة بنصف يوم وربع يوم والإجازة بالساعات.
    # EN:
    # Organize conditional fields for Half Day, Quarter Day, and Hourly Leave.
    # ------------------------------------------------------------------
    partial_eval = "eval:doc.half_day == 1 || doc.quarter_day == 1 || doc.is_hourly == 1"
    hourly_eval = "eval:doc.is_hourly == 1"

    conditional_fields = {
        "custom_partial_leave_date": partial_eval,
        "custom_partial_from_time_ar": partial_eval,
        "custom_partial_to_time_ar": hourly_eval,
        "custom_partial_time_ar_display": partial_eval,
        "custom_leave_hours": partial_eval,
        "custom_shift_hours": partial_eval,
    }

    for fieldname, depends_on in conditional_fields.items():
        if meta.has_field(fieldname):
            make_property_setter(
                doctype=doctype,
                fieldname=fieldname,
                property="depends_on",
                value=depends_on,
                property_type="Data",
            )

    # ------------------------------------------------------------------
    # AR:
    # تحسين العناوين العربية/الإنجليزية للحقول الظاهرة في القسم العلوي
    # وقسم رصيد الإجازة والمسؤول المباشر.
    # EN:
    # Improve field labels for the top area and for balance/direct-manager fields.
    # ------------------------------------------------------------------
    label_updates = {
        "custom_substitute_employee": "Substitute Employee",
        "custom_substitute_approval": "Substitute Approval Status",
        "custom_balance_section": "Actual Leave Balance",
        "custom_direct_manager_employee": "Direct Manager",
        "custom_direct_manager_approval": "Direct Manager Approval Status",
    }

    for fieldname, label in label_updates.items():
        if meta.has_field(fieldname):
            make_property_setter(
                doctype=doctype,
                fieldname=fieldname,
                property="label",
                value=label,
                property_type="Data",
            )

    frappe.clear_cache(doctype=doctype)


# ==========================================
# إعدادات الخصائص (Property Setters)
# ==========================================

def fix_leave_decimal_precision():
    # AR: ضبط الدقة العشرية لحقول أرصدة وأيام الإجازة.
    # EN: Set decimal precision for leave balance and day fields.
    """
    AR: تنفيذ `fix` الإجازة `decimal` `precision` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute fix leave decimal precision within the `setup_leave_and_shift` module.
    """
    fields = {
        "Leave Application": [
            "leave_balance",
            "total_leave_days",
            "custom_leave_hours",
            "custom_shift_hours",
            "custom_actual_leave_balance",
            "custom_balance_after_this_request",
        ],
    }

    for doctype, fieldnames in fields.items():
        for fieldname in fieldnames:
            if frappe.get_meta(doctype).has_field(fieldname):
                make_property_setter(
                    doctype=doctype,
                    fieldname=fieldname,
                    property="precision",
                    value="4",
                    property_type="Data",
                )


def fix_leave_application_link_permissions():
    # AR: تصحيح خصائص روابط الموظفين لمنع قيود صلاحيات غير مقصودة.
    # EN: Correct Employee link properties to avoid unintended restrictions.
    """
    AR: تنفيذ `fix` الإجازة `application` `link` الصلاحيات ضمن وحدة `setup_leave_and_shift`.
    EN: Execute fix leave application link permissions within the `setup_leave_and_shift` module.
    """
    fields_to_ignore_user_permissions = [
        "employee",
        "custom_substitute_employee",
        "custom_direct_manager_employee",
        "custom_direct_manager_secretary_employee",
        "custom_substitute_user",
        "custom_direct_manager_user",
        "custom_direct_manager_secretary_user",
    ]

    for fieldname in fields_to_ignore_user_permissions:
        make_property_setter(
            doctype="Leave Application",
            fieldname=fieldname,
            property="ignore_user_permissions",
            value=1,
            property_type="Check",
        )

    make_property_setter(
        doctype="Leave Application",
        fieldname="custom_substitute_employee",
        property="reqd",
        value=0,
        property_type="Check",
    )

    make_property_setter(
        doctype="Leave Application",
        fieldname="custom_substitute_approval",
        property="options",
        value="\nPending\nApproved\nRejected\nBypassed",
        property_type="Text",
    )

    make_property_setter(
        doctype="Leave Application",
        fieldname="custom_substitute_approval",
        property="default",
        value="",
        property_type="Text",
    )


def set_employee_link_fields_to_show_employee_name():
    # AR: ضبط حقول الربط لعرض اسم الموظف بدل المعرّف.
    # EN: Configure Employee links to display employee names.
    """
    AR: تنفيذ تعيين الموظف `link` الحقول `to` `show` الموظف `name` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute set employee link fields to show employee name within the `setup_leave_and_shift` module.
    """

    frappe.db.set_value(
        "DocType",
        "Employee",
        "title_field",
        "employee_name",
        update_modified=False,
    )

    frappe.db.set_value(
        "DocType",
        "Employee",
        "show_title_field_in_link",
        1,
        update_modified=False,
    )

    frappe.clear_cache(doctype="Employee")
    frappe.clear_cache(doctype=LEAVE_APPLICATION_DOCTYPE)
    frappe.clear_cache()

# ==========================================
# إعدادات سير العمل / Workflow Setup
# ==========================================

def get_system_manager_workflow_transitions():
    # AR: إرجاع انتقالات سير العمل المخصصة لمدير النظام.
    # EN: Return workflow transitions reserved for System Manager.
    """
    AR: تنفيذ استرجاع `system` المدير سير العمل `transitions` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute get system manager workflow transitions within the `setup_leave_and_shift` module.
    """
    return [
        {"state": STATE_DRAFT, "action": ACTION_SEND_TO_SUBSTITUTE, "next_state": STATE_WAITING_SUBSTITUTE, "allowed": SYSTEM_MANAGER_ROLE, "condition": "doc.custom_substitute_user and doc.custom_direct_manager_user"},
        {"state": STATE_DRAFT, "action": ACTION_SEND_TO_DIRECT_MANAGER, "next_state": STATE_WAITING_DIRECT_MANAGER, "allowed": SYSTEM_MANAGER_ROLE, "condition": "doc.custom_direct_manager_user"},
        {"state": STATE_DRAFT, "action": ACTION_FINAL_APPROVE, "next_state": STATE_APPROVED, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_DRAFT, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_SUBSTITUTE_APPROVE, "next_state": STATE_WAITING_DIRECT_MANAGER, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_DIRECT_MANAGER_APPROVE, "next_state": STATE_WAITING_HR_MANAGER, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_FINAL_APPROVE, "next_state": STATE_APPROVED, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_WAITING_DIRECT_MANAGER, "action": ACTION_DIRECT_MANAGER_APPROVE, "next_state": STATE_WAITING_HR_MANAGER, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_WAITING_DIRECT_MANAGER, "action": ACTION_FINAL_APPROVE, "next_state": STATE_APPROVED, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_WAITING_DIRECT_MANAGER, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_WAITING_HR_MANAGER, "action": ACTION_FINAL_APPROVE, "next_state": STATE_APPROVED, "allowed": SYSTEM_MANAGER_ROLE},
        {"state": STATE_WAITING_HR_MANAGER, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": SYSTEM_MANAGER_ROLE},
    ]


def get_hr_manager_override_transitions():
    """
    AR: تنفيذ استرجاع `hr` المدير `override` `transitions` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute get hr manager override transitions within the `setup_leave_and_shift` module.

    DETAILS / التفاصيل:
    AR:
            يمنح مدير الموارد البشرية صلاحية الاعتماد النهائي أو الرفض
            من أي مرحلة نشطة في سير العمل، بما فيها المسودة، دون انتظار
            الموظف البديل أو المسؤول المباشر.

        EN:
            Allows HR Manager to finally approve or reject from any active
            workflow stage, including Draft, without waiting for the
            substitute or direct manager.
    """
    return [
        # AR: الموارد البشرية تستطيع الحسم من المسودة مباشرة.
        # EN: HR can make the final decision directly from Draft.
        {"state": STATE_DRAFT, "action": ACTION_FINAL_APPROVE, "next_state": STATE_APPROVED, "allowed": HR_MANAGER_ROLE},
        {"state": STATE_DRAFT, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": HR_MANAGER_ROLE},

        # AR: الموارد البشرية تستطيع الحسم أثناء انتظار البديل.
        # EN: HR can decide while waiting for the substitute.
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_FINAL_APPROVE, "next_state": STATE_APPROVED, "allowed": HR_MANAGER_ROLE},
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": HR_MANAGER_ROLE},

        # AR: الموارد البشرية تستطيع الحسم أثناء انتظار المسؤول المباشر.
        # EN: HR can decide while waiting for the direct manager.
        {"state": STATE_WAITING_DIRECT_MANAGER, "action": ACTION_FINAL_APPROVE, "next_state": STATE_APPROVED, "allowed": HR_MANAGER_ROLE},
        {"state": STATE_WAITING_DIRECT_MANAGER, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": HR_MANAGER_ROLE},

        # AR: المرحلة الطبيعية للموارد البشرية.
        # EN: Normal HR approval stage.
        {"state": STATE_WAITING_HR_MANAGER, "action": ACTION_FINAL_APPROVE, "next_state": STATE_APPROVED, "allowed": HR_MANAGER_ROLE},
        {"state": STATE_WAITING_HR_MANAGER, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": HR_MANAGER_ROLE},
    ]


def create_leave_application_workflow():
    # AR: إنشاء أو تحديث سير عمل طلب الإجازة.
    # EN: Create or update the Leave Application workflow.
    """
    AR: تنفيذ إنشاء الإجازة `application` سير العمل ضمن وحدة `setup_leave_and_shift`.
    EN: Execute create leave application workflow within the `setup_leave_and_shift` module.
    """
    create_leave_workflow_actions()
    create_leave_workflow_states()

    existing_workflow_name = frappe.db.get_value(
        "Workflow",
        {
            "workflow_name": WORKFLOW_NAME,
            "document_type": LEAVE_APPLICATION_DOCTYPE,
        },
        "name",
    )

    if existing_workflow_name:
        workflow = frappe.get_doc("Workflow", existing_workflow_name)
        workflow.set("states", [])
        workflow.set("transitions", [])
    else:
        workflow = frappe.new_doc("Workflow")

    workflow.workflow_name = WORKFLOW_NAME
    workflow.document_type = LEAVE_APPLICATION_DOCTYPE
    workflow.is_active = 1
    workflow.workflow_state_field = "workflow_state"
    workflow.send_email_alert = 0

    workflow_states = [
        {"state": STATE_DRAFT, "doc_status": 0, "allow_edit": EMPLOYEE_ROLE, "update_field": "status", "update_value": "Open"},
        {"state": STATE_WAITING_SUBSTITUTE, "doc_status": 0, "allow_edit": ALL_ROLE, "update_field": "status", "update_value": "Open"},
        {"state": STATE_WAITING_DIRECT_MANAGER, "doc_status": 0, "allow_edit": ALL_ROLE, "update_field": "status", "update_value": "Open"},
        {"state": STATE_WAITING_HR_MANAGER, "doc_status": 0, "allow_edit": HR_MANAGER_ROLE, "update_field": "status", "update_value": "Open"},
        {"state": STATE_APPROVED, "doc_status": 1, "allow_edit": HR_MANAGER_ROLE, "update_field": "status", "update_value": "Approved"},
        {"state": STATE_REJECTED, "doc_status": 0, "allow_edit": HR_MANAGER_ROLE, "update_field": "status", "update_value": "Rejected"},
    ]

    workflow_transitions = [
        {"state": STATE_DRAFT, "action": ACTION_SEND_TO_SUBSTITUTE, "next_state": STATE_WAITING_SUBSTITUTE, "allowed": EMPLOYEE_ROLE, "condition": "doc.custom_substitute_user and doc.custom_direct_manager_user"},
        {"state": STATE_DRAFT, "action": ACTION_SEND_TO_DIRECT_MANAGER, "next_state": STATE_WAITING_DIRECT_MANAGER, "allowed": EMPLOYEE_ROLE, "condition": "doc.custom_direct_manager_user and not doc.custom_substitute_user"},
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_SUBSTITUTE_APPROVE, "next_state": STATE_WAITING_DIRECT_MANAGER, "allowed": ALL_ROLE, "condition": "doc.custom_substitute_user == frappe.session.user"},
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_REJECT, "next_state": STATE_DRAFT, "allowed": ALL_ROLE, "condition": "doc.custom_substitute_user == frappe.session.user"},
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_DIRECT_MANAGER_APPROVE, "next_state": STATE_WAITING_HR_MANAGER, "allowed": ALL_ROLE, "condition": "doc.custom_direct_manager_user == frappe.session.user"},
        {"state": STATE_WAITING_SUBSTITUTE, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": ALL_ROLE, "condition": "doc.custom_direct_manager_user == frappe.session.user"},
        {"state": STATE_WAITING_DIRECT_MANAGER, "action": ACTION_DIRECT_MANAGER_APPROVE, "next_state": STATE_WAITING_HR_MANAGER, "allowed": ALL_ROLE, "condition": "doc.custom_direct_manager_user == frappe.session.user"},
        {"state": STATE_WAITING_DIRECT_MANAGER, "action": ACTION_REJECT, "next_state": STATE_REJECTED, "allowed": ALL_ROLE, "condition": "doc.custom_direct_manager_user == frappe.session.user"},
    ]

    # AR:
    # إضافة صلاحيات HR Manager من جميع المراحل النشطة:
    # Draft، انتظار البديل، انتظار المسؤول المباشر، وانتظار الموارد البشرية.
    #
    # EN:
    # Add HR Manager final approve/reject transitions from every active stage:
    # Draft, substitute, direct-manager, and HR waiting states.
    workflow_transitions.extend(get_hr_manager_override_transitions())

    workflow_transitions.extend(get_system_manager_workflow_transitions())

    for row in workflow_states:
        workflow.append(
            "states",
            {
                "state": row["state"],
                "doc_status": row["doc_status"],
                "allow_edit": row["allow_edit"],
                "update_field": row["update_field"],
                "update_value": row["update_value"],
            },
        )

    for row in workflow_transitions:
        transition = {
            "state": row["state"],
            "action": row["action"],
            "next_state": row["next_state"],
            "allowed": row["allowed"],
            "allow_self_approval": 1,
        }

        if row.get("condition"):
            transition["condition"] = row["condition"]

        workflow.append("transitions", transition)

    if existing_workflow_name:
        workflow.save(ignore_permissions=True)
    else:
        workflow.insert(ignore_permissions=True)

    deactivate_other_leave_workflows(workflow.name)


def create_leave_workflow_actions():
    # AR: إنشاء إجراءات سير عمل الإجازة المطلوبة.
    # EN: Create required leave workflow actions.
    """
    AR: تنفيذ إنشاء الإجازة سير العمل `actions` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute create leave workflow actions within the `setup_leave_and_shift` module.
    """
    actions = [
        ACTION_SEND_TO_SUBSTITUTE, ACTION_SEND_TO_DIRECT_MANAGER,
        ACTION_SUBSTITUTE_APPROVE, ACTION_DIRECT_MANAGER_APPROVE,
        ACTION_FINAL_APPROVE, ACTION_REJECT,
    ]

    for action in actions:
        if frappe.db.exists("Workflow Action Master", action):
            continue
        frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(ignore_permissions=True)


def create_leave_workflow_states():
    # AR: إنشاء حالات سير عمل الإجازة المطلوبة.
    # EN: Create required leave workflow states.
    """
    AR: تنفيذ إنشاء الإجازة سير العمل `states` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute create leave workflow states within the `setup_leave_and_shift` module.
    """
    states = [
        STATE_DRAFT, STATE_WAITING_SUBSTITUTE, STATE_WAITING_DIRECT_MANAGER,
        STATE_WAITING_HR_MANAGER, STATE_APPROVED, STATE_REJECTED,
    ]

    for state in states:
        if frappe.db.exists("Workflow State", state):
            continue
        frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": get_workflow_state_style(state)}).insert(ignore_permissions=True)


def get_workflow_state_style(state):
    # AR: تحديد لون ونمط حالة سير العمل.
    # EN: Return the color style for a workflow state.
    """
    AR: تنفيذ استرجاع سير العمل الحالة `style` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute get workflow state style within the `setup_leave_and_shift` module.
    """
    if state == STATE_APPROVED: return "Success"
    if state == STATE_REJECTED: return "Danger"
    if state in [STATE_WAITING_SUBSTITUTE, STATE_WAITING_DIRECT_MANAGER, STATE_WAITING_HR_MANAGER]: return "Warning"
    return "Primary"


def deactivate_other_leave_workflows(active_workflow_name):
    # AR: تعطيل مسارات الإجازة الأخرى المتعارضة.
    # EN: Deactivate conflicting Leave Application workflows.
    """
    AR: تنفيذ `deactivate` `other` الإجازة `workflows` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute deactivate other leave workflows within the `setup_leave_and_shift` module.
    """
    workflows = frappe.get_all("Workflow", filters={"document_type": LEAVE_APPLICATION_DOCTYPE}, pluck="name")
    for workflow_name in workflows:
        if workflow_name != active_workflow_name:
            frappe.db.set_value("Workflow", workflow_name, "is_active", 0)


# ==========================================
# دوال الحذف / Cleanup Functions
# ==========================================

def delete_custom_fields(custom_fields: dict):
    # AR: حذف الحقول المخصصة المحددة عند إزالة التطبيق.
    # EN: Delete selected custom fields during uninstall.
    """
    AR: تنفيذ حذف `custom` الحقول ضمن وحدة `setup_leave_and_shift`.
    EN: Execute delete custom fields within the `setup_leave_and_shift` module.
    """
    for doctype, fields in custom_fields.items():
        frappe.db.delete(
            "Custom Field",
            {"fieldname": ("in", [field["fieldname"] for field in fields]), "dt": doctype},
        )
        frappe.clear_cache(doctype=doctype)


def delete_leave_application_workflow():
    # AR: حذف سير عمل طلب الإجازة التابع للتطبيق.
    # EN: Delete the app-owned Leave Application workflow.
    """
    AR: تنفيذ حذف الإجازة `application` سير العمل ضمن وحدة `setup_leave_and_shift`.
    EN: Execute delete leave application workflow within the `setup_leave_and_shift` module.
    """
    workflow_name = frappe.db.get_value(
        "Workflow",
        {"workflow_name": WORKFLOW_NAME, "document_type": LEAVE_APPLICATION_DOCTYPE},
        "name",
    )
    if workflow_name:
        frappe.delete_doc("Workflow", workflow_name, ignore_permissions=True, force=True)

def create_employee_name_display_fields():
    # AR: إنشاء حقول أسماء الموظفين المستخدمة للعرض.
    # EN: Create Employee-name fields used for display.
    """
    AR: تنفيذ إنشاء الموظف `name` `display` الحقول ضمن وحدة `setup_leave_and_shift`.
    EN: Execute create employee name display fields within the `setup_leave_and_shift` module.
    """
    pass

def remove_extra_employee_name_display_fields():
    # AR: إزالة حقول أسماء العرض القديمة أو الزائدة.
    # EN: Remove obsolete Employee-name display fields.
    """
    AR: تنفيذ إزالة `extra` الموظف `name` `display` الحقول ضمن وحدة `setup_leave_and_shift`.
    EN: Execute remove extra employee name display fields within the `setup_leave_and_shift` module.
    """
    pass

# ==========================================
# استعادة واجهة طلب الإجازة الأصلية مع إبقاء سير العمل والصلاحيات
# Restore original Leave Application UI while keeping workflow and permissions
# ==========================================

EXTRA_LEAVE_LAYOUT_FIELDS = {
    "custom_leave_request_tab",
    "custom_approval_tab",
    "custom_other_details_tab",
    "custom_employee_info_section",
    "custom_employee_info_column",
    "custom_leave_details_section",
    "custom_leave_details_column",
    "custom_approval_route_section",
    "custom_approval_route_column",
    "custom_hr_approval_section",
    "custom_request_summary_section",
    "custom_request_summary_column",
    "custom_leave_duration_section",
    "custom_leave_duration_column",
    "custom_partial_details_section",
    "custom_partial_details_column",
    "custom_approval_summary_section",
    "custom_approval_summary_column",
    "custom_reason_section",
    "custom_balance_column",
    "custom_employee_designation",
    "custom_substitute_employee_name",
    "custom_direct_manager_employee_name",
    "custom_direct_manager_secretary_name",
}

LEAVE_LAYOUT_PROPERTY_NAMES = {
    "insert_after",
    "hidden",
    "depends_on",
    "mandatory_depends_on",
    "collapsible",
    "collapsible_depends_on",
}


def restore_original_leave_ui_keep_workflow():
    """
    AR: تنفيذ استعادة `original` الإجازة `ui` `keep` سير العمل ضمن وحدة `setup_leave_and_shift`.
    EN: Execute restore original leave ui keep workflow within the `setup_leave_and_shift` module.

    DETAILS / التفاصيل:
    AR:
            يعيد واجهة Leave Application إلى حقول وترتيب مشروع Masar Requests الأصلي،
            ويحذف فقط حقول التخطيط والتخصيصات البصرية التي أضيفت لاحقاً.
            بعد ذلك يعيد بناء سير العمل بالتعديلات المطلوبة:
            - ظهور إجراءات البديل والمسؤول المباشر بناءً على المستخدم الفعلي.
            - قدرة HR Manager على الاعتماد النهائي أو الرفض من أي مرحلة نشطة، بما فيها المسودة.
            لا يغيّر ملف صلاحيات Leave Application ولا بيانات الطلبات.

        EN:
            Restores the original Masar Requests Leave Application fields and order,
            removes only later UI-layout additions, then rebuilds the workflow
            with the required manager transitions and HR override from every active stage.
            It does not alter the Leave Application permission module or request data.
    """
    deleted_property_setters = 0
    deleted_layout_fields = 0

    # AR: إزالة تعديلات التخطيط والإخفاء من Leave Application فقط.
    # EN: Remove only layout/visibility Property Setters for Leave Application.
    setters = frappe.get_all(
        "Property Setter",
        filters={
            "doc_type": LEAVE_APPLICATION_DOCTYPE,
            "property": ["in", sorted(LEAVE_LAYOUT_PROPERTY_NAMES)],
        },
        pluck="name",
    )

    for setter_name in setters:
        frappe.delete_doc(
            "Property Setter",
            setter_name,
            ignore_permissions=True,
            force=True,
        )
        deleted_property_setters += 1

    # AR: حذف حقول التخطيط الإضافية فقط؛ لا تُحذف حقول الإجازة الفعلية.
    # EN: Delete UI-only layout fields; functional leave fields are preserved.
    for fieldname in sorted(EXTRA_LEAVE_LAYOUT_FIELDS):
        custom_field_name = frappe.db.get_value(
            "Custom Field",
            {"dt": LEAVE_APPLICATION_DOCTYPE, "fieldname": fieldname},
            "name",
        )
        if custom_field_name:
            frappe.delete_doc(
                "Custom Field",
                custom_field_name,
                ignore_permissions=True,
                force=True,
            )
            deleted_layout_fields += 1

    # AR: إعادة إنشاء حقول المشروع الأصلية، بما فيها حقول السكرتير المخفية.
    # EN: Recreate the original project fields, including hidden secretary fields.
    create_custom_fields(get_leave_and_shift_custom_fields(), update=True)
    create_custom_fields(get_direct_manager_secretary_fields(), update=True)

    # AR: إعادة الخصائص الفنية الأصلية فقط.
    # EN: Restore only the original technical field properties.
    fix_leave_application_link_permissions()
    fix_leave_decimal_precision()

    # AR: إعادة بناء سير العمل بالتعديلات المطلوبة دون تغيير ملف الصلاحيات.
    # EN: Rebuild the workflow with the required changes, without touching permissions code.
    create_leave_application_workflow()

    frappe.clear_cache(doctype=LEAVE_APPLICATION_DOCTYPE)
    frappe.clear_cache()

    return {
        "status": "ok",
        "ui": "original_masar_requests_layout",
        "deleted_layout_property_setters": deleted_property_setters,
        "deleted_extra_layout_fields": deleted_layout_fields,
        "workflow_rebuilt": True,
        "permissions_file_changed": False,
        "leave_data_changed": False,
    }

# MASAR_LEAVE_LAYOUT_SOURCE_V21_8
def _masar_apply_leave_layout_v218():
    """
    AR: تنفيذ `masar` تطبيق الإجازة `layout` `v218` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute masar apply leave layout v218 within the `setup_leave_and_shift` module.

    DETAILS / التفاصيل:
    Keep Leave Application on one page with dates always visible:
        - right column: From Date, To Date, partial-leave options;
        - left column: Reason and Total Leave Days.
    """
    import json

    import frappe
    from frappe.custom.doctype.property_setter.property_setter import (
        make_property_setter,
    )

    doctype = "Leave Application"
    meta = frappe.get_meta(doctype, cached=False)

    existing_fields = [
        field.fieldname
        for field in meta.fields
        if field.fieldname
    ]
    existing_set = set(existing_fields)

    preferred_order = [
        "workflow_state",
        "naming_series",

        "employee",
        "custom_substitute_employee",
        "column_break_4",
        "leave_type",

        "company",
        "department",
        "employee_name",

        "section_break_5",

        "from_date",
        "to_date",
        "half_day",
        "quarter_day",
        "is_hourly",
        "custom_partial_leave_date",
        "custom_partial_from_time_ar",
        "custom_partial_to_time_ar",
        "custom_partial_time_ar_display",
        "custom_leave_hours",
        "custom_shift_hours",

        "column_break1",
        "description",
        "total_leave_days",

        "half_day_date",
        "custom_leave_period",
        "from_time",
        "to_time",
        "leave_balance",

        "custom_balance_section",
        "custom_actual_leave_balance",
        "custom_balance_after_this_request",
        "custom_balance_manager_column_break",
        "custom_direct_manager_employee",
        "custom_direct_manager_approval",
        "custom_direct_manager_user",
        "custom_direct_manager_secretary_employee",
        "custom_direct_manager_secretary_user",
        "custom_direct_manager_section",

        "custom_substitute_section",
        "custom_substitute_approval",
        "custom_substitute_user",

        "section_break_7",
        "leave_approver",
        "leave_approver_name",
        "follow_via_email",
        "column_break_18",
        "posting_date",
        "status",

        "sb_other_details",
        "salary_slip",
        "color",
        "column_break_17",
        "letter_head",
        "amended_from",
    ]

    final_order = [
        fieldname
        for fieldname in preferred_order
        if fieldname in existing_set
    ]

    for fieldname in existing_fields:
        if fieldname not in final_order:
            final_order.append(fieldname)

    make_property_setter(
        doctype=doctype,
        fieldname=None,
        property="field_order",
        value=json.dumps(final_order),
        property_type="Text",
        for_doctype=True,
    )

    fields_to_show = (
        "section_break_5",
        "column_break1",
        "from_date",
        "to_date",
        "description",
        "half_day",
        "quarter_day",
        "is_hourly",
        "total_leave_days",
        "custom_substitute_employee",
    )

    for fieldname in fields_to_show:
        if not meta.has_field(fieldname):
            continue

        make_property_setter(
            doctype=doctype,
            fieldname=fieldname,
            property="hidden",
            value=0,
            property_type="Check",
        )

    core_fields = (
        "from_date",
        "to_date",
        "description",
    )

    for fieldname in core_fields:
        if not meta.has_field(fieldname):
            continue

        make_property_setter(
            doctype=doctype,
            fieldname=fieldname,
            property="depends_on",
            value="",
            property_type="Data",
        )

    if meta.has_field("section_break_5"):
        make_property_setter(
            doctype=doctype,
            fieldname="section_break_5",
            property="label",
            value="Dates and Reason",
            property_type="Data",
        )

    frappe.clear_cache(doctype=doctype)
    frappe.clear_cache()

    return {
        "doctype": doctype,
        "field_order": final_order,
    }


# Override both historical setup entry points so future installs/migrations
# cannot restore the old hidden-date layout.
def apply_leave_application_layout_preferences():
    """
    AR: تنفيذ تطبيق الإجازة `application` `layout` `preferences` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute apply leave application layout preferences within the `setup_leave_and_shift` module.
    """
    return _masar_apply_leave_layout_v218()


def reorder_leave_application_fields():
    """
    AR: تنفيذ `reorder` الإجازة `application` الحقول ضمن وحدة `setup_leave_and_shift`.
    EN: Execute reorder leave application fields within the `setup_leave_and_shift` module.
    """
    return _masar_apply_leave_layout_v218()


# MASAR_LEAVE_LAYOUT_SOURCE_V21_8_1
def _masar_apply_leave_layout_v218():
    """
    AR: تنفيذ `masar` تطبيق الإجازة `layout` `v218` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute masar apply leave layout v218 within the `setup_leave_and_shift` module.

    DETAILS / التفاصيل:
    Final Leave Application layout:
        - partial options first;
        - normal From/To dates immediately below the three options;
        - normal dates are hidden when any partial option is selected.
    """
    import json

    import frappe
    from frappe.custom.doctype.property_setter.property_setter import (
        make_property_setter,
    )

    doctype = "Leave Application"
    meta = frappe.get_meta(doctype, cached=False)

    existing_fields = [
        field.fieldname
        for field in meta.fields
        if field.fieldname
    ]
    existing_set = set(existing_fields)

    preferred_order = [
        "workflow_state",
        "naming_series",

        "employee",
        "custom_substitute_employee",
        "column_break_4",
        "leave_type",

        "company",
        "department",
        "employee_name",

        "section_break_5",

        # The three partial-leave options.
        "half_day",
        "quarter_day",
        "is_hourly",

        # Normal date range must appear last under the three options.
        "from_date",
        "to_date",

        # Fields used by the selected partial-leave mode.
        "half_day_date",
        "custom_partial_leave_date",
        "custom_partial_from_time_ar",
        "custom_partial_to_time_ar",
        "custom_partial_time_ar_display",
        "custom_leave_hours",
        "custom_shift_hours",
        "custom_leave_period",
        "from_time",
        "to_time",

        "column_break1",
        "description",
        "total_leave_days",
        "leave_balance",

        "custom_balance_section",
        "custom_actual_leave_balance",
        "custom_balance_after_this_request",
        "custom_balance_manager_column_break",
        "custom_direct_manager_employee",
        "custom_direct_manager_approval",
        "custom_direct_manager_user",
        "custom_direct_manager_secretary_employee",
        "custom_direct_manager_secretary_user",
        "custom_direct_manager_section",

        "custom_substitute_section",
        "custom_substitute_approval",
        "custom_substitute_user",

        "section_break_7",
        "leave_approver",
        "leave_approver_name",
        "follow_via_email",
        "column_break_18",
        "posting_date",
        "status",

        "sb_other_details",
        "salary_slip",
        "color",
        "column_break_17",
        "letter_head",
        "amended_from",
    ]

    final_order = [
        fieldname
        for fieldname in preferred_order
        if fieldname in existing_set
    ]

    for fieldname in existing_fields:
        if fieldname not in final_order:
            final_order.append(fieldname)

    make_property_setter(
        doctype=doctype,
        fieldname=None,
        property="field_order",
        value=json.dumps(final_order),
        property_type="Text",
        for_doctype=True,
    )

    always_visible = (
        "section_break_5",
        "column_break1",
        "half_day",
        "quarter_day",
        "is_hourly",
        "description",
        "total_leave_days",
        "custom_substitute_employee",
    )

    for fieldname in always_visible:
        if not meta.has_field(fieldname):
            continue

        make_property_setter(
            doctype=doctype,
            fieldname=fieldname,
            property="hidden",
            value=0,
            property_type="Check",
        )

    normal_date_condition = (
        "eval:!doc.half_day && !doc.quarter_day && !doc.is_hourly"
    )

    for fieldname in ("from_date", "to_date"):
        if not meta.has_field(fieldname):
            continue

        make_property_setter(
            doctype=doctype,
            fieldname=fieldname,
            property="hidden",
            value=0,
            property_type="Check",
        )
        make_property_setter(
            doctype=doctype,
            fieldname=fieldname,
            property="depends_on",
            value=normal_date_condition,
            property_type="Data",
        )

    if meta.has_field("description"):
        make_property_setter(
            doctype=doctype,
            fieldname="description",
            property="hidden",
            value=0,
            property_type="Check",
        )
        make_property_setter(
            doctype=doctype,
            fieldname="description",
            property="depends_on",
            value="",
            property_type="Data",
        )

    if meta.has_field("section_break_5"):
        make_property_setter(
            doctype=doctype,
            fieldname="section_break_5",
            property="label",
            value="Dates and Reason",
            property_type="Data",
        )

    frappe.clear_cache(doctype=doctype)
    frappe.clear_cache()

    return {
        "doctype": doctype,
        "field_order": final_order,
        "normal_date_condition": normal_date_condition,
    }


def apply_leave_application_layout_preferences():
    """
    AR: تنفيذ تطبيق الإجازة `application` `layout` `preferences` ضمن وحدة `setup_leave_and_shift`.
    EN: Execute apply leave application layout preferences within the `setup_leave_and_shift` module.
    """
    return _masar_apply_leave_layout_v218()


def reorder_leave_application_fields():
    """
    AR: تنفيذ `reorder` الإجازة `application` الحقول ضمن وحدة `setup_leave_and_shift`.
    EN: Execute reorder leave application fields within the `setup_leave_and_shift` module.
    """
    return _masar_apply_leave_layout_v218()
