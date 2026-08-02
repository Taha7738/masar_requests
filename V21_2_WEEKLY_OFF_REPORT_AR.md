# تقرير تصحيح V21.2 — استبعاد أيام العطلة الأسبوعية من جدول الوردية

## الهدف

تعديل جدول الأوقات المتغيرة داخل `Shift Type` ليعرض أيام العمل فقط، مع استبعاد أيام العطلة الأسبوعية المتكررة المسجلة في `Holiday List`.

## السلوك المعتمد

- تُقرأ أيام العطلة الأسبوعية من صفوف `Holiday` التي تحمل `weekly_off = 1`.
- يُستخدم حقل `Holiday List.weekly_off` كخيار احتياطي للتوافق.
- تُستبعد أيام العطلة الأسبوعية من جدول `custom_shift_times`.
- لا تُستبعد العطلات الرسمية ذات التاريخ الواحد، لأنها لا تعني أن يوم الأسبوع كله عطلة.
- عند تغيير `Holiday List` في نموذج `Shift Type` يتزامن الجدول مباشرة.
- عند عدم تحديد `Holiday List` تظهر أيام الأسبوع السبعة؛ لأن نوع الوردية لا يستطيع معرفة قائمة عطلات الموظف أو الشركة على مستوى النموذج.
- التحقق الخادمي يمنع حفظ يوم عطلة أسبوعية داخل الجدول.
- فحص تداخل الورديات يتجاهل أيام العطلة الأسبوعية المستبعدة.

## الملفات المعدلة

- `masar_requests/overrides/shift_type.py`
- `masar_requests/public/js/shift_type.js`
- `masar_requests/setup_leave_and_shift.py`
- `masar_requests/translations/ar.csv`
- `masar_requests/patches.txt`
- `masar_requests/tests/test_security_and_workflow.py`
- `masar_requests/patches/apply_variable_shift_holiday_exclusions_v21_2.py`

كما تتضمن الحزمة تصحيح V21.1 لحقل `status` داخل ترحيل `Attendance Request`:

- `masar_requests/setup_official_duty_request.py`

## حدود التصميم

العطلة الرسمية المفردة، مثل عطلة يوم اثنين في تاريخ محدد، لا تؤدي إلى حذف يوم الاثنين من جدول الوردية. يتولى HRMS القياسي استبعاد ذلك التاريخ من الحضور عبر `Holiday List`.
