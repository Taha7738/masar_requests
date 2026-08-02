"""
AR: تعريف ومنطق نوع المستند المرتبط بالوحدة `official_duty_request`.
EN: DocType definition and behavior for the `official_duty_request` module.
"""

# Copyright (c) 2026, AlphaCode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from masar_requests.official_duty_engine import (
    cancel_official_duty_reconciliation,
    reconcile_official_duty_now,
)
from masar_requests.official_duty_request_permissions import (
    before_submit_official_duty_request,
    on_submit_official_duty_request,
    on_update_official_duty_request,
    sync_official_duty_request_shares,
    validate_official_duty_request,
)


class OfficialDutyRequest(Document):
    """
    AR: فئة `OfficialDutyRequest` لتنظيم منطق الرسمية المهمة الطلب.
    EN: Class `OfficialDutyRequest` that organizes official duty request logic.

    DETAILS / التفاصيل:
    AR:
            المستند الإداري المستقل للمهمة الرسمية. يحتفظ بتفاصيل المهمة
            والاعتمادات والتقرير، ثم يطلب من محرك التسوية معالجة الحضور.

        EN:
            Independent administrative Official Duty document. It owns mission
            details, approvals, and the report, then delegates attendance handling
            to the reconciliation engine.
    """

    def validate(self):
        """
        AR: تنفيذ التحقق من صحة ضمن وحدة `official_duty_request`.
        EN: Execute validate within the `official_duty_request` module.
        """
        validate_official_duty_request(self)

    def after_insert(self):
        """
        AR: تنفيذ معالجة ما بعد إدراج ضمن وحدة `official_duty_request`.
        EN: Execute after insert within the `official_duty_request` module.
        """
        sync_official_duty_request_shares(self)

    def on_update(self):
        """
        AR: تنفيذ معالجة حدث تحديث ضمن وحدة `official_duty_request`.
        EN: Execute on update within the `official_duty_request` module.
        """
        on_update_official_duty_request(self)

    def before_submit(self):
        """
        AR: تنفيذ معالجة ما قبل اعتماد ضمن وحدة `official_duty_request`.
        EN: Execute before submit within the `official_duty_request` module.
        """
        before_submit_official_duty_request(self)

    def on_submit(self):
        """
        AR: تنفيذ معالجة حدث اعتماد ضمن وحدة `official_duty_request`.
        EN: Execute on submit within the `official_duty_request` module.
        """
        on_submit_official_duty_request(self)

    def on_cancel(self):
        """
        AR: تنفيذ معالجة حدث إلغاء ضمن وحدة `official_duty_request`.
        EN: Execute on cancel within the `official_duty_request` module.
        """
        cancel_official_duty_reconciliation(self)

    @frappe.whitelist()
    def reconcile_attendance(self):
        """
        AR: تنفيذ `reconcile` الحضور ضمن وحدة `official_duty_request`.
        EN: Execute reconcile attendance within the `official_duty_request` module.
        """
        if self.docstatus != 1:
            frappe.throw(_("Only an approved Official Duty Request can be reconciled."))
        return reconcile_official_duty_now(self.name)
