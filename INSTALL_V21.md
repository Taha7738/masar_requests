# تثبيت Masar Requests V21

## 1. نسخة احتياطية

```bash
cd ~/frappe-v-15
bench --site masar-test.local backup --with-files
```

## 2. استبدال التطبيق بالمشروع الكامل

```bash
cd ~/frappe-v-15/apps/masar_requests
unzip -o /المسار/masar_requests_v21_variable_shift_full_project.zip
```

> يجب أن تظهر ملفات التطبيق مباشرة داخل `apps/masar_requests`، وليس داخل مجلد إضافي متداخل.

## 3. فحص Python وJavaScript

```bash
cd ~/frappe-v-15
./env/bin/python -m compileall -q apps/masar_requests/masar_requests

find apps/masar_requests/masar_requests -name '*.js' -print0 \
  | xargs -0 -n1 node --check
```

## 4. الترحيل والبناء

```bash
bench --site masar-test.local migrate
bench build --app masar_requests
bench --site masar-test.local clear-cache
bench --site masar-test.local clear-website-cache
bench restart
```

ثم نفّذ تحديثًا قاسيًا للمتصفح:

```text
Ctrl + Shift + R
```

## 5. فحص توافق HRMS

```bash
bench --site masar-test.local execute \
  masar_requests.overrides.shift_type.audit_shift_times_patch
```

يجب أن تكون القيم الأساسية `true`:

```text
patch_compatible
get_shift_details_wrapped
last_sync_calculation_wrapped
no_checkin_absence_wrapped
half_day_absence_wrapped
```

## 6. فحص الجاهزية

```bash
bench --site masar-test.local execute \
  masar_requests.preflight.run_preflight
```

## 7. الاختبارات

```bash
bench --site masar-test.local run-tests --app masar_requests
```

بعد نجاح الموقع التجريبي، تطبق الخطوات نفسها على موقع الإنتاج بعد نسخة احتياطية جديدة.
