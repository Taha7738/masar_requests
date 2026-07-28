# Masar Requests V13 — الملفات المعدلة

## النتيجة الوظيفية

- طلب المهمة يستخدم نفس حالات وإجراءات سير عمل طلب الإجازة الجاهز.
- الموظف البديل اختياري؛ عند غيابه يرسل الطلب مباشرة إلى المسؤول المباشر.
- المسؤول المباشر يرى الطلب فور إرساله إلى البديل، ويستطيع اعتماده قبل البديل أو الانتظار.
- رفض الموظف البديل في طلب الإجازة أو طلب المهمة يعيد الطلب إلى الموظف لاختيار بديل جديد أو الإرسال مباشرة إلى المدير.
- ألغيت دورة تقرير الإنجاز المستقلة بالكامل، وأصبح التقرير المنسق مطلوباً من أول إنشاء الطلب، والمرفق ظاهر من البداية.
- اعتماد التقرير في الطباعة يستخدم نفس موافقات المسؤول المباشر والموارد البشرية في دورة الطلب الأولى.
- HR User يشاهد ويطبع جميع طلبات الإجازة والمهمة والمواد، دون تعديل أو إجراءات Workflow.
- سير عمل طلب المواد لم يتغير؛ تغيرت صلاحية HR User والطباعة فقط.
- عند الاعتماد النهائي المبكر، تعرض خانات الاعتماد المتجاوزة: «تم الاعتماد من قبل / Approved by: اسم المستخدم».

## الملفات البرمجية الرئيسية

- `masar_requests/setup_attendance_request.py`
- `masar_requests/attendance_request_permissions.py`
- `masar_requests/setup_leave_and_shift.py`
- `masar_requests/leave_application_permissions.py`
- `masar_requests/hr_user_read_only.py`
- `masar_requests/setup_material_request.py`
- `masar_requests/material_request_engine.py`
- `masar_requests/hooks.py`
- `masar_requests/install.py`
- `masar_requests/public/js/attendance_request.js`
- `masar_requests/public/js/masar_requests.js`
- `masar_requests/public/js/material_request.js`
- تنسيقات الطباعة الثلاثة داخل `masar_requests/masar_requests/print_format/`
- `masar_requests/patches/simplify_attendance_leave_workflow_and_hr_user_v13.py`
- `masar_requests/patches.txt`

## ملفات قديمة أزيلت

أزيلت ملفات Patches الخاصة بإصدارات Attendance V1–V12، وأزيل ملف القائمة القديم `attendance_request_list.js`؛ لأنها لم تعد مستخدمة بعد ترقية V13.
