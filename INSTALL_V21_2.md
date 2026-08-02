# تثبيت تصحيح V21.2 بعد النقل اليدوي

انسخ الملفات الموجودة في حزمة `masar_requests_v21_2_manual_update.zip` فوق نفس المسارات داخل:

`~/frappe-v-15/apps/masar_requests`

لا تنشئ تطبيقًا أو مجلد مشروع جديدًا.

بعد النسخ:

```bash
cd ~/frappe-v-15
./env/bin/python -m compileall -q apps/masar_requests/masar_requests
find apps/masar_requests/masar_requests -type f -name "*.js" -print0 | xargs -0 -r -n1 node --check
bench --site masar-test.local migrate
bench build --app masar_requests
bench --site masar-test.local clear-cache
bench --site masar-test.local clear-website-cache
bench restart
```
