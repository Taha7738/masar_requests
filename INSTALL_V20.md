# تثبيت Masar Requests V20

## 1. نطاق هذا الإصدار

هذا الإصدار مبني حصراً على الملف المصدر:

`masar_requestsاخر اصدار 30-7-2026.zip`

ولا يعيد بناء المشروع من إصدار أقدم. التعديلات محصورة في:

1. فصل المهمة الرسمية عن `Attendance Request` القياسي.
2. تسوية المهمة الرسمية بالساعات مع البصمات العادية فقط، دون إنشاء بصمات وهمية.
3. تسجيل ربع اليوم والإجازة بالساعات في `Attendance` بعد نهاية الوردية، ومنع الراتب حتى اكتمال التسوية، وتصحيح أثرها الدقيق في `Salary Slip`.
4. ترحيل بيانات المهمة القديمة ثم حذف تخصيصات التطبيق القديمة من `Attendance Request` بصورة آمنة.

## 2. النسخة الاحتياطية

نفّذ من مجلد bench، مع استبدال اسم الموقع:

```bash
cd ~/frappe-v-15
bench --site masar-test.local backup --with-files
```

لا تنتقل إلى الإنتاج قبل تجربة الترقية على نسخة اختبار حديثة من قاعدة البيانات.

## 3. تثبيت حزمة الملفات المعدلة فقط

```bash
cd ~/frappe-v-15/apps/masar_requests
unzip -o /المسار/masar_requests_v20_official_duty_partial_leave_modified_files_only.zip
```

لأن فك الضغط لا يحذف الملفات القديمة غير الموجودة في الحزمة، شغّل منظف ملفات التخصيص القديم:

```bash
cd ~/frappe-v-15/apps/masar_requests
bash cleanup_obsolete_attendance_files.sh .
```

هذا الأمر يحذف ملفات المصدر القديمة الخاصة بـ `Attendance Request` فقط، مثل JavaScript وقالب الطباعة القديم. لا يحذف أي سجل من قاعدة البيانات.

## 4. فحص الصياغة قبل الترحيل

```bash
cd ~/frappe-v-15
./env/bin/python -m compileall -q apps/masar_requests/masar_requests
```

## 5. الترحيل والبناء

```bash
cd ~/frappe-v-15
bench --site masar-test.local migrate
bench build --app masar_requests
bench --site masar-test.local clear-cache
bench --site masar-test.local clear-website-cache
bench restart
```

ثم نفّذ تحديثاً قاسياً في المتصفح:

```text
Ctrl + Shift + R
```

## 6. ماذا يفعل Patch V20 أثناء migrate؟

ينفذ بالترتيب التالي:

1. مزامنة `Official Duty Request` وحقول الربط التقنية.
2. إنشاء Workflow المهمة الرسمية على المستند الجديد فقط.
3. إنشاء حقول تدقيق المهمة على `Attendance`، وحقول حالة تسوية الإجازة الجزئية على `Leave Application` و`Attendance`.
4. نسخ طلبات المهمة القديمة من `Attendance Request` إلى المستند الجديد، دون إعادة إنشاء الحضور.
5. حذف حقول وProperty Setters وWorkflow وقالب الطباعة وصف صلاحية HR User التي أنشأها التطبيق سابقاً على `Attendance Request`.
6. إبقاء كل سجلات `Attendance Request` و`Attendance` و`Employee Checkin` التاريخية دون حذف.

## 7. فحص التنظيف بعد migrate

```bash
cd ~/frappe-v-15
bench --site masar-test.local execute \
  masar_requests.setup_official_duty_request.audit_legacy_attendance_request_customization
```

النتيجة السليمة تكون تقريباً:

```text
legacy_custom_fields = []
legacy_workflow_exists = false
legacy_print_format_exists = false
legacy_property_setters = []
legacy_custom_permissions = []
native_hooks_removed_from_code = true
```

قد يظهر `preserved_non_app_property_setter_count` بقيمة أكبر من صفر، وهذا مقصود: هي تخصيصات أخرى لم يثبت أنها مملوكة لهذا التطبيق، ولذلك لم تُحذف.

## 8. أمر التنظيف اليدوي الاحتياطي

عادة لا يلزم لأن Patch V20 ينفذه تلقائياً. يستخدم فقط عندما كان Patch Log مسجلاً سابقاً أو توقفت الترقية بعد مزامنة المستندات:

```bash
cd ~/frappe-v-15
bench --site masar-test.local execute \
  masar_requests.setup_official_duty_request.cleanup_legacy_attendance_request_customization
```

الدالة محمية: ترفض العمل قبل مزامنة `Official Duty Request`، وتحاول ترحيل أي سجل قديم متبقٍ قبل حذف الحقول.

بعدها أعد الفحص:

```bash
bench --site masar-test.local execute \
  masar_requests.setup_official_duty_request.audit_legacy_attendance_request_customization
```

## 9. الاختبارات

```bash
cd ~/frappe-v-15
bench --site masar-test.local run-tests --app masar_requests
```

راجع أيضاً ملف `ACCEPTANCE_TESTS_V20_AR.md` ونفّذ السيناريوهات على الموقع التجريبي.

## 10. الرجوع للخلف

لا تطبق رجوعاً جزئياً عبر نسخ ملفات قديمة فوق الجديدة. الرجوع الآمن يكون باستعادة نسخة قاعدة البيانات والملفات المأخوذة قبل الترقية، ثم إعادة تشغيل البناء والكاش.
