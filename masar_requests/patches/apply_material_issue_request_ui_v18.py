"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `apply_material_issue_request_ui_v18` على المواقع القائمة.
EN: Idempotent migration patch for applying `apply_material_issue_request_ui_v18` changes to existing sites.
"""

# ============================================================================
# AR: إخفاء السعر في طلب الصرف الداخلي وتطبيق إعدادات طلب المواد — V18
# EN: Hide pricing for internal issues and apply Material Request settings — V18
# ============================================================================

import frappe

from masar_requests.setup_material_request import modify_material_request_properties


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `apply_material_issue_request_ui_v18`.
    EN: Execute execute within the `apply_material_issue_request_ui_v18` module.

    DETAILS / التفاصيل:
    AR:
            تطبيق واجهة طلب المواد الجديدة على المواقع الموجودة:
            - إخفاء السعر والمبلغ في طلب Material Issue.
            - إبقاؤهما متاحين في طلب Purchase فقط.
            - إبقاؤهما خارج العرض المختصر لجدول الأصناف.

            منطق السماح بالتقييم الصفري في Stock Entry يُفعّل من خلال hooks.py
            ولا يحتاج إلى إنشاء بيانات إضافية في قاعدة البيانات.

        EN:
            Apply the updated Material Request UI to existing sites:
            - Hide rate and amount for Material Issue requests.
            - Keep them available only for Purchase requests.
            - Keep them out of the compact item grid.

            Zero-valuation handling for linked Stock Entries is enabled by hooks.py
            and does not require additional database records.
    """
    modify_material_request_properties()

    frappe.clear_cache(doctype="Material Request")
    frappe.clear_cache(doctype="Material Request Item")
    frappe.clear_cache(doctype="Stock Entry")
    frappe.clear_cache(doctype="Stock Entry Detail")
    frappe.clear_cache()
