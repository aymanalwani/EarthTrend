# Time-series preprocessing

`earthtrend/preprocessing.py` cleans one time series before analysis. It does
not retrieve data, aggregate observations, calculate trends, or change the
interface.

## Contract

```python
from earthtrend.preprocessing import preprocess_timeseries

result = preprocess_timeseries(
    frame,  # pandas DataFrame with date and value columns
    metadata,  # mapping containing unit and temporal_resolution
)
chart_data = result.data
analysis_data = result.analysis_data
quality = result.report
source_metadata = result.metadata
```

`date_column` and `value_column` support other column names. Each call must
contain one variable/location series. The caller is responsible for separating
multiple series and ensuring metadata describes the supplied observations.

## Processing decisions

| Concern | Policy |
|---|---|
| Metadata | Require nonempty `unit` and `temporal_resolution` strings. Deep-copy all metadata, including provider-specific fields, without changing units or resolution. |
| Input ownership | Copy the DataFrame; never modify caller inputs. Preserve extra columns and their row associations. Output indexes are reset. |
| Dates | Accept date/datetime objects and ISO `YYYY-MM`, `YYYY-MM-DD`, or ISO datetime strings. A monthly label is represented by the first day of that month; this is an indexing convention, not a claim of daily sampling. |
| Other date formats | Require an explicit Python `strptime` format via `date_format`, e.g. `%d/%m/%Y`. Never guess ambiguous day/month ordering. Numeric epoch dates are rejected because their units are unspecified. |
| Invalid/missing dates | Raise `PreprocessingError` with zero-based input row positions. Do not silently discard undated observations. |
| Timezones | Preserve naive timestamps as naive. Normalize aware timestamps to UTC without changing their instants. Reject mixed aware/naive input; the caller must establish its timezone convention first. Original source timezone metadata is retained. |
| Duplicates | Check parsed timestamps, including equivalent UTC instants. Reject all duplicate groups, even identical measurements. Error positions identify all affected input rows. No implicit averaging, selection, or deduplication. |
| Ordering | Stable chronological sort; retain date/value associations. |
| Missing measurements | `None`, pandas/NumPy missing scalars, and blank strings become `NaN` and are counted as missing. Zero remains a valid observation. |
| Numeric measurements | Accept real numeric values and finite numeric strings. Normalize the measurement column to floating point; ordinary float64 precision limits apply. |
| Invalid measurements | Nonnumeric values, boolean/complex values, collections, and infinities become `NaN`; report separately from missing input. Literal strings `NaN`/`inf` are invalid, rather than silently treated as ordinary measurements. |
| Provider fill values | The NASA client must decode its documented sentinel values before calling this function. This generic module cannot infer whether a finite number such as `-999` is missing or a real measurement. |
| Quality flags and physical ranges | Retain extra quality columns. Provider-specific quality masks and valid ranges must be applied explicitly upstream; this module does not invent scientific thresholds. |
| Gaps | Retain missing rows in `data`; never interpolate or fill with zero. Do not create timestamps for absent rows, infer a calendar, resample, aggregate, or convert units. |
| Analysis view | `analysis_data` contains only rows with finite measurements, retaining actual timestamps. Statistical code must use elapsed time rather than row number and evaluate gaps, sample size, seasonality, and dependence. |
| Empty input | Return empty typed date/value columns and zero counts when the schema and metadata are valid. All-missing/all-invalid measurements similarly yield an empty analysis view. No claim of statistical suitability is made. |

The quality report includes `observations_before`, `observations_after` (rows
retained for plotting), `valid_observations` (rows in the analysis view),
`missing_measurements`, and `invalid_measurements`. `missing_positions` and
`invalid_positions` refer to original zero-based row positions, independently
of the input index and the output sort order. The unchanged caller input can
therefore be used to inspect the original offending values. Counts do not
include dates absent from the input.

Validation of schema, metadata, timestamps, and duplicates fails explicitly;
measurement problems are retained as visible gaps with a quality report. A
successful return establishes a sorted, unique timestamp series with finite
analysis measurements, not sufficient evidence for any statistical test.

## Tests

All fixtures are synthetic and labeled as such. With the project's pandas and
NumPy dependencies installed:

```powershell
python -m unittest discover -s tests -p test_preprocessing.py -v
```

Coverage includes missing and invalid values, duplicate timestamps, timezone
handling, sorting, nonmutation, metadata preservation, custom columns, empty
input, and calendar gaps. No NASA client or network access is used.
