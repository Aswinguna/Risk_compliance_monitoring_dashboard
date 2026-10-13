"""Seeded simulation of a Risk and Compliance alert queue.

Everything here is invented. A storyline is planted on purpose so the dashboard
has something real to find: from 1 July 2026 the sanctions desk is
under-staffed, its alerts take much longer to close, breaches rise and its
backlog builds.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (ALERT_TYPES, DEFAULT_SEED, SEVERITIES, SIM_END, SIM_START, SLA_DAYS,
                     STORYLINE_START)

TYPE_WEIGHTS = [0.50, 0.20, 0.20, 0.10]
SEVERITY_WEIGHTS = [0.05, 0.15, 0.35, 0.45]
TEAM_BY_TYPE = {
    "transaction_monitoring": ["Alerts L1", "Alerts L2"],
    "sanctions_screening": ["Sanctions desk"],
    "kyb_review": ["KYB operations"],
    "adverse_media": ["Alerts L2"],
}
TEAM_WEIGHTS_BY_TYPE = {"transaction_monitoring": [0.8, 0.2]}
# Relative handling time. Higher means slower.
TYPE_SPEED = {"transaction_monitoring": 1.0, "sanctions_screening": 0.9, "kyb_review": 1.1, "adverse_media": 1.2}
STORYLINE_SLOWDOWN = 1.8
STUCK_SHARE = 0.01  # alerts that are never picked up


def simulate(seed: int = DEFAULT_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.date_range(SIM_START, SIM_END, freq="D")

    rows = []
    for i, day in enumerate(days):
        base = 24 * (1 + 0.0008 * i)
        rate = base * (0.3 if day.dayofweek >= 5 else 1.0)
        n = rng.poisson(rate)
        seconds = np.sort(rng.integers(0, 86400, n))
        for s in seconds:
            rows.append(day + pd.Timedelta(seconds=int(s)))
    created = pd.Series(rows, name="created_at")
    n = len(created)

    alert_type = rng.choice(ALERT_TYPES, size=n, p=TYPE_WEIGHTS)
    severity = rng.choice(SEVERITIES, size=n, p=SEVERITY_WEIGHTS)
    team = np.empty(n, dtype=object)
    for t in ALERT_TYPES:
        idx = np.where(alert_type == t)[0]
        team[idx] = rng.choice(TEAM_BY_TYPE[t], size=len(idx), p=TEAM_WEIGHTS_BY_TYPE.get(t))

    sla = np.array([SLA_DAYS[s] for s in severity], dtype=float)
    speed = np.array([TYPE_SPEED[t] for t in alert_type])
    storyline = (alert_type == "sanctions_screening") & (created >= pd.Timestamp(STORYLINE_START)).to_numpy()
    speed = np.where(storyline, speed * STORYLINE_SLOWDOWN, speed)

    duration_days = sla * speed * rng.lognormal(mean=np.log(0.55), sigma=0.55, size=n)
    closed = created + pd.to_timedelta(duration_days, unit="D")
    stuck = rng.random(n) < STUCK_SHARE
    stuck &= np.isin(severity, ["low", "medium"])
    closed = closed.where(~stuck & (closed <= pd.Timestamp(SIM_END) + pd.Timedelta(days=1)))

    df = pd.DataFrame({
        "alert_id": [f"AL-{i:06d}" for i in range(1, n + 1)],
        "alert_type": alert_type,
        "severity": severity,
        "team": team,
        "created_at": created,
        "closed_at": closed.dt.round("s"),
    })
    df["created_at"] = df["created_at"].dt.floor("s")
    df["sla_due_at"] = df["created_at"] + pd.to_timedelta(df["severity"].map(SLA_DAYS), unit="D")
    return df
