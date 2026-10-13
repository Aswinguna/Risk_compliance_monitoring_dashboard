"""Definitions, simulation and view layer."""
import pandas as pd
import pytest

from monitoring import metrics
from monitoring.definitions import BY_ID, KPIS
from monitoring.simulate import simulate
from monitoring.views import filter_alerts, render
from tests.conftest import AS_OF_DAY


def test_every_kpi_has_a_complete_definition_and_vice_versa(tiny):
    computed = set(metrics.kpis(tiny, metrics.as_of_end_of_day(AS_OF_DAY), 30))
    defined = {k.id for k in KPIS}
    assert computed == defined, "a KPI is calculated without a definition, or defined without being calculated"
    for k in KPIS:
        for field in ("name", "short", "plain", "calculation", "caveat"):
            assert getattr(k, field).strip(), f"{k.id} has an empty {field}"
        assert k.fmt in {"int", "pct", "days"}


def test_every_kpi_states_what_it_does_not_tell_you():
    """Controllers should never read a number without knowing its blind spot."""
    assert all(len(BY_ID[i].caveat) > 30 for i in BY_ID)


def test_simulation_is_deterministic_and_valid():
    a, b, c = simulate(42), simulate(42), simulate(7)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(c)
    metrics.validate(a)


def test_planted_storyline_is_visible_in_the_kpis(simulated):
    """From July the sanctions desk slips; the dashboard must make that visible."""
    def compliance(day, alert_type):
        s = metrics.sla_by_group(simulated, metrics.as_of_end_of_day(day), 30).set_index("alert_type")
        return s.loc[alert_type, "compliance"]

    before, after = compliance("2026-06-30", "sanctions_screening"), compliance("2026-09-30", "sanctions_screening")
    assert after < before - 0.2 and after < 0.75
    assert compliance("2026-09-30", "transaction_monitoring") > 0.8   # other queues unaffected


def test_filters_empty_means_all_and_selection_narrows(simulated):
    assert len(filter_alerts(simulated)) == len(simulated)
    assert len(filter_alerts(simulated, [], [], [])) == len(simulated)
    only = filter_alerts(simulated, types=["kyb_review"], severities=["low"])
    assert set(only["alert_type"]) == {"kyb_review"} and set(only["severity"]) == {"low"}


def test_render_produces_tiles_and_figures(simulated):
    out = render(simulated, "2026-10-09", 30)
    assert [t["id"] for t in out["tiles"]] == [k.id for k in KPIS]
    assert all(t["value"] for t in out["tiles"])
    assert len(out["fig_flow"].data) == 3          # received, closed, backlog
    assert len(out["fig_ageing"].data) == 4        # one trace per severity
    assert len(out["fig_sla"].data) == 1
    assert len(out["table"]) == 15
    ages = [r["age_days"] for r in out["table"]]
    assert ages == sorted(ages, reverse=True)


def test_render_tile_values_match_metrics(simulated):
    out = render(simulated, "2026-10-09", 30)
    k = metrics.kpis(simulated, metrics.as_of_end_of_day("2026-10-09"), 30)
    tiles = {t["id"]: t["value"] for t in out["tiles"]}
    assert tiles["open_backlog"] == f"{k['open_backlog']:,}"
    assert tiles["sla_compliance"] == f"{k['sla_compliance']:.1%}"


def test_render_handles_a_selection_with_no_alerts(simulated):
    out = render(simulated, "2026-10-09", 30, types=["kyb_review"], severities=["critical"], teams=["Sanctions desk"])
    assert out["n_alerts_in_view"] == 0
    assert {t["id"]: t["value"] for t in out["tiles"]}["sla_compliance"] == "n/a"
    assert out["table"] == []


@pytest.mark.parametrize("day", ["2025-12-31", "2026-03-15", "2026-10-09"])
def test_render_works_for_different_as_at_dates(simulated, day):
    out = render(simulated, day, 90)
    assert out["values"]["open_backlog"] >= 0
