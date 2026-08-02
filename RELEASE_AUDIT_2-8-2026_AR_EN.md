# تدقيق إصدار تطبيق Masar Requests — 2 أغسطس 2026

## العربية

هذا الإصدار هو نسخة نظيفة ومهيأة للرفع من المشروع المضغوط المقدم. يتضمن أحدث تعديلات المشروع الموجودة في النسخة المصدر، ومنها نظام الرؤية الصارمة V21.9 ونظام وصول السكرتير الموحد V22 حتى V22.4.

### سياسة التنظيف

حُذفت فقط الملفات غير التشغيلية الآتية من نسخة الإصدار:

- مجلد `.git` الداخلي؛ لتجنب رفع سجل أو إعدادات مستودع محلي ضمن الملف المضغوط.
- مجلدات `__pycache__` وملفات `*.pyc`.
- النسخ الاحتياطية المؤقتة `*.backup_*` و`*.bak`.
- أدوات التدقيق والإصلاح أحادية الاستخدام التي تبدأ بـ `_audit_` أو `_fix_` أو `_find_`.

لم تُحذف ملفات التشغيل أو الاختبارات أو التصحيحات أو تعريفات DocType أو ملفات JavaScript أو الترجمات أو صيغ الطباعة.

### التوثيق ثنائي اللغة

أضيف توثيق عربي وإنجليزي إلى:

- جميع وحدات Python.
- جميع الدوال والفئات في Python.
- ملفات JavaScript والدوال والمعالجات المسماة فيها.
- سكربتات Shell.

التعليقات تشرح الغرض والقواعد غير الواضحة، ولا تعيد وصف كل سطر بديهي حتى يبقى الكود قابلًا للصيانة.

## English

This release is a cleaned, upload-ready snapshot of the supplied project archive. It contains the latest changes present in the source snapshot, including strict request visibility V21.9 and the unified secretary-access system through V22.4.

### Cleanup policy

Only non-runtime artifacts were removed:

- The local `.git` directory.
- `__pycache__` directories and `*.pyc` files.
- Temporary backup copies such as `*.backup_*` and `*.bak`.
- One-off diagnostic or repair helpers prefixed with `_audit_`, `_fix_`, or `_find_`.

Runtime modules, tests, migration patches, DocTypes, JavaScript, translations, and print formats were retained.

### Bilingual documentation

Arabic and English documentation was added to all Python modules, functions, and classes, as well as named JavaScript functions/handlers and shell scripts.
