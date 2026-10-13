"""KPI maths checked against answers worked out by hand on the `tiny` fixture."""
import pandas as pd
import pytest

from monitoring import metrics
from tests.conftest import AS_OF_DAY, make_alert

AS_OF = metrics.as_of_end_of_day(AS_OF_DAY)


def test_headline_kpis_match_hand_calculation(tiny):
    k = metrics.kpis(tiny, AS_OF, 30)
    assert k["open_backlog"] == 6               # A2, A4, A6, A8, A9, A10
    assert k["received"] == 8                   # everything except A4 and A5
    assert k["closed"] == 3                     # A1, A3, A7
    assert k["clearance_rate"] == pytest.approx(3 / 8)
    assert k["sla_compliance"] == pytest.approx(2 / 3)   # A1 and A7 met, A3 breached
    assert k["overdue_open"] == 2               # A2 and A4
    assert k["median_age_open"] == pytest.approx(7.5, abs=1e-3)   # between A10 (7.0) and A9 (8.0)
    assert k["pct_over_30d"] == pytest.approx(1 / 6)               # only A4
    assert k["oldest_open"] == pytest.approx(48.0, abs=1e-3)       # A4


def test_alert_closed_after_the_selected_day_counts_as_open(tiny):
    """A2 is closed on 5 Feb, but as at 31 Jan it was still waiting."""
    opened = metrics.open_alerts(tiny, AS_OF)
    assert "A2" in set(opened["alert_id"])


def test_alert_created_after_the_selected_day_is_invisible(tiny):
    future = pd.concat([tiny, pd.DataFrame([make_alert("A11", "kyb_review", "low", "2026-02-02 09:00")])],
                       ignore_index=True)
    assert metrics.kpis(future, AS_OF, 30) == metrics.kpis(tiny, AS_OF, 30)


def test_ageing_bucket_boundaries(tiny):
    """Exactly 8.0 days old is in 8-14; 7 days and 1 second is still in 0-7."""
    opened = metrics.open_alerts(tiny, AS_OF).set_index("alert_id")
    assert opened.loc["A9", "age_bucket"] == "8-14 days"
    assert opened.loc["A10", "age_bucket"] == "0-7 days"
    assert opened.loc["A4", "age_bucket"] == "31-60 days"
    assert opened.loc["A2", "age_bucket"] == "0-7 days"


def test_ageing_table_counts_and_completeness(tiny):
    table = metrics.ageing_table(tiny, AS_OF)
    assert len(table) == 5 * 4                               # every bucket x severity cell exists
    assert table["alerts"].sum() == 6                        # equals open backlog
    cell = lambda b, s: int(table[(table.age_bucket == b) & (table.severity == s)]["alerts"].iloc[0])
    assert cell("0-7 days", "critical") == 1                 # A2
    assert cell("0-7 days", "low") == 2                      # A6, A10
    assert cell("8-14 days", "low") == 2                     # A8, A9
    assert cell("31-60 days", "low") == 1                    # A4
    assert cell("Over 60 days", "low") == 0


def test_sla_by_alert_type(tiny):
    sla = metrics.sla_by_group(tiny, AS_OF, 30).set_index("alert_type")
    assert sla.loc["transaction_monitoring", "closed"] == 2
    assert sla.loc["transaction_monitoring", "compliance"] == pytest.approx(1.0)
    assert sla.loc["sanctions_screening", "closed"] == 1
    assert sla.loc["sanctions_screening", "compliance"] == pytest.approx(0.0)


def test_oldest_overdue_is_sorted_oldest_first(tiny):
    out = metrics.oldest_overdue(tiny, AS_OF)
    assert list(out["alert_id"]) == ["A4", "A2"]
    assert out["days_past_sla"].iloc[0] == pytest.approx(27.9999, abs=1e-3)   # due 4 Jan, 28 days before 1 Feb


def test_window_edges_are_start_exclusive_end_inclusive():
    edge_in = make_alert("IN", "kyb_review", "low", "2026-01-31 23:59:59")        # exactly at as_of: counted
    edge_out = make_alert("OUT", "kyb_review", "low", "2026-01-01 23:59:59")      # exactly at window start: not counted
    df = pd.DataFrame([edge_in, edge_out])
    assert metrics.kpis(df, AS_OF, 30)["received"] == 1


def test_empty_data_gives_none_not_errors(tiny):
    empty = tiny.iloc[0:0]
    k = metrics.kpis(empty, AS_OF, 30)
    assert k["open_backlog"] == 0 and k["received"] == 0
    assert k["clearance_rate"] is None and k["sla_compliance"] is None
    assert k["median_age_open"] is None and k["oldest_open"] is None
    assert metrics.sla_by_group(empty, AS_OF, 30).empty
    assert len(metrics.weekly_flow(empty, AS_OF)) == 26


def test_weekly_backlog_matches_brute_force_on_simulated_data(simulated):
    """The fast searchsorted version must equal counting open alerts one edge at a time."""
    flow = metrics.weekly_flow(simulated, metrics.as_of_end_of_day("2026-10-09"), weeks=26)
    as_of = metrics.as_of_end_of_day("2026-10-09")
    for k, row in enumerate(flow.itertuples()):
        edge = as_of - pd.Timedelta(days=7 * (25 - k))
        assert row.backlog == int(metrics.open_mask(simulated, edge).sum())


def test_weekly_flow_totals_equal_window_counts(simulated):
    as_of = metrics.as_of_end_of_day("2026-10-09")
    flow = metrics.weekly_flow(simulated, as_of, weeks=26)
    assert flow["received"].sum() == int(metrics.in_window(simulated["created_at"], as_of, 26 * 7).sum())
    assert flow["closed"].sum() == int(metrics.in_window(simulated["closed_at"], as_of, 26 * 7).sum())


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.assign(alert_id="DUP"), "Duplicate"),
    (lambda d: d.assign(severity="urgent"), "Unknown severities"),
    (lambda d: d.assign(team=None), "Nulls"),
    (lambda d: d.assign(closed_at=d["created_at"] - pd.Timedelta(hours=1)), "before they were created"),
    (lambda d: d.drop(columns=["sla_due_at"]), "Missing columns"),
])
def test_validation_rejects_bad_data(tiny, mutate, message):
    with pytest.raises(ValueError, match=message):
        metrics.validate(mutate(tiny))


def test_validation_accepts_good_data(tiny, simulated):
    metrics.validate(tiny)
    metrics.validate(simulated)
