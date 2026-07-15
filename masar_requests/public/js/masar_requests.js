// ======================================================
// masar_requests - Leave Application Partial Leave UI
// Half Day + Quarter Day + Hourly Leave
// UI only. Actual deduction is handled by Python Override.
// No workflow button manipulation here.
// ======================================================

console.log("masar_requests partial leave JS loaded");

frappe.ui.form.on("Leave Application", {
    refresh(frm) {
        masar_requests_inject_leave_application_styles();
        masar_requests_decorate_leave_application_form(frm);

        masar_requests_partial_leave_setup(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    onload(frm) {
        masar_requests_inject_leave_application_styles();
        masar_requests_decorate_leave_application_form(frm);

        masar_requests_partial_leave_setup(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    employee(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_decorate_leave_application_form(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    leave_type(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_decorate_leave_application_form(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    from_date(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        if (masar_requests_is_any_partial(frm) && frm.doc.from_date) {
            masar_requests_set_value_if_changed(frm, "custom_partial_leave_date", frm.doc.from_date);
        }

        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    to_date(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        if (masar_requests_is_any_partial(frm)) {
            masar_requests_apply_partial_single_date(frm);
        }

        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    custom_partial_leave_date(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_apply_partial_single_date(frm);
        masar_requests_update_time_fields_live(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    custom_partial_from_time_ar(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_apply_display_time_to_internal_fields(frm);
        masar_requests_update_time_fields_live(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

    custom_partial_to_time_ar(frm) {
        if (!masar_requests_can_update_partial_leave_values(frm)) return;

        masar_requests_apply_display_time_to_internal_fields(frm);
        masar_requests_update_time_fields_live(frm);
        masar_requests_partial_leave_preview(frm);
        masar_requests_schedule_precise_leave_balance(frm);
    },

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

    total_leave_days(frm) {
        masar_requests_update_balance_after_request_local(frm);
    },

    validate(frm) {
        masar_requests_validate_partial_leave_client(frm);
    }
});


// ======================================================
// Main UI
// ======================================================

function masar_requests_partial_leave_setup(frm) {
    const is_half_day = cint(frm.doc.half_day);
    const is_hourly = cint(frm.doc.is_hourly);
    const is_partial = masar_requests_is_any_partial(frm);

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


function masar_requests_set_display_text_direct(frm, text) {
    if (!masar_requests_has_field(frm, "custom_partial_time_ar_display")) return;

    frm.doc.custom_partial_time_ar_display = text || "";
    frm.refresh_field("custom_partial_time_ar_display");
}


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


function masar_requests_update_balance_after_request_local(frm) {
    if (!frm || !frm.doc) return;
    if (!masar_requests_has_field(frm, "custom_balance_after_this_request")) return;

    const actual_balance = flt(frm.doc.custom_actual_leave_balance || 0, 4);
    const request_days = flt(frm.doc.total_leave_days || 0, 4);
    const after_request = flt(actual_balance - request_days, 4);

    frm.doc.custom_balance_after_this_request = after_request;
    frm.refresh_field("custom_balance_after_this_request");
}


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

function masar_requests_interval_inside_shift(start, end, shift_start, shift_end) {
    const DAY = 24 * 60 * 60;

    if (shift_end > DAY && start < shift_start) {
        start += DAY;
        end += DAY;
    }

    return start >= shift_start && end <= shift_end;
}


function masar_requests_display_time_to_seconds(value) {
    if (!value) return 0;

    value = String(value).trim();

    const parts = value.split(":").map(Number);

    const h = parts[0] || 0;
    const m = parts[1] || 0;
    const s = parts[2] || 0;

    return h * 3600 + m * 60 + s;
}


function masar_requests_time_to_seconds(value) {
    if (!value) return 0;

    value = String(value);

    const parts = value.split(":").map(Number);

    const h = parts[0] || 0;
    const m = parts[1] || 0;
    const s = parts[2] || 0;

    return h * 3600 + m * 60 + s;
}


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

function masar_requests_inject_leave_application_styles() {
    // UI styling and icons have been fully disabled as requested.
    // The interface will revert to the default ERPNext design.
    return;
}


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


function masar_requests_hide_leave_application_dashboard(frm) {
    if (!frm || !frm.doc || frm.doctype !== "Leave Application") return;

    if (masar_requests_has_field(frm, "leave_balance")) {
        frm.set_df_property("leave_balance", "hidden", 1);
        frm.toggle_display("leave_balance", false);
        frm.refresh_field("leave_balance");
    }

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

function masar_requests_is_any_partial(frm) {
    return (
        cint(frm.doc.half_day) ||
        cint(frm.doc.quarter_day) ||
        cint(frm.doc.is_hourly)
    );
}


function masar_requests_is_custom_partial(frm) {
    return cint(frm.doc.quarter_day) || cint(frm.doc.is_hourly);
}


function masar_requests_has_field(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}



function masar_requests_is_full_admin_user() {
    return (
        frappe.session.user === "Administrator" ||
        frappe.user.has_role("System Manager")
    );
}

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


async function masar_requests_set_value_if_changed(frm, fieldname, value) {
    if (!masar_requests_has_field(frm, fieldname)) return;

    const current = frm.doc[fieldname];

    if (String(current ?? "") === String(value ?? "")) return;

    await frm.set_value(fieldname, value);
}


function masar_requests_set_if_exists(frm, fieldname, value) {
    if (!masar_requests_has_field(frm, fieldname)) return;

    const current = frm.doc[fieldname];

    if (String(current ?? "") === String(value ?? "")) return;

    frm.set_value(fieldname, value);
}


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