import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitoring.config import SLA_DAYS  # noqa: E402
from monitoring.simulate import simulate  # noqa: E402

AS_OF_DAY = "2026-01-31"  # as_of = 2026-01-31 23:59:59


def make_alert(alert_id, alert_type, severity, created, closed=None, team="Alerts L1"):
    created = pd.Timestamp(created)
    return {
        "alert_id": alert_id, "alert_type": alert_type, "severity": severity, "team": team,
        "created_at": created, "closed_at": pd.Timestamp(closed) if closed else pd.NaT,
        "sla_due_at": created + pd.Timedelta(days=SLA_DAYS[severity]),
    }


@pytest.fixture
def tiny():
    """Ten alerts with answers worked out by hand. See tests/test_metrics.py.

    As at 2026-01-31 23:59:59, window 30 days:
      received 8, closed 3, open 6, overdue open 2, SLA met 2 of 3.
    """
    rows = [
        make_alert("A1", "transaction_monitoring", "critical", "2026-01-30 10:00", "2026-01-31 09:00"),  # met
        make_alert("A2", "transaction_monitoring", "critical", "2026-01-28 10:00", "2026-02-05 00:00"),  # open at as_of, overdue
        make_alert("A3", "sanctions_screening", "high", "2026-01-10 08:00", "2026-01-20 08:00", "Sanctions desk"),  # breach
        make_alert("A4", "kyb_review", "low", "2025-12-15 00:00", None, "KYB operations"),                # open, 47 days, overdue
        make_alert("A5", "transaction_monitoring", "medium", "2025-11-01 00:00", "2025-11-05 00:00"),    # closed long ago
        make_alert("A6", "adverse_media", "low", "2026-01-25 12:00", None, "Alerts L2"),                  # open, 6 days
        make_alert("A7", "transaction_monitoring", "medium", "2026-01-24 00:00", "2026-01-27 00:00"),    # met
        make_alert("A8", "sanctions_screening", "low", "2026-01-22 00:00", None, "Sanctions desk"),       # open, 9 days
        make_alert("A9", "transaction_monitoring", "low", "2026-01-23 23:59:59", None),                   # open, exactly 8.0 days
        make_alert("A10", "transaction_monitoring", "low", "2026-01-24 23:59:58", None),                  # open, 7 days and 1 second
    ]
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def simulated():
    return simulate(42)
