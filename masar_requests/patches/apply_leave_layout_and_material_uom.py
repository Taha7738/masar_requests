"""
AR:
تطبيق تحديث واجهة طلب الإجازة وإظهار وحدة القياس في جدول طلب المواد
مرة واحدة على المواقع القائمة عند تنفيذ bench migrate.

EN:
Apply the Leave Application layout update and show UOM in the Material
Request items grid once on existing sites during bench migrate.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from masar_requests.setup_leave_and_shift import (
    apply_leave_application_layout_preferences,
    get_direct_manager_secretary_fields,
    get_leave_and_shift_custom_fields,
)


LEAVE_APPLICATION_DOCTYPE = "Leave Application"
MATERIAL_REQUEST_DOCTYPE = "Material Request"
MATERIAL_REQUEST_ITEM_DOCTYPE = "Material Request Item"


def execute():
    """
    AR:
    ضمان وجود حقول طلب الإجازة المملوكة للتطبيق، ثم تطبيق ترتيب النموذج
    وإظهار حقل uom داخل جدول أصناف طلب المواد. لا يتم إنشاء Workflows
    أو أدوار أو Server Scripts، ولا تتغير صلاحيات rate أو amount.

    EN:
    Ensure the app-owned Leave Application fields exist, apply the form
    layout, and show uom in the Material Request items grid. This patch does
    not recreate Workflows, roles, or Server Scripts and does not change
    rate or amount permissions.
    """

    _ensure_leave_application_fields()
    apply_leave_application_layout_preferences()
    _show_material_request_item_uom()
    _clear_related_caches()


def _ensure_leave_application_fields():
    """
    AR: إنشاء أو تحديث حقول طلب الإجازة التابعة للتطبيق فقط.
    EN: Create or update only the app-owned Leave Application fields.
    """

    leave_fields = get_leave_and_shift_custom_fields().get(
        LEAVE_APPLICATION_DOCTYPE,
        [],
    )
    secretary_fields = get_direct_manager_secretary_fields().get(
        LEAVE_APPLICATION_DOCTYPE,
        [],
    )

    create_custom_fields(
        {
            LEAVE_APPLICATION_DOCTYPE: leave_fields + secretary_fields,
        },
        update=True,
    )

    frappe.clear_cache(doctype=LEAVE_APPLICATION_DOCTYPE)


def _show_material_request_item_uom():
    """
    AR:
    إظهار وحدة القياس في جدول الطلب فقط، دون لمس منطق أو صلاحيات الكمية
    أو السعر أو المبلغ.

    EN:
    Show UOM in the request grid only, without touching quantity, rate,
    or amount logic and permissions.
    """

    meta = frappe.get_meta(MATERIAL_REQUEST_ITEM_DOCTYPE, cached=False)
    if not meta.has_field("uom"):
        frappe.throw(
            "Material Request Item.uom was not found; "
            "the UI patch cannot be applied safely."
        )

    property_updates = (
        ("hidden", 0, "Check"),
        ("in_list_view", 1, "Check"),
        ("columns", "1", "Int"),
    )

    for property_name, value, property_type in property_updates:
        make_property_setter(
            doctype=MATERIAL_REQUEST_ITEM_DOCTYPE,
            fieldname="uom",
            property=property_name,
            value=value,
            property_type=property_type,
        )


def _clear_related_caches():
    """
    AR: تنظيف كاش النماذج المتأثرة بعد تطبيق التحديث.
    EN: Clear caches for the DocTypes affected by this update.
    """

    for doctype in (
        LEAVE_APPLICATION_DOCTYPE,
        MATERIAL_REQUEST_DOCTYPE,
        MATERIAL_REQUEST_ITEM_DOCTYPE,
    ):
        frappe.clear_cache(doctype=doctype)