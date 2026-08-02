// AR: يحتوي هذا الملف على منطق واجهة المستخدم مع توثيق ثنائي اللغة للدوال والمعالجات.
// EN: This file contains user-interface logic with bilingual documentation for functions and handlers.

// =======================================================================
// AR: إعدادات وأحداث نموذج طلب المواد - تطبيق masar_requests
// EN: Material Request form events and UI rules - Masar Requests
// =======================================================================

frappe.ui.form.on('Material Request', {
    // AR: تهيئة استعلامات وقواعد النموذج عند إنشائه.
    // EN: Initialize form queries and rules when the form is created.
    setup(frm) {
        frm.trigger('manage_qty_permissions');
    },

    // ===================================================================
    // AR: تهيئة الواجهة والحسابات عند تحميل المستند.
    // EN: Initialize UI state and calculations when the document loads.
    // ===================================================================
    async onload(frm) {
        if (!frm.is_new()) {
            return;
        }

        const employee_result = await frappe.db.get_value(
            'Employee',
            { user_id: frappe.session.user },
            ['name', 'reports_to']
        );

        const employee_data = employee_result?.message;

        if (!employee_data?.reports_to) {
            await frm.set_value('reports_to', '');
            await frm.set_value('custom_secretary_employee', '');
            return;
        }

        await frm.set_value(
            'reports_to',
            employee_data.reports_to
        );

        await frm.trigger('fetch_manager_secretary');
    },

    // AR: تحديث بيانات السكرتير عند تغيير المدير المباشر.
    // EN: Refresh secretary data when the direct manager changes.
    async reports_to(frm) {
        await frm.trigger('fetch_manager_secretary');
    },

    // AR: جلب السكرتير المرتبط بالمدير المباشر.
    // EN: Fetch the secretary linked to the direct manager.
    async fetch_manager_secretary(frm) {
        if (!frm.doc.reports_to) {
            await frm.set_value(
                'custom_secretary_employee',
                ''
            );
            return;
        }

        const response = await frappe.db.get_value(
            'Employee',
            frm.doc.reports_to,
            ['custom_secretary_employee']
        );

        await frm.set_value(
            'custom_secretary_employee',
            response?.message?.custom_secretary_employee || ''
        );
    },

    // AR: إعادة تطبيق قواعد العرض والحماية عند تحديث الواجهة.
    // EN: Reapply display and protection rules when the UI refreshes.
    refresh(frm) {
        frm.trigger('toggle_grid_columns');
        frm.trigger('manage_qty_permissions');
        frm.trigger('apply_strict_lockdown');
        masar_requests_material_apply_hr_user_read_only(frm);
    },

    // AR: تحديث أعمدة جدول الأصناف عند تغيير نوع الطلب.
    // EN: Refresh item-grid columns when request type changes.
    material_request_type(frm) {
        frm.trigger('toggle_grid_columns');
    },

    // AR: تنفيذ معالج `toggle_grid_columns` ضمن هذا الملف.
    // EN: Execute the `toggle_grid_columns` handler within this file.
    toggle_grid_columns(frm) {
        // AR:
        // إخفاء السعر والمبلغ من الجدول المختصر دائمًا. تظهر الحقول داخل
        // الصف الموسع فقط لطلبات الشراء وفق Property Setter الخادمي.
        //
        // EN:
        // Always hide Rate and Amount from the compact grid. Server-side
        // Property Setters expose them in the expanded row only for Purchase.
        const grid = frm.fields_dict.items?.grid;
        if (!grid) return;

        grid.docfields.forEach((df) => {
            if (["rate", "amount"].includes(df.fieldname)) {
                df.in_list_view = 0;
            }
        });
        grid.refresh();
    },

    // ===================================================================
    // AR:
    // التحكم في qty وفق المنطق الأصلي:
    // - الموظف يعدله في المسودة.
    // - أمين المخزن يعدله أثناء Pending Stock Check.
    // - MR Qty Modifier وSystem Manager يستطيعان التعديل.
    //
    // EN:
    // Control qty using the original business logic:
    // - Employee edits it in Draft.
    // - Warehouse Manager edits it during Pending Stock Check.
    // - MR Qty Modifier and System Manager retain override access.
    // ===================================================================
    // AR: تحديد إمكانية تعديل الكمية حسب المرحلة والدور.
    // EN: Determine quantity editability from stage and role.
    manage_qty_permissions(frm) {
        const is_draft = (
            !frm.doc.workflow_state
            || frm.doc.workflow_state === 'Draft'
        );

        const is_warehouse_stage = (
            frm.doc.workflow_state === 'Pending Stock Check'
            && frappe.user.has_role('Warehouse Manager')
        );

        const has_override_role = (
            frappe.user.has_role('MR Qty Modifier')
            || frappe.user.has_role('System Manager')
        );

        const can_edit_qty = (
            is_draft
            || is_warehouse_stage
            || has_override_role
        );

        const grid = frm.fields_dict.items?.grid;
        if (!grid) {
            return;
        }

        grid.update_docfield_property(
            'qty',
            'read_only',
            can_edit_qty ? 0 : 1
        );

        grid.refresh();
    },

    // ===================================================================
    // AR:
    // قفل بقية الطلب بعد خروجه من المسودة، مع إبقاء qty تحت إدارة
    // manage_qty_permissions وعدم الاعتماد على حقل custom_issued_qty
    // غير الموجود في تعريف المشروع.
    //
    // EN:
    // Lock the rest of the document after Draft. qty remains controlled by
    // manage_qty_permissions; no dependency on the undefined custom_issued_qty.
    // ===================================================================
    // AR: قفل حقول طلب المواد بعد مغادرة المسودة.
    // EN: Lock Material Request fields after Draft.
    apply_strict_lockdown(frm) {
        const is_after_draft = (
            frm.doc.workflow_state
            && frm.doc.workflow_state !== 'Draft'
            && frm.doc.docstatus === 0
        );

        if (!is_after_draft) {
            return;
        }

        frm.set_df_property(
            'items',
            'cannot_add_rows',
            true
        );
        frm.set_df_property(
            'items',
            'cannot_delete_rows',
            true
        );
        frm.set_df_property(
            'items',
            'cannot_delete_all_rows',
            true
        );

        Object.entries(frm.fields_dict).forEach(
            ([fieldname, field]) => {
                if (
                    field?.df
                    && field.df.fieldtype !== 'Button'
                    && fieldname !== 'items'
                ) {
                    field.df.read_only = 1;
                }
            }
        );

        const grid = frm.fields_dict.items?.grid;
        if (grid) {
            grid.docfields.forEach((df) => {
                if (df.fieldname !== 'qty') {
                    df.read_only = 1;
                }
            });
        }

        frm.refresh_fields();
        frm.trigger('manage_qty_permissions');
    },
});


// =======================================================================
// AR: إعادة تطبيق صلاحية الكمية عند تغيير الصنف.
// EN: Reapply quantity permissions when Item Code changes.
// =======================================================================

frappe.ui.form.on('Material Request Item', {
    // AR: تنفيذ معالج `item_code` ضمن هذا الملف.
    // EN: Execute the `item_code` handler within this file.
    item_code(frm) {
        frm.trigger('manage_qty_permissions');
    },

    // AR: ضبط إمكانية تعديل كمية صف الصنف عند عرضه.
    // EN: Set row quantity editability when the child form renders.
    form_render(frm, cdt, cdn) {
        const is_draft = (
            !frm.doc.workflow_state
            || frm.doc.workflow_state === 'Draft'
        );

        const is_warehouse_stage = (
            frm.doc.workflow_state === 'Pending Stock Check'
            && frappe.user.has_role('Warehouse Manager')
        );

        const has_override_role = (
            frappe.user.has_role('MR Qty Modifier')
            || frappe.user.has_role('System Manager')
        );

        const can_edit_qty = (
            is_draft
            || is_warehouse_stage
            || has_override_role
        );

        const row = (
            frm.fields_dict.items
                ?.grid
                ?.grid_rows_by_docname?.[cdn]
        );

        if (row) {
            row.toggle_enable('qty', can_edit_qty);
        }
    },
});


// =======================================================================
// AR: حماية طلبات المواد للآخرين مع استثناء الطلب الشخصي لمستخدم HR User.
// EN: Protect others' Material Requests while exempting an HR User's personal request.
// =======================================================================
function masar_requests_material_is_hr_user_read_only() {
    return (
        frappe.user.has_role('HR User') &&
        !frappe.user.has_role('HR Manager') &&
        !frappe.user.has_role('System Manager') &&
        frappe.session.user !== 'Administrator'
    );
}

// AR: تنفيذ معالج `masar_requests_material_is_personal_request` ضمن هذا الملف.
// EN: Execute the `masar_requests_material_is_personal_request` handler within this file.
function masar_requests_material_is_personal_request(frm) {
    // AR: الطلب الجديد أو المملوك للمستخدم يعد طلب مواد شخصياً.
    // EN: A new request or one owned by the current user is a personal Material Request.
    return Boolean(frm.is_new() || frm.doc.owner === frappe.session.user);
}

// AR: تنفيذ معالج `masar_requests_material_apply_hr_user_read_only` ضمن هذا الملف.
// EN: Execute the `masar_requests_material_apply_hr_user_read_only` handler within this file.
function masar_requests_material_apply_hr_user_read_only(frm) {
    // AR: تقفل طلبات الآخرين فقط، ولا تمنع المستخدم من إنشاء طلبه الشخصي.
    // EN: Lock other users' requests only and allow the user to create a personal request.
    if (
        !masar_requests_material_is_hr_user_read_only() ||
        masar_requests_material_is_personal_request(frm)
    ) return;

    Object.keys(frm.fields_dict).forEach((fieldname) => {
        const fieldtype = frm.fields_dict[fieldname]?.df?.fieldtype;
        if (!['Section Break', 'Column Break', 'Tab Break', 'HTML', 'Button'].includes(fieldtype)) {
            frm.set_df_property(fieldname, 'read_only', 1);
        }
    });

    const grid = frm.fields_dict.items?.grid;
    if (grid) {
        grid.cannot_add_rows = true;
        grid.cannot_delete_rows = true;
        grid.wrapper.find('.grid-add-row, .grid-remove-rows').hide();
        grid.refresh();
    }

    frm.disable_save();
    window.setTimeout(() => {
        frm.page.clear_primary_action();
        frm.page.clear_secondary_action();
    }, 0);
}

// MASAR_PURCHASE_COLUMNS_V21_7
// AR: تنفيذ معالج `masar_v217_is_purchase` ضمن هذا الملف.
// EN: Execute the `masar_v217_is_purchase` handler within this file.
function masar_v217_is_purchase(frm) {
    return frm.doc.material_request_type === "Purchase";
}

// AR: تنفيذ معالج `masar_v217_toggle_purchase_columns` ضمن هذا الملف.
// EN: Execute the `masar_v217_toggle_purchase_columns` handler within this file.
function masar_v217_toggle_purchase_columns(frm) {
    const purchase = masar_v217_is_purchase(frm);
    const grid = frm.fields_dict.items && frm.fields_dict.items.grid;

    if (grid) {
        ["rate", "amount"].forEach((fieldname) => {
            try {
                grid.update_docfield_property(
                    fieldname,
                    "hidden",
                    purchase ? 0 : 1
                );
            } catch (error) {
                // Compatibility fallback.
            }

            try {
                grid.set_column_disp(fieldname, purchase);
            } catch (error) {
                // Metadata still keeps the field available.
            }
        });
    }

    if (frm.fields_dict.custom_estimated_total) {
        frm.toggle_display("custom_estimated_total", purchase);
    }

    frm.refresh_field("items");
}

// AR: تنفيذ معالج `masar_v217_recalculate_purchase_total` ضمن هذا الملف.
// EN: Execute the `masar_v217_recalculate_purchase_total` handler within this file.
function masar_v217_recalculate_purchase_total(frm) {
    if (!masar_v217_is_purchase(frm)) {
        if (
            frm.fields_dict.custom_estimated_total
            && Number(frm.doc.custom_estimated_total || 0) !== 0
        ) {
            frm.set_value("custom_estimated_total", 0);
        }
        return;
    }

    let total = 0;

    (frm.doc.items || []).forEach((row) => {
        const qty = frappe.utils.flt(row.qty || 0);
        const rate = frappe.utils.flt(row.rate || 0);
        const amount = frappe.utils.flt(qty * rate);

        if (frappe.utils.flt(row.amount || 0) !== amount) {
            frappe.model.set_value(
                row.doctype,
                row.name,
                "amount",
                amount
            );
        }

        total += amount;
    });

    if (
        frm.fields_dict.custom_estimated_total
        && frappe.utils.flt(
            frm.doc.custom_estimated_total || 0
        ) !== frappe.utils.flt(total)
    ) {
        frm.set_value("custom_estimated_total", total);
    }
}

frappe.ui.form.on("Material Request", {
    // AR: تنفيذ معالج `refresh` ضمن هذا الملف.
    // EN: Execute the `refresh` handler within this file.
    refresh(frm) {
        masar_v217_toggle_purchase_columns(frm);
        masar_v217_recalculate_purchase_total(frm);
    },
    // AR: تنفيذ معالج `material_request_type` ضمن هذا الملف.
    // EN: Execute the `material_request_type` handler within this file.
    material_request_type(frm) {
        masar_v217_toggle_purchase_columns(frm);
        masar_v217_recalculate_purchase_total(frm);
    },
    // AR: تنفيذ معالج `items_add` ضمن هذا الملف.
    // EN: Execute the `items_add` handler within this file.
    items_add(frm) {
        masar_v217_recalculate_purchase_total(frm);
    },
    // AR: تنفيذ معالج `items_remove` ضمن هذا الملف.
    // EN: Execute the `items_remove` handler within this file.
    items_remove(frm) {
        masar_v217_recalculate_purchase_total(frm);
    },
});

frappe.ui.form.on("Material Request Item", {
    // AR: تنفيذ معالج `qty` ضمن هذا الملف.
    // EN: Execute the `qty` handler within this file.
    qty(frm) {
        masar_v217_recalculate_purchase_total(frm);
    },
    // AR: تنفيذ معالج `rate` ضمن هذا الملف.
    // EN: Execute the `rate` handler within this file.
    rate(frm) {
        masar_v217_recalculate_purchase_total(frm);
    },
    // AR: تنفيذ معالج `items_remove` ضمن هذا الملف.
    // EN: Execute the `items_remove` handler within this file.
    items_remove(frm) {
        masar_v217_recalculate_purchase_total(frm);
    },
});
