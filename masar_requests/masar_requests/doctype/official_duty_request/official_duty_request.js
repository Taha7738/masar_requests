// AR: يحتوي هذا الملف على منطق واجهة المستخدم مع توثيق ثنائي اللغة للدوال والمعالجات.
// EN: This file contains user-interface logic with bilingual documentation for functions and handlers.

// ============================================================================
// AR: واجهة مستند المهمة الرسمية المستقل
// EN: Independent Official Duty Request client interface
// ============================================================================

const MASAR_OFFICIAL_DUTY = {
    DRAFT: "Draft",
    APPROVAL_REJECTED: "Rejected",
    HOURLY: "Hourly",
};

frappe.ui.form.on("Official Duty Request", {
    // AR: تنفيذ معالج `setup` ضمن هذا الملف.
    // EN: Execute the `setup` handler within this file.
    setup(frm) {
        // AR: قصر اختيار البديل على موظفي نفس الشركة والقسم.
        // EN: Limit substitute selection to the applicant's company/department.
        frm.set_query("custom_substitute_employee", () => ({
            filters: {
                status: "Active",
                company: frm.doc.company || undefined,
                department: frm.doc.department || undefined,
                name: ["!=", frm.doc.employee || ""],
            },
        }));
    },

    async onload(frm) {
        // AR: تعبئة الموظف المرتبط بالمستخدم عند إنشاء طلب شخصي جديد.
        // EN: Populate the Employee linked to the current user on a new personal request.
        if (frm.is_new() && !frm.doc.employee) {
            const response = await frappe.call({
                method: "masar_requests.official_duty_request_permissions.get_current_user_employee",
            });
            if (response.message?.name) {
                await frm.set_value("employee", response.message.name);
            }
        }

        if (frm.is_new()) {
            await frm.set_value("reason", "On Duty");
            if (!frm.doc.from_date) await frm.set_value("from_date", frappe.datetime.get_today());
            if (!frm.doc.to_date) await frm.set_value("to_date", frm.doc.from_date);
        }
    },

    // AR: تنفيذ معالج `refresh` ضمن هذا الملف.
    // EN: Execute the `refresh` handler within this file.
    refresh(frm) {
        masar_official_duty_apply_style();
        frm.page.wrapper.addClass("masar-official-duty-request");
        masar_official_duty_manage_type(frm);
        masar_official_duty_lock_fields(frm);
        masar_official_duty_enforce_hr_user_read_only(frm);
        masar_official_duty_add_reconcile_button(frm);
        masar_official_duty_add_manual_reconciliation_button(frm);
    },

    // AR: تنفيذ معالج `duty_type` ضمن هذا الملف.
    // EN: Execute the `duty_type` handler within this file.
    duty_type(frm) {
        masar_official_duty_manage_type(frm);
    },

    // AR: تنفيذ معالج `from_date` ضمن هذا الملف.
    // EN: Execute the `from_date` handler within this file.
    from_date(frm) {
        if (frm.doc.duty_type === MASAR_OFFICIAL_DUTY.HOURLY) {
            frm.set_value("to_date", frm.doc.from_date);
        }
    },

    // AR: تنفيذ معالج `custom_leaving_time` ضمن هذا الملف.
    // EN: Execute the `custom_leaving_time` handler within this file.
    custom_leaving_time(frm) {
        masar_official_duty_validate_times(frm);
    },

    // AR: تنفيذ معالج `custom_return_time` ضمن هذا الملف.
    // EN: Execute the `custom_return_time` handler within this file.
    custom_return_time(frm) {
        masar_official_duty_validate_times(frm);
    },
});

// AR: تنفيذ معالج `masar_official_duty_manage_type` ضمن هذا الملف.
// EN: Execute the `masar_official_duty_manage_type` handler within this file.
function masar_official_duty_manage_type(frm) {
    // AR: إظهار حقول الوقت للمهمة بالساعات فقط.
    // EN: Show time fields only for hourly duty.
    const isHourly = frm.doc.duty_type === MASAR_OFFICIAL_DUTY.HOURLY;
    ["custom_leaving_time", "custom_return_time"].forEach((fieldname) => {
        if (!frm.fields_dict[fieldname]) return;
        frm.toggle_display(fieldname, isHourly);
        frm.toggle_reqd(fieldname, isHourly);
    });

    if (isHourly && frm.doc.from_date && frm.doc.to_date !== frm.doc.from_date) {
        frm.set_value("to_date", frm.doc.from_date);
    }
}

// AR: تنفيذ معالج `masar_official_duty_lock_fields` ضمن هذا الملف.
// EN: Execute the `masar_official_duty_lock_fields` handler within this file.
function masar_official_duty_lock_fields(frm) {
    // AR: الطلب الجديد قابل للتعبئة؛ بعد أول حفظ تقفل بيانات المهمة.
    // EN: New request data is editable; mission data is locked after first save.
    if (frm.is_new()) return;

    Object.keys(frm.fields_dict).forEach((fieldname) => {
        const fieldtype = frm.fields_dict[fieldname]?.df?.fieldtype;
        if (["Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table"].includes(fieldtype)) {
            return;
        }
        frm.set_df_property(fieldname, "read_only", 1);
    });

    // AR: بعد رفض البديل يستطيع مقدم الطلب اختيار بديل آخر.
    // EN: After substitute rejection, the applicant may select another substitute.
    const applicantUser = frm.doc.custom_applicant_user || frm.doc.owner;
    const canReselectSubstitute =
        frappe.session.user === applicantUser &&
        frm.doc.workflow_state === MASAR_OFFICIAL_DUTY.DRAFT &&
        frm.doc.custom_substitute_approval === MASAR_OFFICIAL_DUTY.APPROVAL_REJECTED;

    if (canReselectSubstitute && frm.fields_dict.custom_substitute_employee) {
        frm.set_df_property("custom_substitute_employee", "read_only", 0);
    }
}

// AR: تنفيذ معالج `masar_official_duty_is_hr_user_read_only` ضمن هذا الملف.
// EN: Execute the `masar_official_duty_is_hr_user_read_only` handler within this file.
function masar_official_duty_is_hr_user_read_only() {
    // AR: HR Manager وSystem Manager غير مشمولين بقيد العرض فقط.
    // EN: HR Manager and System Manager are exempt from the read-only HR User rule.
    return (
        frappe.user.has_role("HR User") &&
        !frappe.user.has_role("HR Manager") &&
        !frappe.user.has_role("System Manager") &&
        frappe.session.user !== "Administrator"
    );
}

// AR: تنفيذ معالج `masar_official_duty_is_personal_request` ضمن هذا الملف.
// EN: Execute the `masar_official_duty_is_personal_request` handler within this file.
function masar_official_duty_is_personal_request(frm) {
    // AR: تحديد طلب المستخدم الشخصي.
    // EN: Determine whether this is the current user's personal request.
    return Boolean(
        frm.is_new() ||
        frm.doc.owner === frappe.session.user ||
        frm.doc.custom_applicant_user === frappe.session.user
    );
}

// AR: تنفيذ معالج `masar_official_duty_enforce_hr_user_read_only` ضمن هذا الملف.
// EN: Execute the `masar_official_duty_enforce_hr_user_read_only` handler within this file.
function masar_official_duty_enforce_hr_user_read_only(frm) {
    // AR: مستخدم الموارد البشرية يعرض ويطبع طلبات الآخرين فقط.
    // EN: HR User may only read and print other employees' requests.
    if (
        !masar_official_duty_is_hr_user_read_only() ||
        masar_official_duty_is_personal_request(frm)
    ) return;

    frm.disable_save();
    window.setTimeout(() => {
        frm.page.clear_primary_action();
        frm.page.clear_secondary_action();
    }, 0);
}

// AR: تنفيذ معالج `masar_official_duty_add_reconcile_button` ضمن هذا الملف.
// EN: Execute the `masar_official_duty_add_reconcile_button` handler within this file.
function masar_official_duty_add_reconcile_button(frm) {
    // AR: إعادة المعالجة متاحة فقط للموارد البشرية بعد اعتماد الطلب.
    // EN: Manual retry is available to HR only after final approval.
    const authorized =
        frappe.session.user === "Administrator" ||
        frappe.user.has_role("HR Manager") ||
        frappe.user.has_role("System Manager");

    if (!authorized || frm.doc.docstatus !== 1) return;

    frm.add_custom_button(__("Reconcile Attendance"), async () => {
        const response = await frappe.call({
            method: "masar_requests.official_duty_engine.reconcile_official_duty_now",
            args: { name: frm.doc.name },
            freeze: true,
            freeze_message: __("Reconciling attendance..."),
        });
        if (response.message) {
            frappe.show_alert({
                message: __("Attendance reconciliation completed."),
                indicator: "green",
            });
            await frm.reload_doc();
        }
    }, __("Attendance"));
}

// AR: تنفيذ معالج `masar_official_duty_validate_times` ضمن هذا الملف.
// EN: Execute the `masar_official_duty_validate_times` handler within this file.
function masar_official_duty_validate_times(frm) {
    // AR: يمنع تساوي الوقتين فقط؛ الوردية الليلية قد تعبر منتصف الليل.
    // EN: Only equal times are blocked; an overnight shift may cross midnight.
    if (
        frm.doc.duty_type !== MASAR_OFFICIAL_DUTY.HOURLY ||
        !frm.doc.custom_leaving_time ||
        !frm.doc.custom_return_time
    ) return;

    if (frm.doc.custom_leaving_time === frm.doc.custom_return_time) {
        frappe.msgprint({
            title: __("Time Error"),
            indicator: "red",
            message: __("Leaving Time and Return Time cannot be the same."),
        });
        frm.set_value("custom_return_time", "");
    }
}

// AR: تنفيذ معالج `masar_official_duty_apply_style` ضمن هذا الملف.
// EN: Execute the `masar_official_duty_apply_style` handler within this file.
function masar_official_duty_apply_style() {
    // AR: تنسيق خفيف ومتوافق مع الوضعين الفاتح والداكن.
    // EN: Lightweight styling compatible with light and dark modes.
    if (document.getElementById("masar-official-duty-style")) return;

    const style = document.createElement("style");
    style.id = "masar-official-duty-style";
    style.textContent = `
        .masar-official-duty-request .form-section {
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-bottom: 14px;
            padding: 14px 16px 6px;
            background: var(--card-bg);
        }
        .masar-official-duty-request .section-head {
            font-weight: 700;
        }
    `;
    document.head.appendChild(style);
}

// MASAR_OFFICIAL_DUTY_LEAVE_CONFLICT_CHECK
// AR: تنبيه مبكر عند تعارض المهمة الرسمية مع إجازة معتمدة.
// EN: Early warning for approved leave overlapping Official Duty.

async function masar_check_official_duty_leave_conflict(frm) {
    if (
        !frm.doc.employee ||
        !frm.doc.from_date ||
        !frm.doc.to_date
    ) {
        frm.__masar_leave_conflict_key = null;
        return;
    }

    const response = await frappe.call({
        method:
            "masar_requests.official_duty_request_permissions." +
            "get_official_duty_leave_conflicts",
        args: {
            employee: frm.doc.employee,
            from_date: frm.doc.from_date,
            to_date: frm.doc.to_date,
        },
        freeze: false,
        quiet: true,
    });

    const conflicts = response.message || [];

    if (!conflicts.length) {
        frm.__masar_leave_conflict_key = null;
        return;
    }

    const conflictKey = conflicts
        .map((row) => row.name)
        .sort()
        .join("|");

    if (frm.__masar_leave_conflict_key === conflictKey) {
        return;
    }

    frm.__masar_leave_conflict_key = conflictKey;

    const rows = conflicts
        .map(
            (row) =>
                `<li>
                    <b>${frappe.utils.escape_html(row.name)}</b>
                    — ${frappe.utils.escape_html(row.leave_type || "")}
                    (${frappe.datetime.str_to_user(row.from_date)}
                    إلى
                    ${frappe.datetime.str_to_user(row.to_date)})
                </li>`
        )
        .join("");

    frappe.msgprint({
        title: __("تعارض مع إجازة معتمدة"),
        indicator: "orange",
        message:
            __("الموظف لديه إجازة معتمدة متداخلة مع تاريخ المهمة:") +
            `<ul>${rows}</ul>` +
            __(
                "لن يمكن حفظ الطلب حتى تُلغى الإجازة أو يُختار تاريخ آخر."
            ),
    });
}

frappe.ui.form.on("Official Duty Request", {
    // AR: تنفيذ معالج `employee` ضمن هذا الملف.
    // EN: Execute the `employee` handler within this file.
    employee(frm) {
        return masar_check_official_duty_leave_conflict(frm);
    },

    // AR: تنفيذ معالج `from_date` ضمن هذا الملف.
    // EN: Execute the `from_date` handler within this file.
    from_date(frm) {
        return masar_check_official_duty_leave_conflict(frm);
    },

    // AR: تنفيذ معالج `to_date` ضمن هذا الملف.
    // EN: Execute the `to_date` handler within this file.
    to_date(frm) {
        return masar_check_official_duty_leave_conflict(frm);
    },

    // AR: تنفيذ معالج `onload_post_render` ضمن هذا الملف.
    // EN: Execute the `onload_post_render` handler within this file.
    onload_post_render(frm) {
        return masar_check_official_duty_leave_conflict(frm);
    },
});

// MASAR_MANUAL_OFFICIAL_DUTY_RECONCILIATION
// AR: تنفيذ معالج `masar_official_duty_add_manual_reconciliation_button` ضمن هذا الملف.
// EN: Execute the `masar_official_duty_add_manual_reconciliation_button` handler within this file.
function masar_official_duty_add_manual_reconciliation_button(frm) {
    const authorized =
        frappe.session.user === "Administrator" ||
        frappe.user.has_role("HR Manager") ||
        frappe.user.has_role("System Manager");

    if (
        !authorized ||
        frm.doc.docstatus !== 1 ||
        frm.doc.processing_status !== "Manual Review"
    ) return;

    frm.add_custom_button(__("Settle Uncovered Hours"), async () => {
        const contextResponse = await frappe.call({
            method:
                "masar_requests.manual_official_duty_reconciliation." +
                "get_manual_reconciliation_context",
            args: { name: frm.doc.name },
            freeze: true,
            freeze_message: __("Loading manual reconciliation details..."),
        });

        const context = contextResponse.message || {};
        const rows = context.eligible_rows || [];
        if (!rows.length) {
            const blocked = (context.rows || [])
                .filter((row) => row.blocked_reason)
                .map(
                    (row) =>
                        `<li><b>${frappe.datetime.str_to_user(row.attendance_date)}</b>: ` +
                        `${frappe.utils.escape_html(row.blocked_reason)}</li>`
                )
                .join("");
            frappe.msgprint({
                title: __("Manual Reconciliation Unavailable"),
                indicator: "orange",
                message:
                    blocked ||
                    __("No eligible uncovered attendance hours were found."),
            });
            return;
        }

        const byDate = Object.fromEntries(
            rows.map((row) => [row.attendance_date, row])
        );
        const dialog = new frappe.ui.Dialog({
            title: __("Settle Uncovered Attendance Hours"),
            fields: [
                {
                    fieldname: "attendance_date",
                    fieldtype: "Select",
                    label: __("Attendance Date"),
                    options: rows.map((row) => row.attendance_date).join("\n"),
                    default: rows[0].attendance_date,
                    reqd: 1,
                },
                {
                    fieldname: "official_duty_hours",
                    fieldtype: "Float",
                    label: __("Official Duty Hours"),
                    read_only: 1,
                },
                {
                    fieldname: "credited_working_hours",
                    fieldtype: "Float",
                    label: __("Currently Credited Hours"),
                    read_only: 1,
                },
                {
                    fieldname: "uncovered_hours",
                    fieldtype: "Float",
                    label: __("Uncovered Hours"),
                    read_only: 1,
                },
                {
                    fieldname: "confirmed_hours",
                    fieldtype: "Float",
                    label: __("Administratively Confirmed Hours"),
                    description: __(
                        "For safety, this action must confirm all uncovered hours."
                    ),
                    reqd: 1,
                },
                {
                    fieldname: "notes",
                    fieldtype: "Small Text",
                    label: __("HR Reconciliation Notes"),
                    reqd: 1,
                },
            ],
            primary_action_label: __("Apply Manual Reconciliation"),
            primary_action: async (values) => {
                const response = await frappe.call({
                    method:
                        "masar_requests.manual_official_duty_reconciliation." +
                        "apply_manual_reconciliation",
                    args: {
                        name: frm.doc.name,
                        attendance_date: values.attendance_date,
                        confirmed_hours: values.confirmed_hours,
                        notes: values.notes,
                    },
                    freeze: true,
                    freeze_message: __("Applying manual reconciliation..."),
                });
                dialog.hide();
                frappe.show_alert({
                    message: __("Manual attendance reconciliation completed."),
                    indicator: "green",
                });
                if (response.message) await frm.reload_doc();
            },
        });

        // AR: تنفيذ معالج `updateDialog` ضمن هذا الملف.
        // EN: Execute the `updateDialog` handler within this file.
        const updateDialog = () => {
            const selected = byDate[dialog.get_value("attendance_date")];
            if (!selected) return;
            dialog.set_value("official_duty_hours", selected.official_duty_hours);
            dialog.set_value("credited_working_hours", selected.credited_working_hours);
            dialog.set_value("uncovered_hours", selected.uncovered_hours);
            dialog.set_value("confirmed_hours", selected.uncovered_hours);
        };

        dialog.fields_dict.attendance_date.df.onchange = updateDialog;
        dialog.show();
        updateDialog();
    }, __("Attendance"));
}
