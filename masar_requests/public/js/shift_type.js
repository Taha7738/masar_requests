// AR: يحتوي هذا الملف على منطق واجهة المستخدم مع توثيق ثنائي اللغة للدوال والمعالجات.
// EN: This file contains user-interface logic with bilingual documentation for functions and handlers.

// ======================================================
// AR: أوقات الوردية المتغيرة حسب يوم الأسبوع
// EN: Weekday-specific Shift Type timings
// ======================================================

const MASAR_SHIFT_DAYS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
];

frappe.ui.form.on("Shift Type", {
    // AR: تنفيذ معالج `refresh` ضمن هذا الملف.
    // EN: Execute the `refresh` handler within this file.
    refresh(frm) {
        // AR: لا تظهر أدوات الجدول إلا عند تفعيل الميزة.
        // EN: Show schedule tools only when the feature is enabled.
        if (!frm.doc.custom_enable_variable_shift_times) return;

        masar_apply_working_day_options(frm);

        frm.add_custom_button(__("Populate Missing Weekdays"), async () => {
            await masar_sync_working_weekdays(frm);
        }, __("Variable Weekday Times"));

        frm.add_custom_button(__("Reset Weekday Times to Standard"), () => {
            frappe.confirm(
                __("This will replace all working-weekday times with the standard Start Time and End Time. Continue?"),
                async () => masar_reset_weekday_times(frm)
            );
        }, __("Variable Weekday Times"));
    },

    async custom_enable_variable_shift_times(frm) {
        // AR: عند التفعيل نضيف أيام العمل الناقصة فقط ولا نمسح الصفوف الصحيحة.
        // EN: On enable, add missing working days only and preserve valid rows.
        if (frm.doc.custom_enable_variable_shift_times) {
            await masar_sync_working_weekdays(frm);
        }
    },

    async holiday_list(frm) {
        // AR: عند تغيير قائمة العطلات نحذف أيام العطلة الأسبوعية من الجدول فورًا.
        // EN: When Holiday List changes, remove recurring weekly-off days immediately.
        if (frm.doc.custom_enable_variable_shift_times) {
            await masar_sync_working_weekdays(frm);
        }
    },

    // AR: تنفيذ معالج `start_time` ضمن هذا الملف.
    // EN: Execute the `start_time` handler within this file.
    start_time(frm) {
        masar_fill_empty_weekday_times(frm);
    },

    // AR: تنفيذ معالج `end_time` ضمن هذا الملف.
    // EN: Execute the `end_time` handler within this file.
    end_time(frm) {
        masar_fill_empty_weekday_times(frm);
    },
});

frappe.ui.form.on("Shift Time Table", {
    // AR: تنفيذ معالج `start_time` ضمن هذا الملف.
    // EN: Execute the `start_time` handler within this file.
    start_time(frm, cdt, cdn) {
        masar_update_row_hours(frm, cdt, cdn);
    },

    // AR: تنفيذ معالج `end_time` ضمن هذا الملف.
    // EN: Execute the `end_time` handler within this file.
    end_time(frm, cdt, cdn) {
        masar_update_row_hours(frm, cdt, cdn);
    },
});

// AR: تنفيذ معالج `masar_get_working_day_configuration` ضمن هذا الملف.
// EN: Execute the `masar_get_working_day_configuration` handler within this file.
async function masar_get_working_day_configuration(frm) {
    // AR: الخادم يميز بين العطلة الأسبوعية والعطلة الرسمية ذات التاريخ الواحد.
    // EN: The server distinguishes recurring weekly offs from one-off holidays.
    const response = await frappe.call({
        method: "masar_requests.overrides.shift_type.get_variable_shift_working_days",
        args: {
            holiday_list: frm.doc.holiday_list || "",
        },
        freeze: false,
    });

    const message = response.message || {};
    return {
        working_days: Array.isArray(message.working_days)
            ? message.working_days
            : [...MASAR_SHIFT_DAYS],
        excluded_days: Array.isArray(message.excluded_days)
            ? message.excluded_days
            : [],
    };
}

// AR: تنفيذ معالج `masar_apply_working_day_options` ضمن هذا الملف.
// EN: Execute the `masar_apply_working_day_options` handler within this file.
async function masar_apply_working_day_options(frm) {
    // AR: قصر قائمة اختيار اليوم على أيام العمل فقط دون تعديل الصفوف عند مجرد الفتح.
    // EN: Limit selectable days to working days without dirtying the form on refresh.
    try {
        const configuration = await masar_get_working_day_configuration(frm);
        masar_set_day_field_options(frm, configuration.working_days);
    } catch (error) {
        console.warn("Could not load working weekdays for Shift Type.", error);
    }
}

// AR: تنفيذ معالج `masar_sync_working_weekdays` ضمن هذا الملف.
// EN: Execute the `masar_sync_working_weekdays` handler within this file.
async function masar_sync_working_weekdays(frm) {
    const configuration = await masar_get_working_day_configuration(frm);
    const workingDays = configuration.working_days;
    const allowed = new Set(workingDays);

    // AR: إزالة صفوف العطلات الأسبوعية فقط؛ العطلات الرسمية لا تغيّر بنية الجدول.
    // EN: Remove recurring weekly-off rows only; one-off holidays do not alter the table.
    frm.doc.custom_shift_times = (frm.doc.custom_shift_times || [])
        .filter(row => allowed.has(row.day_of_week));

    const existing = new Map(
        (frm.doc.custom_shift_times || [])
            .filter(row => row.day_of_week)
            .map(row => [row.day_of_week, row])
    );

    workingDays.forEach(day => {
        if (existing.has(day)) return;
        const row = frm.add_child("custom_shift_times");
        row.day_of_week = day;
        row.start_time = frm.doc.start_time;
        row.end_time = frm.doc.end_time;
        row.shift_hours = masar_shift_duration_hours(row.start_time, row.end_time);
    });

    masar_sort_weekday_rows(frm, workingDays);
    masar_set_day_field_options(frm, workingDays);
    frm.refresh_field("custom_shift_times");
    frm.dirty();
}

// AR: تنفيذ معالج `masar_fill_empty_weekday_times` ضمن هذا الملف.
// EN: Execute the `masar_fill_empty_weekday_times` handler within this file.
function masar_fill_empty_weekday_times(frm) {
    if (!frm.doc.custom_enable_variable_shift_times) return;

    (frm.doc.custom_shift_times || []).forEach(row => {
        if (!row.start_time) row.start_time = frm.doc.start_time;
        if (!row.end_time) row.end_time = frm.doc.end_time;
        row.shift_hours = masar_shift_duration_hours(row.start_time, row.end_time);
    });
    frm.refresh_field("custom_shift_times");
}

// AR: تنفيذ معالج `masar_reset_weekday_times` ضمن هذا الملف.
// EN: Execute the `masar_reset_weekday_times` handler within this file.
async function masar_reset_weekday_times(frm) {
    const configuration = await masar_get_working_day_configuration(frm);
    const allowed = new Set(configuration.working_days);

    (frm.doc.custom_shift_times || [])
        .filter(row => allowed.has(row.day_of_week))
        .forEach(row => {
            row.start_time = frm.doc.start_time;
            row.end_time = frm.doc.end_time;
            row.shift_hours = masar_shift_duration_hours(row.start_time, row.end_time);
        });

    await masar_sync_working_weekdays(frm);
}

// AR: تنفيذ معالج `masar_set_day_field_options` ضمن هذا الملف.
// EN: Execute the `masar_set_day_field_options` handler within this file.
function masar_set_day_field_options(frm, workingDays) {
    const grid = frm.fields_dict.custom_shift_times?.grid;
    if (!grid) return;

    grid.update_docfield_property(
        "day_of_week",
        "options",
        ["", ...workingDays].join("\n")
    );
}

// AR: تنفيذ معالج `masar_sort_weekday_rows` ضمن هذا الملف.
// EN: Execute the `masar_sort_weekday_rows` handler within this file.
function masar_sort_weekday_rows(frm, preferredOrder = MASAR_SHIFT_DAYS) {
    const order = Object.fromEntries(preferredOrder.map((day, index) => [day, index]));
    frm.doc.custom_shift_times = (frm.doc.custom_shift_times || []).sort((a, b) => {
        return (order[a.day_of_week] ?? 99) - (order[b.day_of_week] ?? 99);
    });
    frm.doc.custom_shift_times.forEach((row, index) => {
        row.idx = index + 1;
    });
}

// AR: تنفيذ معالج `masar_update_row_hours` ضمن هذا الملف.
// EN: Execute the `masar_update_row_hours` handler within this file.
function masar_update_row_hours(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    row.shift_hours = masar_shift_duration_hours(row.start_time, row.end_time);
    frm.refresh_field("custom_shift_times");
}

// AR: تنفيذ معالج `masar_shift_duration_hours` ضمن هذا الملف.
// EN: Execute the `masar_shift_duration_hours` handler within this file.
function masar_shift_duration_hours(startValue, endValue) {
    const start = masar_time_to_seconds(startValue);
    let end = masar_time_to_seconds(endValue);
    if (start === null || end === null) return 0;
    if (end <= start) end += 24 * 60 * 60;
    return flt((end - start) / 3600, 4);
}

// AR: تنفيذ معالج `masar_time_to_seconds` ضمن هذا الملف.
// EN: Execute the `masar_time_to_seconds` handler within this file.
function masar_time_to_seconds(value) {
    if (!value) return null;
    const parts = String(value).split(":").map(part => Number(part));
    if (parts.length < 2 || parts.some(number => Number.isNaN(number))) return null;
    return (parts[0] * 3600) + (parts[1] * 60) + (parts[2] || 0);
}
