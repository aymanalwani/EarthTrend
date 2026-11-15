"""Tests for the pipeline, the team-module connectors and the UI wording.

The NASA input is the REAL saved response in tests/fixtures. Stand-in team
modules and trend dictionaries defined here are SYNTHETIC and exist only to
check that the interface passes values through unchanged.

No test contacts the network.
"""

import json
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from earthtrend import integration
from earthtrend.data import power_client
from earthtrend.pipeline import AnalysisRequest, run_analysis
from earthtrend.ui import charts, text

ROOT = Path(__file__).parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "power_monthly_cairo.json"


def fake_fetch(*args, **kwargs):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return power_client.parse_monthly_response(payload)


def make_request(resolution="monthly", variables=("T2M", "PRECTOTCORR")):
    return AnalysisRequest(variables, 30.05, 31.25, 2025, 2026, resolution, "Cairo")


@pytest.fixture
def no_team_modules(monkeypatch):
    """Behave as if steps 4-6 are not merged, whatever is on disk."""
    monkeypatch.setattr(integration, "_find", lambda target: None)


# --- pipeline -----------------------------------------------------------------

def test_monthly_pipeline_counts_valid_and_missing(no_team_modules):
    output = run_analysis(make_request(), fetch=fake_fetch)
    assert [v.variable for v in output.variables] == ["T2M", "PRECTOTCORR"]
    for item in output.variables:
        assert (item.n_total, item.n_valid, item.n_missing) == (23, 21, 2)
        assert item.first_valid == pd.Timestamp("2025-01-01")
        assert item.last_valid == pd.Timestamp("2026-09-01")
    assert output.variables[0].unit == "C"
    assert output.variables[1].unit == "mm/day"


def test_no_results_are_invented_without_analysis_module(no_team_modules):
    output = run_analysis(make_request(), fetch=fake_fetch)
    for item in output.variables:
        assert item.trend is None
        assert item.trend_error is None
        assert item.preprocessing_applied is False


def test_annual_pipeline_uses_power_annual_values(no_team_modules):
    output = run_analysis(make_request("annual", ("T2M",)), fetch=fake_fetch)
    item = output.variables[0]
    assert item.series["date"].tolist() == [pd.Timestamp("2025-01-01")]
    assert item.series["value"].tolist() == [22.54]
    assert list(item.series.columns) == power_client.TIMESERIES_COLUMNS
    assert output.metadata["temporal_resolution"] == "annual"


def test_unknown_resolution_is_rejected():
    with pytest.raises(ValueError):
        run_analysis(make_request("weekly"), fetch=fake_fetch)


def test_retrieval_errors_propagate():
    def failing_fetch(*args, **kwargs):
        raise power_client.PowerTimeoutError("slow")

    with pytest.raises(power_client.PowerTimeoutError):
        run_analysis(make_request(), fetch=failing_fetch)


# --- connectors to team modules (synthetic stand-ins) --------------------------

def _install(monkeypatch, name, **functions):
    module = types.ModuleType(name)
    for key, value in functions.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(
        integration.importlib.util, "find_spec",
        lambda target, _real=integration.importlib.util.find_spec:
            object() if target == name else _real(target),
    )


def test_analysis_module_result_is_passed_through(monkeypatch):
    synthetic = {"direction": "increasing", "slope": 0.2, "p_value": 0.01, "significant": True}
    _install(monkeypatch, "earthtrend.analysis",
             analyze_timeseries=lambda series, metadata, alpha: {**synthetic, "alpha": alpha})
    output = run_analysis(make_request(variables=("T2M",)), fetch=fake_fetch, alpha=0.05)
    assert output.variables[0].trend == {**synthetic, "alpha": 0.05}


def test_analysis_failure_is_reported_not_hidden(monkeypatch):
    def refuse(series, metadata, alpha):
        raise ValueError("not enough observations")

    _install(monkeypatch, "earthtrend.analysis", analyze_timeseries=refuse)
    item = run_analysis(make_request(variables=("T2M",)), fetch=fake_fetch).variables[0]
    assert item.trend is None
    assert "not enough observations" in item.trend_error


def test_module_with_wrong_function_name_is_an_integration_error(monkeypatch):
    _install(monkeypatch, "earthtrend.analysis", something_else=lambda: None)
    with pytest.raises(integration.IntegrationError):
        run_analysis(make_request(variables=("T2M",)), fetch=fake_fetch)


def test_preprocessing_module_is_applied(monkeypatch):
    _install(monkeypatch, "earthtrend.preprocessing",
             preprocess_timeseries=lambda s, metadata: (s.dropna(subset=["value"]), {"removed": 2}))
    item = run_analysis(make_request(variables=("T2M",)), fetch=fake_fetch).variables[0]
    assert item.preprocessing_applied is True
    assert item.preprocessing_report == {"removed": 2}
    assert (item.n_total, item.n_missing) == (21, 0)


# --- wording -------------------------------------------------------------------

def test_real_scientific_modules_connect_to_saved_nasa_response():
    output = run_analysis(make_request(variables=("T2M",)), fetch=fake_fetch)
    item = output.variables[0]
    assert item.preprocessing_applied
    assert item.trend_error is None
    assert item.trend["n_valid"] == 21
    assert item.trend["analysis_details"]["diagnostics"]["seasonal_period"] == 12
    # 21 monthly values cannot separate the seasonal cycle from a trend, so
    # no rate, direction or significance may be reported for this real series.
    assert item.trend["analysis_details"]["status"] == "seasonal_adjustment_unavailable"
    assert item.trend["slope"] is None and item.trend["direction"] is None
    assert item.trend["p_value"] is None and item.trend["significant"] is None
    assert "trend_line" not in item.trend


def test_interpretation_without_analysis_makes_no_trend_claim():
    message = text.interpret(None, "Temperature", "1991–2025", "Cairo")
    assert message == text.INTERPRETATION_UNAVAILABLE
    assert "increasing" not in message and "decreasing" not in message


def test_interpretation_of_significant_trend_uses_given_values():
    trend = {"direction": "increasing", "slope": 0.31, "slope_unit": "C per decade",
             "p_value": 0.0004, "significant": True, "alpha": 0.05}
    message = text.interpret(trend, "Temperature", "1991–2025", "Cairo")
    assert "statistically significant increasing trend" in message
    assert "+0.31 C per decade" in message and "< 0.001" in message


def test_interpretation_of_non_significant_trend_does_not_overclaim():
    trend = {"direction": "increasing", "slope": 0.05, "slope_unit": "mm/day per decade",
             "p_value": 0.41, "significant": False, "alpha": 0.05}
    message = text.interpret(trend, "Precipitation", "1991–2025", "Cairo")
    assert "no statistically significant trend" in message
    assert "0.410" in message and "not proof that nothing is changing" in message
    assert "insufficient evidence of a trend" in message
    assert "natural variability" not in message


def test_formatting_handles_absent_values():
    assert text.format_p_value(None) == text.NOT_REPORTED
    assert text.format_rate({}) == text.NOT_REPORTED
    assert text.format_confidence_interval({"ci_low": 0.1}) == "Not available"
    assert text.format_confidence_interval(
        {"ci_low": 0.1, "ci_high": 0.5, "ci_level": 0.95}) == "95%: +0.1 to +0.5"
    assert text.significance_label({}) == "Not tested (see notes)"


def test_significance_label_marks_short_records_indicative():
    assert text.significance_label({"significant": True, "test_years": 21}) == \
        "Statistically significant (indicative: 21 years)"
    assert text.significance_label({"significant": False, "test_years": 35}) == "Not statistically significant"
    limits = " ".join(text.GENERAL_LIMITATIONS)
    for phrase in ("not ground-truth", "multiple comparisons", "Not tested"):
        assert phrase in limits


# --- chart ---------------------------------------------------------------------

def test_basic_chart_keeps_gaps_and_draws_no_trend_by_default(no_team_modules):
    item = run_analysis(make_request(variables=("T2M",)), fetch=fake_fetch).variables[0]
    figure = charts.basic_timeseries_figure(
        item.series, variable_name=item.name, unit=item.unit, title="t", source="s")
    assert len(figure.data) == 1
    assert figure.data[0].connectgaps is False
    assert pd.isna(figure.data[0].y[-1])
    assert "(C)" in figure.layout.yaxis.title.text


# --- app smoke test --------------------------------------------------------------

@pytest.mark.parametrize("resolution", ["monthly", "annual"])
def test_ui_routes_real_fixture_to_team_plotting(monkeypatch, resolution):
    """Offline NASA fixture -> pipeline -> actual plotting entry point -> UI."""
    from earthtrend.ui import components

    find = integration._find
    monkeypatch.setattr(integration, "_find", lambda target:
                        find(target) if target == integration.PLOTTING_FUNCTION else None)
    output = run_analysis(make_request(resolution, ("T2M",)), fetch=fake_fetch)
    rendered = []
    monkeypatch.setattr(components.st, "plotly_chart", lambda figure, **kw: rendered.append(figure))
    monkeypatch.setattr(components.st, "caption", lambda *args, **kw: None)
    components.render_chart(output.variables[0], output)
    assert len(rendered) == 1
    figure = rendered[0]
    assert figure.layout.meta["unit"] == "C"
    assert figure.layout.meta["source"] == output.metadata["source"]
    assert figure.layout.meta["temporal_resolution"] == resolution
    assert list(figure.layout.xaxis.range) == ["2025-01-01T00:00:00", "2027-01-01T00:00:00"]
    assert figure.data[0].mode == "lines+markers"
    assert len(figure.data) == 1


def test_app_starts_without_errors():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "EarthTrend"
    assert app.button[0].label == "Analyze"


def test_app_displays_connected_statistics_with_saved_response(monkeypatch):
    """Exercise the real UI and scientific modules, with offline NASA retrieval."""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(power_client, "get_monthly_series", fake_fetch)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.button[0].click().run()
    assert not app.exception
    labels = [metric.label for metric in app.metric]
    assert "Trend rate" in labels
    assert "Mann–Kendall decision" in labels
    assert "Sen’s slope" in labels


# --- study location map (step 8) -----------------------------------------------

def test_map_marks_only_the_analysed_point():
    from earthtrend.ui import maps

    figure = maps.study_point_map(
        30.05, 31.25, location_label="Cairo", variable_names=["Temperature at 2 Meters"])
    assert len(figure.data) == 1
    assert list(figure.data[0].lat) == [30.05] and list(figure.data[0].lon) == [31.25]
    assert figure.layout.map.center.lat == 30.05 and figure.layout.map.center.lon == 31.25
    assert "Temperature at 2 Meters" in figure.layout.title.text
    assert "Single point, not a region" in figure.data[0].hovertemplate
    assert figure.layout.meta["shows_measurements"] is False


@pytest.mark.parametrize("lat, lon", [(91, 0), (0, 181), (float("nan"), 0), ("30", 0), (True, 0)])
def test_map_rejects_invalid_coordinates(lat, lon):
    from earthtrend.ui import maps

    with pytest.raises(maps.MapError):
        maps.study_point_map(lat, lon)


def test_map_uses_coordinates_of_the_actual_analysis(monkeypatch, no_team_modules):
    from earthtrend.ui import components

    output = run_analysis(make_request(variables=("T2M",)), fetch=fake_fetch)
    rendered = []
    monkeypatch.setattr(components.st, "plotly_chart", lambda figure, **kw: rendered.append(figure))
    components.render_location_map(output)
    assert len(rendered) == 1
    assert rendered[0].layout.meta["latitude"] == output.metadata["latitude"] == 30.05
    assert rendered[0].layout.meta["longitude"] == output.metadata["longitude"] == 31.25


def test_map_failure_does_not_break_results(monkeypatch, no_team_modules):
    from earthtrend.ui import components

    output = run_analysis(make_request(variables=("T2M",)), fetch=fake_fetch)

    def broken(*args, **kwargs):
        raise RuntimeError("map unavailable")

    monkeypatch.setattr(components.maps, "study_point_map", broken)
    components.render_location_map(output)  # must not raise


def test_map_is_skipped_without_point_coordinates(monkeypatch, no_team_modules):
    from earthtrend.ui import components

    output = run_analysis(make_request(variables=("T2M",)), fetch=fake_fetch)
    output.metadata.pop("latitude")
    rendered = []
    monkeypatch.setattr(components.st, "plotly_chart", lambda figure, **kw: rendered.append(figure))
    components.render_location_map(output)
    assert rendered == []
