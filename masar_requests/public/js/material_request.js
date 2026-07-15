// =======================================================================
// AR: إعدادات وأحداث نموذج طلب المواد - تطبيق masar_requests
// EN: Material Request form events and UI rules - Masar Requests
// =======================================================================

frappe.ui.form.on('Material Request', {
    // AR: إعداد القواعد عند تهيئة النموذج.
    // EN: Initialize field rules when the form is created.
    setup(frm) {
        frm.trigger('manage_qty_permissions');
    },

    // ===================================================================
    // AR: جلب المسؤول المباشر وسكرتيره للطلب الجديد.
    // EN: Resolve the direct supervisor and their secretary for new docs.
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

    // AR: تحديث السكرتير عند تغيير المسؤول المباشر.
    // EN: Refresh secretary data when the manager changes.
    async reports_to(frm) {
        await frm.trigger('fetch_manager_secretary');
    },

    // AR: دالة مشتركة لجلب سكرتير المسؤول.
    // EN: Shared helper to fetch the manager's secretary.
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

    // AR: إعادة تطبيق العرض والقفل بعد كل تحديث.
    // EN: Reapply visibility and locking rules on every refresh.
    refresh(frm) {
        frm.trigger('toggle_grid_columns');
        frm.trigger('manage_qty_permissions');
        frm.trigger('apply_strict_lockdown');
    },

    // AR: إظهار السعر والإجمالي لطلب الشراء فقط.
    // EN: Show Rate and Amount only for Purchase requests.
    material_request_type(frm) {
        frm.trigger('toggle_grid_columns');
    },

    toggle_grid_columns(frm) {
        const is_purchase = (
            frm.doc.material_request_type === 'Purchase'
        );

        const grid = frm.fields_dict.items?.grid;
        if (!grid) {
            return;
        }

        grid.docfields.forEach((df) => {
            if (['rate', 'amount'].includes(df.fieldname)) {
                df.in_list_view = is_purchase ? 1 : 0;
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
// AR: أحداث جدول أصناف طلب المواد.
// EN: Material Request Item child-table events.
// =======================================================================

frappe.ui.form.on('Material Request Item', {
    item_code(frm) {
        frm.trigger('manage_qty_permissions');
    },

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