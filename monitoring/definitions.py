"""Single source of truth for what every KPI means.

The dashboard's "KPI definitions" tab, the tile captions and the tests all read
from this list, so the wording a controller sees is the wording that was
reviewed, and no KPI can be shown without a definition.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KPI:
    id: str
    name: str
    fmt: str          # "int", "pct" or "days"
    short: str        # one line shown under the tile
    plain: str        # plain-language meaning
    calculation: str  # exact calculation
    caveat: str       # what the number does NOT tell you


KPIS: list[KPI] = [
    KPI("open_backlog", "Open backlog", "int",
        "Alerts raised and not yet closed",
        "How many alerts are waiting for a decision at the end of the selected day.",
        "Count of alerts with created_at on or before the selected day and either no closed_at or a closed_at after it.",
        "Says nothing about how old the alerts are. Read it together with the ageing chart."),
    KPI("received", "Alerts received", "int",
        "Raised in the selected window",
        "How many new alerts arrived during the window.",
        "Count of alerts with created_at inside the window (window end inclusive, window start exclusive).",
        "Volume depends on detection rules and thresholds. A rise can mean more risk or noisier rules."),
    KPI("closed", "Alerts closed", "int",
        "Closed in the selected window",
        "How many alerts were given a final decision during the window.",
        "Count of alerts with closed_at inside the window.",
        "Includes alerts raised before the window. Closing fast is not the same as closing correctly."),
    KPI("clearance_rate", "Clearance rate", "pct",
        "Closed divided by received",
        "Whether the team is keeping up. Above 100% the backlog is shrinking, below 100% it is growing.",
        "Alerts closed in the window divided by alerts received in the window.",
        "Over a short window one large batch can swing it. Check the backlog trend before drawing conclusions."),
    KPI("sla_compliance", "SLA compliance", "pct",
        "Closed within deadline",
        "Of the alerts closed in the window, the share closed on or before their deadline.",
        "Alerts closed in the window with closed_at on or before sla_due_at, divided by all alerts closed in the window. "
        "The deadline is the creation time plus the SLA days for the severity.",
        "Only counts closed alerts, so it flatters a team that closes easy alerts and leaves hard ones open. "
        "Always read it next to overdue open alerts."),
    KPI("overdue_open", "Overdue open alerts", "int",
        "Open and already past deadline",
        "Alerts that are still waiting and have already missed their deadline.",
        "Count of open alerts whose sla_due_at is before the end of the selected day.",
        "A snapshot, not a rate. A large number of low severity alerts can matter less than a few critical ones."),
    KPI("median_age_open", "Median age of open alerts", "days",
        "Typical age of the backlog",
        "The age in days of the middle alert in the backlog.",
        "Median of (end of selected day minus created_at) over all open alerts, in days.",
        "A median hides the tail. A few very old alerts will not move it, which is why the oldest alert is shown too."),
    KPI("pct_over_30d", "Backlog older than 30 days", "pct",
        "Share of backlog past one month",
        "How much of the backlog is genuinely stale.",
        "Open alerts older than 30 days divided by all open alerts.",
        "Thirty days is a convention, not a regulatory limit. Adjust it to your own policy."),
    KPI("oldest_open", "Oldest open alert", "days",
        "Age of the single oldest alert",
        "The age in days of the alert that has waited longest. This is usually the one an auditor asks about.",
        "Maximum of (end of selected day minus created_at) over all open alerts, in days.",
        "One alert can be an outlier or a data issue. Use the table of oldest overdue alerts to see which one."),
]

BY_ID = {k.id: k for k in KPIS}
