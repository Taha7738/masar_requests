# =======================================================================
# 🚀 إعدادات مسار طلب المواد - نظام مسار
# 🚀 Material Request Setup - masar_requests System
# =======================================================================

# AR: استيراد مكتبة فرابي الأساسية للتفاعل مع الخادم وقاعدة البيانات
# EN: Import standard Frappe library to interact with the server and database
# AR: الأيقونات ثابتة خارج دالة الترجمة، بينما النص الإنجليزي داخل frappe._() أو _().
# EN: Icons stay outside the translation call, while English text stays inside frappe._() or _().
import frappe

# AR: استيراد الدوال المسؤولة عن إنشاء وتعديل الحقول والخصائص برمجياً
# EN: Import functions responsible for creating and modifying fields and properties programmatically
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def setup_material_request_all():
    '''
    AR:
        الدالة الرئيسية لإعداد طلب المواد مع المحافظة على منطق سير العمل
        الأصلي، وتطبيق إصلاحات الوصول والمشاركة على الطلبات الحالية.

    EN:
        Main Material Request setup. Preserves the original workflow logic
        and applies access/share fixes to existing requests.
    '''
    print("🚀 " + frappe._("Setting up Material Requests..."))

    create_material_workflow_prerequisites()
    create_material_request_custom_fields()
    modify_material_request_properties()
    grant_employee_base_permissions()
    create_sharing_server_script()
    create_fission_engine_server_script()
    create_material_request_workflow()
    remove_legacy_direct_supervisor_role()
    setup_university_secretary_role()

    if frappe.db.exists("Client Script", "Material Request UI masar_requests"):
        frappe.delete_doc(
            "Client Script",
            "Material Request UI masar_requests",
            ignore_permissions=True,
            force=True,
        )

    # AR: تحديث مشاركات المعاملات القديمة والحالية، ومنها الطلب الموجود عند المخزن.
    # EN: Re-sync existing requests, including requests already at Warehouse stage.
    resync_all_material_request_shares()

    frappe.db.commit()
    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache(doctype="Material Request Item")

    print("✅ " + frappe._("Material Request setup completed successfully."))



def create_material_workflow_prerequisites():
    """
    AR: إنشاء الأدوار، الحالات، والإجراءات المطلوبة لسير العمل
    EN: Create roles, states, and actions required for the workflow
    """
    # AR:
    # لا يتم إنشاء دور Direct Supervisor. المسؤول المباشر يُحدَّد حصراً من
    # Employee.reports_to ثم يُمنح الوصول إلى الطلب المحدد عبر DocShare.
    #
    # EN:
    # Do not create a Direct Supervisor role. The direct supervisor is resolved
    # exclusively from Employee.reports_to and receives document-specific access
    # through DocShare.
    roles = [
        "Warehouse Manager",
        "HR Manager",
        "Accounts Manager",
        "Secretary General",
        "University President",
        "MR Qty Modifier",
        "MR Financial Modifier",
    ]
    for role in roles:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role}).insert(ignore_permissions=True)

    # AR: إنشاء حالات مسار العمل (محدثة للمسميات الإنجليزية القياسية)
    # EN: Create workflow states (updated to standard English names)
    states = ["Draft", "Pending Direct Supervisor", "Pending Stock Check", "Pending HR Manager", "Pending Accounts Manager", "Pending Sec Gen", "Pending President", "Approved", "Rejected"]
    for state in states:
        if not frappe.db.exists("Workflow State", state):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(ignore_permissions=True)

    # AR: إنشاء الإجراءات (الأزرار التي يضغط عليها المستخدم)
    # EN: Create actions (Buttons clicked by the user)
    actions = ["Submit to Direct Supervisor", "Submit (Auto Bypass)", "Direct Supervisor Approve", "Confirm Availability", "HR Manager Approve", "Accounts Manager Approve", "Forward to President", "Final Approve", "Super Final Approval", "Reject"]
    for action in actions:
        if not frappe.db.exists("Workflow Action Master", action):
            frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(ignore_permissions=True)



def remove_legacy_direct_supervisor_role():
    '''
    AR:
        إزالة دور Direct Supervisor القديم بعد تحديث سير العمل، مع حذف
        إسنادات المستخدمين والصلاحيات وإجراءات Workflow القديمة المرتبطة به.

    EN:
        Remove the legacy Direct Supervisor role after updating the workflow,
        including user assignments, permissions, and stale workflow actions.
    '''
    role_name = "Direct Supervisor"

    # AR: إزالة السجلات القديمة التي تربط المستخدمين والصلاحيات بالدور.
    # EN: Remove legacy user assignments, permissions, and pending action links.
    frappe.db.delete("Has Role", {"role": role_name})
    frappe.db.delete("Custom DocPerm", {"role": role_name})

    if frappe.db.exists("DocType", "Workflow Action Permitted Role"):
        workflow_action_names = frappe.get_all(
            "Workflow Action Permitted Role",
            filters={"role": role_name},
            pluck="parent",
        )
        for workflow_action_name in set(workflow_action_names):
            if frappe.db.exists("Workflow Action", workflow_action_name):
                frappe.delete_doc(
                    "Workflow Action",
                    workflow_action_name,
                    ignore_permissions=True,
                    force=True,
                )

    if frappe.db.exists("Role", role_name):
        # AR:
        # لا نستخدم force هنا حتى لا نحذف الدور مع ترك مراجع غير معروفة في
        # تخصيصات أخرى. يجب أن يفشل التحديث بوضوح إن كان الدور مستخدماً خارج
        # هذا المسار بدلاً من إنشاء بيانات يتيمة.
        #
        # EN:
        # Do not force deletion. Unknown external references should stop the
        # migration instead of leaving orphaned links.
        frappe.delete_doc(
            "Role",
            role_name,
            ignore_permissions=True,
        )

    frappe.clear_cache()


def create_material_request_custom_fields():
    '''
    AR:
        إنشاء الحقول المخصصة المطلوبة لطلب المواد مع منع حقول
        المسؤول والسكرتير التقنية من تفعيل قيود User Permission.

    EN:
        Create Material Request custom fields while preventing the
        technical manager/secretary links from triggering User Permissions.
    '''
    old_fields = [
        "custom_direct_manager_user",
        "custom_secretary_user",
        "custom_issued_qty",
    ]

    for fieldname in old_fields:
        for doctype in ("Material Request", "Material Request Item"):
            custom_field_name = frappe.db.get_value(
                "Custom Field",
                {"dt": doctype, "fieldname": fieldname},
                "name",
            )
            if custom_field_name:
                frappe.delete_doc(
                    "Custom Field",
                    custom_field_name,
                    ignore_permissions=True,
                    force=True,
                )

    custom_fields_data = {
        "Material Request": [
            {
                "fieldname": "custom_approval_section1",
                "label": "",
                "fieldtype": "Section Break",
                "insert_after": "schedule_date",
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_reason_for_request",
                "label": "Reason for Request",
                "fieldtype": "Small Text",
                "insert_after": "custom_approval_section1",
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_approval_col_break1",
                "fieldtype": "Column Break",
                "insert_after": "custom_reason_for_request",
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_auto_create_purchase",
                "label": "Auto-Create Purchase for Shortage",
                "fieldtype": "Check",
                "default": "0",
                "insert_after": "custom_approval_col_break1",
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manager_is_top_level",
                "label": "Is Manager Top Level",
                "fieldtype": "Check",
                "default": "0",
                "hidden": 1,
                "insert_after": "custom_auto_create_purchase",
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_approval_section",
                "label": "Approval Workflow",
                "fieldtype": "Section Break",
                "hidden": 1,
                "insert_after": "custom_manager_is_top_level",
                "module": "Masar Requests",
            },
            {
                "fieldname": "reports_to",
                "label": "Direct Supervisor ID",
                "fieldtype": "Link",
                "options": "Employee",
                "insert_after": "custom_approval_section",
                "hidden": 1,
                "read_only": 1,
                # AR: رابط تقني؛ لا يجب أن يمنع أصحاب الأدوار من فتح الطلب.
                # EN: Technical link; must not restrict role users through Employee User Permission.
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_manager_name",
                "label": "Direct Supervisor",
                "fieldtype": "Data",
                "insert_after": "reports_to",
                "hidden": 1,
                "read_only": 1,
                "fetch_from": "reports_to.employee_name",
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_approval_col_break",
                "fieldtype": "Column Break",
                "insert_after": "custom_manager_name",
                "hidden": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_secretary_employee",
                "label": "Secretary ID",
                "fieldtype": "Link",
                "options": "Employee",
                "insert_after": "custom_approval_col_break",
                "hidden": 1,
                "read_only": 1,
                # AR: رابط تقني؛ لا يجب أن يطبق قيود Employee على طلب المواد.
                # EN: Technical link; ignore Employee User Permission on the Material Request.
                "ignore_user_permissions": 1,
                "module": "Masar Requests",
            },
            {
                "fieldname": "custom_secretary_name",
                "label": "Manager Secretary",
                "fieldtype": "Data",
                "insert_after": "custom_secretary_employee",
                "hidden": 1,
                "read_only": 1,
                "fetch_from": "custom_secretary_employee.employee_name",
                "module": "Masar Requests",
            },
        ],
        "Material Request Item": [
            {
                "fieldname": "custom_original_qty",
                "label": "Requested Qty",
                "fieldtype": "Float",
                "insert_after": "qty",
                "read_only": 1,
                "in_list_view": 1,
                "module": "Masar Requests",
            }
        ],
    }

    create_custom_fields(custom_fields_data, update=True)
    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache(doctype="Material Request Item")



def modify_material_request_properties():
    '''
    AR:
        تعديل خصائص واجهة طلب المواد مع إبقاء منطق الكمية الحالي:
        الموظف يحدد الكمية المطلوبة، وأمين المخزن يستطيع تعديل qty
        فقط خلال مرحلة Pending Stock Check.

    EN:
        Configure Material Request UI properties while preserving the
        quantity logic: the employee requests a quantity and the Warehouse
        Manager may adjust qty only during Pending Stock Check.
    '''
    make_property_setter(
        "Material Request",
        "naming_series",
        "default",
        "MAT-MR-.YYYY.-",
        "Text",
    )
    make_property_setter(
        "Material Request",
        "material_request_type",
        "options",
        "\nPurchase\nMaterial Issue",
        "Text",
    )

    fields_to_hide = [
        "terms_tab",
        "more_info_tab",
        "connections_tab",
        "set_warehouse",
        "scan_barcode",
        "naming_series",
    ]
    for fieldname in fields_to_hide:
        make_property_setter(
            "Material Request",
            fieldname,
            "hidden",
            1,
            "Check",
        )

    for fieldname in ("rate", "amount"):
        make_property_setter(
            "Material Request Item",
            fieldname,
            "depends_on",
            "",
            "Data",
        )
        make_property_setter(
            "Material Request Item",
            fieldname,
            "hidden",
            0,
            "Check",
        )
        make_property_setter(
            "Material Request Item",
            fieldname,
            "in_list_view",
            1,
            "Check",
        )

    frappe.db.sql(
        """
        DELETE FROM `tabProperty Setter`
        WHERE doc_type = 'Material Request Item'
          AND field_name IN ('qty', 'rate', 'amount')
          AND property IN ('read_only_depends_on', 'depends_on')
        """
    )

    cols_to_remove = [
        "description",
        "stock_uom",
        "warehouse",
        "schedule_date",
    ]
    for fieldname in cols_to_remove:
        make_property_setter(
            "Material Request Item",
            fieldname,
            "in_list_view",
            0,
            "Check",
        )

    make_property_setter(
        "Material Request Item", "qty", "columns", "1", "Int"
    )
    make_property_setter(
        "Material Request Item", "qty", "label", "Qty", "Data"
    )
    make_property_setter(
        "Material Request Item",
        "custom_original_qty",
        "columns",
        "1",
        "Int",
    )
    make_property_setter(
        "Material Request Item", "uom", "columns", "1", "Int"
    )
    make_property_setter(
        "Material Request Item", "uom", "hidden", 0, "Check"
    )
    make_property_setter(
        "Material Request Item", "uom", "in_list_view", 1, "Check"
    )    
    make_property_setter(
        "Material Request Item", "rate", "columns", "1", "Int"
    )
    make_property_setter(
        "Material Request Item", "amount", "columns", "1", "Int"
    )
    

    # AR:
    # qty قابل للتعديل في ثلاث حالات فقط:
    # 1) المستند جديد/مسودة.
    # 2) أمين المخزن أثناء Pending Stock Check.
    # 3) MR Qty Modifier أو System Manager.
    #
    # EN:
    # qty is editable only for Draft/new documents, Warehouse Manager during
    # Pending Stock Check, or users with MR Qty Modifier/System Manager.
    qty_eval = (
        "eval:!parent.__islocal "
        "&& !(parent.workflow_state === 'Pending Stock Check' "
        "&& frappe.user.has_role('Warehouse Manager')) "
        "&& !frappe.user.has_role('MR Qty Modifier') "
        "&& !frappe.user.has_role('System Manager')"
    )
    make_property_setter(
        "Material Request Item",
        "qty",
        "read_only_depends_on",
        qty_eval,
        "Data",
    )

    fin_eval = (
        "eval:parent.material_request_type !== 'Purchase' "
        "|| (!parent.__islocal "
        "&& !frappe.user.has_role('MR Financial Modifier') "
        "&& !frappe.user.has_role('Accounts Manager') "
        "&& !frappe.user.has_role('System Manager'))"
    )
    make_property_setter(
        "Material Request Item",
        "rate",
        "read_only_depends_on",
        fin_eval,
        "Data",
    )
    make_property_setter(
        "Material Request Item",
        "amount",
        "read_only_depends_on",
        fin_eval,
        "Data",
    )

    

def grant_employee_base_permissions():
    '''
    AR:
        مزامنة صلاحيات الأدوار التي يديرها تطبيق masar_requests فقط، دون حذف
        صلاحيات أدوار أخرى أضافها النظام أو تطبيقات أخرى.

    EN:
        Synchronize only the Material Request roles managed by Masar Requests,
        without deleting permissions owned by other apps or administrators.
    '''
    doctype_name = "Material Request"

    managed_roles = [
        "System Manager",
        "Administrator",
        "Employee",
        # AR: مدرج للحذف فقط؛ لا يعاد إنشاؤه أو منحه صلاحيات.
        # EN: Included for cleanup only; it is not recreated or granted permissions.
        "Direct Supervisor",
        "Warehouse Manager",
        "HR Manager",
        "Accounts Manager",
        "Secretary General",
        "University President",
        "Material Request Secretary",
    ]

    existing_rows = frappe.get_all(
        "Custom DocPerm",
        filters={
            "parent": doctype_name,
            "role": ["in", managed_roles],
        },
        pluck="name",
    )
    for row_name in existing_rows:
        frappe.delete_doc(
            "Custom DocPerm",
            row_name,
            ignore_permissions=True,
            force=True,
        )

    def add_permission(role, **permissions):
        if role != "Administrator" and not frappe.db.exists("Role", role):
            frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role,
                    "desk_access": 1,
                }
            ).insert(ignore_permissions=True)

        row = frappe.new_doc("Custom DocPerm")
        row.update(
            {
                "parent": doctype_name,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": 0,
                **permissions,
            }
        )
        row.insert(ignore_permissions=True)

    for role in ("System Manager", "Administrator"):
        add_permission(
            role,
            read=1,
            write=1,
            create=1,
            delete=1,
            submit=1,
            cancel=1,
            amend=1,
            print=1,
            email=1,
            report=1,
            share=1,
            export=1,
        )

    add_permission(
        "Employee",
        read=1,
        write=1,
        create=1,
        print=1,
        email=1,
        share=1,
        if_owner=1,
    )

    for role in (
        "Warehouse Manager",
        "HR Manager",
        "Accounts Manager",
        "Secretary General",
        "University President",
    ):
        add_permission(
            role,
            read=1,
            write=1,
            submit=1,
            cancel=1,
            print=1,
            email=1,
            share=1,
        )

    # AR: وصول السكرتير إلى المعاملات المحددة يأتي عبر DocShare فقط.
    # EN: Secretary access to specific requests is granted through DocShare only.
    add_permission(
        "Material Request Secretary",
        read=1,
        print=1,
        email=1,
        if_owner=1,
    )

    frappe.clear_cache(doctype=doctype_name)

def create_sharing_server_script():
    """
    Remove the obsolete safe-exec Server Script.

    Material Request sharing is now implemented as a native Python
    doc_events hook in material_request_sharing.py.
    """
    script_name = "Auto Share MR with Direct Supervisor masar_requests"

    if frappe.db.exists("Server Script", script_name):
        frappe.delete_doc(
            "Server Script",
            script_name,
            ignore_permissions=True,
            force=True,
        )


# AR: تم حذف النسخة القديمة المعطلة من محرك الانشطار لمنع الالتباس.
# EN: The obsolete disabled fission-engine version was removed to avoid confusion.

def create_fission_engine_server_script():
    """
    AR: دالة لإنشاء محرك الانشطار (سكربت خلفي): جدار حماية، إشعارات، وانشطار الطلبات مع دعم نظام الترجمة
    EN: Function to create Fission Engine (Backend Script): Firewall, notifications, and splitting with translation support
    """
    
    # AR: تحديد اسم السكربت في قاعدة البيانات / EN: Define the script name in the database
    script_name = "Warehouse Fission Engine masar_requests"
    
    # AR: التحقق من وجود السكربت القديم وحذفه لتحديثه / EN: Check if the old script exists and delete it for updating
    if frappe.db.exists("Server Script", script_name):
        frappe.delete_doc("Server Script", script_name, force=True)
        
    # AR: إنشاء مستند سكربت خادم جديد / EN: Create a new Server Script document
    script = frappe.new_doc("Server Script")
    script.name = script_name
    script.script_type = "DocType Event"
    script.reference_doctype = "Material Request" # AR: ربطه بطلب المواد / EN: Link to Material Request
    script.doctype_event = "Before Save" # AR: التنفيذ قبل الحفظ / EN: Execute Before Save
    
    # AR: كتابة كود بايثون الذي سينفذه السيرفر / EN: Write the Python code that the server will execute
    script.script = """
# =======================================================================
# AR: 1. التحقق مما إذا كان المدير المباشر من القيادة العليا / EN: 1. Check if direct supervisor is top management
# =======================================================================
if doc.reports_to:
    # AR: جلب حساب المستخدم للمدير المباشر / EN: Fetch user ID of direct supervisor
    mgr_user = frappe.db.get_value('Employee', doc.reports_to, 'user_id')
    if mgr_user:
        # AR: جلب جميع أدوار المدير المباشر / EN: Fetch all roles of direct supervisor
        roles_list = frappe.get_all('Has Role', filters={'parent': mgr_user}, fields=['role'])
        mgr_roles = [r.role for r in roles_list]
        
        # AR: إذا كان أميناً عاماً أو رئيساً، يتم تمييزه كقيادة عليا / EN: If Sec Gen or President, mark as top management
        if 'Secretary General' in mgr_roles or 'University President' in mgr_roles:
            doc.custom_manager_is_top_level = 1
        else:
            doc.custom_manager_is_top_level = 0

# AR: الحصول على النسخة القديمة من المستند قبل التعديل / EN: Get the old version of the document before modification
old_doc = doc.get_doc_before_save()

# =======================================================================
# AR: 2. تثبيت الكمية الأصلية في حالة المسودة / EN: 2. Freeze original quantity in Draft state
# =======================================================================
if doc.workflow_state in ['Draft', None]:
    for item in doc.items:
        # AR: حفظ الكمية المدخلة ككمية أصلية قبل أي تعديل / EN: Save entered quantity as original quantity before any edits
        if not item.custom_original_qty:
            item.custom_original_qty = item.qty

# =======================================================================
# 🚨 3. الجدار الناري الخلفي / EN: 3. Backend Firewall
# =======================================================================
if old_doc:
    # AR: جلب أدوار المستخدم الحالي / EN: Fetch roles of current user
    user_roles = [r.role for r in frappe.db.get_all('Has Role', filters={'parent': frappe.session.user}, fields=['role'])]
    
    # AR: أ. حماية حقل الكمية / EN: A. Protect Quantity field
    can_edit_qty = (
        'MR Qty Modifier' in user_roles
        or 'System Manager' in user_roles
        or (
            'Warehouse Manager' in user_roles
            and old_doc.workflow_state == 'Pending Stock Check'
        )
    )

    if not can_edit_qty:
        old_qtys = {d.name: float(d.qty or 0) for d in old_doc.items}
        for item in doc.items:
            # AR: رفض الحفظ إذا تم تغيير الكمية / EN: Reject save if quantity is changed
            if item.name in old_qtys and float(item.qty or 0) != old_qtys[item.name]:
                frappe.throw(
                    "🔒 "
                    + _(
                        "Quantity field is locked. Only Warehouse Manager during Stock Check, MR Qty Modifier, or System Manager can edit it."
                    )
                )
                
    # AR: ب. حماية حقول السعر والتكلفة / EN: B. Protect Rate and Amount fields
    if 'MR Financial Modifier' not in user_roles and 'Accounts Manager' not in user_roles and 'System Manager' not in user_roles:
        old_financials = {d.name: {'rate': float(d.rate or 0), 'amount': float(d.amount or 0)} for d in old_doc.items}
        for item in doc.items:
            if item.name in old_financials:
                # AR: تقريب الأرقام لتجنب أخطاء الكسور الوهمية / EN: Round numbers to avoid phantom decimal errors
                old_rate = round(old_financials[item.name]['rate'], 2)
                old_amount = round(old_financials[item.name]['amount'], 2)
                new_rate = round(float(item.rate or 0), 2)
                new_amount = round(float(item.amount or 0), 2)
                
                # AR: رفض الحفظ إذا تم تغيير السعر / EN: Reject save if rate is changed
                if new_rate != old_rate or new_amount != old_amount:
                    frappe.throw(
                        "🔒 "
                        + _(
                            "Rate fields are locked after saving. You need the 'MR Financial Modifier' role to edit them."
                        )
                    )

# =======================================================================
# 🔔 4. محرك الإشعارات (مع المتغيرات) / EN: 4. Notification Engine (with variables)
# =======================================================================
if old_doc and old_doc.workflow_state != doc.workflow_state:
    try:
        current_state = doc.workflow_state
        owner = doc.owner
        doc_name_str = str(doc.name)
        
        users_to_notify = []
        managers_to_find_secretaries_for = [] 
        alert_msg = ""
        
        # AR: دالة مساعدة لجلب سكرتير المستخدم / EN: Helper function to fetch user's secretary
        def fetch_secretary_for_user(target_user):
            emp = frappe.db.get_value('Employee', {'user_id': target_user}, 'name')
            if emp:
                sec_emp = frappe.db.get_value('Employee', emp, 'custom_secretary_employee')
                if sec_emp:
                    sec_user = frappe.db.get_value('Employee', sec_emp, 'user_id')
                    if sec_user:
                        return sec_user
            return None

        # AR: حالة الرفض / EN: Rejected state
        if current_state == 'Rejected':
            users_to_notify.append(owner)
            owner_sec = fetch_secretary_for_user(owner)
            if owner_sec:
                users_to_notify.append(owner_sec) # AR: إشعار سكرتير المالك / EN: Notify owner's secretary
                
            # AR: نص الترجمة مع تمرير المتغير / EN: Translation text passing the variable
            alert_msg = "❌ " + _("Your Material Request %s has been rejected.") % doc_name_str
                
        # AR: حالة الاعتماد النهائي / EN: Fully Approved state
        elif current_state == 'Approved':
            users_to_notify.append(owner)
            owner_sec = fetch_secretary_for_user(owner)
            if owner_sec:
                users_to_notify.append(owner_sec)
                
            alert_msg = "✅ " + _("Your Material Request %s has been fully approved and is now in progress.") % doc_name_str
            
            # AR: إشعار أمناء المخازن / EN: Notify warehouse managers
            wh_users = frappe.get_all('Has Role', filters={'role': 'Warehouse Manager'}, fields=['parent'])
            for u in wh_users:
                if u and u.parent:
                    users_to_notify.append(u.parent)
                        
        # AR: حالة التحديث العادية / EN: Normal update state
        elif current_state not in ['Draft']:
            users_to_notify.append(owner)
            owner_sec = fetch_secretary_for_user(owner)
            if owner_sec:
                users_to_notify.append(owner_sec)
            
            # AR: تمرير متغيرين: رقم المستند والحالة / EN: Pass two variables: document name and state
            alert_msg = "🔄 " + _("Your Material Request %s has moved to workflow state: %s.") % (doc_name_str, str(current_state))

        # AR: الإدارات المعتمدة / EN: Approving departments
        state_roles = {
            'Pending Stock Check': 'Warehouse Manager',
            'Pending HR Manager': 'HR Manager',
            'Pending Accounts Manager': 'Accounts Manager',
            'Pending Sec Gen': 'Secretary General',
            'Pending President': 'University President'
        }
        
        # AR: إشعار المدير المباشر / EN: Notify Direct Supervisor
        if current_state == 'Pending Direct Supervisor':
            if doc.reports_to:
                mgr_user = frappe.db.get_value('Employee', doc.reports_to, 'user_id')
                if mgr_user:
                    users_to_notify.append(mgr_user)
                    managers_to_find_secretaries_for.append(mgr_user) 
                    
                    alert_msg = "🔔 " + _("Action required: Material Request %s is waiting for your approval.") % doc_name_str
                        
        # AR: إشعار مدراء الإدارات العليا / EN: Notify Top Management Managers
        elif current_state in state_roles:
            role = state_roles[current_state]
            r_users = frappe.get_all('Has Role', filters={'role': role}, fields=['parent'])
            for user in r_users:
                if user and user.parent:
                    users_to_notify.append(user.parent)
                    managers_to_find_secretaries_for.append(user.parent)
                    
                    alert_msg = "🔔 " + _("Action required: Material Request %s has reached your department and is awaiting approval.") % doc_name_str

        # AR: إضافة سكرتارية المدراء لقائمة الإشعار / EN: Add managers' secretaries to notification list
        for m_user in managers_to_find_secretaries_for:
            m_sec = fetch_secretary_for_user(m_user)
            if m_sec:
                users_to_notify.append(m_sec)

        # AR: إرسال الإشعارات / EN: Send notifications
        for target_user in set(users_to_notify): 
            if target_user and target_user != 'Administrator' and target_user != frappe.session.user:
                if frappe.db.exists("User", target_user):
                    notification = frappe.new_doc('Notification Log')
                    notification.subject = alert_msg
                    notification.for_user = target_user
                    notification.document_type = 'Material Request'
                    notification.document_name = doc.name
                    notification.type = 'Alert'
                    notification.insert(ignore_permissions=True)
                    
    except Exception as error:
        # AR: تسجيل الخطأ دون إيقاف حفظ المعاملة / EN: Log the error without blocking document save
        frappe.log_error(
            message=str(error),
            title="⚠️ " + _("Material Request Notification Error"),
        )

# =======================================================================
# ✂️ 5. محرك الانشطار: توليد طلب الشراء / EN: 5. Fission Engine: Auto-purchase generation
# =======================================================================
valid_forward_states = ['Pending HR Manager', 'Pending Accounts Manager', 'Pending Sec Gen', 'Pending President', 'Approved']

# AR: التحقق من الانتقال من حالة فحص المخزون للإمام / EN: Check transition from Stock Check forward
if old_doc and old_doc.workflow_state == 'Pending Stock Check' and doc.workflow_state in valid_forward_states:
    needs_split = False 
    all_zero = True 
    auto_purchase_enabled = doc.custom_auto_create_purchase
    
    # AR: فحص الكميات الناقصة / EN: Check for shortage quantities
    for item in doc.items:
        available_qty = float(item.qty or 0) 
        orig_qty = float(item.custom_original_qty or item.qty or 0) 
        
        if available_qty < orig_qty:
            needs_split = True 
        if available_qty > 0:
            all_zero = False 
            
    if needs_split:
        if auto_purchase_enabled:
            # AR: إذا كانت كل الكميات صفر، حوّل المستند بالكامل لشراء / EN: If all quantities are zero, convert full doc to purchase
            if all_zero:
                doc.material_request_type = 'Purchase'
                for item in doc.items:
                    item.qty = float(item.custom_original_qty or 0)
                frappe.msgprint(
                    "🛒 "
                    + _(
                        "All items are out of stock. The request has been converted to a Purchase request."
                    ),
                    indicator='orange',
                    alert=True,
                )
            else:
                # AR: إنشاء مستند شراء جديد للنواقص / EN: Create a new purchase document for shortages
                new_mr = frappe.new_doc('Material Request')
                new_mr.material_request_type = 'Purchase'
                new_mr.company = doc.company
                new_mr.transaction_date = doc.transaction_date
                new_mr.schedule_date = doc.schedule_date
                new_mr.department = doc.department
                new_mr.owner = doc.owner

                # AR: نسخ بيانات المسار الإداري إلى طلب الشراء الجديد.
                # EN: Copy administrative routing data to the generated purchase request.
                new_mr.reports_to = doc.reports_to
                new_mr.custom_manager_name = doc.custom_manager_name
                new_mr.custom_secretary_employee = doc.custom_secretary_employee
                new_mr.custom_secretary_name = doc.custom_secretary_name
                new_mr.custom_auto_create_purchase = 0
                
                # AR: وضع سبب الطلب مع رقم المعاملة الأصلية / EN: Set request reason with original document ID
                new_mr.custom_reason_for_request = _("Auto-generated from Material Request %s.") % str(doc.name)
                
                # AR: نقل الأصناف الناقصة للمستند الجديد / EN: Transfer shortage items to the new document
                for item in doc.items:
                    orig_qty = float(item.custom_original_qty or item.qty or 0)
                    available_qty = float(item.qty or 0)
                    if available_qty < orig_qty:
                        new_mr.append('items', {
                            'item_code': item.item_code,
                            'qty': orig_qty - available_qty,
                            'uom': item.uom,
                            'schedule_date': item.schedule_date
                        })
                
                # AR: حفظ مستند الشراء الجديد كمسودة مؤقتاً / EN: Save new purchase document temporarily as draft
                new_mr.flags.ignore_workflow = True
                new_mr.insert(ignore_permissions=True) 
                
                # AR: تجاوز مسار العمل ووضعه عند مدير الحسابات / EN: Bypass workflow and place it at Accounts Manager
                frappe.db.set_value('Material Request', new_mr.name, 'workflow_state', 'Pending Accounts Manager')
                
                # AR: مشاركة طلب الشراء الجديد مع الحسابات والأطراف المرتبطة.
                # EN: Share the generated purchase request with Accounts and related parties.
                write_users = []
                read_only_users = [doc.owner]

                if doc.reports_to:
                    mgr_user_id = frappe.db.get_value(
                        'Employee',
                        doc.reports_to,
                        'user_id'
                    )
                    if mgr_user_id:
                        read_only_users.append(mgr_user_id)

                account_rows = frappe.get_all(
                    'Has Role',
                    filters={
                        'role': 'Accounts Manager',
                        'parenttype': 'User'
                    },
                    fields=['parent']
                )

                for account_row in account_rows:
                    account_user = account_row.parent
                    if account_user and frappe.db.get_value('User', account_user, 'enabled'):
                        write_users.append(account_user)

                        account_employee = frappe.db.get_value(
                            'Employee',
                            {'user_id': account_user},
                            'name'
                        )
                        if account_employee:
                            account_secretary_employee = frappe.db.get_value(
                                'Employee',
                                account_employee,
                                'custom_secretary_employee'
                            )
                            if account_secretary_employee:
                                account_secretary_user = frappe.db.get_value(
                                    'Employee',
                                    account_secretary_employee,
                                    'user_id'
                                )
                                if account_secretary_user:
                                    read_only_users.append(account_secretary_user)

                for target_user in set(read_only_users + write_users):
                    if not target_user or target_user == 'Administrator':
                        continue

                    if not frappe.db.exists('User', target_user):
                        continue

                    can_write = target_user in write_users
                    existing_share = frappe.db.get_value(
                        'DocShare',
                        {
                            'share_doctype': 'Material Request',
                            'share_name': new_mr.name,
                            'user': target_user,
                        },
                        'name'
                    )

                    share_values = {
                        'read': 1,
                        'write': 1 if can_write else 0,
                        'submit': 0,
                        'share': 0,
                    }

                    if existing_share:
                        frappe.db.set_value(
                            'DocShare',
                            existing_share,
                            share_values,
                            update_modified=False,
                        )
                    else:
                        share = frappe.new_doc('DocShare')
                        share.share_doctype = 'Material Request'
                        share.share_name = new_mr.name
                        share.user = target_user
                        share.read = share_values['read']
                        share.write = share_values['write']
                        share.submit = share_values['submit']
                        share.share = share_values['share']
                        share.insert(ignore_permissions=True)

                # AR: إشعار الحسابات بوجود طلب شراء مولد آلياً.
                # EN: Notify Accounts Managers about the generated purchase request.
                for account_user in set(write_users):
                    if account_user and account_user != frappe.session.user:
                        notification = frappe.new_doc('Notification Log')
                        notification.subject = (
                            "🛒 "
                            + _(
                                "Action required: Auto-generated Purchase Request %s is waiting for Accounts approval."
                            )
                            % str(new_mr.name)
                        )
                        notification.for_user = account_user
                        notification.document_type = 'Material Request'
                        notification.document_name = new_mr.name
                        notification.type = 'Alert'
                        notification.insert(ignore_permissions=True)

                # AR: إبقاء المتوفر فقط في المستند الأصلي (طلب صرف) / EN: Keep only available items in original doc (Material Issue)
                current_items = [item for item in doc.items if float(item.qty or 0) > 0]
                doc.set('items', current_items)
                doc.material_request_type = 'Material Issue'
                
                # AR: إظهار رسالة النجاح / EN: Show success message
                frappe.msgprint(
                    "✅ "
                    + _(
                        "Available items were issued, and Purchase Request %s was created for the shortage."
                    )
                    % str(new_mr.name),
                    indicator='green',
                    alert=True,
                )
        else:
            # AR: تنبيه في حال الشراء الآلي معطل / EN: Alert if auto-purchase is disabled
            frappe.msgprint(
                "⚠️ "
                + _(
                    "Some requested quantities are unavailable, and automatic purchase creation is disabled. The request will continue with the available quantities only."
                ),
                indicator='blue',
                alert=True,
            )
"""
    # AR: إدخال السكربت لقاعدة البيانات / EN: Insert script to database
    script.insert(ignore_permissions=True)


def create_material_request_workflow():
    '''
    AR:
        إعادة بناء سير العمل بنفس المراحل والمنطق الأصلي، مع تقييد
        اعتماد ورفض مرحلة المسؤول المباشر بالمستخدم المحدد في reports_to.

    EN:
        Rebuild the workflow with the original stages and routing, while
        restricting direct-supervisor actions to the user linked in reports_to.
    '''
    workflow_name = "Material Request Approval masar_requests"

    if frappe.db.exists("Workflow", workflow_name):
        frappe.delete_doc(
            "Workflow",
            workflow_name,
            ignore_permissions=True,
            force=True,
        )

    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Material Request"
    workflow.is_active = 1
    workflow.send_email_alert = 0

    # AR:
    # أبقينا allow_edit كما كان في المشروع الأصلي حتى لا نغيّر سلوك
    # الاعتماد الاستثنائي للأمين العام ورئيس الجامعة.
    #
    # EN:
    # Keep allow_edit as in the original project to preserve the existing
    # super-final-approval behavior for Secretary General and President.
    states = [
        {"state": "Draft", "doc_status": 0, "allow_edit": "Employee"},
        {
            "state": "Pending Direct Supervisor",
            "doc_status": 0,
            # AR: لا يتطلب دوراً مخصصاً؛ الوصول الفعلي يأتي عبر DocShare.
            # EN: No custom role is required; actual access comes from DocShare.
            "allow_edit": "All",
        },
        {
            "state": "Pending Stock Check",
            "doc_status": 0,
            "allow_edit": "Employee",
        },
        {
            "state": "Pending HR Manager",
            "doc_status": 0,
            "allow_edit": "Employee",
        },
        {
            "state": "Pending Accounts Manager",
            "doc_status": 0,
            "allow_edit": "Employee",
        },
        {
            "state": "Pending Sec Gen",
            "doc_status": 0,
            "allow_edit": "Employee",
        },
        {
            "state": "Pending President",
            "doc_status": 0,
            "allow_edit": "Employee",
        },
        {
            "state": "Approved",
            "doc_status": 1,
            "allow_edit": "System Manager",
        },
        {
            "state": "Rejected",
            "doc_status": 0,
            "allow_edit": "System Manager",
        },
    ]

    for state in states:
        workflow.append("states", state)

    direct_supervisor_condition = (
        "doc.reports_to "
        "and frappe.db.get_value('Employee', doc.reports_to, 'user_id') "
        "== frappe.session.user"
    )

    transitions = [
        {
            "state": "Draft",
            "action": "Submit to Direct Supervisor",
            "next_state": "Pending Direct Supervisor",
            "allowed": "Employee",
            "condition": (
                "frappe.session.user == doc.owner "
                "and doc.reports_to "
                "and doc.custom_manager_is_top_level == 0"
            ),
        },
        {
            "state": "Draft",
            "action": "Submit (Auto Bypass)",
            "next_state": "Pending Stock Check",
            "allowed": "Employee",
            "condition": (
                "frappe.session.user == doc.owner "
                "and (not doc.reports_to "
                "or doc.custom_manager_is_top_level == 1)"
            ),
        },
        {
            "state": "Pending Direct Supervisor",
            "action": "Direct Supervisor Approve",
            "next_state": "Pending Stock Check",
            # AR: All دور تلقائي لكل مستخدم؛ شرط reports_to هو المحدد الفعلي.
            # EN: All is automatic; reports_to is the effective authorization check.
            "allowed": "All",
            "condition": direct_supervisor_condition,
        },
        {
            "state": "Pending Direct Supervisor",
            "action": "Reject",
            "next_state": "Rejected",
            # AR: All دور تلقائي لكل مستخدم؛ شرط reports_to هو المحدد الفعلي.
            # EN: All is automatic; reports_to is the effective authorization check.
            "allowed": "All",
            "condition": direct_supervisor_condition,
        },
        {
            "state": "Pending Stock Check",
            "action": "Confirm Availability",
            "next_state": "Pending HR Manager",
            "allowed": "Warehouse Manager",
            "condition": "",
        },
        {
            "state": "Pending Stock Check",
            "action": "Reject",
            "next_state": "Rejected",
            "allowed": "Warehouse Manager",
            "condition": "",
        },
        {
            "state": "Pending HR Manager",
            "action": "HR Manager Approve",
            "next_state": "Pending Accounts Manager",
            "allowed": "HR Manager",
            "condition": "",
        },
        {
            "state": "Pending HR Manager",
            "action": "Reject",
            "next_state": "Rejected",
            "allowed": "HR Manager",
            "condition": "",
        },
        {
            "state": "Pending Accounts Manager",
            "action": "Accounts Manager Approve",
            "next_state": "Pending Sec Gen",
            "allowed": "Accounts Manager",
            "condition": "",
        },
        {
            "state": "Pending Accounts Manager",
            "action": "Reject",
            "next_state": "Rejected",
            "allowed": "Accounts Manager",
            "condition": "",
        },
        {
            "state": "Pending Sec Gen",
            "action": "Forward to President",
            "next_state": "Pending President",
            "allowed": "Secretary General",
            "condition": "",
        },
        {
            "state": "Pending Sec Gen",
            "action": "Final Approve",
            "next_state": "Approved",
            "allowed": "Secretary General",
            "condition": "",
        },
        {
            "state": "Pending Sec Gen",
            "action": "Reject",
            "next_state": "Rejected",
            "allowed": "Secretary General",
            "condition": "",
        },
        {
            "state": "Pending President",
            "action": "Final Approve",
            "next_state": "Approved",
            "allowed": "University President",
            "condition": "",
        },
        {
            "state": "Pending President",
            "action": "Reject",
            "next_state": "Rejected",
            "allowed": "University President",
            "condition": "",
        },
    ]

    # AR: الاعتماد الاستثنائي للإدارة العليا بقي كما هو.
    # EN: Preserve the original super-final-approval behavior.
    all_intermediate_states = [
        "Draft",
        "Pending Direct Supervisor",
        "Pending Stock Check",
        "Pending HR Manager",
        "Pending Accounts Manager",
        "Pending Sec Gen",
        "Pending President",
    ]

    for state in all_intermediate_states:
        transitions.append(
            {
                "state": state,
                "action": "Super Final Approval",
                "next_state": "Approved",
                "allowed": "Secretary General",
                "condition": "",
            }
        )
        transitions.append(
            {
                "state": state,
                "action": "Super Final Approval",
                "next_state": "Approved",
                "allowed": "University President",
                "condition": "",
            }
        )

    for transition in transitions:
        workflow.append("transitions", transition)

    workflow.insert(ignore_permissions=True)
    frappe.db.commit()



def setup_university_secretary_role():
    '''
    AR:
        تثبيت دور سكرتير طلب المواد بصلاحية قراءة وطباعة فقط.
        لا تمنحه هذه الدالة وصولاً عاماً؛ المستندات المحددة تصل إليه
        بواسطة DocShare من سكربت المشاركة.

    EN:
        Configure Material Request Secretary as read/print-only.
        Specific documents are granted through DocShare, not broad access.
    '''
    doctype_name = "Material Request"
    role_name = "Material Request Secretary"

    if not frappe.db.exists("Role", role_name):
        role = frappe.new_doc("Role")
        role.role_name = role_name
        role.desk_access = 1
        role.insert(ignore_permissions=True)

    existing_rows = frappe.get_all(
        "Custom DocPerm",
        filters={
            "parent": doctype_name,
            "role": role_name,
        },
        pluck="name",
    )

    for row_name in existing_rows:
        frappe.delete_doc(
            "Custom DocPerm",
            row_name,
            ignore_permissions=True,
            force=True,
        )

    permission = frappe.new_doc("Custom DocPerm")
    permission.update(
        {
            "parent": doctype_name,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": role_name,
            "permlevel": 0,
            "read": 1,
            "print": 1,
            "email": 1,
            "write": 0,
            "submit": 0,
            "cancel": 0,
            "share": 0,
            # AR: يمنع القائمة العامة؛ DocShare يفتح المعاملات المرتبطة فقط.
            # EN: Prevent broad list access; DocShare grants only related requests.
            "if_owner": 1,
        }
    )
    permission.insert(ignore_permissions=True)

    # AR:
    # منح دور السكرتير تلقائياً لكل مستخدم تم اختياره كسكرتير في Employee.
    # وجود DocShare وحده لا يكفي إذا لم يحمل المستخدم DocPerm لهذا النوع.
    # لا نحذف الدور من مستخدم آخر حتى لا نلغي تعييناً يدوياً للعميل.
    #
    # EN:
    # Automatically give the secretary role to every User selected as an
    # Employee secretary. A DocShare alone is not enough without a DocPerm
    # for this DocType. Never remove the role from another user, so a
    # customer's manual assignment is preserved.
    sync_material_request_secretary_roles(role_name)

    frappe.clear_cache(doctype=doctype_name)
    frappe.db.commit()


def sync_material_request_secretary_roles(role_name="Material Request Secretary"):
    """
    AR: إضافة دور Material Request Secretary لسجلات السكرتارية المفعلة.
    EN: Add Material Request Secretary to enabled secretary User accounts.
    """
    employee_meta = frappe.get_meta("Employee")
    if not employee_meta.has_field("custom_secretary_employee"):
        return 0

    secretary_employees = frappe.get_all(
        "Employee",
        filters={"custom_secretary_employee": ["is", "set"]},
        pluck="custom_secretary_employee",
    )

    assigned = 0
    for secretary_employee in set(secretary_employees):
        secretary_user = frappe.db.get_value(
            "Employee",
            secretary_employee,
            "user_id",
        )
        if not secretary_user:
            continue

        if not frappe.db.get_value("User", secretary_user, "enabled"):
            continue

        if role_name in frappe.get_roles(secretary_user):
            continue

        user_doc = frappe.get_doc("User", secretary_user)
        user_doc.append("roles", {"role": role_name})
        user_doc.save(ignore_permissions=True)
        assigned += 1

    return assigned

def resync_all_material_request_shares():
    """
    Re-sync all Material Request shares using the native app hook logic.
    """
    from masar_requests.material_request_sharing import (
        resync_all_material_request_shares as run_resync,
    )

    return run_resync()

    
    def get_user_secretary(target_user):
        '''Return the secretary User linked to a specific User.'''
        if not target_user:
            return None

        employee = frappe.db.get_value(
            "Employee",
            {"user_id": target_user},
            "name",
        )
        if not employee:
            return None

        secretary_employee = frappe.db.get_value(
            "Employee",
            employee,
            "custom_secretary_employee",
        )
        if not secretary_employee:
            return None

        return frappe.db.get_value(
            "Employee",
            secretary_employee,
            "user_id",
        )

    def get_enabled_users_with_role(role):
        '''Return enabled users assigned to a role.'''
        rows = frappe.get_all(
            "Has Role",
            filters={
                "role": role,
                "parenttype": "User",
            },
            pluck="parent",
        )

        return [
            user
            for user in rows
            if user and frappe.db.get_value("User", user, "enabled")
        ]

    def get_role_secretaries(role):
        '''Return secretaries of enabled users assigned to a role.'''
        secretaries = set()

        for principal_user in get_enabled_users_with_role(role):
            secretary_user = get_user_secretary(principal_user)
            if secretary_user:
                secretaries.add(secretary_user)

        return secretaries

    def get_all_secretary_users():
        '''Return all Users configured as Employee secretaries.'''
        secretary_employees = frappe.get_all(
            "Employee",
            filters={"custom_secretary_employee": ["is", "set"]},
            pluck="custom_secretary_employee",
        )

        users = set()
        for secretary_employee in secretary_employees:
            secretary_user = frappe.db.get_value(
                "Employee",
                secretary_employee,
                "user_id",
            )
            if secretary_user:
                users.add(secretary_user)

        return users

    def grant_share(docname, user, write):
        '''Create or update an exact DocShare permission.'''
        if (
            not user
            or user == "Administrator"
            or not frappe.db.exists("User", user)
        ):
            return False

        frappe_share.add_docshare(
            "Material Request",
            docname,
            user,
            read=1,
            write=1 if write else 0,
            submit=0,
            share=0,
            flags={"ignore_share_permission": True},
        )
        return True

    def remove_share(docname, user):
        '''Remove a stale user-specific Material Request share.'''
        if not user or user == "Administrator":
            return False

        share_name = frappe.db.get_value(
            "DocShare",
            {
                "share_doctype": "Material Request",
                "share_name": docname,
                "user": user,
            },
            "name",
        )

        if not share_name:
            return False

        frappe.delete_doc(
            "DocShare",
            share_name,
            ignore_permissions=True,
            force=True,
        )
        return True

    # AR: قائمة السكرتارية التي يدير التطبيق مشاركاتها آلياً.
    # EN: Secretary users whose automatic shares are managed by this app.
    managed_secretaries = get_all_secretary_users()

    request_names = frappe.get_all(
        "Material Request",
        pluck="name",
    )

    processed = 0
    shares_updated = 0
    shares_removed = 0

    for request_name in request_names:
        doc = frappe.get_doc("Material Request", request_name)
        actor_users = []
        secretary_users = []

        if doc.workflow_state == "Pending Direct Supervisor":
            manager_user = (
                frappe.db.get_value(
                    "Employee",
                    doc.reports_to,
                    "user_id",
                )
                if doc.reports_to
                else None
            )

            if manager_user:
                actor_users.append(manager_user)

        elif doc.workflow_state in state_role_map:
            actor_users.extend(
                get_enabled_users_with_role(
                    state_role_map[doc.workflow_state]
                )
            )

        # AR:
        # سكرتير صاحب الإجراء الحالي يرى الطلب للقراءة والطباعة فقط، بما في
        # ذلك سكرتير الأمين العام وسكرتير رئيس الجامعة عندما تصل المعاملة
        # إلى مرحلة مسؤولهم.
        #
        # EN:
        # The current workflow actor's secretary gets read/print-only access,
        # including Secretary General and President secretaries when the
        # request reaches their principal's stage.
        for actor_user in actor_users:
            actor_secretary = get_user_secretary(actor_user)

            if actor_secretary:
                secretary_users.append(actor_secretary)

        actor_user_set = set(actor_users)
        secretary_user_set = set(secretary_users)

        # AR: إزالة الوصول عند مغادرة مرحلة مدير السكرتير.
        # EN: Remove access once the secretary's principal leaves the stage.
        for managed_secretary in managed_secretaries:
            if (
                managed_secretary not in secretary_user_set
                and managed_secretary not in actor_user_set
                and remove_share(request_name, managed_secretary)
            ):
                shares_removed += 1

        for actor_user in actor_user_set:
            if grant_share(request_name, actor_user, True):
                shares_updated += 1

        for secretary_user in secretary_user_set:
            if grant_share(
                request_name,
                secretary_user,
                secretary_user in actor_user_set,
            ):
                shares_updated += 1

        processed += 1

    frappe.db.commit()
    frappe.clear_cache(doctype="Material Request")

    return {
        "processed_requests": processed,
        "updated_shares": shares_updated,
        "removed_stale_secretary_shares": shares_removed,
    }


def audit_material_request_access(docname):
    '''
    AR:
        فحص وصول جميع مستخدمي أدوار سير طلب المواد إلى مستند محدد.
        الدالة للقراءة والتشخيص فقط ولا تعدل البيانات.

    EN:
        Audit all Material Request workflow-role users against one document.
        Read-only diagnostic function; it does not modify data.
    '''
    from frappe.model.workflow import get_transitions

    if not frappe.db.exists("Material Request", docname):
        frappe.throw("❌ " + frappe._("Material Request %s does not exist.") % docname)

    roles_to_check = [
        "Warehouse Manager",
        "HR Manager",
        "Accounts Manager",
        "Secretary General",
        "University President",
        "Material Request Secretary",
    ]

    original_user = frappe.session.user
    results = []

    try:
        request_doc = frappe.get_doc("Material Request", docname)
        manager_user = (
            frappe.db.get_value(
                "Employee",
                request_doc.reports_to,
                "user_id",
            )
            if request_doc.reports_to
            else None
        )

        # AR: فحص المسؤول المباشر الفعلي من reports_to دون أي دور مخصص.
        # EN: Audit the actual reports_to user without a custom role.
        manager_row = {
            "role": "reports_to user",
            "user": manager_user,
            "read": False,
            "write": False,
            "actions": [],
            "error": None,
        }

        if not manager_user:
            manager_row["error"] = "reports_to has no linked User"
        else:
            try:
                frappe.set_user(manager_user)
                manager_doc = frappe.get_doc("Material Request", docname)
                manager_row["read"] = frappe.has_permission(
                    "Material Request",
                    ptype="read",
                    doc=manager_doc,
                    user=manager_user,
                    throw=False,
                )
                manager_row["write"] = frappe.has_permission(
                    "Material Request",
                    ptype="write",
                    doc=manager_doc,
                    user=manager_user,
                    throw=False,
                )
                if manager_row["read"]:
                    manager_row["actions"] = [
                        transition.get("action")
                        for transition in get_transitions(manager_doc)
                    ]
            except Exception as error:
                manager_row["error"] = (
                    type(error).__name__ + ": " + str(error)
                )

        results.append(manager_row)

        for role in roles_to_check:
            users = frappe.get_all(
                "Has Role",
                filters={
                    "role": role,
                    "parenttype": "User",
                },
                pluck="parent",
            )

            if not users:
                results.append(
                    {
                        "role": role,
                        "user": None,
                        "read": False,
                        "write": False,
                        "actions": [],
                        "error": "No user has this role",
                    }
                )
                continue

            for user in users:
                row = {
                    "role": role,
                    "user": user,
                    "read": False,
                    "write": False,
                    "actions": [],
                    "error": None,
                }

                try:
                    frappe.set_user(user)
                    doc = frappe.get_doc("Material Request", docname)

                    row["read"] = frappe.has_permission(
                        "Material Request",
                        ptype="read",
                        doc=doc,
                        user=user,
                        throw=False,
                    )
                    row["write"] = frappe.has_permission(
                        "Material Request",
                        ptype="write",
                        doc=doc,
                        user=user,
                        throw=False,
                    )

                    if row["read"]:
                        row["actions"] = [
                            transition.get("action")
                            for transition in get_transitions(doc)
                        ]

                except Exception as error:
                    row["error"] = (
                        type(error).__name__
                        + ": "
                        + str(error)
                    )

                results.append(row)

    finally:
        frappe.set_user(original_user)

    return results