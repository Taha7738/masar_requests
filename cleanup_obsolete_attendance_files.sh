#!/usr/bin/env bash
# AR: حذف ملفات Attendance القديمة التي لم تعد مسجلة في patches.txt.
# EN: Remove obsolete Attendance files no longer registered in patches.txt.
set -euo pipefail

APP_ROOT="${1:-.}"
FILES=(
  "masar_requests/patches/setup_attendance_request_patch.py"
  "masar_requests/patches/fix_attendance_request_layout_v2.py"
  "masar_requests/patches/fix_attendance_request_workflow_v3.py"
  "masar_requests/patches/enhance_attendance_request_v4.py"
  "masar_requests/patches/enhance_attendance_request_v5.py"
  "masar_requests/patches/fix_attendance_report_submit_permission_v6.py"
  "masar_requests/patches/fix_attendance_report_lock_and_progress_v7.py"
  "masar_requests/patches/align_attendance_workflow_and_rich_report_v8.py"
  "masar_requests/patches/fix_attendance_approval_signatures_and_hr_override_v10.py"
  "masar_requests/patches/fix_attendance_stage_signature_separation_v11.py"
  "masar_requests/patches/fix_attendance_print_approval_cycles_v12.py"
  "masar_requests/public/js/attendance_request_list.js"
)

for relative_path in "${FILES[@]}"; do
  rm -f "${APP_ROOT}/${relative_path}"
done

echo "Obsolete Attendance files removed from: ${APP_ROOT}"
