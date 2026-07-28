// ============================================================================
// AR: واجهة طلب المهمة الرسمية - سير عمل واحد مطابق لطلب الإجازة
// EN: Official Duty UI - one Leave-like workflow
// ============================================================================

const MASAR_ATTENDANCE = Object.freeze({
    DRAFT: "Draft",
    WAITING_SUBSTITUTE: "Waiting for Substitute Approval",
    WAITING_DIRECT_MANAGER: "Waiting for Direct Manager Approval",
    WAITING_HR_MANAGER: "Waiting for HR Manager Approval",
    APPROVED: "Approved",
    REJECTED: "Rejected",

    APPROVAL_REJECTED: "Rejected",

    WORKFLOW_ACTIONS: [
        "Send to Substitute",
        "Send to Direct Manager",
        "Substitute Approve",
        "Direct Manager Approve",
        "Final Approve",
        "Reject",
    ],
});

masar_requests_register_employee_formatter();

frappe.ui.form.on("Attendance Request", {
    setup(frm) {
        // AR: حصر البديل في نفس الإدارة والشركة.
        // EN: Restrict substitute selection to the same department and company.
        frm.set_query("custom_substitute_employee", function () {
            if (!frm.doc.employee) return {};
            return {
                query: "masar_requests.leave_application_permissions.get_same_department_substitute_employees",
                filters: { employee: frm.doc.employee },
            };
        });
    },

    async onload(frm) {
        await masar_requests_prepare_new_request(frm);
    },

    async refresh(frm) {
        frm.$wrapper.addClass("masar-attendance-request");
        masar_requests_apply_attendance_style();
        await masar_requests_prepare_new_request(frm);
        await masar_requests_refresh_substitute_name(frm);
        masar_requests_manage_official_duty_ui(frm);
        masar_requests_lock_request_fields(frm);
        masar_requests_render_employee_names(frm);
        masar_requests_enforce_hr_user_read_only(frm);

        // AR: لا نعرض رسالة "الطلب لا يزال ضمن مسار الاعتماد".
        // EN: Do not show the former approval-route intro alert.
        frm.set_intro("");
    },

    reason(frm) {
        masar_requests_manage_official_duty_ui(frm);
    },

    async custom_substitute_employee(frm) {
        await masar_requests_refresh_substitute_name(frm, true);
        masar_requests_render_employee_names(frm);
    },

    workflow_state(frm) {
        masar_requests_manage_official_duty_ui(frm);
        masar_requests_lock_request_fields(frm);
        masar_requests_enforce_hr_user_read_only(frm);
    },

    custom_leaving_time(frm) {
        masar_requests_validate_times(frm);
    },

    custom_return_time(frm) {
        masar_requests_validate_times(frm);
    },
});

async function masar_requests_prepare_new_request(frm) {
    // AR: تهيئة السبب والموظف في الطلب الجديد فقط.
    // EN: Initialize Reason and Employee only on a new request.
    if (!frm.is_new()) return;

    if (!frm.doc.reason) {
        await frm.set_value("reason", "On Duty");
    }

    if (frm.doc.employee || frm.__masar_loading_employee) return;
    frm.__masar_loading_employee = true;

    try {
        const response = await frappe.call({
            method: "masar_requests.attendance_request_permissions.get_current_user_employee",
            freeze: false,
        });
        const employee = response.message || {};

        if (employee.name) {
            await frm.set_value("employee", employee.name);
        }
        if (employee.employee_name && frm.fields_dict.employee_name) {
            await frm.set_value("employee_name", employee.employee_name);
        }
        if (employee.user_id && frm.fields_dict.custom_applicant_user) {
            await frm.set_value("custom_applicant_user", employee.user_id);
        }
    } finally {
        frm.__masar_loading_employee = false;
    }
}

async function masar_requests_refresh_substitute_name(frm, clearWhenEmpty = false) {
    // AR: تخزين اسم البديل للعرض والطباعة.
    // EN: Store the substitute display name for UI and printing.
    if (!frm.fields_dict.custom_substitute_employee_name) return;

    const employee = frm.doc.custom_substitute_employee;
    if (!employee) {
        if (clearWhenEmpty && frm.doc.custom_substitute_employee_name) {
            await frm.set_value("custom_substitute_employee_name", "");
        }
        return;
    }

    const result = await frappe.db.get_value("Employee", employee, "employee_name");
    const employeeName = result?.message?.employee_name || "";
    if (employeeName && employeeName !== frm.doc.custom_substitute_employee_name) {
        await frm.set_value("custom_substitute_employee_name", employeeName);
    }
}

function masar_requests_manage_official_duty_ui(frm) {
    // AR: التقرير والمرفق ظاهران من أول المعاملة ولا توجد دورة تقرير مستقلة.
    // EN: Report and attachment are visible from creation; no separate report cycle exists.
    const isOnDuty = frm.doc.reason === "On Duty";

    [
        "employee_name",
        "department",
        "company",
        "custom_substitute_employee_name",
        "custom_applicant_user",
        "custom_direct_manager_employee",
        "custom_substitute_approval",
        "custom_direct_manager_approval",
        "custom_substitute_user",
        "custom_direct_manager_user",
        "custom_substitute_approved_by",
        "custom_substitute_approved_on",
        "custom_direct_manager_approved_by",
        "custom_direct_manager_approved_on",
        "custom_hr_approved_by",
        "custom_hr_approved_on",
    ].forEach((fieldname) => masar_requests_toggle_if_present(frm, fieldname, false));

    masar_requests_toggle_if_present(frm, "custom_substitute_employee", isOnDuty);
    masar_requests_toggle_if_present(frm, "custom_on_duty_section", isOnDuty);
    masar_requests_toggle_if_present(frm, "custom_assignment_section", isOnDuty);
    masar_requests_toggle_if_present(frm, "custom_achievement_report_section", isOnDuty);
    masar_requests_toggle_if_present(frm, "custom_achievement_report", isOnDuty);
    masar_requests_toggle_if_present(
        frm,
        "custom_achievement_report_attachment",
        isOnDuty
    );

    [
        "custom_assignment_explanation",
        "custom_mission_location",
        "custom_leaving_time",
        "custom_return_time",
        "custom_achievement_report",
    ].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) frm.toggle_reqd(fieldname, isOnDuty);
    });

    masar_requests_toggle_empty_native_fields(frm, isOnDuty);
}

function masar_requests_toggle_empty_native_fields(frm, isOnDuty) {
    const hasValue = (fieldname) => {
        const value = frm.doc[fieldname];
        return value !== undefined && value !== null && String(value).trim() !== "";
    };

    if (!isOnDuty) {
        masar_requests_toggle_if_present(frm, "half_day", true);
        masar_requests_toggle_if_present(frm, "half_day_date", cint(frm.doc.half_day) === 1);
        masar_requests_toggle_if_present(frm, "include_holidays", true);
        masar_requests_toggle_if_present(frm, "explanation", true);
        return;
    }

    masar_requests_toggle_if_present(frm, "half_day", cint(frm.doc.half_day) === 1);
    masar_requests_toggle_if_present(
        frm,
        "half_day_date",
        cint(frm.doc.half_day) === 1 && hasValue("half_day_date")
    );
    masar_requests_toggle_if_present(
        frm,
        "include_holidays",
        frm.is_new() || cint(frm.doc.include_holidays) === 1
    );
    masar_requests_toggle_if_present(frm, "explanation", hasValue("explanation"));
}

function masar_requests_lock_request_fields(frm) {
    // AR: الطلب الجديد قابل للتعبئة، وبعد أول حفظ تقفل جميع البيانات.
    // EN: A new request is editable; after first save all request data is locked.
    if (frm.is_new()) {
        if (frm.fields_dict.employee) {
            frm.set_df_property("employee", "read_only", 1);
        }
        return;
    }

    Object.keys(frm.fields_dict).forEach((fieldname) => {
        const fieldtype = frm.fields_dict[fieldname]?.df?.fieldtype;
        if (["Section Break", "Column Break", "Tab Break", "HTML", "Button"].includes(fieldtype)) {
            return;
        }
        frm.set_df_property(fieldname, "read_only", 1);
    });

    // AR: الاستثناء الوحيد: بعد رفض البديل يستطيع مقدم الطلب اختيار بديل جديد.
    // EN: The only exception: after substitute rejection, applicant may select a new substitute.
    const applicantUser = frm.doc.custom_applicant_user || frm.doc.owner;
    const isApplicant =
        frappe.session.user === applicantUser || frappe.session.user === frm.doc.owner;
    const canReselectSubstitute =
        isApplicant &&
        frm.doc.workflow_state === MASAR_ATTENDANCE.DRAFT &&
        frm.doc.custom_substitute_approval === MASAR_ATTENDANCE.APPROVAL_REJECTED;

    if (canReselectSubstitute && frm.fields_dict.custom_substitute_employee) {
        frm.set_df_property("custom_substitute_employee", "read_only", 0);
    }

    // AR: استثناء ترحيل للطلبات القديمة التي كان تقريرها فارغاً قبل V13.
    // EN: Migration exception for legacy requests whose report was empty before V13.
    const activeStates = [
        MASAR_ATTENDANCE.DRAFT,
        MASAR_ATTENDANCE.WAITING_SUBSTITUTE,
        MASAR_ATTENDANCE.WAITING_DIRECT_MANAGER,
        MASAR_ATTENDANCE.WAITING_HR_MANAGER,
    ];
    const reportIsEmpty = !masar_requests_rich_text_has_content(
        frm.doc.custom_achievement_report
    );
    if (isApplicant && activeStates.includes(frm.doc.workflow_state) && reportIsEmpty) {
        ["custom_achievement_report", "custom_achievement_report_attachment"].forEach(
            (fieldname) => {
                if (frm.fields_dict[fieldname]) {
                    frm.set_df_property(fieldname, "read_only", 0);
                }
            }
        );
    }
}

function masar_requests_rich_text_has_content(value) {
    // AR: إزالة HTML للتحقق من وجود نص ظاهر. EN: Strip HTML to detect visible text.
    if (!value) return false;
    const holder = document.createElement("div");
    holder.innerHTML = value;
    return (holder.textContent || holder.innerText || "").replace(/\u00a0/g, " ").trim().length > 0;
}

function masar_requests_is_hr_user_read_only() {
    // AR: HR Manager وSystem Manager غير مشمولين بالقيد.
    // EN: HR Manager and System Manager are not subject to the read-only HR User rule.
    return (
        frappe.user.has_role("HR User") &&
        !frappe.user.has_role("HR Manager") &&
        !frappe.user.has_role("System Manager") &&
        frappe.session.user !== "Administrator"
    );
}

function masar_requests_attendance_is_personal_request(frm) {
    // AR: الطلب الجديد أو المملوك للمستخدم يعد طلباً شخصياً.
    // EN: A new request or one owned by the current user is personal.
    return Boolean(
        frm.is_new() ||
        frm.doc.owner === frappe.session.user ||
        frm.doc.custom_applicant_user === frappe.session.user
    );
}

function masar_requests_enforce_hr_user_read_only(frm) {
    // AR: تقفل طلبات الآخرين فقط، ويظل الطلب الشخصي متاحاً حسب سير العمل.
    // EN: Lock other users' requests only; personal requests follow normal workflow.
    if (
        !masar_requests_is_hr_user_read_only() ||
        masar_requests_attendance_is_personal_request(frm)
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

        // AR: إزالة أزرار سير العمل فقط مع إبقاء الطباعة في قائمة Menu.
        // EN: Remove workflow actions only; the Print option remains in Menu.
        frm.page.wrapper.find("button, a").each(function () {
            const $item = $(this);
            const label = ($item.attr("data-label") || $item.text() || "").trim();
            if (MASAR_ATTENDANCE.WORKFLOW_ACTIONS.some((action) => label.includes(action))) {
                $item.remove();
            }
        });
    }, 0);
}

function masar_requests_register_employee_formatter() {
    // AR: عرض اسم الموظف بدلاً من الرقم مع الاحتفاظ بالقيمة الداخلية.
    // EN: Display Employee name while retaining the internal Employee ID.
    if (window.__masarAttendanceEmployeeFormatterRegistered) return;
    window.__masarAttendanceEmployeeFormatterRegistered = true;

    const previousFormatter = frappe.form.link_formatters.Employee;
    frappe.form.link_formatters.Employee = function (value, doc) {
        if (doc?.doctype === "Attendance Request") {
            if (value && value === doc.employee && doc.employee_name) {
                return frappe.utils.escape_html(doc.employee_name);
            }
            if (
                value &&
                value === doc.custom_substitute_employee &&
                doc.custom_substitute_employee_name
            ) {
                return frappe.utils.escape_html(doc.custom_substitute_employee_name);
            }
        }
        return previousFormatter ? previousFormatter(value, doc) : value;
    };
}

function masar_requests_render_employee_names(frm) {
    // AR: في وضع القراءة يعرض الاسم فقط دون HR-EMP-xxxxx.
    // EN: In read-only view show only the name, without HR-EMP-xxxxx.
    window.setTimeout(() => {
        masar_requests_replace_readonly_value(frm, "employee", frm.doc.employee_name);
        masar_requests_replace_readonly_value(
            frm,
            "custom_substitute_employee",
            frm.doc.custom_substitute_employee_name
        );
    }, 0);
}

function masar_requests_replace_readonly_value(frm, fieldname, text) {
    if (!text || !frm.fields_dict[fieldname]) return;
    const field = frm.fields_dict[fieldname];
    const isReadOnly = cint(field.df.read_only) === 1 || !frm.is_new();
    if (!isReadOnly) return;

    const $value = field.$wrapper.find(".control-value");
    if ($value.length) {
        $value.text(text);
    }
}

function masar_requests_toggle_if_present(frm, fieldname, visible) {
    if (frm.fields_dict[fieldname]) {
        frm.toggle_display(fieldname, visible);
    }
}

function masar_requests_validate_times(frm) {
    // AR: وقت العودة يجب أن يكون بعد وقت المغادرة.
    // EN: Return Time must be after Leaving Time.
    if (
        frm.doc.reason !== "On Duty" ||
        !frm.doc.custom_leaving_time ||
        !frm.doc.custom_return_time
    ) {
        return;
    }

    if (frm.doc.custom_leaving_time >= frm.doc.custom_return_time) {
        frappe.msgprint({
            title: __("Time Error"),
            indicator: "red",
            message: __("Return Time must be after Leaving Time."),
        });
        frm.set_value("custom_return_time", "");
    }
}

function masar_requests_apply_attendance_style() {
    // AR: تنسيق بصري خفيف ومتوافق مع الوضعين الفاتح والداكن.
    // EN: Lightweight styling compatible with light and dark modes.
    if (document.getElementById("masar-attendance-request-style")) return;

    const style = document.createElement("style");
    style.id = "masar-attendance-request-style";
    style.textContent = `
        .masar-attendance-request .form-section {
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-bottom: 14px;
            padding: 14px 16px 6px;
            background: var(--card-bg);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.025);
        }

        .masar-attendance-request .section-head {
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 12px;
        }

        .masar-attendance-request .control-input,
        .masar-attendance-request .control-value,
        .masar-attendance-request .form-control {
            border-radius: 8px;
        }

        .masar-attendance-request textarea {
            min-height: 115px;
            line-height: 1.75;
            resize: vertical;
        }

        .masar-attendance-request [data-fieldname="custom_achievement_report"] .ql-toolbar {
            border-radius: 8px 8px 0 0;
            background: var(--control-bg);
        }

        .masar-attendance-request [data-fieldname="custom_achievement_report"] .ql-container {
            border-radius: 0 0 8px 8px;
            background: var(--card-bg);
        }

        .masar-attendance-request [data-fieldname="custom_achievement_report"] .ql-editor {
            min-height: 220px;
            line-height: 1.8;
            font-size: 14px;
        }

        .masar-attendance-request .like-disabled-input {
            opacity: 1;
        }

        @media (max-width: 991px) {
            .masar-attendance-request .form-column {
                min-width: 100%;
            }
        }
    `;
    document.head.appendChild(style);
}
