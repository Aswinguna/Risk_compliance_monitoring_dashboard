"""Turn metrics into display-ready pieces: formatted tile values and Plotly figures.

Kept separate from the Dash wiring so it can be tested without a running server.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import metrics
from .config import BUCKET_LABELS, SEVERITIES, SLA_COMPLIANCE_TARGET
from .definitions import KPIS, KPI

SEVERITY_COLOURS = {"critical": "#7f1d1d", "high": "#c2410c", "medium": "#d9a441", "low": "#9aa5b1"}
PRETTY = {"kyb_review": "KYB review", "transaction_monitoring": "Transaction monitoring",
          "sanctions_screening": "Sanctions screening", "adverse_media": "Adverse media"}


def pretty(value: str) -> str:
    return PRETTY.get(value, value.replace("_", " ").capitalize())


INK = "#1a1a1a"
GRID = "#e5e7eb"


def format_value(kpi: KPI, value) -> str:
    if value is None:
        return "n/a"
    if kpi.fmt == "pct":
        return f"{value:.1%}"
    if kpi.fmt == "days":
        return f"{value:.1f} days"
    return f"{int(value):,}"


def filter_alerts(df: pd.DataFrame, types=None, severities=None, teams=None) -> pd.DataFrame:
    """An empty or missing selection means 'all'."""
    out = df
    if types:
        out = out[out["alert_type"].isin(types)]
    if severities:
        out = out[out["severity"].isin(severities)]
    if teams:
        out = out[out["team"].isin(teams)]
    return out


def _layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, font=dict(size=15, color=INK)),
        template="plotly_white", font=dict(color=INK, size=12),
        margin=dict(l=50, r=30, t=60, b=50), legend=dict(orientation="h", y=-0.2),
        paper_bgcolor="white", plot_bgcolor="white",
    )
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def flow_figure(flow: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=flow["week_ending"], y=flow["received"], name="Received", marker_color="#9aa5b1")
    fig.add_bar(x=flow["week_ending"], y=flow["closed"], name="Closed", marker_color="#1f3a5f")
    fig.add_scatter(x=flow["week_ending"], y=flow["backlog"], name="Open backlog (right axis)",
                    mode="lines+markers", line=dict(color="#c2410c", width=2.5), secondary_y=True)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Alerts per week", secondary_y=False)
    top = max(int(flow["backlog"].max()), 1) * 1.15
    step = next(d for d in (10, 20, 50, 100, 200, 500, 1000, 5000) if top / d <= 6)
    fig.update_yaxes(title_text="Open backlog", secondary_y=True, showgrid=False, range=[0, top],
                     tickformat="d", dtick=step)
    return _layout(fig, "Weekly alert volume and open backlog")


def ageing_figure(table: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for sev in SEVERITIES:
        part = table[table["severity"] == sev].set_index("age_bucket").reindex(BUCKET_LABELS)
        fig.add_bar(x=BUCKET_LABELS, y=part["alerts"], name=sev.capitalize(), marker_color=SEVERITY_COLOURS[sev])
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text="Open alerts")
    return _layout(fig, "Backlog ageing by severity")


def sla_figure(sla: pd.DataFrame, window_days: int) -> go.Figure:
    fig = go.Figure()
    if not sla.empty:
        colours = ["#1f3a5f" if c >= SLA_COMPLIANCE_TARGET else "#c2410c" for c in sla["compliance"]]
        labels = [pretty(a) for a in sla["alert_type"]]
        fig.add_bar(x=labels, y=sla["compliance"], marker_color=colours,
                    text=[f"{c:.0%}<br>({n} closed)" for c, n in zip(sla["compliance"], sla["closed"])],
                    textposition="inside", insidetextanchor="end",
                    textfont=dict(color="white", size=13), name="SLA compliance")
    fig.add_hline(y=SLA_COMPLIANCE_TARGET, line_dash="dash", line_color=INK,
                  annotation_text=f"Target {SLA_COMPLIANCE_TARGET:.0%}", annotation_position="top right")
    fig.update_yaxes(tickformat=".0%", range=[0, 1.05])
    fig.update_layout(showlegend=False)
    return _layout(fig, f"SLA compliance by alert type (closed in last {window_days} days)")


def render(df: pd.DataFrame, as_of_day, window_days: int = 30, types=None, severities=None, teams=None) -> dict:
    """Everything the dashboard shows for one set of filters."""
    as_of = metrics.as_of_end_of_day(as_of_day)
    view = filter_alerts(df, types, severities, teams)
    values = metrics.kpis(view, as_of, window_days)
    overdue = metrics.oldest_overdue(view, as_of)
    table = overdue.assign(
        created_at=overdue["created_at"].dt.strftime("%Y-%m-%d %H:%M"),
        age_days=overdue["age_days"].round(1),
        days_past_sla=overdue["days_past_sla"].round(1),
        alert_type=overdue["alert_type"].map(pretty),
    )
    return {
        "as_of": as_of,
        "tiles": [{"id": k.id, "name": k.name, "short": k.short, "value": format_value(k, values[k.id])} for k in KPIS],
        "values": values,
        "fig_flow": flow_figure(metrics.weekly_flow(view, as_of)),
        "fig_ageing": ageing_figure(metrics.ageing_table(view, as_of)),
        "fig_sla": sla_figure(metrics.sla_by_group(view, as_of, window_days), window_days),
        "table": table.to_dict("records"),
        "n_alerts_in_view": len(view),
    }
