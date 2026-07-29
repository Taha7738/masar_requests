"""Native Material Request validation, notification, and shortage splitting.

AR: بديل قابل للاختبار والصيانة عن Server Script النصي القديم.
EN: Testable and maintainable replacement for the legacy text Server Script.
"""

import frappe
from frappe import _

from masar_requests.constants import (
    MR_STATE_APPROVED,
    MR_STATE_DRAFT,
    MR_STATE_PENDING_ACCOUNTS_MANAGER,
    MR_STATE_PENDING_DIRECT_SUPERVISOR,
    MR_STATE_PENDING_HR_MANAGER,
    MR_STATE_PENDING_PRESIDENT,
    MR_STATE_PENDING_SEC_GEN,
    MR_STATE_PENDING_STOCK_CHECK,
    MR_STATE_REJECTED,
    MR_STATE_ROLE_MAP,
)
from masar_requests.material_request_sharing import (
    get_enabled_users_with_role,
    get_user_secretary,
    sync_material_request_shares,
    upsert_share,
)


FORWARD_STATES_AFTER_STOCK = {
    MR_STATE_PENDING_HR_MANAGER,
    MR_STATE_PENDING_ACCOUNTS_MANAGER,
    MR_STATE_PENDING_SEC_GEN,
    MR_STATE_PENDING_PRESIDENT,
    MR_STATE_APPROVED,
}


def allow_zero_valuation_for_internal_material_issue(doc, method=None):
    """
    AR:
        السماح بسعر تقييم صفري فقط لأسطر Stock Entry من نوع Material Issue
        والمرتبطة فعليًا بطلب مواد داخلي. لا يغيّر هذا أسعار طلب المواد،
        ولا يطبق على الاستلام أو الشراء أو التحويل.

        هذا الخيار لا يفرض سعرًا صفريًا عندما يوجد تقييم فعلي للصنف؛
        بل يسمح فقط بإكمال الحركة إذا لم يجد ERPNext تقييمًا سابقًا.

    EN:
        Permit zero valuation only for Material Issue Stock Entry rows that
        are actually linked to an internal Material Request. This does not
        change Material Request prices and does not apply to receipts,
        purchases, or transfers.

        This does not force a zero rate when ERPNext already has a valuation;
        it only permits submission when no prior valuation can be resolved.
    """
    if getattr(doc, "purpose", None) != "Material Issue":
        return

    request_type_cache = {}

    for row in getattr(doc, "items", []) or []:
        material_request = getattr(row, "material_request", None)
        if not material_request:
            continue

        if material_request not in request_type_cache:
            request_type_cache[material_request] = frappe.db.get_value(
                "Material Request",
                material_request,
                "material_request_type",
            )

        if request_type_cache[material_request] == "Material Issue":
            row.allow_zero_valuation_rate = 1


def before_save_material_request(doc, method=None):
    # AR: تشغيل قواعد حماية وانشطار طلب المواد قبل الحفظ.
    # EN: Run Material Request protection and splitting rules before save.
    """Apply server-side business rules before each Material Request save."""
    # AR: حماية خادمية تمنع HR User من التعديل أو تنفيذ إجراءات سير العمل.
    # EN: Server-side guard blocks HR User from editing or running workflow actions.
    from masar_requests.hr_user_read_only import enforce_hr_user_read_only

    enforce_hr_user_read_only(doc, method)
    old_doc = doc.get_doc_before_save()

    set_manager_level_flag(doc)
    freeze_original_quantities(doc)
    validate_protected_item_values(doc, old_doc)
    notify_workflow_state_change(doc, old_doc)
    split_stock_shortage(doc, old_doc)


def set_manager_level_flag(doc):
    # AR: تحديد ما إذا كان المدير المباشر من القيادة العليا.
    # EN: Mark whether the direct manager is top management.
    """Mark whether the direct manager belongs to top management."""
    doc.custom_manager_is_top_level = 0

    if not doc.reports_to:
        return

    manager_user = frappe.db.get_value("Employee", doc.reports_to, "user_id")
    if not manager_user:
        return

    manager_roles = set(frappe.get_roles(manager_user))
    doc.custom_manager_is_top_level = int(
        bool(manager_roles & {"Secretary General", "University President"})
    )


def freeze_original_quantities(doc):
    # AR: حفظ الكميات المطلوبة الأصلية قبل تعديل المخزون.
    # EN: Preserve originally requested quantities before stock edits.
    """Keep the employee-requested quantity for later shortage calculation."""
    if doc.workflow_state not in {MR_STATE_DRAFT, None, ""}:
        return

    for item in doc.items:
        if not item.custom_original_qty:
            item.custom_original_qty = item.qty


def validate_protected_item_values(doc, old_doc):
    # AR: منع تعديل الكمية والسعر والمبلغ دون الصلاحية المطلوبة.
    # EN: Protect quantity, rate, and amount from unauthorized edits.
    """Enforce quantity and financial locks on the server."""
    if not old_doc:
        return

    user_roles = set(frappe.get_roles(frappe.session.user))
    can_edit_qty = bool(
        user_roles & {"MR Qty Modifier", "System Manager"}
        or (
            "Warehouse Manager" in user_roles
            and old_doc.workflow_state == MR_STATE_PENDING_STOCK_CHECK
        )
    )

    old_items = {row.name: row for row in old_doc.items}

    if not can_edit_qty:
        for item in doc.items:
            old_item = old_items.get(item.name)
            if old_item and float(item.qty or 0) != float(old_item.qty or 0):
                frappe.throw(
                    "🔒 "
                    + _(
                        "Quantity field is locked. Only Warehouse Manager during Stock Check, "
                        "MR Qty Modifier, or System Manager can edit it."
                    )
                )

    # AR: السعر والمبلغ يخصان طلبات الشراء فقط، وليس طلبات الصرف الداخلي.
    # EN: Rate and amount are relevant only to Purchase requests.
    if doc.material_request_type != "Purchase":
        return

    can_edit_financials = bool(
        user_roles
        & {"MR Financial Modifier", "Accounts Manager", "System Manager"}
    )
    if can_edit_financials:
        return

    for item in doc.items:
        old_item = old_items.get(item.name)
        if not old_item:
            continue

        old_rate = round(float(old_item.rate or 0), 2)
        old_amount = round(float(old_item.amount or 0), 2)
        new_rate = round(float(item.rate or 0), 2)
        new_amount = round(float(item.amount or 0), 2)

        if (new_rate, new_amount) != (old_rate, old_amount):
            frappe.throw(
                "🔒 "
                + _(
                    "Rate fields are locked after saving. You need the "
                    "'MR Financial Modifier' role to edit them."
                )
            )


def notify_workflow_state_change(doc, old_doc):
    # AR: إرسال الإشعارات عند تغير حالة سير عمل طلب المواد.
    # EN: Send notifications when Material Request workflow state changes.
    """Create notifications after a workflow state change."""
    if not old_doc or old_doc.workflow_state == doc.workflow_state:
        return

    try:
        targets, subject = _notification_targets_and_subject(doc)
        for target_user in targets:
            if (
                not target_user
                or target_user == "Administrator"
                or target_user == frappe.session.user
                or not frappe.db.exists("User", target_user)
            ):
                continue

            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "subject": subject,
                    "for_user": target_user,
                    "document_type": "Material Request",
                    "document_name": doc.name,
                    "type": "Alert",
                }
            ).insert(ignore_permissions=True)
    except Exception:
        # AR: فشل الإشعار لا يفشل المعاملة، لكنه يسجل التفاصيل كاملة.
        # EN: Notification failure does not abort the request; full details are logged.
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Material Request Notification Error",
        )


def _notification_targets_and_subject(doc):
    # AR: تحديد مستلمي إشعار طلب المواد ونص الإشعار.
    # EN: Resolve Material Request notification recipients and subject.
    state = doc.workflow_state
    targets = {doc.owner}
    principals = set()

    if state == MR_STATE_REJECTED:
        subject = _("Your Material Request %s has been rejected.") % doc.name
    elif state == MR_STATE_APPROVED:
        subject = _(
            "Your Material Request %s has been fully approved and is now in progress."
        ) % doc.name
        targets.update(get_enabled_users_with_role("Warehouse Manager"))
    elif state == MR_STATE_PENDING_DIRECT_SUPERVISOR:
        manager_user = frappe.db.get_value("Employee", doc.reports_to, "user_id")
        if manager_user:
            principals.add(manager_user)
        subject = _(
            "Action required: Material Request %s is waiting for your approval."
        ) % doc.name
    elif state in MR_STATE_ROLE_MAP:
        principals.update(get_enabled_users_with_role(MR_STATE_ROLE_MAP[state]))
        subject = _(
            "Action required: Material Request %s has reached your department and is awaiting approval."
        ) % doc.name
    else:
        subject = _("Your Material Request %s has moved to workflow state: %s.") % (
            doc.name,
            state,
        )

    targets.update(principals)
    targets.update(filter(None, (get_user_secretary(user) for user in principals)))
    owner_secretary = get_user_secretary(doc.owner)
    if owner_secretary:
        targets.add(owner_secretary)

    return targets, subject


def split_stock_shortage(doc, old_doc):
    # AR: فصل الكميات الناقصة إلى طلب شراء تلقائي.
    # EN: Split stock shortages into an automatic Purchase request.
    """Split unavailable quantities into an automatically generated purchase request."""
    if (
        not old_doc
        or old_doc.workflow_state != MR_STATE_PENDING_STOCK_CHECK
        or doc.workflow_state not in FORWARD_STATES_AFTER_STOCK
    ):
        return

    shortages = []
    available_items = []

    for item in doc.items:
        requested_qty = float(item.custom_original_qty or item.qty or 0)
        available_qty = float(item.qty or 0)

        if available_qty < 0 or available_qty > requested_qty:
            frappe.throw(
                _("Available quantity must be between zero and the originally requested quantity.")
            )

        if available_qty < requested_qty:
            shortages.append((item, requested_qty - available_qty))
        if available_qty > 0:
            available_items.append(item)

    if not shortages:
        return

    if not doc.custom_auto_create_purchase:
        frappe.msgprint(
            _(
                "Some requested quantities are unavailable, and automatic purchase creation is disabled. "
                "The request will continue with the available quantities only."
            ),
            indicator="blue",
            alert=True,
        )
        return

    if not available_items:
        doc.material_request_type = "Purchase"
        for item in doc.items:
            item.qty = float(item.custom_original_qty or 0)
        frappe.msgprint(
            _("All items are out of stock. The request has been converted to a Purchase request."),
            indicator="orange",
            alert=True,
        )
        return

    purchase_request = _create_purchase_request_for_shortages(doc, shortages)
    doc.set("items", available_items)
    doc.material_request_type = "Material Issue"

    frappe.msgprint(
        _("Available items were issued, and Purchase Request %s was created for the shortage.")
        % purchase_request.name,
        indicator="green",
        alert=True,
    )


def _create_purchase_request_for_shortages(source_doc, shortages):
    # AR: إنشاء طلب شراء مستقل للكميات غير المتوفرة.
    # EN: Create a separate Purchase request for unavailable quantities.
    new_doc = frappe.new_doc("Material Request")
    new_doc.update(
        {
            "material_request_type": "Purchase",
            # استخدام get لجلب القيم بأمان وتجنب خطأ AttributeError
            "company": source_doc.get("company"),
            "transaction_date": source_doc.get("transaction_date"),
            "schedule_date": source_doc.get("schedule_date"),
            "department": source_doc.get("department"),
            "reports_to": source_doc.get("reports_to"),
            "custom_manager_name": source_doc.get("custom_manager_name"),
            "custom_secretary_employee": source_doc.get("custom_secretary_employee"),
            "custom_secretary_name": source_doc.get("custom_secretary_name"),
            "custom_auto_create_purchase": 0,
            "custom_reason_for_request": _("Auto-generated from Material Request %s.")
            % source_doc.name,
        }
    )

    for source_item, shortage_qty in shortages:
        new_doc.append(
            "items",
            {
                "item_code": source_item.item_code,
                "qty": shortage_qty,
                "uom": source_item.uom,
                "schedule_date": source_item.schedule_date,
            },
        )

    new_doc.flags.ignore_workflow = True
    new_doc.insert(ignore_permissions=True)
    frappe.db.set_value(
        "Material Request",
        new_doc.name,
        "workflow_state",
        MR_STATE_PENDING_ACCOUNTS_MANAGER,
        update_modified=False,
    )
    new_doc.workflow_state = MR_STATE_PENDING_ACCOUNTS_MANAGER

    # AR: المالك والمدير قراءة فقط؛ الحسابات كتابة؛ السكرتير قراءة فقط.
    # EN: Owner/manager read-only, Accounts write, secretaries read-only.
    upsert_share(new_doc, source_doc.owner, can_write=False)
    manager_user = (
        frappe.db.get_value("Employee", source_doc.reports_to, "user_id")
        if source_doc.reports_to
        else None
    )
    upsert_share(new_doc, manager_user, can_write=False)

    for account_user in get_enabled_users_with_role("Accounts Manager"):
        upsert_share(new_doc, account_user, can_write=True)
        upsert_share(new_doc, get_user_secretary(account_user), can_write=False)

    sync_material_request_shares(new_doc, method="automatic_purchase")
    return new_doc
