# Masar Requests

Masar Requests customizes Leave Application, Shift Type, and Material Request workflows for Frappe/ERPNext. It provides partial leave, direct-manager routing through `Employee.reports_to`, stage-specific sharing, secretary read-only access, and automatic purchase requests for stock shortages.

## Supported versions

- Frappe 15.106.0
- ERPNext 15.21.2
- HRMS 15.59.1
- Python 3.10+

Later compatible version-15 releases may work, but should be verified in staging first.

## Installation

```bash
cd /path/to/frappe-bench
bench get-app <repository-url> --branch main
bench --site <site-name> install-app masar_requests
bench --site <site-name> migrate
bench build --app masar_requests
bench restart
```

Configure every active employee with a User ID and, when applicable, `reports_to` and `custom_secretary_employee`. Assign enabled users to each Material Request approval role.

## Production readiness check

The check is read-only:

```bash
bench --site <site-name> execute masar_requests.preflight.run_preflight
```

The site is ready when `ready` is `true` and `errors` is empty.

## Automated tests

```bash
bench --site <test-site> run-tests --app masar_requests
```

For focused security tests:

```bash
bench --site <test-site> run-tests --app masar_requests \
  --module masar_requests.tests.test_security_and_workflow
```

## Architecture

- `leave_application_permissions.py`: leave visibility, write access, sharing, and workflow actions.
- `leave_application_partial_leave.py`: half-day, quarter-day, and hourly leave calculations.
- `material_request_engine.py`: server-side item locks, notifications, and shortage splitting.
- `material_request_sharing.py`: current actor and secretary DocShare synchronization.
- `constants.py`: shared workflow states and actions.
- `setup_*.py`: first-install configuration only.
- `patches/`: idempotent updates for existing sites.

The Material Request engine uses native Python hooks. Legacy text Server Scripts are removed by migration.

## Updating

```bash
cd /path/to/frappe-bench
bench update --reset
bench --site <site-name> migrate
bench build --app masar_requests
bench restart
```

Always back up the site and test workflow transitions in staging before production migration.

## Uninstall

```bash
bench --site <site-name> uninstall-app masar_requests
```

Uninstall removes app-owned workflows, fields, property setters, scripts, and permissions while preserving Material Request business documents.

## License

MIT

## الإصدار V21 — أوقات وردية متغيرة حسب أيام الأسبوع

يضيف V21 تكاملًا مركزيًا لأوقات `Shift Type` المختلفة حسب اليوم مع `Employee Checkin` و`Auto Attendance` والإجازة الجزئية والمهمة الرسمية، دون تعديل ملفات HRMS الأصلية. راجع:

- `V21_VARIABLE_SHIFT_REPORT_AR.md`
- `INSTALL_V21.md`
- `ACCEPTANCE_TESTS_V21_AR.md`
