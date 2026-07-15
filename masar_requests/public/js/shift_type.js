// AR: أحداث نموذج نوع المناوبة (الوردية) / EN: Shift Type form events
frappe.ui.form.on('Shift Type', {
    
    // AR: حدث يتفعل عند اختيار أو تغيير قائمة العطلات (Holiday List) / EN: Triggered when holiday list is selected or changed
    holiday_list: function(frm) {
        // AR: التأكد من وجود قيمة في الحقل / EN: Ensure field has a value
        if (frm.doc.holiday_list) {
            // AR: جلب يوم الإجازة الأسبوعية من إعدادات قائمة العطلات المختارة / EN: Fetch weekly off day from selected holiday list settings
            frappe.db.get_value('Holiday List', frm.doc.holiday_list, 'weekly_off', (r) => {
                // AR: إذا تم العثور على يوم الإجازة بنجاح / EN: If weekly off day is successfully found
                if (r && r.weekly_off) {
                    // AR: استدعاء دالة تعبئة جدول المناوبات بناءً على أيام العمل / EN: Call function to populate shift table based on working days
                    populate_shift_table(frm, r.weekly_off);
                }
            });
        }
    }
});

// AR: دالة تعبئة جدول توقيتات المناوبة آلياً / EN: Function to auto-populate shift times table
function populate_shift_table(frm, weekly_off) {
    // AR: مصفوفة تحتوي على كافة أيام الأسبوع باللغة الإنجليزية القياسية / EN: Array containing all days of the week in standard English
    const all_days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    
    // AR: فلترة الأيام لاستبعاد يوم الإجازة الأسبوعية / EN: Filter days to exclude the weekly off day
    const active_days = all_days.filter(day => day !== weekly_off);
    
    // AR: تفريغ الجدول الفرعي الحالي لبنائه من جديد بنظافة / EN: Clear current child table to rebuild it cleanly
    frm.clear_table('custom_shift_times');

    // AR: حلقة للمرور على أيام العمل النشطة لإنشاء أسطر في الجدول / EN: Loop through active working days to create table rows
    active_days.forEach(day => {
        // AR: إضافة سطر جديد في جدول أوقات المناوبة / EN: Add a new row to custom shift times table
        let row = frm.add_child('custom_shift_times');
        
        // AR: تعيين اسم اليوم في السطر الجديد / EN: Set day name in the new row
        row.day_of_week = day; 
        
        // AR: تعيين وقت بداية الوردية الافتراضي (الذي أدخله المستخدم في الأعلى) / EN: Set default shift start time (input by user above)
        row.start_time = frm.doc.start_time; 
        
        // AR: تعيين وقت نهاية الوردية الافتراضي / EN: Set default shift end time
        row.end_time = frm.doc.end_time;
    });
    
    // AR: تحديث الواجهة الأمامية لإظهار السطور الجديدة للمستخدم فوراً / EN: Refresh UI to show the new rows to the user instantly
    frm.refresh_field('custom_shift_times');
}