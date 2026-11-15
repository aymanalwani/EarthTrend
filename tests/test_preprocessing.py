"""Synthetic preprocessing fixtures only; these are not NASA observations."""

import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from earthtrend.preprocessing import PreprocessingError, preprocess_timeseries


class PreprocessingTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "unit": "degC", "temporal_resolution": "monthly",
            "source": "SYNTHETIC TEST DATA", "location": {"latitude": 10.0},
        }

    def process(self, values, dates=None, **kwargs):
        if dates is None:
            dates = pd.date_range("2000-01-01", periods=len(values), freq="MS")
        return preprocess_timeseries(
            pd.DataFrame({"date": dates, "value": values}), self.metadata, **kwargs
        )

    def test_missing_measurements_preserved_as_gaps(self):
        result = self.process([0, None, np.nan, pd.NA, "", "  ", 4])
        self.assertEqual(result.report.observations_before, 7)
        self.assertEqual(result.report.observations_after, 7)
        self.assertEqual(result.report.valid_observations, 2)
        self.assertEqual(result.report.missing_measurements, 5)
        self.assertEqual(result.report.invalid_measurements, 0)
        self.assertEqual(result.report.missing_positions, (1, 2, 3, 4, 5))
        self.assertEqual(result.data.value.isna().sum(), 5)
        self.assertEqual(result.analysis_data.value.tolist(), [0.0, 4.0])
        self.assertEqual(result.analysis_data.date.iloc[1], pd.Timestamp("2000-07-01"))

    def test_invalid_values_flagged_separately(self):
        invalid = ["bad", "NaN", "inf", np.inf, -np.inf, True, complex(1, 2), [2]]
        result = self.process([" 1.25 ", -2, *invalid])
        self.assertEqual(result.report.invalid_measurements, len(invalid))
        self.assertEqual(result.report.missing_measurements, 0)
        self.assertEqual(result.report.invalid_positions, tuple(range(2, 10)))
        self.assertEqual(result.analysis_data.value.tolist(), [1.25, -2.0])

    def test_duplicates_are_rejected_even_if_values_match(self):
        with self.assertRaises(PreprocessingError) as caught:
            self.process([3, 3], ["2000-01", "2000-01-01"])
        self.assertEqual(caught.exception.positions, (0, 1))
        self.assertIn("Duplicate timestamps", str(caught.exception))

    def test_unsorted_dates_keep_original_row_associations(self):
        frame = pd.DataFrame({
            "date": ["2000-03", "2000-01", "2000-02"],
            "value": [3, 1, 2], "quality": ["c", "a", "b"],
        }, index=[8, 8, 1])
        original = frame.copy(deep=True)
        result = preprocess_timeseries(frame, self.metadata)
        self.assertEqual(result.data.value.tolist(), [1, 2, 3])
        self.assertEqual(result.data.quality.tolist(), ["a", "b", "c"])
        self.assertTrue(result.data.date.is_monotonic_increasing)
        assert_frame_equal(frame, original)

    def test_empty_frame_returns_explicit_zero_counts(self):
        result = self.process([])
        self.assertTrue(result.data.empty)
        self.assertTrue(result.analysis_data.empty)
        self.assertEqual(result.report.observations_before, 0)
        self.assertEqual(result.report.observations_after, 0)
        self.assertEqual(result.report.valid_observations, 0)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result.data.date))

    def test_all_missing_has_no_analysis_observations(self):
        result = self.process([None, np.nan])
        self.assertEqual(len(result.data), 2)
        self.assertTrue(result.analysis_data.empty)

    def test_invalid_dates_report_input_positions(self):
        for value in [None, "not-a-date", "2000-02-30", "01/02/2000", 946684800, pd.NaT]:
            with self.subTest(value=value):
                with self.assertRaises(PreprocessingError) as caught:
                    self.process([1, 2], ["2000-01-01", value])
                self.assertEqual(caught.exception.positions, (1,))

    def test_explicit_date_format(self):
        result = self.process([2, 1], ["02/01/2000", "01/01/2000"], date_format="%d/%m/%Y")
        self.assertEqual(result.data.date.iloc[1], pd.Timestamp("2000-01-02"))
        self.assertEqual(result.data.value.tolist(), [1, 2])

    def test_aware_dates_normalized_to_utc(self):
        result = self.process([1, 2], ["2000-01-01T03:00:00+03:00", "2000-02-01T02:00:00+02:00"])
        self.assertEqual(str(result.data.date.dt.tz), "UTC")
        self.assertEqual(result.data.date.iloc[0], pd.Timestamp("2000-01-01T00:00:00Z"))

    def test_equivalent_instants_are_duplicates(self):
        with self.assertRaisesRegex(PreprocessingError, "Duplicate"):
            self.process([1, 2], ["2000-01-01T03:00:00+03:00", "2000-01-01T00:00:00Z"])

    def test_mixed_timezone_awareness_rejected(self):
        with self.assertRaisesRegex(PreprocessingError, "Cannot mix"):
            self.process([1, 2], ["2000-01-01", "2000-02-01T00:00:00Z"])

    def test_metadata_preserved_and_independent(self):
        result = self.process([1])
        self.assertEqual(result.metadata, self.metadata)
        result.metadata["location"]["latitude"] = 99
        self.assertEqual(self.metadata["location"]["latitude"], 10)

    def test_required_metadata(self):
        for metadata in [{}, {"unit": "degC"}, {"unit": "", "temporal_resolution": "monthly"}]:
            with self.subTest(metadata=metadata):
                with self.assertRaises(PreprocessingError):
                    preprocess_timeseries(pd.DataFrame({"date": [], "value": []}), metadata)

    def test_custom_columns(self):
        result = preprocess_timeseries(
            pd.DataFrame({"timestamp": ["2000-01"], "temperature": [2]}),
            self.metadata, date_column="timestamp", value_column="temperature",
        )
        self.assertEqual(result.analysis_data.temperature.iloc[0], 2)

    def test_schema_errors(self):
        frames = [pd.DataFrame(), pd.DataFrame([[1, 2]], columns=["date", "date"])]
        for frame in frames:
            with self.subTest(columns=frame.columns.tolist()):
                with self.assertRaises(PreprocessingError):
                    preprocess_timeseries(frame, self.metadata)
        with self.assertRaises(PreprocessingError):
            preprocess_timeseries(pd.DataFrame({"date": []}), self.metadata, value_column="date")

    def test_absent_month_is_not_fabricated(self):
        result = self.process([1, 3], ["2000-01", "2000-03"])
        self.assertEqual(len(result.data), 2)
        self.assertEqual(result.metadata["temporal_resolution"], "monthly")
        self.assertEqual(result.data.date.iloc[1], pd.Timestamp("2000-03-01"))


if __name__ == "__main__":
    unittest.main()
