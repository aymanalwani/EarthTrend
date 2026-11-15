"""Synthetic contract tests for the real UI module-discovery entry point."""

import unittest

from earthtrend import integration
from earthtrend.plotting import make_timeseries_figure
from earthtrend.visualization import VisualizationError


class PlottingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.series = [{"date": "2020-02-01", "value": 1},
                       {"date": "2020-04-01", "value": 3}]
        self.context = dict(
            variable="TEST", start_date="2020-01-01", end_date="2020-12-31",
            location_name="Synthetic study point",
            metadata={"units": {"TEST": "mm/day"}, "variable_names": {"TEST": "Test rain"},
                      "source": "SYNTHETIC", "latitude": 0, "longitude": 0,
                      "temporal_resolution": "monthly", "is_synthetic": True},
        )
        self.line = {"dates": ["2020-02-01", "2020-04-01"], "values": [1.2, 2.8]}

    def chart(self, trend=None):
        return integration.make_figure(self.series, trend, "UI title", **self.context)

    def test_discovery_uses_actual_plotting_entry_point(self):
        self.assertIs(integration._find(integration.PLOTTING_FUNCTION), make_timeseries_figure)
        self.assertTrue(integration.available_modules()["plotting"])

    def test_request_period_and_metadata_reach_figure(self):
        fig = self.chart()
        self.assertEqual(list(fig.layout.xaxis.range), ["2020-01-01T00:00:00", "2021-01-01T00:00:00"])
        self.assertEqual(fig.layout.meta["unit"], "mm/day")
        self.assertIn("UI title", fig.layout.title.text)
        self.assertIn("SYNTHETIC TEST DATA", fig.layout.title.text)
        self.assertIn("Synthetic study point", fig.layout.title.text)

    def test_analysis_dictionary_supplies_model_values_unchanged(self):
        fig = self.chart({"slope": 999, "p_value": 0.01, "trend_line": self.line})
        self.assertEqual(list(fig.data[1].y), [1.2, 2.8])
        self.assertEqual(fig.data[1].name, "Fitted trend (model)")

    def test_statistics_without_predictions_do_not_invent_a_line(self):
        self.assertEqual(len(self.chart({"slope": 2, "p_value": 0.01}).data), 1)

    def test_prediction_units_are_checked(self):
        with self.assertRaises(VisualizationError):
            self.chart({"trend_line": {**self.line, "unit": "mm/year"}})

    def test_malformed_predictions_are_rejected(self):
        for line in [{}, {"dates": [], "values": []},
                     {"dates": ["2020-01-01"], "values": [1, 2]},
                     {"dates": 4, "values": 5}]:
            with self.subTest(line=line), self.assertRaises(VisualizationError):
                self.chart({"trend_line": line})

    def test_annual_context_is_preserved(self):
        self.context["metadata"]["temporal_resolution"] = "annual"
        self.assertEqual(self.chart().layout.meta["temporal_resolution"], "annual")


if __name__ == "__main__":
    unittest.main()
