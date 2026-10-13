"""Risk and Compliance monitoring dashboard (simulated data).

Run:  python app.py   then open http://127.0.0.1:8050
"""
from __future__ import annotations

from dash import Dash, Input, Output, dash_table, dcc, html

from monitoring import metrics
from monitoring.config import ALERT_TYPES, SEVERITIES, SIM_END, SIM_START
from monitoring.definitions import KPIS
from monitoring.simulate import simulate
from monitoring.views import pretty, render

DATA = simulate()
metrics.validate(DATA)
TEAMS = sorted(DATA["team"].unique())

STYLE = {
    "page": {"fontFamily": "Inter, Helvetica, Arial, sans-serif", "color": "#1a1a1a", "maxWidth": "1280px",
             "margin": "0 auto", "padding": "24px"},
    "tile": {"border": "1px solid #e5e7eb", "borderRadius": "8px", "padding": "14px 16px", "minWidth": "190px",
             "flex": "1 1 190px", "background": "white"},
    "tile_value": {"fontSize": "28px", "fontWeight": "700", "margin": "4px 0"},
    "tile_name": {"fontSize": "13px", "fontWeight": "600", "color": "#374151"},
    "tile_short": {"fontSize": "12px", "color": "#6b7280"},
    "row": {"display": "flex", "gap": "12px", "flexWrap": "wrap", "margin": "12px 0"},
    "card": {"border": "1px solid #e5e7eb", "borderRadius": "8px", "padding": "8px", "flex": "1 1 520px", "background": "white"},
}


def options(values):
    return [{"label": pretty(v), "value": v} for v in values]


def filters_bar():
    label = {"fontSize": "12px", "fontWeight": "600", "marginBottom": "4px"}
    return html.Div([
        html.Div([html.Div("As at", style=label),
                  dcc.DatePickerSingle(id="as-of", date=SIM_END, min_date_allowed=SIM_START, max_date_allowed=SIM_END,
                                       display_format="DD MMM YYYY")]),
        html.Div([html.Div("Window", style=label),
                  dcc.Dropdown(id="window", options=[{"label": f"Last {d} days", "value": d} for d in (7, 30, 90)],
                               value=30, clearable=False, style={"width": "150px"})]),
        html.Div([html.Div("Alert type", style=label),
                  dcc.Dropdown(id="types", options=options(ALERT_TYPES), multi=True, placeholder="All",
                               style={"minWidth": "240px"})]),
        html.Div([html.Div("Severity", style=label),
                  dcc.Dropdown(id="severities", options=options(SEVERITIES), multi=True, placeholder="All",
                               style={"minWidth": "200px"})]),
        html.Div([html.Div("Team", style=label),
                  dcc.Dropdown(id="teams", options=[{"label": t, "value": t} for t in TEAMS], multi=True,
                               placeholder="All", style={"minWidth": "220px"})]),
    ], style={**STYLE["row"], "alignItems": "flex-end"})


def definitions_tab():
    items = []
    for k in KPIS:
        items.append(html.Div([
            html.H4(k.name, style={"margin": "0 0 6px 0"}),
            html.P([html.B("In plain words: "), k.plain], style={"margin": "4px 0"}),
            html.P([html.B("Calculation: "), k.calculation], style={"margin": "4px 0"}),
            html.P([html.B("What it does not tell you: "), k.caveat], style={"margin": "4px 0"}),
        ], style={"borderBottom": "1px solid #e5e7eb", "padding": "12px 0"}))
    extra = html.P("SLA deadlines are calendar days from creation: critical 2, high 5, medium 10, low 20. "
                   "Business days, weekends and public holidays are not modelled. All data on this dashboard is simulated.",
                   style={"fontSize": "13px", "color": "#374151"})
    return html.Div([html.H3("How every number is calculated"), extra, *items], style={"padding": "12px 4px"})


app = Dash(__name__, title="Risk & Compliance Monitoring")
app.layout = html.Div([
    html.H2("Risk & Compliance Monitoring: Alert Backlog, SLA and KPIs", style={"marginBottom": "2px"}),
    html.Div("Simulated data. No real customers, alerts or Qonto data.", style={"fontSize": "13px", "color": "#6b7280", "margin": "4px 0 14px 0"}),
    dcc.Tabs(id="tabs", value="monitor", children=[
        dcc.Tab(label="Monitoring", value="monitor", children=[
            filters_bar(),
            html.Div(id="as-of-note", style={"fontSize": "13px", "color": "#374151"}),
            html.Div(id="tiles", style=STYLE["row"]),
            html.Div([html.Div(dcc.Graph(id="fig-flow"), style=STYLE["card"]),
                      html.Div(dcc.Graph(id="fig-ageing"), style=STYLE["card"])], style=STYLE["row"]),
            html.Div([html.Div(dcc.Graph(id="fig-sla"), style=STYLE["card"]),
                      html.Div([html.H4("Oldest overdue open alerts", style={"margin": "8px"}),
                                dash_table.DataTable(
                                    id="oldest", page_size=10,
                                    columns=[{"name": n, "id": i} for i, n in [
                                        ("alert_id", "Alert"), ("alert_type", "Type"), ("severity", "Severity"),
                                        ("team", "Team"), ("created_at", "Raised"), ("age_days", "Age (days)"),
                                        ("days_past_sla", "Days past SLA")]],
                                    style_header={"fontWeight": "700", "backgroundColor": "#f3f4f6"},
                                    style_cell={"fontSize": "12px", "padding": "6px", "textAlign": "left"},
                                    style_table={"overflowX": "auto"})],
                               style=STYLE["card"])], style=STYLE["row"]),
        ]),
        dcc.Tab(label="KPI definitions", value="defs", children=[definitions_tab()]),
    ]),
], style=STYLE["page"])


def tile(t):
    return html.Div([html.Div(t["name"], style=STYLE["tile_name"]),
                     html.Div(t["value"], style=STYLE["tile_value"]),
                     html.Div(t["short"], style=STYLE["tile_short"])], style=STYLE["tile"])


@app.callback(
    Output("tiles", "children"), Output("fig-flow", "figure"), Output("fig-ageing", "figure"),
    Output("fig-sla", "figure"), Output("oldest", "data"), Output("as-of-note", "children"),
    Input("as-of", "date"), Input("window", "value"), Input("types", "value"),
    Input("severities", "value"), Input("teams", "value"),
)
def update(as_of, window, types, severities, teams):
    out = render(DATA, as_of or SIM_END, window or 30, types, severities, teams)
    note = (f"Showing {out['n_alerts_in_view']:,} alerts in the current selection, as at "
            f"{out['as_of']:%d %b %Y}. Window: last {window or 30} days.")
    return [tile(t) for t in out["tiles"]], out["fig_flow"], out["fig_ageing"], out["fig_sla"], out["table"], note


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
