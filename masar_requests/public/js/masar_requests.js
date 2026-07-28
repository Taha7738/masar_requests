// ============================================================================
// AR: واجهة طلب الإجازة في تطبيق Masar Requests.
//     يدعم نصف يوم، ربع يوم، الإجازة بالساعات، وفلترة الموظف البديل
//     ليظهر فقط موظفو نفس إدارة مقدم الطلب.
//
// EN: Leave Application UI for the Masar Requests app.
//     Supports half-day, quarter-day, hourly leave, and substitute filtering
//     so only employees from the applicant's department are displayed.
//
// AR: هذا الملف مسؤول عن واجهة المستخدم فقط، أما التحقق النهائي والحسم
//     فيتم على الخادم داخل ملفات Python.
// EN: This file handles client-side behavior only. Final validation and
//     leave deduction are enforced server-side in Python.
// ============================================================================

console.log("masar_requests partial leave JS loaded");

frappe.ui.form.on("Leave Application", {
    // AR: تهيئة استعلامات وقواعد النموذج عند إنشائه.
    // EN: Initialize form queries and rules when the form is created.
    setup(frm) {
        // AR: إعادة تطبيق قواعد العرض والحماية عند تحديث الواجهة.
        //     الاستعلام يعرض موظفي نفس إدارة مقدم الطلب فقط.
        // EN: Reapply display and protection rules when the UI refreshes.
        //     the form is initialized. The query returns employees from the
        //     applicant's department only.
        masar_requests_set_substitute_employee_query(frm);
    },

    refresh(frm) {
        masar_requests_inject_leave_application_styles();
        masar_requests_decorate_leave_application_form(frm);

        masar_requests_partial_leave_setup(frm);
        masar_requests_schedule_precise_leave_balance(frm);
        masar_requests_leave_apply_hr_user_read_only(frm);
    },

    // AR: تهيئة الواجهة والحسابات عند تحميل المستند.
    // EN: Initialize UI state and calculations when the document loads.
    onload(frm) {
        masar_requests_inject_leave_application_styles();
        masar_requests_decorate_leave_application_form(frm);

        masar_requests_partial_leave_setup(frm);
        masar_requests_schedule_precise_leave_balance(frm);
        masar_requests_leave_apply_hr_user_read_only(frm);
    },

    // AR: تحديث بيانات الإجازة والبديل عند تغيير الموظف.
    // EN: Refresh leave and substitute data when the Employee changes.
    employee(frm) {
        // AR: عند تغيير الموظف مقدم الطلب، يجب مسح الموظف البديل السابق؛
        //     لأن البديل القديم قد يكون تابعًا لإدارة مختلفة.
        // EN: When the leave applicant changes, clear the previously selected
        //     substitute because that employee may belong to another department.
        if (frm.doc.custom_substitute_employee) {
            frm.set_value("custom_substitute_employee", null);
        }

        // AR: إعادة ربط فلتر الموظف البديل بالإدارة الجديدة لمقدم الطلب.
        // EN: Re-bind the substitute filter to the new applicant's department.
        masar_requests_set_substitute_employee_query(frm);

        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_decorate_leave_application_form(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: إعادة حساب الرصيد عند تغيير نوع الإجازة.
    // EN: Recalculate balance when the Leave Type changes.
    leave_type(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_decorate_leave_application_form(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: تحديث تاريخ الإجازة الجزئية عند تغيير تاريخ البداية.
    // EN: Update the partial-leave date when From Date changes.
    from_date(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        if (masar_requests_is_any_partial(frm) && frm.doc.from_date) {
            masar_requests_set_value_if_changed(frm, "custom_partial_leave_date", frm.doc.from_date);
        }

        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: توحيد تاريخي الطلب عند تغيير تاريخ النهاية.
    // EN: Normalize request dates when To Date changes.
    to_date(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        if (masar_requests_is_any_partial(frm)) {
            masar_requests_apply_partial_single_date(frm);
        }

        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: إعادة حساب الإجازة عند تغيير تاريخها الجزئي.
    // EN: Recalculate partial leave when its date changes.
    custom_partial_leave_date(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_apply_partial_single_date(frm);
        masar_requests_update_time_fields_live(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: تحديث وقت البداية الداخلي والحسابات المباشرة.
    // EN: Update internal start time and live calculations.
    custom_partial_from_time_ar(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_apply_display_time_to_internal_fields(frm);
        masar_requests_update_time_fields_live(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: تحديث وقت النهاية الداخلي والحسابات المباشرة.
    // EN: Update internal end time and live calculations.
    custom_partial_to_time_ar(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_apply_display_time_to_internal_fields(frm);
        masar_requests_update_time_fields_live(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: تفعيل خيار نصف يوم وإلغاء الخيارات الجزئية الأخرى.
    // EN: Enable Half Day and clear other partial-leave options.
    half_day(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        if (cint(frm.doc.half_day)) {
            masar_requests_set_value_if_changed(frm, "quarter_day", 0);
            masar_requests_set_value_if_changed(frm, "is_hourly", 0);
            masar_requests_set_value_if_changed(frm, "custom_partial_to_time_ar", "");

            if (!frm.doc.custom_partial_leave_date && frm.doc.from_date) {
                masar_requests_set_value_if_changed(frm, "custom_partial_leave_date", frm.doc.from_date);
            }

            masar_requests_apply_partial_single_date(frm);
        } else {
            masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
            masar_requests_set_calc_field_live(frm, "custom_shift_hours", 0);
            masar_requests_set_display_text_direct(frm, "");
        }

        masar_requests_partial_leave_setup(frm);
        masar_requests_update_time_fields_live(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: تفعيل خيار ربع يوم وإلغاء الخيارات الجزئية الأخرى.
    // EN: Enable Quarter Day and clear other partial-leave options.
    quarter_day(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        if (cint(frm.doc.quarter_day)) {
            masar_requests_set_value_if_changed(frm, "half_day", 0);
            masar_requests_set_value_if_changed(frm, "half_day_date", "");
            masar_requests_set_value_if_changed(frm, "is_hourly", 0);
            masar_requests_set_value_if_changed(frm, "custom_partial_to_time_ar", "");

            if (!frm.doc.custom_partial_leave_date && frm.doc.from_date) {
                masar_requests_set_value_if_changed(frm, "custom_partial_leave_date", frm.doc.from_date);
            }

            masar_requests_apply_partial_single_date(frm);
        } else {
            masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
            masar_requests_set_calc_field_live(frm, "custom_shift_hours", 0);
            masar_requests_set_display_text_direct(frm, "");
        }

        masar_requests_partial_leave_setup(frm);
        masar_requests_update_time_fields_live(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: تفعيل الإجازة بالساعات وإلغاء الخيارات الجزئية الأخرى.
    // EN: Enable Hourly Leave and clear other partial options.
    is_hourly(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        if (cint(frm.doc.is_hourly)) {
            masar_requests_set_value_if_changed(frm, "half_day", 0);
            masar_requests_set_value_if_changed(frm, "half_day_date", "");
            masar_requests_set_value_if_changed(frm, "quarter_day", 0);

            if (!frm.doc.custom_partial_leave_date && frm.doc.from_date) {
                masar_requests_set_value_if_changed(frm, "custom_partial_leave_date", frm.doc.from_date);
            }

            masar_requests_apply_partial_single_date(frm);
        } else {
            masar_requests_set_value_if_changed(frm, "custom_partial_to_time_ar", "");
            masar_requests_set_value_if_changed(frm, "from_time", "");
            masar_requests_set_value_if_changed(frm, "to_time", "");
            masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
            masar_requests_set_calc_field_live(frm, "custom_shift_hours", 0);
            masar_requests_set_display_text_direct(frm, "");
        }

        masar_requests_partial_leave_setup(frm);
        masar_requests_update_time_fields_live(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    // AR: تحديث الرصيد المتبقي عند تغير عدد أيام الإجازة.
    // EN: Update the remaining balance when total days change.
    total_leave_days(frm) {
        masar_requests_update_balance_after_request_local(frm);
    },

    // AR: التحقق من مدخلات الإجازة الجزئية قبل الحفظ.
    // EN: Validate partial-leave inputs before saving.
    validate(frm) {
        masar_requests_validate_partial_leave_client(frm);
    }
});


// ============================================================================
// AR: ربط حقل الموظف البديل باستعلام موظفي الإدارة نفسها.
// EN: Bind the substitute field to the same-department Employee query.
// ============================================================================

function masar_requests_set_substitute_employee_query(frm) {
    // AR: التوقف بأمان إذا لم يكن الحقل المخصص موجودًا في النموذج.
    // EN: Exit safely when the custom substitute field is not present.
    if (!frm.fields_dict.custom_substitute_employee) return;

    // AR: ربط حقل الموظف البديل باستعلام Python مخصص على الخادم.
    // EN: Bind the substitute field to a custom server-side Python query.
    frm.set_query("custom_substitute_employee", function () {
        // AR: لا تعرض أي موظف قبل تحديد مقدم طلب الإجازة.
        // EN: Return no employees until the leave applicant is selected.
        if (!frm.doc.employee) {
            return {
                filters: {
                    name: ["=", ""],
                },
            };
        }

        // AR: إرسال الموظف الحالي إلى الخادم؛ ليحدد الخادم إدارته ويعيد
        //     الموظفين النشطين من الإدارة نفسها فقط.
        // EN: Send the selected employee to the server. The server resolves
        //     the employee's department and returns active employees from the
        //     same department only.
        return {
            query: "masar_requests.leave_application_permissions.get_same_department_substitute_employees",
            filters: {
                employee: frm.doc.employee,
            },
        };
    });
}


// ======================================================
// Main UI
// ======================================================

// AR: ضبط ظهور وقراءة حقول الإجازة الجزئية.
// EN: Configure visibility and read-only state for partial-leave fields.
function masar_requests_partial_leave_setup(frm) {
    const is_half_day = cint(frm.doc.half_day);
    const is_hourly = cint(frm.doc.is_hourly);
    const is_partial = masar_requests_is_any_partial(frm);

    // AR:
    // إخفاء حقل المسؤول المباشر من واجهة طلب الإجازة فقط.
    // يبقى الحقل موجودًا داخليًا لاستخدامه في الصلاحيات وسير العمل.
    //
    // EN:
    // Hide the direct manager field from the Leave Application UI only.
    // Keep the field internally for permissions and workflow processing.
    if (masar_requests_has_field(frm, "custom_direct_manager_employee")) {
        frm.set_df_property("custom_direct_manager_employee", "hidden", 1);
        frm.toggle_display("custom_direct_manager_employee", false);
    }

    masar_requests_hide_leave_application_dashboard(frm);

    masar_requests_toggle_if_exists(frm, "leave_balance", false);

    frm.toggle_display("custom_partial_leave_date", is_partial);
    frm.toggle_reqd("custom_partial_leave_date", is_partial);

    frm.toggle_display("custom_partial_from_time_ar", is_partial);
    frm.toggle_reqd("custom_partial_from_time_ar", is_partial);

    frm.toggle_display("custom_partial_to_time_ar", is_hourly);
    frm.toggle_reqd("custom_partial_to_time_ar", is_hourly);

    masar_requests_toggle_if_exists(frm, "custom_partial_time_ar_display", is_partial);

    frm.toggle_display("from_time", false);
    frm.toggle_display("to_time", false);
    frm.toggle_reqd("from_time", false);
    frm.toggle_reqd("to_time", false);

    if (masar_requests_has_field(frm, "custom_leave_period")) {
        frm.toggle_display("custom_leave_period", false);
        frm.toggle_reqd("custom_leave_period", false);
    }

    masar_requests_toggle_if_exists(frm, "custom_leave_hours", is_partial);
    masar_requests_toggle_if_exists(frm, "custom_shift_hours", is_partial);

    if (masar_requests_can_update_partial_leave_values(frm)) {
        if (is_partial) {
            frm.toggle_display("from_date", false);
            frm.toggle_display("to_date", false);
            frm.toggle_display("half_day_date", false);
        } else {
            frm.toggle_display("from_date", true);
            frm.toggle_display("to_date", true);
            frm.toggle_display("half_day_date", is_half_day);
        }

        frm.set_df_property("quarter_day", "read_only", 0);
        frm.set_df_property("is_hourly", "read_only", 0);
        frm.set_df_property("custom_partial_leave_date", "read_only", 0);
        frm.set_df_property("custom_partial_from_time_ar", "read_only", 0);
        frm.set_df_property("custom_partial_to_time_ar", "read_only", 0);
    } else {
        frm.toggle_display("from_date", true);
        frm.toggle_display("to_date", true);
        frm.toggle_display("half_day_date", is_half_day);

        frm.set_df_property("quarter_day", "read_only", 1);
        frm.set_df_property("is_hourly", "read_only", 1);
        frm.set_df_property("custom_partial_leave_date", "read_only", 1);
        frm.set_df_property("custom_partial_from_time_ar", "read_only", 1);
        frm.set_df_property("custom_partial_to_time_ar", "read_only", 1);
        frm.set_df_property("custom_partial_time_ar_display", "read_only", 1);
        frm.set_df_property("custom_leave_hours", "read_only", 1);
        frm.set_df_property("custom_shift_hours", "read_only", 1);
    }
}


// AR: التحقق في الواجهة من صحة خيارات وأوقات الإجازة الجزئية.
// EN: Validate partial-leave options and times in the client.
function masar_requests_validate_partial_leave_client(frm) {
    const selected =
        cint(frm.doc.half_day) +
        cint(frm.doc.quarter_day) +
        cint(frm.doc.is_hourly);

    if (selected > 1) {
        frappe.throw(__("Only one option can be selected: Half Day, Quarter Day, or Hourly Leave."));
    }

    if (selected) {
        if (!frm.doc.employee) {
            frappe.throw(__("Employee is required."));
        }

        if (!frm.doc.custom_partial_leave_date) {
            frappe.throw(__("Partial Leave Date is required."));
        }

        if (!frm.doc.custom_partial_from_time_ar) {
            frappe.throw(__("Start Time is required."));
        }

        frm.doc.from_date = frm.doc.custom_partial_leave_date;
        frm.doc.to_date = frm.doc.custom_partial_leave_date;

        frm.doc.from_time = masar_requests_seconds_to_time(
            masar_requests_display_time_to_seconds(frm.doc.custom_partial_from_time_ar)
        );

        if (cint(frm.doc.half_day)) {
            frm.doc.half_day_date = frm.doc.custom_partial_leave_date;
            frm.doc.total_leave_days = 0.5;
        }

        if (cint(frm.doc.is_hourly)) {
            if (!frm.doc.custom_partial_to_time_ar) {
                frappe.throw(__("End Time is required for Hourly Leave."));
            }

            const interval = masar_requests_get_live_hourly_interval(frm);

            if (interval) {
                frm.doc.to_time = masar_requests_seconds_to_time(interval.end);
            } else {
                frm.doc.to_time = masar_requests_seconds_to_time(
                    masar_requests_display_time_to_seconds(frm.doc.custom_partial_to_time_ar)
                );
            }
        }
    }
}


// AR: توحيد طلب الإجازة الجزئية على تاريخ واحد.
// EN: Force a partial leave request to use one date.
async function masar_requests_apply_partial_single_date(frm) {
    if (!masar_requests_can_update_partial_leave_values(frm)) return;
    if (!masar_requests_is_any_partial(frm)) return;
    if (!frm.doc.custom_partial_leave_date) return;

    await masar_requests_set_value_if_changed(frm, "from_date", frm.doc.custom_partial_leave_date);
    await masar_requests_set_value_if_changed(frm, "to_date", frm.doc.custom_partial_leave_date);

    if (cint(frm.doc.half_day)) {
        await masar_requests_set_value_if_changed(frm, "half_day_date", frm.doc.custom_partial_leave_date);
    } else {
        await masar_requests_set_value_if_changed(frm, "half_day_date", "");
    }
}


// AR: تحويل الوقت المعروض إلى حقول الوقت الداخلية.
// EN: Convert display times into internal time fields.
function masar_requests_apply_display_time_to_internal_fields(frm) {
    if (!masar_requests_is_any_partial(frm)) return;

    if (frm.doc.custom_partial_from_time_ar) {
        frm.doc.from_time = masar_requests_seconds_to_time(
            masar_requests_display_time_to_seconds(frm.doc.custom_partial_from_time_ar)
        );
    }

    if (cint(frm.doc.is_hourly) && frm.doc.custom_partial_to_time_ar) {
        const interval = masar_requests_get_live_hourly_interval(frm);

        if (interval) {
            frm.doc.to_time = masar_requests_seconds_to_time(interval.end);
        } else {
            frm.doc.to_time = masar_requests_seconds_to_time(
                masar_requests_display_time_to_seconds(frm.doc.custom_partial_to_time_ar)
            );
        }
    }
}


// ======================================================
// Live UI Updates Before Save
// ======================================================

// AR: تحديث الساعات والأيام مباشرة أثناء إدخال الوقت.
// EN: Update hours and day fraction while the user enters time.
function masar_requests_update_time_fields_live(frm) {
    if (!masar_requests_can_update_partial_leave_values(frm)) return;
    if (!masar_requests_is_any_partial(frm)) return;
    if (!frm.doc.custom_partial_from_time_ar) return;

    const start_seconds = masar_requests_display_time_to_seconds(frm.doc.custom_partial_from_time_ar);

    if (cint(frm.doc.half_day)) {
        if (frm.doc.custom_shift_hours && flt(frm.doc.custom_shift_hours) > 0) {
            const leave_hours = flt(frm.doc.custom_shift_hours / 2, 4);
            const duration_seconds = leave_hours * 3600;
            const end_seconds = start_seconds + duration_seconds;

            masar_requests_set_display_text_direct(
                frm,
                `${__("From")} ${masar_requests_seconds_to_display_time(start_seconds)} ${__("to")} ${masar_requests_seconds_to_display_time(end_seconds)}`
            );

            masar_requests_set_calc_field_live(frm, "custom_leave_hours", leave_hours);
            masar_requests_set_calc_field_live(frm, "total_leave_days", 0.5);
        }

        return;
    }

    if (cint(frm.doc.quarter_day)) {
        if (frm.doc.custom_shift_hours && flt(frm.doc.custom_shift_hours) > 0) {
            const leave_hours = flt(frm.doc.custom_shift_hours / 4, 4);
            const duration_seconds = leave_hours * 3600;
            const end_seconds = start_seconds + duration_seconds;

            masar_requests_set_display_text_direct(
                frm,
                `${__("From")} ${masar_requests_seconds_to_display_time(start_seconds)} ${__("to")} ${masar_requests_seconds_to_display_time(end_seconds)}`
            );

            masar_requests_set_calc_field_live(frm, "custom_leave_hours", leave_hours);
            masar_requests_set_calc_field_live(frm, "total_leave_days", 0.25);
        }

        return;
    }

    if (cint(frm.doc.is_hourly)) {
        if (!frm.doc.custom_partial_to_time_ar) {
            masar_requests_set_display_text_direct(
                frm,
                `${__("From")} ${masar_requests_seconds_to_display_time(start_seconds)} ${__("to")}`
            );

            masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
            masar_requests_set_calc_field_live(frm, "total_leave_days", 0);
            return;
        }

        const interval = masar_requests_get_live_hourly_interval(frm);

        if (!interval) {
            masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
            masar_requests_set_calc_field_live(frm, "total_leave_days", 0);
            return;
        }

        masar_requests_set_display_text_direct(
            frm,
            `${__("From")} ${masar_requests_seconds_to_display_time(interval.start)} ${__("to")} ${masar_requests_seconds_to_display_time(interval.end)}`
        );

        masar_requests_set_calc_field_live(frm, "custom_leave_hours", interval.hours);

        if (frm.doc.custom_shift_hours && flt(frm.doc.custom_shift_hours) > 0) {
            masar_requests_set_calc_field_live(
                frm,
                "total_leave_days",
                flt(interval.hours / flt(frm.doc.custom_shift_hours), 4)
            );
        }
    }
}


// AR: حساب الفاصل الزمني المدخل للإجازة بالساعات.
// EN: Calculate the currently entered hourly-leave interval.
function masar_requests_get_live_hourly_interval(frm) {
    if (!frm.doc.custom_partial_from_time_ar || !frm.doc.custom_partial_to_time_ar) {
        return null;
    }

    let start = masar_requests_display_time_to_seconds(frm.doc.custom_partial_from_time_ar);
    let end = masar_requests_display_time_to_seconds(frm.doc.custom_partial_to_time_ar);

    if (end <= start) {
        end += 12 * 60 * 60;
    }

    if (end <= start) {
        end += 24 * 60 * 60;
    }

    const hours = flt((end - start) / 3600, 4);

    if (hours <= 0) {
        return null;
    }

    return {
        start: start,
        end: end,
        hours: hours
    };
}


// AR: تحديث نص فترة الإجازة الظاهر للمستخدم.
// EN: Update the displayed leave-period text.
function masar_requests_set_display_text_direct(frm, text) {
    if (!masar_requests_has_field(frm, "custom_partial_time_ar_display")) return;

    frm.doc.custom_partial_time_ar_display = text || "";
    frm.refresh_field("custom_partial_time_ar_display");
}


// AR: تحديث قيمة حقل محسوب دون دورة حفظ إضافية.
// EN: Update a calculated field without an extra save cycle.
function masar_requests_set_calc_field_live(frm, fieldname, value) {
    if (!masar_requests_has_field(frm, fieldname)) return;

    frm.doc[fieldname] = value;
    frm.refresh_field(fieldname);

    if (
        fieldname === "total_leave_days" ||
        fieldname === "custom_actual_leave_balance" ||
        fieldname === "custom_leave_hours" ||
        fieldname === "custom_shift_hours"
    ) {
        masar_requests_update_balance_after_request_local(frm);
    }
}

// ======================================================
// Preview and Calculations
// ======================================================

// AR: معاينة مدة الإجازة الجزئية والتحقق من وقوعها داخل الوردية.
// EN: Preview partial duration and validate it against the shift.
async function masar_requests_partial_leave_preview(frm) {
    if (!masar_requests_can_update_partial_leave_values(frm)) return;
    if (!frm.doc.employee || !frm.doc.custom_partial_leave_date) return;
    if (!masar_requests_is_any_partial(frm)) return;
    if (!frm.doc.custom_partial_from_time_ar) return;

    await masar_requests_apply_partial_single_date(frm);
    masar_requests_apply_display_time_to_internal_fields(frm);

    const shift = await masar_requests_get_employee_shift(
        frm.doc.employee,
        frm.doc.custom_partial_leave_date
    );

    if (!shift) {
        masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
        masar_requests_set_calc_field_live(frm, "custom_shift_hours", 0);
        console.warn("No shift found for employee/date");
        return;
    }

    let shift_start = masar_requests_time_to_seconds(shift.start_time);
    let shift_end = masar_requests_time_to_seconds(shift.end_time);

    if (shift_end <= shift_start) {
        shift_end += 24 * 60 * 60;
    }

    const shift_hours = flt((shift_end - shift_start) / 3600, 4);

    if (!shift_hours || shift_hours <= 0) {
        masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
        masar_requests_set_calc_field_live(frm, "custom_shift_hours", 0);
        return;
    }

    masar_requests_set_calc_field_live(frm, "custom_shift_hours", flt(shift_hours, 4));

    if (cint(frm.doc.half_day)) {
        const start_seconds = masar_requests_display_time_to_seconds(frm.doc.custom_partial_from_time_ar);
        const leave_hours = flt(shift_hours / 2, 4);
        const duration_seconds = leave_hours * 3600;
        const end_seconds = start_seconds + duration_seconds;

        if (!masar_requests_interval_inside_shift(start_seconds, end_seconds, shift_start, shift_end)) {
            frappe.msgprint({
                title: __('Shift Time Exceeded'),
                indicator: 'red',
                message: __('Half-day leave time exceeds the shift time for today. The shift ends at ') + masar_requests_seconds_to_display_time(shift_end)
            });
            // Clearing the field prevents the user from saving
            frappe.model.set_value(frm.doctype, frm.docname, 'custom_partial_from_time_ar', '');
            masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
            masar_requests_set_calc_field_live(frm, "total_leave_days", 0);
            masar_requests_set_display_text_direct(frm, "");
            return;
        }

        masar_requests_set_display_text_direct(
            frm,
            `${__("From")} ${masar_requests_seconds_to_display_time(start_seconds)} ${__("to")} ${masar_requests_seconds_to_display_time(end_seconds)}`
        );

        await masar_requests_set_value_if_changed(frm, "from_time", masar_requests_seconds_to_time(start_seconds));
        await masar_requests_set_value_if_changed(frm, "to_time", masar_requests_seconds_to_time(end_seconds));

        masar_requests_set_calc_field_live(frm, "custom_leave_hours", leave_hours);
        masar_requests_set_calc_field_live(frm, "total_leave_days", 0.5);

        return;
    }

    if (cint(frm.doc.quarter_day)) {
        const start_seconds = masar_requests_display_time_to_seconds(frm.doc.custom_partial_from_time_ar);
        const leave_hours = flt(shift_hours / 4, 4);
        const duration_seconds = leave_hours * 3600;
        const end_seconds = start_seconds + duration_seconds;

        if (!masar_requests_interval_inside_shift(start_seconds, end_seconds, shift_start, shift_end)) {
            frappe.msgprint({
                title: __('Shift Time Exceeded'),
                indicator: 'red',
                message: __('Quarter-day leave time exceeds the shift time for today. The shift ends at ') + masar_requests_seconds_to_display_time(shift_end)
            });
            frappe.model.set_value(frm.doctype, frm.docname, 'custom_partial_from_time_ar', '');
            masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
            masar_requests_set_calc_field_live(frm, "total_leave_days", 0);
            masar_requests_set_display_text_direct(frm, "");
            return;
        }

        masar_requests_set_display_text_direct(
            frm,
            `${__("From")} ${masar_requests_seconds_to_display_time(start_seconds)} ${__("to")} ${masar_requests_seconds_to_display_time(end_seconds)}`
        );

        await masar_requests_set_value_if_changed(frm, "from_time", masar_requests_seconds_to_time(start_seconds));
        await masar_requests_set_value_if_changed(frm, "to_time", masar_requests_seconds_to_time(end_seconds));

        masar_requests_set_calc_field_live(frm, "custom_leave_hours", leave_hours);
        masar_requests_set_calc_field_live(frm, "total_leave_days", 0.25);

        return;
    }

    if (cint(frm.doc.is_hourly)) {
        if (!frm.doc.custom_partial_to_time_ar) {
            masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
            masar_requests_set_calc_field_live(frm, "total_leave_days", 0);
            return;
        }

        const interval = masar_requests_get_hourly_interval_inside_shift(
            frm.doc.custom_partial_from_time_ar,
            frm.doc.custom_partial_to_time_ar,
            shift_start,
            shift_end
        );

        if (!interval || interval.hours <= 0) {
            frappe.model.set_value(frm.doctype, frm.docname, 'custom_partial_to_time_ar', '');
            masar_requests_set_calc_field_live(frm, "custom_leave_hours", 0);
            masar_requests_set_calc_field_live(frm, "total_leave_days", 0);
            masar_requests_set_display_text_direct(frm, "");
            return;
        }

        const leave_days = flt(interval.hours / shift_hours, 4);

        await masar_requests_set_value_if_changed(
            frm,
            "from_time",
            masar_requests_seconds_to_time(interval.start)
        );

        await masar_requests_set_value_if_changed(
            frm,
            "to_time",
            masar_requests_seconds_to_time(interval.end)
        );

        masar_requests_set_calc_field_live(frm, "custom_leave_hours", flt(interval.hours, 4));
        masar_requests_set_calc_field_live(frm, "total_leave_days", leave_days);

        masar_requests_set_display_text_direct(
            frm,
            `${__("From")} ${masar_requests_seconds_to_display_time(interval.start)} ${__("to")} ${masar_requests_seconds_to_display_time(interval.end)}`
        );
    }
}
// ======================================================
// Precise Leave Balance
// ======================================================

// AR: جلب رصيد الإجازة الدقيق من الخادم وعرضه.
// EN: Fetch and display the precise server-side leave balance.
async function masar_requests_update_precise_leave_balance(frm) {
    if (!frm || !frm.doc) return;
    if (!frm.doc.employee || !frm.doc.leave_type) return;

    const balance_date =
        frm.doc.custom_partial_leave_date ||
        frm.doc.from_date ||
        frappe.datetime.get_today();

    let exclude_docname = null;

    if (frm.doc.name && !frm.doc.__islocal) {
        exclude_docname = frm.doc.name;
    }

    const r = await frappe.call({
        method: "masar_requests.leave_application_partial_leave.get_precise_leave_balance",
        args: {
            employee: frm.doc.employee,
            leave_type: frm.doc.leave_type,
            date: balance_date,
            exclude_docname: exclude_docname
        }
    });

    if (r && r.message !== undefined && r.message !== null) {
        const actual_balance = flt(r.message, 4);

        masar_requests_set_calc_field_live(frm, "custom_actual_leave_balance", actual_balance);
        masar_requests_update_balance_after_request_local(frm);
    }
}


// AR: حساب الرصيد المتوقع بعد الطلب محليًا.
// EN: Calculate projected balance after the request locally.
function masar_requests_update_balance_after_request_local(frm) {
    if (!frm || !frm.doc) return;
    if (!masar_requests_has_field(frm, "custom_balance_after_this_request")) return;

    const actual_balance = flt(frm.doc.custom_actual_leave_balance || 0, 4);
    const request_days = flt(frm.doc.total_leave_days || 0, 4);
    const after_request = flt(actual_balance - request_days, 4);

    frm.doc.custom_balance_after_this_request = after_request;
    frm.refresh_field("custom_balance_after_this_request");
}


// AR: جدولة تحديث الرصيد لتجنب تكرار طلبات الخادم.
// EN: Debounce balance updates to avoid duplicate server calls.
function masar_requests_schedule_precise_leave_balance(frm) {
    if (!frm || !frm.doc) return;

    masar_requests_hide_leave_application_dashboard(frm);

    if (frm._masar_requests_balance_timer) {
        clearTimeout(frm._masar_requests_balance_timer);
    }

    if (frm._masar_requests_dashboard_timer) {
        clearTimeout(frm._masar_requests_dashboard_timer);
    }

    frm._masar_requests_balance_timer = setTimeout(async () => {
        await masar_requests_update_precise_leave_balance(frm);
        masar_requests_hide_leave_application_dashboard(frm);
    }, 300);

    frm._masar_requests_dashboard_timer = setTimeout(() => {
        masar_requests_hide_leave_application_dashboard(frm);
    }, 900);
}


// ======================================================
// Shift Fetching
// ======================================================

// AR: جلب وردية الموظف في التاريخ المحدد.
// EN: Fetch the Employee shift for the selected date.
async function masar_requests_get_employee_shift(employee, date) {
    const assignments = await frappe.db.get_list("Shift Assignment", {
        filters: [
            ["employee", "=", employee],
            ["docstatus", "=", 1],
            ["start_date", "<=", date]
        ],
        fields: ["name", "shift_type", "start_date", "end_date"],
        order_by: "start_date desc",
        limit: 20
    });

    let shift_type = null;

    if (assignments && assignments.length) {
        const valid_assignment = assignments.find(row => {
            return !row.end_date || row.end_date >= date;
        });

        if (valid_assignment) {
            shift_type = valid_assignment.shift_type;
        }
    }

    if (!shift_type) {
        const employee_value = await frappe.db.get_value(
            "Employee",
            employee,
            ["default_shift"]
        );

        if (
            employee_value &&
            employee_value.message &&
            employee_value.message.default_shift
        ) {
            shift_type = employee_value.message.default_shift;
        }
    }

    if (!shift_type) return null;

    // Fetch the entire shift document to access the child table
    const shift_doc = await frappe.db.get_doc("Shift Type", shift_type);

    if (!shift_doc) return null;

    let actual_start_time = shift_doc.start_time;
    let actual_end_time = shift_doc.end_time;

    // Extract the day name strictly in English to match the stored values in the table
    const day_name = moment(date).locale('en').format('dddd');

    // Search the child table for custom times specifically for this day
    if (shift_doc.custom_shift_times && shift_doc.custom_shift_times.length > 0) {
        const custom_day = shift_doc.custom_shift_times.find(row => row.day_of_week === day_name);
        
        if (custom_day) {
            actual_start_time = custom_day.start_time;
            actual_end_time = custom_day.end_time;
        }
    }

    return {
        shift_type: shift_type,
        start_time: actual_start_time,
        end_time: actual_end_time
    };
}

// ======================================================
// Time Calculations
// ======================================================

// AR: حساب ساعات الإجازة الواقعة داخل الوردية.
// EN: Calculate leave hours that fall inside the shift.
function masar_requests_calculate_leave_hours_inside_shift(from_value, to_value, shift_start, shift_end) {
    const interval = masar_requests_get_hourly_interval_inside_shift(
        from_value,
        to_value,
        shift_start,
        shift_end
    );

    if (!interval) {
        return 0;
    }

    return interval.hours;
}


// AR: تطبيع فترة الإجازة بالساعات داخل الوردية.
// EN: Normalize the hourly-leave interval inside the shift.
function masar_requests_get_hourly_interval_inside_shift(from_value, to_value, shift_start, shift_end) {
    const DAY = 24 * 60 * 60;
    const HALF_DAY = 12 * 60 * 60;

    let leave_start = masar_requests_display_time_to_seconds(from_value);
    let leave_end = masar_requests_display_time_to_seconds(to_value);

    if (leave_end <= leave_start) {
        const end_plus_12 = leave_end + HALF_DAY;

        if (end_plus_12 > leave_start && end_plus_12 <= shift_end) {
            leave_end = end_plus_12;
        } else {
            leave_end += DAY;
        }
    }

    if (shift_end > DAY && leave_start < shift_start) {
        leave_start += DAY;
        leave_end += DAY;
    }

    if (leave_start < shift_start || leave_end > shift_end) {
        frappe.msgprint({
            title: __('Shift Time Exceeded'),
            indicator: 'red',
            message: __('Leave time is outside shift hours. Today\'s shift: from ') + masar_requests_seconds_to_display_time(shift_start) + __(' to ') + masar_requests_seconds_to_display_time(shift_end)
        });
        return null;
    }

    return {
        start: leave_start,
        end: leave_end,
        hours: flt((leave_end - leave_start) / 3600, 4)
    };
}

// AR: التحقق من احتواء الوردية لفترة الإجازة كاملة.
// EN: Check whether the shift contains the full leave interval.
function masar_requests_interval_inside_shift(start, end, shift_start, shift_end) {
    const DAY = 24 * 60 * 60;

    if (shift_end > DAY && start < shift_start) {
        start += DAY;
        end += DAY;
    }

    return start >= shift_start && end <= shift_end;
}


// AR: تحويل الوقت المعروض إلى ثوانٍ.
// EN: Convert a displayed time to seconds.
function masar_requests_display_time_to_seconds(value) {
    if (!value) return 0;

    value = String(value).trim();

    const parts = value.split(":").map(Number);

    const h = parts[0] || 0;
    const m = parts[1] || 0;
    const s = parts[2] || 0;

    return h * 3600 + m * 60 + s;
}


// AR: تحويل قيمة وقت قياسية إلى ثوانٍ.
// EN: Convert a standard time value to seconds.
function masar_requests_time_to_seconds(value) {
    if (!value) return 0;

    value = String(value);

    const parts = value.split(":").map(Number);

    const h = parts[0] || 0;
    const m = parts[1] || 0;
    const s = parts[2] || 0;

    return h * 3600 + m * 60 + s;
}


// AR: تحويل الثواني إلى وقت بصيغة 24 ساعة.
// EN: Convert seconds to 24-hour time.
function masar_requests_seconds_to_time(seconds) {
    const DAY = 24 * 60 * 60;

    seconds = Math.floor(seconds) % DAY;

    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    return [
        String(h).padStart(2, "0"),
        String(m).padStart(2, "0"),
        String(s).padStart(2, "0")
    ].join(":");
}


// AR: تحويل الثواني إلى وقت مقروء بصيغة 12 ساعة.
// EN: Convert seconds to readable 12-hour time.
function masar_requests_seconds_to_display_time(seconds) {
    const DAY = 24 * 60 * 60;

    seconds = Math.floor(seconds) % DAY;

    const hour24 = Math.floor(seconds / 3600);
    const minute = Math.floor((seconds % 3600) / 60);
    const second = Math.floor(seconds % 60);

    const period = hour24 >= 12 ? __("PM") : __("AM");

    let hour12 = hour24 % 12;

    if (hour12 === 0) {
        hour12 = 12;
    }

    return `${String(hour12).padStart(2, "0")}:${String(minute).padStart(2, "0")}:${String(second).padStart(2, "0")} ${period}`;
}


// ======================================================
// UI Styling and Dashboard Hide
// ======================================================

// AR: إضافة أنماط واجهة طلب الإجازة مرة واحدة.
// EN: Inject Leave Application UI styles once.
function masar_requests_inject_leave_application_styles() {
    // UI styling and icons have been fully disabled as requested.
    // The interface will revert to the default ERPNext design.
    return;
}


// AR: جلب الحاوية المرئية لنموذج طلب الإجازة.
// EN: Return the visible Leave Application form wrapper.
function masar_requests_get_form_wrapper(frm) {
    if (!frm || !frm.wrapper) return null;

    const wrapper = frm.wrapper;

    if (wrapper instanceof HTMLElement) {
        return wrapper;
    }

    if (wrapper.get && typeof wrapper.get === "function") {
        return wrapper.get(0);
    }

    if (wrapper.jquery && wrapper.length) {
        return wrapper[0];
    }

    if (wrapper[0] instanceof HTMLElement) {
        return wrapper[0];
    }

    return null;
}


// AR: تطبيق تنسيق واجهة طلب الإجازة.
// EN: Apply Leave Application form decoration.
function masar_requests_decorate_leave_application_form(frm) {
    if (!frm || frm.doctype !== "Leave Application") return;

    const wrapper = masar_requests_get_form_wrapper(frm);

    if (!wrapper) return;

    wrapper.classList.add("masar_requests-leave-form");

    [100, 300, 900, 1500].forEach((delay) => {
        setTimeout(() => {
            const fresh_wrapper = masar_requests_get_form_wrapper(frm);

            if (fresh_wrapper) {
                fresh_wrapper.classList.add("masar_requests-leave-form");
            }
        }, delay);
    });
}


// AR: إخفاء لوحة معلومات الإجازة القياسية.
// EN: Hide the standard leave dashboard.
function masar_requests_hide_leave_application_dashboard(frm) {
    if (!frm || !frm.doc || frm.doctype !== "Leave Application") return;

    if (masar_requests_has_field(frm, "leave_balance")) {
        frm.set_df_property("leave_balance", "hidden", 1);
        frm.toggle_display("leave_balance", false);
        frm.refresh_field("leave_balance");
    }

    // AR: تنفيذ إخفاء لوحة الإجازة فورًا وبعد اكتمال تحديث الواجهة.
    // EN: Hide the leave dashboard immediately and after UI refreshes.
    const hide_dashboard = () => {
        if (frm.dashboard && frm.dashboard.wrapper) {
            frm.dashboard.wrapper.hide();
            frm.dashboard.wrapper.css("display", "none");
        }

        const wrapper = masar_requests_get_form_wrapper(frm);

        if (!wrapper) return;

        const dashboards = wrapper.querySelectorAll(".form-dashboard");

        dashboards.forEach((dashboard) => {
            dashboard.style.setProperty("display", "none", "important");
            dashboard.setAttribute("data-masar_requests-hidden-dashboard", "1");
        });
    };

    hide_dashboard();
    setTimeout(hide_dashboard, 100);
    setTimeout(hide_dashboard, 300);
    setTimeout(hide_dashboard, 900);
}


// ======================================================
// Helpers
// ======================================================

// AR: التحقق من اختيار أي نوع إجازة جزئية.
// EN: Check whether any partial-leave option is selected.
function masar_requests_is_any_partial(frm) {
    return (
        cint(frm.doc.half_day) ||
        cint(frm.doc.quarter_day) ||
        cint(frm.doc.is_hourly)
    );
}


// AR: التحقق من اختيار ربع يوم أو إجازة بالساعات.
// EN: Check whether Quarter Day or Hourly Leave is selected.
function masar_requests_is_custom_partial(frm) {
    return cint(frm.doc.quarter_day) || cint(frm.doc.is_hourly);
}


// AR: التحقق من وجود حقل داخل النموذج.
// EN: Check whether a field exists on the form.
function masar_requests_has_field(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}



// AR: التحقق من أن المستخدم مدير نظام كامل.
// EN: Check whether the current user is a full administrator.
function masar_requests_is_full_admin_user() {
    return (
        frappe.session.user === "Administrator" ||
        frappe.user.has_role("System Manager")
    );
}

// AR: تحديد إمكانية المستخدم تعديل قيم الإجازة الجزئية.
// EN: Determine whether the user may edit partial-leave values.
function masar_requests_can_update_partial_leave_values(frm) {
    if (masar_requests_is_full_admin_user()) {
        return true;
    }

    if (cint(frm.doc.docstatus) !== 0) {
        return false;
    }

    if (frm.is_new()) {
        return true;
    }

    if (!frm.doc.workflow_state) {
        return true;
    }

    return frm.doc.workflow_state === "Draft";
}


// AR: تعيين قيمة الحقل فقط عندما تختلف عن قيمته الحالية.
// EN: Set a field only when its value has changed.
async function masar_requests_set_value_if_changed(frm, fieldname, value) {
    if (!masar_requests_has_field(frm, fieldname)) return;

    const current = frm.doc[fieldname];

    if (String(current ?? "") === String(value ?? "")) return;

    await frm.set_value(fieldname, value);
}


// AR: تعيين قيمة حقل عند وجوده.
// EN: Set a field value when the field exists.
function masar_requests_set_if_exists(frm, fieldname, value) {
    if (!masar_requests_has_field(frm, fieldname)) return;

    const current = frm.doc[fieldname];

    if (String(current ?? "") === String(value ?? "")) return;

    frm.set_value(fieldname, value);
}


// AR: إظهار أو إخفاء حقل عند وجوده.
// EN: Show or hide a field when it exists.
function masar_requests_toggle_if_exists(frm, fieldname, show) {
    if (masar_requests_has_field(frm, fieldname)) {
        frm.toggle_display(fieldname, show);
    }
}


// Make selected functions visible for browser console diagnostics.
window.masar_requests_schedule_precise_leave_balance = masar_requests_schedule_precise_leave_balance;
window.masar_requests_update_precise_leave_balance = masar_requests_update_precise_leave_balance;
window.masar_requests_update_balance_after_request_local = masar_requests_update_balance_after_request_local;
window.masar_requests_hide_leave_application_dashboard = masar_requests_hide_leave_application_dashboard;
window.masar_requests_inject_leave_application_styles = masar_requests_inject_leave_application_styles;
window.masar_requests_decorate_leave_application_form = masar_requests_decorate_leave_application_form;
window.masar_requests_get_form_wrapper = masar_requests_get_form_wrapper;
window.masar_requests_leave_debug = function () {
    const wrapper = masar_requests_get_form_wrapper(cur_frm);

    return {
        style_loaded: !!document.getElementById("masar_requests-leave-application-style"),
        form_class: !!(wrapper && wrapper.classList.contains("masar_requests-leave-form")),
        hide_fn: typeof masar_requests_hide_leave_application_dashboard,
        actual: cur_frm && cur_frm.doc ? cur_frm.doc.custom_actual_leave_balance : null,
        after: cur_frm && cur_frm.doc ? cur_frm.doc.custom_balance_after_this_request : null,
        total_days: cur_frm && cur_frm.doc ? cur_frm.doc.total_leave_days : null,
    };
};


// ======================================================
// User Form Restrictions
// ======================================================

frappe.ui.form.on("User", {
    // AR: إعادة تطبيق قواعد العرض والحماية عند تحديث الواجهة.
    // EN: Reapply display and protection rules when the UI refreshes.
    refresh(frm) {
        if (
            frappe.session.user === frm.doc.name &&
            !masar_requests_is_full_admin_user()
        ) {
            const allowed_fields = ["new_password", "desk_theme"];

            frm.fields.forEach(field => {
                if (!allowed_fields.includes(field.df.fieldname)) {
                    frm.set_df_property(field.df.fieldname, "read_only", 1);
                }
            });
        }
    }
});


// ======================================================
// Realtime Notification Sound
// ======================================================

$(document).ready(function () {
    frappe.realtime.on("masar_requests_sound", (data) => {
        frappe.utils.play_sound("alert");
        frappe.show_alert({
            message: data?.subject || __(" "),
            indicator: "info"
        });
    });
});


// ============================================================================
// AR: حماية طلبات الإجازة للآخرين مع استثناء الطلب الشخصي لمستخدم HR User.
// EN: Protect others' leave requests while exempting an HR User's personal request.
// ============================================================================
function masar_requests_leave_is_hr_user_read_only() {
    return (
        frappe.user.has_role("HR User") &&
        !frappe.user.has_role("HR Manager") &&
        !frappe.user.has_role("System Manager") &&
        frappe.session.user !== "Administrator"
    );
}

function masar_requests_leave_is_personal_request(frm) {
    // AR: الطلب الجديد أو المملوك للمستخدم يعد طلب إجازة شخصياً.
    // EN: A new request or one owned by the current user is a personal leave request.
    return Boolean(frm.is_new() || frm.doc.owner === frappe.session.user);
}

function masar_requests_leave_apply_hr_user_read_only(frm) {
    // AR: تقفل طلبات الآخرين فقط، ويظل طلب المستخدم الشخصي قابلاً للتعامل الطبيعي.
    // EN: Lock other users' requests only; keep the user's personal request fully functional.
    if (
        !masar_requests_leave_is_hr_user_read_only() ||
        masar_requests_leave_is_personal_request(frm)
    ) return;

    Object.keys(frm.fields_dict).forEach((fieldname) => {
        const fieldtype = frm.fields_dict[fieldname]?.df?.fieldtype;
        if (!["Section Break", "Column Break", "Tab Break", "HTML", "Button"].includes(fieldtype)) {
            frm.set_df_property(fieldname, "read_only", 1);
        }
    });

    frm.disable_save();
    window.setTimeout(() => {
        frm.page.clear_primary_action();
        frm.page.clear_secondary_action();
        const actions = [
            "Send to Substitute",
            "Send to Direct Manager",
            "Substitute Approve",
            "Direct Manager Approve",
            "Final Approve",
            "Reject",
        ];
        frm.page.wrapper.find("button, a").each(function () {
            const $item = $(this);
            const label = ($item.attr("data-label") || $item.text() || "").trim();
            if (actions.some((action) => label.includes(action))) $item.remove();
        });
    }, 0);
}
