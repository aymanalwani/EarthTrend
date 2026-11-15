"""Controlled SYNTHETIC data only; no NASA results."""
import json
import unittest
import numpy as np
import pandas as pd
from earthtrend.analysis import analyze_timeseries


class AnalysisTests(unittest.TestCase):
    def analyze(self, y, dates=None, resolution="annual", **kwargs):
        if dates is None:
            dates = pd.date_range("1900-01-01", periods=len(y), freq="YS")
        return analyze_timeseries(pd.DataFrame({"date": dates, "value": y}),
                                  {"unit": "degC", "temporal_resolution": resolution}, **kwargs)

    def test_increasing_and_decreasing_known_rates(self):
        dates = pd.date_range("1900-01-01", periods=50, freq="YS")
        x = np.asarray((dates - dates[0]).days) / 365.25
        for rate in [2.0, -2.0]:
            with self.subTest(rate=rate):
                r = self.analyze(5 + rate * x, dates)
                self.assertAlmostEqual(r.regression.slope, rate, places=10)
                self.assertAlmostEqual(r.sen.slope, rate, places=10)
                self.assertAlmostEqual(r.regression.intercept, 5, places=10)
                self.assertEqual(r.status, "descriptive_only")

    def test_constant(self):
        r = self.analyze(np.ones(40))
        self.assertEqual(r.regression.slope, 0)
        self.assertEqual(r.mann_kendall.p_value, 1)
        self.assertFalse(r.mann_kendall.significant)
        self.assertIsNone(r.regression.confidence_interval)

    def test_noise_structured_finite_results(self):
        r = self.analyze(np.random.default_rng(9).normal(size=150))
        self.assertTrue(np.isfinite(r.regression.slope))
        self.assertTrue(0 <= r.regression.p_value <= 1)
        self.assertLess(r.regression.confidence_interval[0], r.regression.confidence_interval[1])
        json.dumps(r.to_dict(), allow_nan=False)

    def test_noisy_trend_significance(self):
        for sign in [-1, 1]:
            r = self.analyze(sign * np.arange(120) + np.random.default_rng(6).normal(size=120))
            self.assertTrue(r.regression.significant)
            self.assertTrue(r.mann_kendall.significant)
            self.assertEqual(r.mann_kendall.decision, "increasing" if sign > 0 else "decreasing")

    def test_sen_resists_single_outlier(self):
        dates = pd.date_range("1900-01-01", periods=50, freq="YS")
        x = np.asarray((dates - dates[0]).days) / 365.25
        y = 2 * x
        y[-1] += 10000
        r = self.analyze(y, dates)
        self.assertAlmostEqual(r.sen.slope, 2)
        self.assertGreater(r.regression.slope, 10)

    def test_missing_and_invalid_preserve_actual_time(self):
        dates = pd.date_range("2000-01-01", periods=10, freq="YS")
        y = np.asarray((dates - dates[0]).days, dtype=float) / 365.25
        values = y.astype(object)
        values[2], values[4] = None, "bad"
        r = self.analyze(values, dates)
        self.assertAlmostEqual(r.regression.slope, 1)
        self.assertAlmostEqual(r.sen.slope, 1)
        self.assertEqual(r.n, 8)
        self.assertEqual(r.quality.invalid_measurements, 1)
        self.assertIsNone(r.regression.p_value)

    def test_insufficient(self):
        for values in [[], [1], [1, 2], [None, None, None]]:
            r = self.analyze(values)
            self.assertEqual(r.status, "insufficient_data")
            self.assertIsNone(r.regression)

    def test_monthly_seasonality(self):
        dates = pd.date_range("2000-01-01", periods=240, freq="MS")
        x = np.asarray((dates - dates[0]).days) / 365.25
        y = 0.5 * x + 10 * np.sin(2 * np.pi * np.arange(240) / 12)
        y += np.random.default_rng(8).normal(0, 0.3, 240)
        r = self.analyze(y, dates, "monthly")
        self.assertAlmostEqual(r.regression.slope, 0.5, delta=0.02)
        self.assertGreater(r.diagnostics["seasonal_effect_range"], 15)
        self.assertEqual(r.diagnostics["seasonal_period"], 12)

    def test_autocorrelation_is_reflected_in_uncertainty(self):
        rng = np.random.default_rng(7)
        y = np.zeros(300)
        for i in range(1, len(y)):
            y[i] = 0.95 * y[i-1] + rng.normal()
        r = self.analyze(y)
        self.assertLess(r.diagnostics["residual_ljung_box_p_value"], 0.05)
        self.assertIn("effective-sample-size", r.regression.method)
        self.assertLess(r.diagnostics["effective_sample_size"], 30)
        self.assertIn("lag-1 variance correction", r.mann_kendall.method)
        # SYNTHETIC noise without a trend must not be declared significant.
        self.assertFalse(r.regression.significant)
        self.assertFalse(r.mann_kendall.significant)

    def test_unknown_seasonality_blocks_inference(self):
        r = self.analyze(np.arange(40), resolution="unknown")
        self.assertIsNone(r.regression.p_value)

    def test_bad_configuration(self):
        for alpha in [0, 1, float("nan"), True]:
            with self.assertRaises(ValueError):
                self.analyze([1, 2, 3], alpha=alpha)
        with self.assertRaises(ValueError):
            self.analyze([1, 2, 3], seasonal_period=0)


if __name__ == "__main__":
    unittest.main()
