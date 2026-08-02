"""
AR: تنفيذ وظائف تطبيق مسار ضمن الوحدة `workflow_notification_completion`.
EN: Masar application functionality implemented by the `workflow_notification_completion` module.
"""

import frappe
from frappe import _


MANUAL_REVIEW_STATUS = "Manual Review"


def _enabled_users_with_role(role):
    """
    AR: تنفيذ `enabled` `users` `with` الدور ضمن وحدة `workflow_notification_completion`.
    EN: Execute enabled users with role within the `workflow_notification_completion` module.
    """
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
        for user in set(rows)
        if user
        and user != "Administrator"
        and frappe.db.get_value("User", user, "enabled")
    ]


def _already_notified(user, docname, subject):
    """
    AR: تنفيذ `already` `notified` ضمن وحدة `workflow_notification_completion`.
    EN: Execute already notified within the `workflow_notification_completion` module.
    """
    return bool(
        frappe.db.exists(
            "Notification Log",
            {
                "for_user": user,
                "document_type": "Official Duty Request",
                "document_name": docname,
                "subject": subject,
            },
        )
    )


def notify_official_duty_manual_review(doc):
    """
    AR: تنفيذ إشعار الرسمية المهمة اليدوي `review` ضمن وحدة `workflow_notification_completion`.
    EN: Execute notify official duty manual review within the `workflow_notification_completion` module.
    """
    if not doc or doc.get("processing_status") != MANUAL_REVIEW_STATUS:
        return

    old_doc = doc.get_doc_before_save()
    if old_doc and old_doc.get("processing_status") == MANUAL_REVIEW_STATUS:
        return

    subject = _(
        "Official Duty Request {0} requires manual attendance review."
    ).format(doc.name)

    for user in _enabled_users_with_role("HR Manager"):
        if _already_notified(user, doc.name, subject):
            continue

        notification = frappe.new_doc("Notification Log")
        notification.subject = subject
        notification.for_user = user
        notification.document_type = "Official Duty Request"
        notification.document_name = doc.name
        notification.type = "Alert"
        notification.insert(ignore_permissions=True)
