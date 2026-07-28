# Attendance Request V14 — Installation

## الملفات المعدلة / Modified files

- `masar_requests/setup_attendance_request.py`
- `masar_requests/attendance_request_permissions.py`
- `masar_requests/patches/fix_attendance_workflow_and_print_v14.py`
- `masar_requests/patches.txt`
- `masar_requests/masar_requests/print_format/masar_attendance_request_form/masar_attendance_request_form.json`

## التطبيق / Apply

انسخ الملفات إلى جذر التطبيق:

```bash
cd /home/frappe/frappe-bench/apps/masar_requests
unzip -o /path/to/attendance_request_v14_modified_files_only.zip
```

ثم نفّذ:

```bash
cd /home/frappe/frappe-bench
bench --site SITE_NAME migrate
bench --site SITE_NAME clear-cache
bench build --app masar_requests
bench restart
```

## تحقق مباشر من تنفيذ Patch

```bash
bench --site SITE_NAME console
```

ثم:

```python
frappe.db.exists(
    "Patch Log",
    "masar_requests.patches.fix_attendance_workflow_and_print_v14",
)
```

يجب أن تكون النتيجة اسم الـ Patch وليست `None`.

## تشغيل الإصلاح يدويًا عند الحاجة

لا تُشغّل هذا الأمر عادةً إذا نجح `migrate`. استخدمه فقط إذا لم يظهر الـ Patch في `Patch Log`:

```bash
bench --site SITE_NAME execute \
  masar_requests.patches.fix_attendance_workflow_and_print_v14.execute
```

ثم أعد تنفيذ:

```bash
bench --site SITE_NAME clear-cache
bench build --app masar_requests
bench restart
```
