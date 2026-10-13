"""Shared constants. SLA targets and the ageing buckets are defined once, here."""
from datetime import date

import numpy as np

DEFAULT_SEED = 42

SEVERITIES = ["critical", "high", "medium", "low"]

# Calendar days allowed between an alert being raised and being closed.
SLA_DAYS = {"critical": 2, "high": 5, "medium": 10, "low": 20}

# Share of closed alerts that should meet SLA. Used as the target line on charts.
SLA_COMPLIANCE_TARGET = 0.90

ALERT_TYPES = ["transaction_monitoring", "sanctions_screening", "kyb_review", "adverse_media"]

# Ageing buckets, by whole days since the alert was raised.
BUCKET_LABELS = ["0-7 days", "8-14 days", "15-30 days", "31-60 days", "Over 60 days"]
BUCKET_BINS = [-1, 7, 14, 30, 60, np.inf]

# Simulation window. The dashboard defaults to showing the data as at SIM_END.
SIM_START = date(2025, 10, 13)
SIM_END = date(2026, 10, 9)

# Planted storyline: from this date the sanctions desk is under-staffed.
STORYLINE_START = date(2026, 7, 1)
