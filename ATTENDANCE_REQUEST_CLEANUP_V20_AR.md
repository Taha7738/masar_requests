# أوامر إزالة تخصيصات Attendance Request القديمة — V20

## المبدأ

لا تستخدم SQL يدوياً ولا تحذف سجلات `Attendance Request`. التنظيف يزيل فقط البصمات المحددة لتخصيص التطبيق القديم:

- Custom Fields المعروفة بالاسم.
- Property Setters الخاصة بهذه الحقول وبعض الخصائص القياسية التي غيّرها التطبيق.
- Workflow باسم `Official Duty Workflow masar_requests`.
- Print Format باسم `Masar Attendance Request Form`.
- صف Custom DocPerm المحدد بدقة لدور `HR User`.

أي تخصيص آخر لا يطابق هذه البصمة يُترك كما هو.

## الترتيب الآمن

```bash
cd ~/frappe-v-15
bench --site masar-test.local backup --with-files

cd apps/masar_requests
unzip -o /المسار/masar_requests_v20_official_duty_partial_leave_modified_files_only.zip
bash cleanup_obsolete_attendance_files.sh .

cd ~/frappe-v-15
bench --site masar-test.local migrate
bench build --app masar_requests
bench --site masar-test.local clear-cache
bench restart
```

`migrate` هو الخطوة الأساسية؛ لأن Patch V20 ينشئ المستند الجديد، يرحل السجلات القديمة، ثم يحذف التخصيص القديم.

## تنظيف يدوي احتياطي بعد migrate فقط

```bash
bench --site masar-test.local execute \
  masar_requests.setup_official_duty_request.cleanup_legacy_attendance_request_customization
```

## فحص النتيجة

```bash
bench --site masar-test.local execute \
  masar_requests.setup_official_duty_request.audit_legacy_attendance_request_customization
```

## الملفات القديمة المحذوفة من مصدر التطبيق

```text
masar_requests/public/js/attendance_request.js
masar_requests/public/js/attendance_request_list.js
masar_requests/masar_requests/print_format/masar_attendance_request_form/
```

كما يحذف سكربت التنظيف ملفات Patches القديمة التي لم تعد مسجلة في `patches.txt`.

## ملفات Python القديمة التي بقيت عمداً

تبقى بعض الوحدات القديمة مثل:

```text
attendance_request_override.py
attendance_request_permissions.py
setup_attendance_request.py
```

لكنها غير مسجلة في `hooks.py` ولا تعمل وقت التشغيل. أُبقيت لأن Patches تاريخية ما زالت مسجلة قد تحتاج استيرادها عند تثبيت التطبيق أو ترقية موقع قديم جداً. حذفها قد يؤدي إلى فشل `bench migrate` على تلك المواقع.
