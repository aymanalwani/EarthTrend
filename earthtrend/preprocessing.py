"""Provider-independent preprocessing; see docs/PREPROCESSING.md for policies."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from numbers import Number
import re
from typing import Any, Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class QualityReport:
    """Counts describe supplied rows, not inferred gaps in a calendar."""

    observations_before: int
    observations_after: int
    valid_observations: int
    missing_measurements: int
    invalid_measurements: int
    missing_positions: tuple[int, ...]
    invalid_positions: tuple[int, ...]


@dataclass(frozen=True)
class PreprocessingResult:
    data: pd.DataFrame
    analysis_data: pd.DataFrame
    metadata: dict[str, Any]
    report: QualityReport


class PreprocessingError(ValueError):
    """Input cannot be safely interpreted without a caller decision."""

    def __init__(self, message: str, positions: tuple[int, ...] = ()):
        super().__init__(message)
        self.positions = positions


def _missing(value: Any) -> bool:
    if isinstance(value, str):
        return not value.strip()
    return pd.api.types.is_scalar(value) and bool(pd.isna(value))


def _parse_date(value: Any, date_format: str | None) -> pd.Timestamp:
    if _missing(value) or isinstance(value, (Number, bool)):
        raise ValueError("Missing or numeric date")
    if isinstance(value, str):
        if date_format is not None:
            return pd.Timestamp(datetime.strptime(value, date_format))
        # Require ISO dates rather than guessing whether 01/02 means Jan 2 or Feb 1.
        if not re.fullmatch(r"\d{4}-\d{2}(?:-\d{2}(?:[T ].+)?)?", value):
            raise ValueError("Expected an ISO date or an explicit date_format")
    elif not isinstance(value, (date, datetime, pd.Timestamp, np.datetime64)):
        raise ValueError("Unsupported date type")
    result = pd.Timestamp(value)
    if pd.isna(result):
        raise ValueError("Missing date")
    return result


def preprocess_timeseries(
    frame: pd.DataFrame,
    metadata: Mapping[str, Any],
    *,
    date_column: str = "date",
    value_column: str = "value",
    date_format: str | None = None,
) -> PreprocessingResult:
    """Sort and validate one variable/location series without modifying inputs.

    Missing and invalid values become NaN in ``data``; ``analysis_data`` excludes
    those rows while retaining actual timestamps. Issue positions are zero-based
    input row positions. Invalid dates and all duplicate timestamps are rejected.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame.")
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping.")
    for key in ("unit", "temporal_resolution"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise PreprocessingError(f"metadata must include a nonempty {key!r} string.")
    if date_column == value_column:
        raise PreprocessingError("Date and measurement columns must be different.")
    if not frame.columns.is_unique:
        raise PreprocessingError("Column names must be unique.")
    if date_column not in frame or value_column not in frame:
        raise PreprocessingError("Input must contain the date and measurement columns.")

    dates = []
    bad_dates = []
    for position, value in enumerate(frame[date_column]):
        try:
            dates.append(_parse_date(value, date_format))
        except (ValueError, TypeError, OverflowError):
            bad_dates.append(position)
    if bad_dates:
        raise PreprocessingError(
            f"Invalid or missing dates at input positions {bad_dates}; correct them explicitly.",
            tuple(bad_dates),
        )
    aware = [stamp.tzinfo is not None for stamp in dates]
    if any(aware) and not all(aware):
        raise PreprocessingError("Cannot mix timezone-aware and timezone-naive dates.")
    # Convert aware instants to UTC before constructing an index with mixed offsets.
    index = (
        pd.DatetimeIndex(pd.to_datetime(dates, utc=True))
        if any(aware) else pd.DatetimeIndex(dates)
    )
    duplicate_positions = tuple(np.flatnonzero(index.duplicated(keep=False)).tolist())
    if duplicate_positions:
        raise PreprocessingError(
            f"Duplicate timestamps at input positions {list(duplicate_positions)}; "
            "resolve duplicates before preprocessing. No averaging or removal was performed.",
            duplicate_positions,
        )

    values = []
    missing_positions = []
    invalid_positions = []
    for position, value in enumerate(frame[value_column]):
        if _missing(value):
            missing_positions.append(position)
            values.append(np.nan)
            continue
        try:
            if isinstance(value, (bool, np.bool_, complex, np.complexfloating)):
                raise ValueError("Measurement must be real and not boolean")
            if not isinstance(value, (str, Number, np.number)):
                raise ValueError("Unsupported measurement type")
            numeric = float(value)
            if not np.isfinite(numeric):
                raise ValueError("Nonfinite measurement")
        except (ValueError, TypeError, OverflowError):
            invalid_positions.append(position)
            values.append(np.nan)
        else:
            values.append(numeric)

    cleaned = frame.copy(deep=True)
    cleaned[date_column] = index
    cleaned[value_column] = np.asarray(values, dtype=float)
    cleaned = cleaned.sort_values(date_column, kind="stable").reset_index(drop=True)
    analysis = cleaned.loc[cleaned[value_column].notna()].copy().reset_index(drop=True)
    report = QualityReport(
        observations_before=len(frame),
        observations_after=len(cleaned),
        valid_observations=len(analysis),
        missing_measurements=len(missing_positions),
        invalid_measurements=len(invalid_positions),
        missing_positions=tuple(missing_positions),
        invalid_positions=tuple(invalid_positions),
    )
    return PreprocessingResult(cleaned, analysis, deepcopy(dict(metadata)), report)
