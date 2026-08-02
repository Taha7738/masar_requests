"""
AR: تصحيح ترحيل آمن لتطبيق تغييرات `setup_manual_official_duty_reconciliation_v21_4` على المواقع القائمة.
EN: Idempotent migration patch for applying `setup_manual_official_duty_reconciliation_v21_4` changes to existing sites.
"""

from masar_requests.manual_official_duty_reconciliation import (
    setup_manual_reconciliation_fields,
)


def execute():
    """
    AR: تنفيذ تنفيذ ضمن وحدة `setup_manual_official_duty_reconciliation_v21_4`.
    EN: Execute execute within the `setup_manual_official_duty_reconciliation_v21_4` module.
    """
    setup_manual_reconciliation_fields()
