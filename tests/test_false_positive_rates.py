"""Monte Carlo checks of the significance test on SYNTHETIC series.

Each case simulates trendless (or trending, for power) series with a chosen
autocorrelation structure and counts how often the app reports a significant
trend. Seeds differ from those used to choose the method (docs/ANALYSIS.md),
so these are out-of-sample checks.

Bounds:
- Families inside the method's validity domain (independent noise, AR(1) up to
  0.5) must stay within 5% plus three Monte Carlo standard errors.
- Families outside it (strong multi-year persistence) are KNOWN to exceed 5%.
  Their ceilings guard against the method getting worse and are documented
  limitations, not an acceptance of those rates.
"""
import warnings

import numpy as np
import pandas as pd
import pytest

from earthtrend.analysis import analyze_timeseries

RUNS = 300
NOMINAL_LIMIT = 0.05 + 3 * np.sqrt(0.05 * 0.95 / RUNS)  # about 0.088


def ar_noise(rng, n, phis, burn=200):
    e = rng.normal(size=n + burn)
    s = np.zeros(n + burn)
    for t in range(n + burn):
        s[t] = e[t] + sum(phi * s[t - 1 - i] for i, phi in enumerate(phis) if t - 1 - i >= 0)
    return s[-n:]


def rejection_rate(series_factory, resolution, seed, runs=RUNS):
    rng = np.random.default_rng(seed)
    hits = withheld = 0
    for _ in range(runs):
        values = series_factory(rng)
        freq = "YS" if resolution == "annual" else "MS"
        frame = pd.DataFrame({"date": pd.date_range("1991-01-01", periods=len(values), freq=freq),
                              "value": values})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            regression = analyze_timeseries(frame, {"unit": "C", "temporal_resolution": resolution}).regression
        hits += bool(regression.significant)
        withheld += regression.significant is None
    return hits / runs, withheld / runs


@pytest.mark.parametrize("n", [21, 35])
@pytest.mark.parametrize("phis", [[], [0.3], [0.5]], ids=["independent", "AR1-0.3", "AR1-0.5"])
def test_annual_false_positive_rate_within_validity_domain(n, phis):
    rate, _ = rejection_rate(lambda rng: ar_noise(rng, n, phis), "annual", seed=2027)
    assert rate <= NOMINAL_LIMIT


@pytest.mark.parametrize("n,phis,ceiling", [
    (21, [0.8], 0.13), (35, [0.8], 0.10),
    (21, [0, 0.6], 0.17), (35, [0, 0.6], 0.10),
    (21, [0.5, 0.3], 0.22), (35, [0.5, 0.3], 0.18),
], ids=["AR1-0.8-n21", "AR1-0.8-n35", "lag2-n21", "lag2-n35", "AR2-n21", "AR2-n35"])
def test_annual_known_limitations_do_not_get_worse(n, phis, ceiling):
    """Strong multi-year persistence: rates above 5% are a documented limitation."""
    rate, _ = rejection_rate(lambda rng: ar_noise(rng, n, phis), "annual", seed=2028)
    assert rate <= ceiling


def monthly_noise(years, phi1, phi12):
    def make(rng):
        n, burn = 12 * years, 240
        e = rng.normal(size=n + burn)
        s = np.zeros(n + burn)
        for t in range(n + burn):
            s[t] = e[t] + (phi1 * s[t - 1] if t >= 1 else 0) + (phi12 * s[t - 12] if t >= 12 else 0)
        return s[-n:] + 5 * np.sin(2 * np.pi * np.arange(n) / 12)
    return make


@pytest.mark.parametrize("phi1,phi12", [(0, 0), (0.5, 0), (0.95, 0), (0, 0.3), (0.5, 0.3)],
                         ids=["independent", "month-AR1-0.5", "month-AR1-0.95", "lag12-0.3", "mixed"])
def test_monthly_false_positive_rate(phi1, phi12):
    rate, _ = rejection_rate(monthly_noise(21, phi1, phi12), "monthly", seed=2029, runs=200)
    assert rate <= 0.05 + 3 * np.sqrt(0.05 * 0.95 / 200)  # about 0.096


def test_power_is_retained_for_a_clear_trend():
    """0.08 standard deviations per year over 35 independent years."""
    rate, withheld = rejection_rate(lambda rng: rng.normal(size=35) + 0.08 * np.arange(35),
                                    "annual", seed=2030, runs=200)
    assert rate >= 0.65
    assert withheld <= 0.25


def test_monthly_and_annual_resolutions_give_the_same_test():
    rng = np.random.default_rng(31)
    values = monthly_noise(25, 0.3, 0)(rng) + 0.04 * np.arange(300) / 12
    dates = pd.date_range("2000-01-01", periods=300, freq="MS")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        monthly = analyze_timeseries(pd.DataFrame({"date": dates, "value": values}),
                                     {"unit": "C", "temporal_resolution": "monthly"})
        anomalies = values - pd.Series(values).groupby(dates.month).transform("mean").to_numpy()
        annual = analyze_timeseries(
            pd.DataFrame({"date": pd.date_range("2000-07-01", periods=25, freq="12MS"),
                          "value": anomalies.reshape(25, 12).mean(1)}),
            {"unit": "C", "temporal_resolution": "annual"})
    assert monthly.regression.p_value == pytest.approx(annual.regression.p_value, rel=1e-6)
    assert monthly.regression.slope == pytest.approx(annual.regression.slope, rel=1e-6)
    assert monthly.regression.confidence_interval == pytest.approx(annual.regression.confidence_interval, rel=1e-6)


def test_interval_and_decision_always_agree():
    rng = np.random.default_rng(32)
    for _ in range(200):
        values = ar_noise(rng, 21, [0.4]) + rng.uniform(-0.1, 0.1) * np.arange(21)
        frame = pd.DataFrame({"date": pd.date_range("2005-01-01", periods=21, freq="YS"), "value": values})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = analyze_timeseries(frame, {"unit": "C", "temporal_resolution": "annual"}).regression
        if r.p_value is None:
            continue
        low, high = r.confidence_interval
        assert r.significant == (low > 0 or high < 0)
