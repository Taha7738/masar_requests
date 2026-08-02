"""
AR: تنفيذ وظائف تطبيق مسار ضمن الوحدة `hr_user_read_only`.
EN: Masar application functionality implemented by the `hr_user_read_only` module.
"""

# ============================================================================
# AR: صلاحية HR User للعرض والطباعة مع السماح بالطلبات الشخصية
# EN: HR User read/print access with personal-request participation
# ============================================================================

import frappe
from frappe import _

HR_USER_ROLE = "HR User"
PRIVILEGED_ROLES = {"HR Manager", "System Manager"}
READ_ONLY_DOCTYPES = (
    "Official Duty Request",
    "Leave Application",
    "Material Request",
)

STANDARD_PERMISSION_DOCTYPES = {"Official Duty Request"}


def is_hr_user_read_only(user=None):
    """
    AR: تنفيذ التحقق من كون `hr` المستخدم القراءة `only` ضمن وحدة `hr_user_read_only`.
    EN: Execute is hr user read only within the `hr_user_read_only` module.

    DETAILS / التفاصيل:
    AR:
            يحدد أن المستخدم يحمل دور HR User من دون دور إداري أعلى.
            هذه الدالة تحدد نوع الحساب فقط، أما استثناء الطلب الشخصي
            فيتم بواسطة is_personal_request.

        EN:
            Identify an HR User account without a higher administrative role.
            This function classifies the account only; personal-request exemption
            is handled by is_personal_request.
    """
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    return (
        HR_USER_ROLE in roles
        and not (roles & PRIVILEGED_ROLES)
        and user != "Administrator"
    )


def _employee_user(employee):
    """
    AR: تنفيذ الموظف المستخدم ضمن وحدة `hr_user_read_only`.
    EN: Execute employee user within the `hr_user_read_only` module.
    """
    if not employee:
        return None
    return frappe.get_cached_value("Employee", employee, "user_id")


def is_personal_request(doc, user=None):
    """
    AR: تنفيذ التحقق من كون `personal` الطلب ضمن وحدة `hr_user_read_only`.
    EN: Execute is personal request within the `hr_user_read_only` module.

    DETAILS / التفاصيل:
    AR:
            التحقق من أن الطلب يخص المستخدم نفسه بصفته مقدم الطلب.
            يعتمد طلب المواد على owner، بينما يعتمد طلب الإجازة والمهمة الرسمية
            كذلك على الموظف أو custom_applicant_user.

        EN:
            Check whether the document is the user's own request as applicant.
            Material Request uses owner, while Leave/Official Duty also consider
            the linked Employee and custom_applicant_user.
    """
    if not doc:
        return False

    user = user or frappe.session.user
    owner = doc.get("owner") if hasattr(doc, "get") else getattr(doc, "owner", None)
    if owner == user:
        return True

    doctype = doc.get("doctype") if hasattr(doc, "get") else getattr(doc, "doctype", None)
    if doctype in {"Official Duty Request", "Leave Application"}:
        applicant_user = (
            doc.get("custom_applicant_user")
            if hasattr(doc, "get")
            else getattr(doc, "custom_applicant_user", None)
        )
        employee = doc.get("employee") if hasattr(doc, "get") else getattr(doc, "employee", None)
        return user in {applicant_user, _employee_user(employee)}

    return False


def setup_hr_user_read_only_permissions():
    """
    AR: تنفيذ إعداد `hr` المستخدم القراءة `only` الصلاحيات ضمن وحدة `hr_user_read_only`.
    EN: Execute setup hr user read only permissions within the `hr_user_read_only` module.

    DETAILS / التفاصيل:
    AR:
            منح HR User قراءة وطباعة عامة للأنواع الثلاثة فقط.
            إنشاء وتعديل الطلب الشخصي يأتيان من دور الموظف الطبيعي،
            بينما تمنع دوال has_permission أي تعديل على طلبات الآخرين.

        EN:
            Grant HR User global read/print access to the three request DocTypes.
            Personal create/write rights come from the user's normal employee role,
            while has_permission hooks block edits to other users' requests.
    """
    if not frappe.db.exists("Role", HR_USER_ROLE):
        # AR: إنشاء الدور عند غيابه لدعم التثبيت النظيف.
        # EN: Create the role when missing for clean-install compatibility.
        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": HR_USER_ROLE,
                "desk_access": 1,
            }
        ).insert(ignore_permissions=True)

    for doctype_name in READ_ONLY_DOCTYPES:
        existing_rows = frappe.get_all(
            "Custom DocPerm",
            filters={"parent": doctype_name, "role": HR_USER_ROLE},
            pluck="name",
        )
        for row_name in existing_rows:
            frappe.delete_doc(
                "Custom DocPerm",
                row_name,
                ignore_permissions=True,
                force=True,
            )

        if doctype_name in STANDARD_PERMISSION_DOCTYPES:
            # Official Duty Request has a complete standard permission matrix.
            # Do not create a lone Custom DocPerm that hides the other roles.
            frappe.clear_cache(doctype=doctype_name)
            continue

        permission = frappe.new_doc("Custom DocPerm")
        permission.update(
            {
                "parent": doctype_name,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": HR_USER_ROLE,
                "permlevel": 0,
                "read": 1,
                "print": 1,
                "write": 0,
                "create": 0,
                "delete": 0,
                "submit": 0,
                "cancel": 0,
                "amend": 0,
                "email": 0,
                "report": 0,
                "share": 0,
                "export": 0,
                "import": 0,
                "if_owner": 0,
            }
        )
        permission.insert(ignore_permissions=True)
        frappe.clear_cache(doctype=doctype_name)


def material_request_has_permission(
    doc,
    ptype=None,
    user=None,
    permission_type=None,
):
    """
    AR: تنفيذ المواد الطلب التحقق من وجود صلاحية ضمن وحدة `hr_user_read_only`.
    EN: Execute material request has permission within the `hr_user_read_only` module.

    DETAILS / التفاصيل:
    AR:
            في طلبات الآخرين: HR User للقراءة والطباعة فقط.
            في طلبه الشخصي: نعيد None حتى تطبق صلاحيات Employee وWorkflow الطبيعية.

        EN:
            For other users' requests, HR User is read/print-only.
            For a personal request, return None so normal Employee and Workflow
            permissions remain authoritative.
    """
    user = user or frappe.session.user
    ptype = permission_type or ptype or "read"

    if not is_hr_user_read_only(user):
        return None

    if ptype == "create" or is_personal_request(doc, user):
        return None

    return ptype in {"read", "print"}


def enforce_hr_user_read_only(doc=None, method=None):
    """
    AR: تنفيذ `enforce` `hr` المستخدم القراءة `only` ضمن وحدة `hr_user_read_only`.
    EN: Execute enforce hr user read only within the `hr_user_read_only` module.

    DETAILS / التفاصيل:
    AR:
            حماية خادمية تمنع HR User من تعديل طلبات الآخرين أو تنفيذ
            إجراءات عليها، مع السماح له بالتعامل مع طلبه الشخصي وفق
            الصلاحيات وسير العمل الطبيعيين.

        EN:
            Server-side guard blocking HR User edits/workflow actions on other
            users' requests while allowing normal participation in a personal request.
    """
    if is_hr_user_read_only() and not is_personal_request(doc):
        frappe.throw(
            _(
                "HR User is allowed to view and print other employees' requests only. "
                "You may create and process your own request according to the normal workflow."
            ),
            frappe.PermissionError,
        )
