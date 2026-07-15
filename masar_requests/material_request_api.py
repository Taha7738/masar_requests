# # AR: استيراد مكتبة فرابي الأساسية / EN: Import standard frappe library
# import frappe

# # AR: السماح باستدعاء الدالة من الواجهة الأمامية / EN: Allow calling the function from the frontend
# @frappe.whitelist()
# # AR: تعريف دالة الاعتماد الاستثنائي وتمرير اسم المستند / EN: Define super bypass approval function and pass docname
# def super_bypass_approve(docname):
#     # AR: تحديد الأدوار المسموح لها بالتخطي / EN: Define roles allowed to bypass
#     allowed_roles = ['Secretary General', 'University President', 'Administrator', 'System Manager']
    
#     # AR: جلب أدوار المستخدم الحالي / EN: Fetch roles of the current user
#     user_roles = frappe.get_roles(frappe.session.user)
    
#     # AR: فحص ما إذا كان المستخدم يملك أي دور مسموح / EN: Check if user has any allowed role
#     has_access = any(role in user_roles for role in allowed_roles)
    
#     # AR: إذا لم يملك الصلاحية، قم بإيقاف العملية / EN: If user lacks permission, halt the process
#     if not has_access:
#         # AR: إظهار رسالة الرفض وتوقف الكود / EN: Throw rejection message and stop code
#         frappe.throw("عفواً، لا تملك الصلاحية الكافية لاستخدام الاعتماد الاستثنائي المباشر. <br> Sorry, you do not have permission to use Super Bypass Approval.")
    
#     # AR: جلب كائن المستند المطلوب من قاعدة البيانات / EN: Fetch the requested document object from DB
#     doc = frappe.get_doc('Material Request', docname)
    
#     # AR: التحقق مما إذا كان المستند معتمداً مسبقاً لمنع التكرار / EN: Check if doc is already submitted to prevent duplication
#     if doc.docstatus == 1:
#         # AR: إظهار خطأ إذا كان معتمداً / EN: Throw error if already submitted
#         frappe.throw("هذا المستند معتمد مسبقاً. <br> Document is already submitted.")
        
#     # AR: تفريغ حالة مسار العمل لتجنب الرفض المبرمج / EN: Clear workflow state to avoid programmed rejection
#     doc.workflow_state = None
#     # AR: تجاهل مسار العمل / EN: Ignore workflow rules
#     doc.flags.ignore_workflow = True
#     # AR: تجاهل التحققات المخصصة / EN: Ignore custom validations
#     doc.flags.ignore_validate = True
#     # AR: تجاهل الحقول الإلزامية الفارغة / EN: Ignore empty mandatory fields
#     doc.flags.ignore_mandatory = True
#     # AR: تجاهل قيود الصلاحيات الصارمة / EN: Ignore strict permission restrictions
#     doc.flags.ignore_permissions = True
    
#     # AR: اعتماد المستند رسمياً وترحيله / EN: Officially submit and post the document
#     doc.submit()
    
#     # AR: فرض تحديث حالة مسار العمل إلى 'Approved' في قاعدة البيانات مباشرة / EN: Force update workflow state to 'Approved' directly in DB
#     frappe.db.set_value('Material Request', docname, 'workflow_state', 'Approved')
    
#     # AR: مسح كاش المستند ليتحدث في الواجهة فوراً / EN: Clear doc cache to update instantly on UI
#     frappe.clear_cache(doctype='Material Request')
    
#     # AR: إنشاء وإدراج إشعار لصاحب الطلب بنجاح الاعتماد الاستثنائي / EN: Create and insert notification for owner about successful super bypass
#     frappe.get_doc({
#         # AR: نوع المستند: سجل إشعار / EN: Doctype: Notification Log
#         "doctype": "Notification Log",
#         # AR: موضوع ورسالة الإشعار / EN: Subject and message of notification
#         "subject": f"Your Material Request ({docname}) has been SUPER APPROVED by Top Management.",
#         # AR: المستهدف هو صاحب الطلب / EN: Target is the document owner
#         "for_user": doc.owner,
#         # AR: ربط الإشعار بنوع المستند / EN: Link notification to document type
#         "document_type": "Material Request",
#         # AR: تحديد اسم المستند لسهولة فتحه / EN: Specify document name for easy opening
#         "document_name": docname
#     }).insert(ignore_permissions=True) # AR: إدراج متجاهلاً الصلاحيات / EN: Insert ignoring permissions
    
#     # AR: إرجاع رسالة نجاح للواجهة / EN: Return success message to frontend
#     return "Success"