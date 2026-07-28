__version__ = "1.1.1"


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
        import logging

        logging.getLogger("masar_requests").warning(
            "Optional leave balance report patch could not be applied.",
            exc_info=True,
        )

    try:
        from masar_requests.overrides.shift_type import apply_shift_times_patch

        apply_shift_times_patch()
    except Exception:
        # AR: لا نجعل بدء التطبيق يعتمد على واجهة داخلية قابلة للتغير في HRMS.
        # EN: App startup must not depend on a changeable HRMS internal API.
        import logging

        logging.getLogger("masar_requests").warning(
            "Optional shift-time runtime patch could not be applied.",
            exc_info=True,
        )


_apply_compatible_runtime_patches()
