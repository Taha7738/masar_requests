__version__ = "1.0.0"


def _apply_compatible_runtime_patches():
    """
    AR:
        تطبيق الترقيعات الاختيارية المتوافقة فقط. لا نسجّل خطأ قاعدة بيانات
        أثناء استيراد التطبيق لأن اختلاف واجهة HRMS بين الإصدارات لا ينبغي
        أن يمنع تشغيل Masar Requests أو يملأ Error Log برسائل مضللة.

    EN:
        Apply only compatible optional runtime patches. Do not log a database
        error while the app is imported: an HRMS API difference must not stop
        Masar Requests from loading or create misleading Error Log entries.
    """
    try:
        from masar_requests.leave_balance_report_patch import apply_patch

        apply_patch()
    except Exception:
        # AR: ميزة التقرير اختيارية؛ حاسبة الرصيد الخاصة بطلب الإجازة تبقى فعالة.
        # EN: The report patch is optional; the Leave Application balance logic stays active.
        pass

    try:
        from masar_requests.overrides.shift_type import apply_shift_times_patch

        apply_shift_times_patch()
    except Exception:
        # AR: لا نجعل بدء التطبيق يعتمد على واجهة داخلية قابلة للتغير في HRMS.
        # EN: App startup must not depend on a changeable HRMS internal API.
        pass


_apply_compatible_runtime_patches()