"""Runs one analysis: retrieve -> preprocess -> analyse.

This module contains no Streamlit code so that it can be tested on its own.
Retrieval uses the NASA POWER client. Preprocessing and trend analysis are
delegated to the team modules through ``earthtrend.integration``; when they
are absent the corresponding fields are ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from earthtrend import integration
from earthtrend.data import power_client
from earthtrend.data import giovanni

DEFAULT_ALPHA = 0.05
RESOLUTIONS = {
    "monthly": "Monthly means",
    "annual": "Annual means (complete years only)",
}


@dataclass(frozen=True)
class AnalysisRequest:
    variables: tuple[str, ...]
    latitude: float | None
    longitude: float | None
    start_year: int
    end_year: int
    resolution: str = "monthly"
    location_label: str = ""
    source: str = "power"
    region: str = ""  # saved Giovanni region key; empty for POWER point queries


@dataclass
class VariableOutput:
    variable: str
    name: str
    unit: str
    series: pd.DataFrame
    n_total: int
    n_valid: int
    n_missing: int
    first_valid: pd.Timestamp | None
    last_valid: pd.Timestamp | None
    preprocessing_applied: bool = False
    preprocessing_report: dict | None = None
    trend: dict | None = None
    trend_error: str | None = None


@dataclass
class AnalysisOutput:
    request: AnalysisRequest
    metadata: dict[str, Any]
    variables: list[VariableOutput] = field(default_factory=list)
    alpha: float = DEFAULT_ALPHA


def run_analysis(
    request: AnalysisRequest,
    fetch: Callable[..., power_client.PowerResult] = power_client.get_monthly_series,
    alpha: float = DEFAULT_ALPHA,
) -> AnalysisOutput:
    """Retrieve the data for a request and run the available analysis steps.

    Raises ``power_client.PowerAPIError`` (or a subclass) when the data cannot
    be retrieved, and ``ValueError`` for an unknown resolution.
    """
    if request.resolution not in RESOLUTIONS:
        raise ValueError(f"Unknown temporal resolution: {request.resolution!r}")

    if request.source == "giovanni_saved":
        if request.latitude is not None or request.longitude is not None:
            raise ValueError("Area-average data must not be assigned point coordinates.")
        result = giovanni.load_saved(request.variables, request.region,
                                     request.start_year, request.end_year)
    elif request.source == "power":
        result = fetch(list(request.variables), request.latitude, request.longitude,
                       request.start_year, request.end_year)
    else:
        raise ValueError(f"Unknown data source: {request.source!r}")
    table = result.data if request.resolution == "monthly" else _annual_as_series(result.annual)

    output = AnalysisOutput(request=request, metadata=dict(result.metadata), alpha=alpha)
    output.metadata["temporal_resolution"] = request.resolution

    for code in request.variables:
        series = table[table["variable"] == code].reset_index(drop=True)
        series_metadata = dict(output.metadata)
        series_metadata["unit"] = (result.metadata.get("units") or {}).get(code) or "unknown"
        applied, report = False, None
        if len(series):
            series, report, applied = integration.preprocess(series, series_metadata)

        valid = series["value"].notna()
        item = VariableOutput(
            variable=code,
            name=(result.metadata.get("variable_names") or {}).get(code) or code,
            unit=(result.metadata.get("units") or {}).get(code) or "",
            series=series,
            n_total=int(len(series)),
            n_valid=int(valid.sum()),
            n_missing=int((~valid).sum()),
            first_valid=series.loc[valid, "date"].min() if valid.any() else None,
            last_valid=series.loc[valid, "date"].max() if valid.any() else None,
            preprocessing_applied=applied,
            preprocessing_report=report,
        )
        if item.n_valid:
            try:
                item.trend = integration.analyze(series, alpha, series_metadata)
            except integration.IntegrationError:
                raise
            except Exception as exc:  # the analysis refused this series
                item.trend_error = f"{type(exc).__name__}: {exc}"
        output.variables.append(item)
    return output


def _annual_as_series(annual: pd.DataFrame) -> pd.DataFrame:
    """Give an annual table the standard layout (date = 1 January)."""
    series = annual.copy()
    series["date"] = pd.to_datetime(
        series["year"].astype(int).astype(str) + "-01-01", format="%Y-%m-%d"
    ) if len(series) else pd.Series([], dtype="datetime64[ns]")
    return series[power_client.TIMESERIES_COLUMNS]
