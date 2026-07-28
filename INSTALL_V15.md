# Masar Requests V15

## Arabic / العربية

هذا الإصدار يصلح:

1. مزامنة تنسيق طباعة `Masar Attendance Request Form` مباشرة مع قاعدة البيانات.
2. جلب `custom_achievement_report` ومرفقه من المستند أو من قاعدة البيانات عند الطباعة.
3. استخدام نفس بيانات اعتماد المسؤول المباشر والموارد البشرية في:
   - جهة الاعتماد.
   - اعتماد التقرير.
4. ترجمة إشعارات طلب المهمة وطلب الإجازة حسب لغة المستخدم المستهدف.

### الأوامر

```bash
cd /home/frappe/frappe-bench
bench --site SITE_NAME migrate
bench --site SITE_NAME clear-cache
bench build --app masar_requests
bench restart
```

ثم تحديث المتصفح تحديثاً كاملاً: `Ctrl + Shift + R`.

> الإشعارات القديمة الموجودة مسبقاً لن تتغير؛ الترجمة تطبق على الإشعارات الجديدة.

## English

V15 explicitly syncs the Attendance Request print format into the database,
prints the persisted Achievement Report, repeats the same manager/HR approval
data in both approval sections, and translates new Attendance/Leave notifications
using the target user's language.
