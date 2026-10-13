"""Pure KPI calculations. No Dash, no plotting: just DataFrames in, numbers out.

Every function takes an explicit `as_of` timestamp, so results never depend on
the wall clock and can be tested against hand-computed answers.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import BUCKET_BINS, BUCKET_LABELS, SEVERITIES, SLA_DAYS

REQUIRED_COLUMNS = ["alert_id", "alert_type", "severity", "team", "created_at", "closed_at", "sla_due_at"]


def as_of_end_of_day(day) -> pd.Timestamp:
    """The last second of the selected calendar day."""
    return pd.Timestamp(day).normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)


def validate(df: pd.DataFrame) -> None:
    """Fail loudly on data that would make a KPI wrong, rather than showing it."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    if df["alert_id"].duplicated().any():
        raise ValueError("Duplicate alert_id values")
    if df[["alert_type", "severity", "team", "created_at", "sla_due_at"]].isna().any().any():
        raise ValueError("Nulls in mandatory columns")
    unknown = set(df["severity"]) - set(SLA_DAYS)
    if unknown:
        raise ValueError(f"Unknown severities: {sorted(unknown)}")
    if (df["closed_at"] < df["created_at"]).any():
        raise ValueError("Alerts closed before they were created")


def open_mask(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.Series:
    return (df["created_at"] <= as_of) & (df["closed_at"].isna() | (df["closed_at"] > as_of))


def open_alerts(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    out = df[open_mask(df, as_of)].copy()
    out["age_days"] = (as_of - out["created_at"]) / pd.Timedelta(days=1)
    out["age_bucket"] = pd.cut(np.floor(out["age_days"]), bins=BUCKET_BINS, labels=BUCKET_LABELS)
    out["is_overdue"] = out["sla_due_at"] < as_of
    out["days_past_sla"] = ((as_of - out["sla_due_at"]) / pd.Timedelta(days=1)).clip(lower=0)
    return out


def in_window(series: pd.Series, as_of: pd.Timestamp, window_days: int) -> pd.Series:
    """True where the timestamp is in (as_of - window_days, as_of]."""
    return (series > as_of - pd.Timedelta(days=window_days)) & (series <= as_of)


def kpis(df: pd.DataFrame, as_of: pd.Timestamp, window_days: int) -> dict:
    """All headline KPIs. Keys match monitoring.definitions.KPIS ids."""
    opened = open_alerts(df, as_of)
    received = int(in_window(df["created_at"], as_of, window_days).sum())
    closed_mask = in_window(df["closed_at"], as_of, window_days)
    closed = int(closed_mask.sum())
    met = int((df.loc[closed_mask, "closed_at"] <= df.loc[closed_mask, "sla_due_at"]).sum())
    n_open = len(opened)
    return {
        "open_backlog": n_open,
        "received": received,
        "closed": closed,
        "clearance_rate": closed / received if received else None,
        "sla_compliance": met / closed if closed else None,
        "overdue_open": int(opened["is_overdue"].sum()),
        "median_age_open": float(opened["age_days"].median()) if n_open else None,
        "pct_over_30d": float((opened["age_days"] > 30).mean()) if n_open else None,
        "oldest_open": float(opened["age_days"].max()) if n_open else None,
    }


def weekly_flow(df: pd.DataFrame, as_of: pd.Timestamp, weeks: int = 26) -> pd.DataFrame:
    """Received, closed and end-of-week backlog for each of the last `weeks` weeks.

    Weeks are the seven days ending at `as_of`, counted backwards, so the last
    bar always covers exactly the most recent seven days.
    """
    edges = pd.DatetimeIndex([as_of - pd.Timedelta(days=7 * k) for k in range(weeks, -1, -1)])
    created = np.sort(df["created_at"].to_numpy())
    closed = np.sort(df["closed_at"].dropna().to_numpy())
    e = edges.to_numpy()
    created_upto = np.searchsorted(created, e, side="right")
    closed_upto = np.searchsorted(closed, e, side="right")
    return pd.DataFrame({
        "week_ending": edges[1:].normalize(),
        "received": np.diff(created_upto),
        "closed": np.diff(closed_upto),
        "backlog": (created_upto - closed_upto)[1:],
    })


def ageing_table(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Open alerts by ageing bucket and severity, with every cell present."""
    opened = open_alerts(df, as_of)
    counts = opened.groupby(["age_bucket", "severity"], observed=False).size()
    full = pd.MultiIndex.from_product([BUCKET_LABELS, SEVERITIES], names=["age_bucket", "severity"])
    return counts.reindex(full, fill_value=0).rename("alerts").reset_index()


def sla_by_group(df: pd.DataFrame, as_of: pd.Timestamp, window_days: int, by: str = "alert_type") -> pd.DataFrame:
    closed = df[in_window(df["closed_at"], as_of, window_days)]
    if closed.empty:
        return pd.DataFrame(columns=[by, "closed", "met", "compliance"])
    out = closed.groupby(by).agg(
        closed=("alert_id", "size"),
        met=("closed_at", lambda s: int((s <= closed.loc[s.index, "sla_due_at"]).sum())),
    )
    out["compliance"] = out["met"] / out["closed"]
    return out.reset_index()


def oldest_overdue(df: pd.DataFrame, as_of: pd.Timestamp, limit: int = 15) -> pd.DataFrame:
    opened = open_alerts(df, as_of)
    out = opened[opened["is_overdue"]].sort_values(["age_days", "alert_id"], ascending=[False, True]).head(limit)
    return out[["alert_id", "alert_type", "severity", "team", "created_at", "age_days", "days_past_sla"]]
