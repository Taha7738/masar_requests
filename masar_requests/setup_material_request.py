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


MATERIAL_REQUEST_CUSTOM_FIELDS = {
    "Material Request": (
        "custom_approval_section1",
        "custom_reason_for_request",
        "custom_approval_col_break1",
        "custom_auto_create_purchase",
        "custom_manager_is_top_level",
        "custom_approval_section",
        "reports_to",
        "custom_manager_name",
        "custom_approval_col_break",
        "custom_secretary_employee",
        "custom_secretary_name",
    ),
    "Material Request Item": ("custom_original_qty",),
}

MATERIAL_REQUEST_PROPERTY_SETTERS = {
    "Material Request": {
        "naming_series": ("default", "hidden"),
        "material_request_type": ("options",),
        "terms_tab": ("hidden",),
        "more_info_tab": ("hidden",),
        "connections_tab": ("hidden",),
        "set_warehouse": ("hidden",),
        "scan_barcode": ("hidden",),
    },
    "Material Request Item": {
        "description": ("in_list_view",),
        "stock_uom": ("in_list_view",),
        "warehouse": ("in_list_view",),
        "schedule_date": ("in_list_view",),
        "qty": ("columns", "label", "read_only_depends_on"),
        "custom_original_qty": ("columns",),
        "uom": ("columns", "hidden", "in_list_view"),
        "rate": (
            "depends_on",
            "hidden",
            "in_list_view",
            "columns",
            "read_only_depends_on",
        ),
        "amount": (
            "depends_on",
            "hidden",
            "in_list_view",
            "columns",
            "read_only_depends_on",
        ),
    },
}


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
    remove_legacy_fission_server_script()
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

    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache(doctype="Material Request Item")

    print("✅ " + frappe._("Material Request setup completed successfully."))


def teardown_material_request():
    """Remove app-owned Material Request configuration without deleting requests.

    AR: يحذف إعدادات التطبيق فقط ويحافظ على مستندات طلب المواد وبياناتها.
    EN: Remove app-owned configuration while preserving Material Request documents.
    """
    for doctype, fieldnames in MATERIAL_REQUEST_CUSTOM_FIELDS.items():
        for fieldname in fieldnames:
            custom_field = frappe.db.get_value(
                "Custom Field",
                {"dt": doctype, "fieldname": fieldname},
                "name",
            )
            if custom_field:
                frappe.delete_doc(
                    "Custom Field",
                    custom_field,
                    ignore_permissions=True,
                    force=True,
                )

    for doctype, field_map in MATERIAL_REQUEST_PROPERTY_SETTERS.items():
        for fieldname, properties in field_map.items():
            setter_names = frappe.get_all(
                "Property Setter",
                filters={
                    "doc_type": doctype,
                    "field_name": fieldname,
                    "property": ["in", list(properties)],
                },
                pluck="name",
            )
            for setter_name in setter_names:
                frappe.delete_doc(
                    "Property Setter",
                    setter_name,
                    ignore_permissions=True,
                    force=True,
                )

    workflow_name = "Material Request Approval masar_requests"
    if frappe.db.exists("Workflow", workflow_name):
        frappe.delete_doc(
            "Workflow",
            workflow_name,
            ignore_permissions=True,
            force=True,
        )

    for script_name in (
        "Auto Share MR with Direct Supervisor masar_requests",
        "Warehouse Fission Engine masar_requests",
    ):
        if frappe.db.exists("Server Script", script_name):
            frappe.delete_doc(
                "Server Script",
                script_name,
                ignore_permissions=True,
                force=True,
            )

    client_script = "Material Request UI masar_requests"
    if frappe.db.exists("Client Script", client_script):
        frappe.delete_doc(
            "Client Script",
            client_script,
            ignore_permissions=True,
            force=True,
        )

    managed_roles = (
        "System Manager",
        "Administrator",
        "Employee",
        "Warehouse Manager",
        "HR Manager",
        "HR User",
        "Accounts Manager",
        "Secretary General",
        "University President",
        "Material Request Secretary",
    )
    frappe.db.delete(
        "Custom DocPerm",
        {"parent": "Material Request", "role": ["in", managed_roles]},
    )

    # AR: الدور مملوك للتطبيق؛ تزال إسناداته ثم الدور نفسه عند الإمكان.
    # EN: This role is app-owned; remove assignments and then the role when possible.
    for app_owned_role in (
        "Material Request Secretary",
        "MR Qty Modifier",
        "MR Financial Modifier",
    ):
        frappe.db.delete("Has Role", {"role": app_owned_role})
        if frappe.db.exists("Role", app_owned_role):
            frappe.delete_doc(
                "Role",
                app_owned_role,
                ignore_permissions=True,
                force=True,
            )

    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache(doctype="Material Request Item")



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
        "HR User",
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
        "HR User",
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
        # AR: إنشاء صلاحية DocPerm لدور محدد على طلب المواد.
        # EN: Create a DocPerm for a Material Request role.
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

    # AR: HR User يشاهد ويطبع جميع طلبات المواد دون تعديل أو إجراءات Workflow.
    # EN: HR User can view and print all Material Requests without edit/workflow access.
    add_permission(
        "HR User",
        read=1,
        print=1,
        if_owner=0,
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
    # AR: إزالة سكربت المشاركة القديم بعد نقله إلى Python.
    # EN: Remove the obsolete sharing Server Script after native migration.
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

def remove_legacy_fission_server_script():
    """Remove the obsolete text Server Script after migration to native Python.

    AR: منطق الحماية والإشعارات والانشطار موجود في material_request_engine.py.
    EN: Protection, notifications, and splitting now live in material_request_engine.py.
    """
    script_name = "Warehouse Fission Engine masar_requests"
    if frappe.db.exists("Server Script", script_name):
        frappe.delete_doc(
            "Server Script",
            script_name,
            ignore_permissions=True,
            force=True,
        )


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
            "allow_edit": "Warehouse Manager",
        },
        {
            "state": "Pending HR Manager",
            "doc_status": 0,
            "allow_edit": "HR Manager",
        },
        {
            "state": "Pending Accounts Manager",
            "doc_status": 0,
            "allow_edit": "Accounts Manager",
        },
        {
            "state": "Pending Sec Gen",
            "doc_status": 0,
            "allow_edit": "Secretary General",
        },
        {
            "state": "Pending President",
            "doc_status": 0,
            "allow_edit": "University President",
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
    # AR: إعادة مزامنة مشاركات جميع طلبات المواد.
    # EN: Re-synchronize shares for every Material Request.
    """
    Re-sync all Material Request shares using the native app hook logic.
    """
    from masar_requests.material_request_sharing import (
        resync_all_material_request_shares as run_resync,
    )

    return run_resync()



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
        "HR User",
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
