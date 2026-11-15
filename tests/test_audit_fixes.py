"""Regression tests for the step 9 audit findings.

Every series built in this file is SYNTHETIC test data with a known answer.
None of it is NASA data.
"""

import warnings

import numpy as np
import pandas as pd
import pytest

from earthtrend import integration
from earthtrend.analysis import analyze_timeseries
from earthtrend.data import power_client
from earthtrend.ui import components


def synthetic_frame(values, freq):
    dates = pd.date_range("1991-01-01", periods=len(values), freq=freq)
    return pd.DataFrame({"date": dates, "value": np.asarray(values, dtype=float)})


def analyze(values, resolution):
    frame = synthetic_frame(values, "YS" if resolution == "annual" else "MS")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return analyze_timeseries(frame, {"unit": "C", "temporal_resolution": resolution})


def ar1_noise(rng, n, phi):
    noise = rng.normal(size=n + 50)
    series = np.zeros(n + 50)
    for i in range(1, n + 50):
        series[i] = phi * series[i - 1] + noise[i]
    return series[50:]


# --- significance must not be over-reported ---------------------------------------

@pytest.mark.parametrize("phi, limit", [(0.0, 0.08), (0.6, 0.12)])
def test_false_positive_rate_on_trendless_annual_series(phi, limit):
    """With no true trend, about 5% of runs may be 'significant' at alpha 0.05.

    Before the audit fix the measured rates were about 9% (phi 0) and 24%
    (phi 0.6). The limits leave room for sampling error in 400 runs.
    """
    rng = np.random.default_rng(2026)
    runs = 400
    regression = mann_kendall = 0
    for _ in range(runs):
        result = analyze(ar1_noise(rng, 35, phi), "annual")
        regression += bool(result.regression.significant)
        mann_kendall += bool(result.mann_kendall.significant)
    assert regression / runs <= limit
    assert mann_kendall / runs <= limit


def test_real_trend_is_still_detected():
    """A clear SYNTHETIC trend (0.05/yr, noise 0.3) must usually be found.

    The dependence check withholds roughly one series in eight by design, so
    this is a rate over many series rather than a single fixed example.
    """
    rng = np.random.default_rng(5)
    runs = 200
    detected = wrong_direction = 0
    for _ in range(runs):
        result = analyze(0.05 * np.arange(40) + rng.normal(0, 0.3, 40), "annual")
        assert result.regression.slope == pytest.approx(0.05, abs=0.02)
        assert result.regression.direction == "increasing"
        if result.regression.significant:
            detected += 1
            low, high = result.regression.confidence_interval
            assert low > 0
            wrong_direction += result.mann_kendall.decision == "decreasing"
    assert detected / runs >= 0.75
    assert wrong_direction == 0


def test_decreasing_trend_is_reported_as_decreasing():
    rng = np.random.default_rng(6)
    result = analyze(-0.05 * np.arange(40) + rng.normal(0, 0.3, 40), "annual")
    assert result.regression.direction == "decreasing" and result.regression.significant
    assert result.mann_kendall.decision == "decreasing"


def test_confidence_interval_is_centred_on_the_slope():
    rng = np.random.default_rng(8)
    result = analyze(0.02 * np.arange(35) + rng.normal(0, 1, 35), "annual")
    low, high = result.regression.confidence_interval
    assert (low + high) / 2 == pytest.approx(result.regression.slope)
    assert result.diagnostics["effective_sample_size"] <= 35


# --- seasonal cycle must not be reported as a trend -----------------------------

def test_short_monthly_series_reports_no_rate():
    cycle = 10 * np.sin(2 * np.pi * np.arange(12) / 12)  # one year, no trend
    result = analyze(cycle, "monthly")
    assert result.status == "seasonal_adjustment_unavailable"
    assert result.regression is None and result.sen is None
    assert result.mann_kendall.p_value is None
    assert any("seasonal cycle" in note for note in result.warnings)


def test_gap_does_not_shift_months_into_wrong_season():
    rng = np.random.default_rng(9)
    months = np.arange(240)
    values = 10 * np.sin(2 * np.pi * months / 12) + 0.03 * months / 12 + rng.normal(0, 0.2, 240)
    frame = synthetic_frame(values, "MS").drop(index=100).reset_index(drop=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = analyze_timeseries(frame, {"unit": "C", "temporal_resolution": "monthly"})
    # Calendar-month phases and actual elapsed time: a gap is tolerated.
    assert result.status in ("inference_available", "partial_inference")
    assert result.regression.p_value is not None
    assert result.regression.slope == pytest.approx(0.03, abs=0.005)
    assert any("missing" in note for note in result.warnings)


def test_rounding_noise_is_not_a_direction():
    cycle = 10 * np.sin(2 * np.pi * np.arange(48) / 12)  # exact cycle, zero trend
    result = analyze(cycle, "monthly")
    assert abs(result.regression.slope) < 1e-9
    assert result.regression.direction == "constant"


# --- trend line -----------------------------------------------------------------

def test_annual_trend_line_is_the_fitted_regression_line():
    rng = np.random.default_rng(10)
    frame = synthetic_frame(0.1 * np.arange(35) + rng.normal(0, 0.5, 35), "YS")
    metadata = {"unit": "C", "temporal_resolution": "annual"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        trend = integration.analyze(frame, 0.05, metadata)
    line = trend["trend_line"]
    assert len(line["dates"]) == len(line["values"]) == 35
    assert line["unit"] == "C"
    assert line["values"][0] == pytest.approx(trend["analysis_details"]["regression"]["intercept"])
    years = (pd.Timestamp(line["dates"][-1]) - pd.Timestamp(line["dates"][0])).days / 365.25
    assert line["values"][-1] - line["values"][0] == pytest.approx(trend["slope"] * years)


def test_monthly_trend_line_averages_out_the_seasonal_cycle():
    rng = np.random.default_rng(11)
    months = np.arange(120)
    values = 5 + 10 * np.sin(2 * np.pi * months / 12) + 0.2 * months / 12 + rng.normal(0, 0.3, 120)
    frame = synthetic_frame(values, "MS")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        trend = integration.analyze(frame, 0.05, {"unit": "C", "temporal_resolution": "monthly"})
    line = np.array(trend["trend_line"]["values"])
    # A straight line through the series mean, not through the seasonal cycle.
    assert line.mean() == pytest.approx(values.mean(), abs=0.1)
    assert np.ptp(line) == pytest.approx(abs(trend["slope"]) * 119 / 12, rel=0.02)


# --- error messages -------------------------------------------------------------

@pytest.mark.parametrize("status, expected", [
    (500, "temporarily unavailable"),
    (503, "temporarily unavailable"),
    (429, "limiting requests"),
    (422, "rejected the request"),
])
def test_http_errors_are_described_accurately(monkeypatch, status, expected):
    shown = []
    monkeypatch.setattr(components.st, "error", shown.append)
    monkeypatch.setattr(components.st, "caption", lambda *a, **k: None)
    components.render_error(power_client.PowerRequestError(status, ["detail"]))
    assert expected in shown[0]


# --- disagreement between the two tests -----------------------------------------

def _trend(regression_significant, mk_significant):
    """SYNTHETIC result dictionary; the numbers are not from any analysis."""
    return {
        "direction": "increasing", "slope": 0.01, "slope_unit": "mm/day/year",
        "p_value": 0.021 if regression_significant else 0.2,
        "significant": regression_significant, "alpha": 0.05,
        "analysis_details": {"mann_kendall": {
            "significant": mk_significant, "p_value": 0.03 if mk_significant else 0.3}},
    }


def test_disagreeing_tests_are_not_reported_as_a_clear_trend():
    from earthtrend.ui import text

    message = text.interpret(_trend(True, False), "Precipitation", "1991–2025", "Cairo")
    assert "mixed" in message and "disagree" in message
    assert "shows a statistically significant" not in message
    message = text.interpret(_trend(False, True), "Precipitation", "1991–2025", "Cairo")
    assert "mixed" in message and "disagree" in message


def test_agreeing_or_single_tests_keep_the_normal_wording():
    from earthtrend.ui import text

    assert text.disagreement_note(_trend(True, True)) is None
    assert text.disagreement_note(_trend(False, False)) is None
    only_regression = _trend(True, True)
    only_regression["analysis_details"]["mann_kendall"]["significant"] = None
    assert text.disagreement_note(only_regression) is None
    assert "statistically significant increasing trend" in text.interpret(
        _trend(True, True), "Temperature", "1991–2025", "Cairo")


# --- dependence beyond lag 1 (review of the audit fix) ---------------------------

def lagged_noise(rng, n, lag, phi):
    """SYNTHETIC trendless series whose dependence sits at one chosen lag."""
    noise = rng.normal(size=n + 20 * lag)
    series = np.zeros(n + 20 * lag)
    for i in range(lag, len(series)):
        series[i] = phi * series[i - lag] + noise[i]
    return series[-n:]


@pytest.mark.parametrize("resolution, n, lag, phi, runs", [
    ("annual", 35, 2, 0.6, 300),
    ("annual", 35, 2, 0.9, 300),
    ("monthly", 420, 12, 0.6, 120),
    ("monthly", 420, 12, 0.9, 120),
])
def test_dependence_beyond_lag1_does_not_produce_false_trends(resolution, n, lag, phi, runs):
    """Trendless series with lag-2 or lag-12 dependence.

    Before the dependence check these produced 22-56% false positives. The
    limit of 12% allows for sampling error; measured rates are 0-9%.
    """
    rng = np.random.default_rng(321)
    regression = mann_kendall = withheld = 0
    for _ in range(runs):
        result = analyze(lagged_noise(rng, n, lag, phi), resolution)
        regression += bool(result.regression.significant)
        mann_kendall += bool(result.mann_kendall.significant)
        withheld += result.regression.significant is None
    assert regression / runs <= 0.12
    assert mann_kendall / runs <= 0.12
    assert withheld > 0  # the check is what protects these cases


def test_monthly_significance_is_tested_on_annual_anomalies():
    rng = np.random.default_rng(4)
    result = analyze(lagged_noise(rng, 420, 12, 0.6), "monthly")
    assert any("annual means of the deseasonalized values" in note for note in result.warnings)
    assert result.diagnostics["annual_anomaly_years"] == 35
    assert result.regression.method.startswith("Annual means of deseasonalized monthly values")


def test_withheld_inference_reports_no_p_value_or_interval():
    rng = np.random.default_rng(4)
    result = analyze(lagged_noise(rng, 35, 2, 0.9), "annual")
    assert result.status == "descriptive_only"
    assert result.regression.p_value is None
    assert result.regression.significant is None
    assert result.regression.confidence_interval is None
    assert result.mann_kendall.p_value is None
    assert result.diagnostics["beyond_lag1_ljung_box_p_value"] < 0.10
    assert any("beyond lag 1" in note for note in result.warnings)


def test_dependence_check_rarely_blocks_independent_data():
    """The check itself must not discard most well-behaved series."""
    rng = np.random.default_rng(12)
    runs = 300
    assessed = sum(
        analyze(rng.normal(size=35), "annual").regression.significant is not None
        for _ in range(runs)
    )
    assert assessed / runs >= 0.80


def test_seasonal_sen_and_annual_test_respect_calendar_months_across_a_gap():
    """A dropped month must not shift later values into the wrong season."""
    rng = np.random.default_rng(21)
    months = np.arange(240)
    values = 10 * np.sin(2 * np.pi * months / 12) + 0.05 * months / 12 + rng.normal(0, 0.3, 240)
    frame = synthetic_frame(values, "MS").drop(index=100).reset_index(drop=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = analyze_timeseries(frame, {"unit": "C", "temporal_resolution": "monthly"})
    # The year with one missing month is kept: deseasonalized means stay unbiased.
    assert result.diagnostics["annual_anomaly_years"] == 20
    assert result.sen.slope == pytest.approx(0.05, abs=0.01)
    assert "Seasonal Theil-Sen" in result.sen.method
