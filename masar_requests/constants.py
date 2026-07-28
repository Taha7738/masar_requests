"""Shared workflow constants for Masar Requests.

AR: مرجع موحد لأسماء حالات وإجراءات سير العمل لمنع اختلاف النصوص بين الملفات.
EN: A single source of truth for workflow state/action names across the app.
"""


# Leave Application / طلب الإجازة
LEAVE_STATE_DRAFT = "Draft"
LEAVE_STATE_WAITING_SUBSTITUTE = "Waiting for Substitute Approval"
LEAVE_STATE_WAITING_DIRECT_MANAGER = "Waiting for Direct Manager Approval"
LEAVE_STATE_WAITING_HR_MANAGER = "Waiting for HR Manager Approval"
LEAVE_STATE_APPROVED = "Approved"
LEAVE_STATE_REJECTED = "Rejected"

LEAVE_ACTION_SEND_TO_SUBSTITUTE = "Send to Substitute"
LEAVE_ACTION_SEND_TO_DIRECT_MANAGER = "Send to Direct Manager"
LEAVE_ACTION_SUBSTITUTE_APPROVE = "Substitute Approve"
LEAVE_ACTION_DIRECT_MANAGER_APPROVE = "Direct Manager Approve"
LEAVE_ACTION_FINAL_APPROVE = "Final Approve"
LEAVE_ACTION_REJECT = "Reject"


# Material Request / طلب المواد
MR_STATE_DRAFT = "Draft"
MR_STATE_PENDING_DIRECT_SUPERVISOR = "Pending Direct Supervisor"
MR_STATE_PENDING_STOCK_CHECK = "Pending Stock Check"
MR_STATE_PENDING_HR_MANAGER = "Pending HR Manager"
MR_STATE_PENDING_ACCOUNTS_MANAGER = "Pending Accounts Manager"
MR_STATE_PENDING_SEC_GEN = "Pending Sec Gen"
MR_STATE_PENDING_PRESIDENT = "Pending President"
MR_STATE_APPROVED = "Approved"
MR_STATE_REJECTED = "Rejected"

MR_STATE_ROLE_MAP = {
    MR_STATE_PENDING_STOCK_CHECK: "Warehouse Manager",
    MR_STATE_PENDING_HR_MANAGER: "HR Manager",
    MR_STATE_PENDING_ACCOUNTS_MANAGER: "Accounts Manager",
    MR_STATE_PENDING_SEC_GEN: "Secretary General",
    MR_STATE_PENDING_PRESIDENT: "University President",
}


# Attendance Request (Official Duty) / المهمة الرسمية
# AR: يستخدم طلب المهمة نفس مراحل وإجراءات طلب الإجازة، دون مسار منفصل للتقرير.
# EN: Official Duty uses the same stages/actions as Leave Application, with no separate report workflow.
ATTENDANCE_STATE_DRAFT = LEAVE_STATE_DRAFT
ATTENDANCE_STATE_WAITING_SUBSTITUTE = LEAVE_STATE_WAITING_SUBSTITUTE
ATTENDANCE_STATE_WAITING_DIRECT_MANAGER = LEAVE_STATE_WAITING_DIRECT_MANAGER
ATTENDANCE_STATE_WAITING_HR_MANAGER = LEAVE_STATE_WAITING_HR_MANAGER
ATTENDANCE_STATE_APPROVED = LEAVE_STATE_APPROVED
ATTENDANCE_STATE_REJECTED = LEAVE_STATE_REJECTED

ATTENDANCE_ACTION_SEND_TO_SUBSTITUTE = LEAVE_ACTION_SEND_TO_SUBSTITUTE
ATTENDANCE_ACTION_SEND_TO_DIRECT_MANAGER = LEAVE_ACTION_SEND_TO_DIRECT_MANAGER
ATTENDANCE_ACTION_SUBSTITUTE_APPROVE = LEAVE_ACTION_SUBSTITUTE_APPROVE
ATTENDANCE_ACTION_DIRECT_MANAGER_APPROVE = LEAVE_ACTION_DIRECT_MANAGER_APPROVE
ATTENDANCE_ACTION_FINAL_APPROVE = LEAVE_ACTION_FINAL_APPROVE
ATTENDANCE_ACTION_REJECT = LEAVE_ACTION_REJECT

# AR: حالات الموافقة المخزنة للطباعة والتدقيق.
# EN: Stored approval statuses used by printing and audit logic.
APPROVAL_PENDING = "Pending"
APPROVAL_APPROVED = "Approved"
APPROVAL_REJECTED = "Rejected"
APPROVAL_BYPASSED = "Bypassed"
