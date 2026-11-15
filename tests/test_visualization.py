"""SYNTHETIC test observations only; no NASA measurements or trend claims."""

import copy
import json
import unittest
from unittest.mock import patch

from earthtrend.visualization import (
    VisualizationError, create_time_series_chart, render_time_series_chart,
)


class VisualizationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"date": "2020-03-01", "value": 3.0},
            {"date": "2020-01-01", "value": 0.0},
            {"date": "2020-02-01", "value": None},
        ]
        self.metadata = {
            "units": {"TEST": "C"}, "variable_names": {"TEST": "Test temperature"},
            "source": "SYNTHETIC fixture, not NASA data",
            "latitude": 31.95, "longitude": 35.93,
            "temporal_resolution": "monthly", "is_synthetic": True,
        }

    def chart(self, data=None, **kwargs):
        options = dict(variable="TEST", metadata=self.metadata,
                       start_date="2020-01-01", end_date="2020-12-31")
        options.update(kwargs)
        return create_time_series_chart(self.rows if data is None else data, **options)

    def test_preserves_zero_missing_dates_order_and_input(self):
        original = copy.deepcopy(self.rows)
        fig = self.chart()
        self.assertEqual(list(fig.data[0].y), [0.0, None, 3.0])
        self.assertEqual(list(fig.data[0].x), ["2020-01-01T00:00:00", "2020-02-01T00:00:00", "2020-03-01T00:00:00"])
        self.assertEqual(fig.data[0].mode, "lines+markers")
        self.assertFalse(fig.data[0].connectgaps)
        self.assertEqual(self.rows, original)
        self.assertEqual(fig.layout.meta["missing_count"], 1)

    def test_absent_month_is_not_invented(self):
        fig = self.chart([self.rows[0], self.rows[1]])
        # The absent February breaks the line (None); no value is drawn for it.
        self.assertEqual(list(fig.data[0].y), [0.0, None, 3.0])
        self.assertEqual(fig.layout.meta["valid_count"], 2)
        self.assertFalse(fig.data[0].connectgaps)

    def test_absent_year_breaks_the_annual_line(self):
        rows = [{"date": f"{year}-01-01", "value": value}
                for year, value in [(2005, 20.1), (2007, 20.4), (2008, 20.6)]]
        fig = self.chart(rows, metadata={**self.metadata, "temporal_resolution": "annual"},
                         start_date="2005-01-01", end_date="2008-12-31")
        # 2006 is absent: a null point breaks the line and no value is invented.
        self.assertEqual(list(fig.data[0].y), [20.1, None, 20.4, 20.6])
        self.assertTrue("2005" < fig.data[0].x[1] < "2007")
        self.assertEqual(fig.data[0].mode, "lines+markers")
        self.assertFalse(fig.data[0].connectgaps)
        self.assertEqual(fig.layout.meta["valid_count"], 3)
        self.assertEqual(fig.layout.meta["missing_count"], 0)

    def test_nan_becomes_json_null_not_zero(self):
        fig = self.chart([{"date": "2020-01-01", "value": float("nan")}])
        self.assertEqual(json.loads(fig.to_json())["data"][0]["y"], [None])

    def test_date_selection_includes_end_day(self):
        fig = self.chart([
            {"date": "2019-12-31", "value": 99},
            {"date": "2020-01-01T23:59:00", "value": 2},
            {"date": "2020-01-02", "value": 99},
        ], end_date="2020-01-01")
        self.assertEqual(list(fig.data[0].y), [2.0])

    def test_timezone_normalizes_to_utc(self):
        fig = self.chart([{"date": "2020-01-02T01:00:00+03:00", "value": 2}], end_date="2020-01-01")
        self.assertEqual(fig.data[0].x[0], "2020-01-01T22:00:00")

    def test_metadata_and_linear_axis_are_visible(self):
        fig = self.chart(location_name="Test site")
        text = fig.layout.title.text + fig.layout.annotations[0].text
        for expected in ["SYNTHETIC", "TEST", "Test site", "31.95", "35.93", "2020-12-31", "monthly", "not NASA"]:
            self.assertIn(expected, text)
        self.assertIn("(C)", fig.layout.yaxis.title.text)
        self.assertEqual(fig.layout.yaxis.type, "linear")
        self.assertTrue(fig.layout.yaxis.autorange)
        self.assertTrue(fig.layout.showlegend)

    def test_empty_and_all_missing_are_explicit(self):
        for rows in [[], [{"date": "2020-01-01", "value": None}]]:
            with self.subTest(rows=rows):
                fig = self.chart(rows)
                self.assertEqual(fig.layout.meta["valid_count"], 0)
                self.assertIn("No valid observations", fig.layout.annotations[-1].text)

    def test_invalid_values_dates_and_duplicates_are_rejected(self):
        bad_rows = [
            [{"date": "not a date", "value": 1}],
            [{"date": 20200101, "value": 1}],
            [{"date": "2020-01-01", "value": "bad"}],
            [{"date": "2020-01-01", "value": True}],
            [{"date": "2020-01-01", "value": float("inf")}],
            [{"date": "2020-01-01"}],
            [self.rows[0], self.rows[0]],
        ]
        for rows in bad_rows:
            with self.subTest(rows=rows), self.assertRaises(VisualizationError):
                self.chart(rows)

    def test_bad_period_and_missing_metadata(self):
        with self.assertRaises(VisualizationError):
            self.chart(start_date="2021-01-01")
        for field in ["units", "source", "latitude", "temporal_resolution"]:
            metadata = dict(self.metadata)
            metadata.pop(field)
            with self.subTest(field=field), self.assertRaises(VisualizationError):
                self.chart(metadata=metadata)

    def test_mixed_units_locations_or_sources_are_rejected(self):
        for field, value in [("unit", "K"), ("latitude", 0), ("longitude", 0), ("source", "Other")]:
            with self.subTest(field=field), self.assertRaises(VisualizationError):
                self.chart([{**self.rows[0], field: value}])

    def test_multiple_variables_are_filtered(self):
        fig = self.chart([
            {**self.rows[0], "variable": "TEST"},
            {**self.rows[0], "variable": "OTHER", "unit": "mm/day", "value": 100},
        ])
        self.assertEqual(list(fig.data[0].y), [3.0])

    def test_fitted_line_is_separate_dashed_and_clipped_to_observed_support(self):
        trend = [
            {"date": "2019-12-01", "fitted_value": -1},
            {"date": "2020-01-01", "fitted_value": 0.5},
            {"date": "2020-02-01", "fitted_value": None},
            {"date": "2020-03-01", "fitted_value": 2.5},
            {"date": "2020-04-01", "fitted_value": 4},
        ]
        original = copy.deepcopy(trend)
        fig = self.chart(fitted_trend=trend, fitted_unit="C")
        self.assertEqual(len(fig.data), 2)
        self.assertEqual(list(fig.data[1].y), [0.5, None, 2.5])
        self.assertEqual(fig.data[1].line.dash, "dash")
        self.assertNotEqual(fig.data[0].marker.color, fig.data[1].line.color)
        self.assertFalse(fig.data[1].connectgaps)
        self.assertIn("model", fig.data[1].name)
        self.assertIn("does not establish statistical significance", fig.layout.annotations[0].text)
        self.assertEqual(trend, original)

    def test_bad_trend_is_rejected(self):
        trend = [{"date": "2020-01-01", "fitted_value": 1}, {"date": "2020-03-01", "fitted_value": 2}]
        for options in [dict(fitted_unit="K"), dict(fitted_unit=None),
                        dict(fitted_unit="C", data=[self.rows[0]])]:
            with self.subTest(options=options), self.assertRaises(VisualizationError):
                self.chart(fitted_trend=trend, **options)
        with self.assertRaises(VisualizationError):
            self.chart(fitted_trend=trend[:1], fitted_unit="C")

    def test_dataframe_protocol(self):
        # The protocol can be tested without importing native pandas binaries.
        class RecordsTable:
            def to_dict(table, orient):
                self.assertEqual(orient, "records")
                return copy.deepcopy(self.rows)
        self.assertEqual(list(self.chart(RecordsTable()).data[0].y), [0, None, 3])

    def test_labels_are_escaped(self):
        fig = self.chart(location_name="<script>alert(1)</script>")
        self.assertNotIn("<script>", fig.layout.title.text)

    def test_streamlit_adapter_passes_figure(self):
        with patch("streamlit.plotly_chart") as render:
            fig = render_time_series_chart(self.rows, variable="TEST", metadata=self.metadata,
                                           start_date="2020-01-01", end_date="2020-12-31", key="test-chart")
        self.assertIs(render.call_args.args[0], fig)
        self.assertEqual(render.call_args.kwargs["width"], "stretch")
        self.assertEqual(render.call_args.kwargs["key"], "test-chart")


if __name__ == "__main__":
    unittest.main()
