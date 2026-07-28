# Attendance Request V3 Fix

- On Duty hides only empty optional native fields (`employee_name`, `department`, `half_day`, `half_day_date`, `include_holidays`, and the native `explanation`).
- Work From Home restores the standard HRMS field visibility.
- Attendance workflow now displays its real state instead of the generic Draft status.
- Workflow stages are aligned with Leave Application:
  - Waiting for Substitute Approval
  - Waiting for Direct Manager Approval
  - Waiting for HR Manager Approval
  - Approved / Rejected
- Existing records using `Waiting for HR Approval` are migrated safely.
