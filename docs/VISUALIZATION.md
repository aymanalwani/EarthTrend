# Visualization

`earthtrend.visualization` produces one interactive Plotly chart per variable
and study point. It accepts the existing NASA client's `PowerResult.data` and
`PowerResult.metadata`. No new dependencies are needed.

## Integration for the Streamlit developer (task 7)

The visualization branch is based on `feature/streamlit-ui` (commit `74d5c32`).
Its `earthtrend.plotting.make_timeseries_figure` matches the UI's discovery
constant. `integration.make_figure` now forwards chart context, and
`ui/components.py` supplies the request dates, selected variable, location and
source metadata. The selected period is never guessed from the title or from
the dates returned by the API. `app.py` and the statistics/preprocessing
contracts are unchanged.

The UI path is already connected on this branch. For another Streamlit page,
use the following convenience wrapper:

Call this after retrieval and preprocessing; keep the original metadata and
missing values. This example does not fetch data or fabricate analysis results.

```python
from earthtrend.visualization import render_time_series_chart, VisualizationError

# result = get_monthly_series(...) from the existing data client
# cleaned_data = preprocessing output, retaining the date/value schema
try:
    fig = render_time_series_chart(
        cleaned_data,
        variable="T2M",
        metadata=result.metadata,
        start_date=start_date,  # actual selected date, not inferred coverage
        end_date=end_date,
        location_name="Amman",  # optional label; coordinates always appear too
        key="temperature-series",
    )
except VisualizationError as exc:
    st.error(str(exc))
```

Loop over selected variables, with a distinct key for each chart. Different
units get separate charts, never misleading shared or dual Y-axes.
The shared `app.py` is deliberately left for the teammate implementing task 7.

## Contract for the statistics developer (task 5)

For the established UI contract, return this shape from `analyze_trend`:

```python
{
    # other actual statistics ...
    "trend_line": {"dates": prediction_dates, "values": predicted_values,
                   "unit": original_measurement_unit},
}
```

`unit` is optional for compatibility; omitted units mean the original
measurement unit, never the slope's rate unit. Values and dates must have the
same length. When no predictions are available, omit `trend_line` or set it
to `None`. No line is manufactured from a reported slope or p-value.

Pass model predictions at explicit dates, not slope/intercept coefficients:

```python
fig = render_time_series_chart(
    cleaned_data,
    variable=selected_variable,
    metadata=result.metadata,
    start_date=start_date,
    end_date=end_date,
    fitted_trend=trend_predictions,  # DataFrame: date, fitted_value
    fitted_unit=result.metadata["units"][selected_variable],
    key="analysis-series",
)
```

`trend_predictions` must come from the actual analysis. Omit both trend
arguments until those predictions exist. Visualization does not fit another
model or infer significance. Optional `variable` columns in predictions must
match the selected variable. Predictions are clipped to the selected valid
observations' first/last timestamps: no extrapolation is displayed. At least
two valid observations and two fitted values in that range are required.

## Data contract and scientific decisions

- DataFrame or list of records, with `date` and numeric `value` columns.
- If a `variable` column exists, the requested variable is selected first.
- `unit`, `variable_name`, `source`, `latitude`, `longitude` can come from
  the data columns or from the corresponding NASA client metadata fields
  (`units[variable]`, `variable_names[variable]`, `source`, `latitude`, `longitude`).
  Conflicting metadata is rejected, even if conflicting rows fall outside the
  selected period. Supply `temporal_resolution` in metadata.
- Only a single coordinate is supported per chart. A location name is a label
  for that point, not a claim of a regional spatial average.
- Original units and values are preserved. Actual zero stays zero. `None` and
  numeric NaN remain missing; invalid text, booleans and infinity raise errors.
  Convert provider-specific missing sentinels in the data/preprocessing layer.
- Dates are sorted on a copy. Duplicate timestamps and invalid dates raise
  errors instead of being silently removed or averaged. Use ISO date strings
  or date/datetime objects. Aware timestamps are converted to UTC.
- Both selected calendar dates are included. Full selected period appears on
  the X-axis even when data coverage is shorter. Monthly dates retain the
  client's first-day-of-month convention; values are not daily measurements.
- Monthly and annual measurements are drawn as a teal line with markers on a
  dark navy background. The line joins consecutive observations only.
  Wherever a timestamp is absent (a gap longer than one month or one year),
  a null point breaks the line, so no value is implied across the gap. Other
  cadences are drawn as markers only. Missing counts describe supplied rows
  only; absent rows are not counted or manufactured. No interpolation is
  performed.
- Fitted values are an orange dashed line, distinct from the teal data line.
  `connectgaps=False` also preserves explicit gaps in model predictions.
- Y-axis is linear and auto-scaled to all visible traces, with a visible note
  that it may not start at zero. No log scale, manual truncation or smoothing.
- Empty/all-missing selections show an explicit message, without a fake trend.
- Set `metadata["is_synthetic"] = True` for synthetic data; it is visibly labeled
  in the title and legend. Provenance is the caller's responsibility.
- The source, location, selected period, units, counts and temporal resolution
  are embedded in the figure and remain in HTML/SVG exports.

## Standalone figure / export

`create_time_series_chart(...)` has the same chart arguments and returns a
`plotly.graph_objects.Figure`, without importing Streamlit or Pandas.

```python
fig = create_time_series_chart(...)
fig.write_html("chart.html", include_plotlyjs=True)
plotly_json = fig.to_json()  # usable by Plotly.js if needed later
```

## Verification

```bash
python -m pytest -q tests/test_visualization.py tests/test_plotting_integration.py
```

Tests use explicitly synthetic inputs and cover gaps, zeros, sorting, input
immutability, selections, UTC dates, conflicting units/locations, empty data,
invalid inputs, trend units/support, provenance and the Streamlit adapter.
Contract tests also exercise the actual integration module's discovery and
the UI-style trend dictionary. Two tests in `tests/test_ui_pipeline.py` cover
the offline NASA fixture through monthly/annual pipeline and UI rendering.
The DataFrame protocol test is not a real Pandas integration test; the
end-to-end tests in `tests/test_ui_pipeline.py` and `tests/test_giovanni.py`
use real DataFrames.

API references: [Plotly line gaps](https://plotly.com/python/line-charts/),
[Streamlit Plotly integration](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart).
