"""Connection points to the modules written by other team members.

The interface (step 7) was built before the preprocessing (step 4), analysis
(step 5) and plotting (step 6) modules were merged. This file is the single
place where the application looks for them. If a module is not present, the
function here returns ``None`` and the interface says the feature is not
available. It never substitutes invented results.

Expected interface
------------------
If a teammate's function has a different name or signature, change it HERE
(the three ``*_FUNCTION`` constants or the call below), not in the UI.

``earthtrend/preprocessing.py``
    ``preprocess_timeseries(series, metadata) -> PreprocessingResult``
    ``series`` is one variable in the standard layout (columns ``date``,
    ``value``, ``unit``, ``variable``, ...; missing values are ``NaN``).
    ``report`` is a dict (e.g. counts before/after); it is shown as-is.
    Returning only a DataFrame is also accepted.

``earthtrend/analysis.py``
    ``analyze_timeseries(series, metadata, alpha=0.05) -> AnalysisResult``
    The adapter flattens regression fields for the UI and retains the full
    result under ``analysis_details``. Metadata must include unit and resolution.
    Keys used by the interface; all are optional and shown as "not reported"
    when absent:
      ``direction``    "increasing" | "decreasing" | "no trend"
      ``slope``        float, the trend rate
      ``slope_unit``   str, e.g. "C per decade"
      ``p_value``      float
      ``significant``  bool, decision at ``alpha``
      ``alpha``        float
      ``ci_low``, ``ci_high``, ``ci_level``   confidence interval of the slope
      ``n_valid``      int, observations actually used
      ``method``       str, e.g. "Mann-Kendall + Sen's slope"
      ``notes``        list[str], assumptions or warnings
      ``trend_line``   {"dates": [...], "values": [...]} fitted line to draw

``earthtrend/plotting.py``
    ``make_timeseries_figure(series, trend=None, title=None, *, variable,
    metadata, start_date, end_date, location_name=None)`` returning a Plotly
    figure. Chart context comes from the actual UI request, never title parsing
    or an assumption that data coverage equals the selected period.
    ``trend_line.values`` must use the original variable unit; optional
    ``trend_line.unit`` is validated against it.
"""

from __future__ import annotations

import dataclasses
import importlib
import importlib.util
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    import pandas as pd

PREPROCESSING_FUNCTION = ("earthtrend.preprocessing", "preprocess_timeseries")
ANALYSIS_FUNCTION = ("earthtrend.analysis", "analyze_timeseries")
PLOTTING_FUNCTION = ("earthtrend.plotting", "make_timeseries_figure")


class IntegrationError(Exception):
    """A team module exists but does not match the expected interface."""


def _find(target: tuple[str, str]) -> Callable[..., Any] | None:
    """Return the function, or None when its module has not been added yet."""
    module_name, function_name = target
    if importlib.util.find_spec(module_name) is None:
        return None
    module = importlib.import_module(module_name)
    function = getattr(module, function_name, None)
    if not callable(function):
        raise IntegrationError(
            f"{module_name} exists but has no function '{function_name}'. "
            "Update earthtrend/integration.py to match the module."
        )
    return function


def available_modules() -> dict[str, bool]:
    """Which optional modules are present (for display in the interface)."""
    status = {}
    for label, target in (
        ("preprocessing", PREPROCESSING_FUNCTION),
        ("analysis", ANALYSIS_FUNCTION),
        ("plotting", PLOTTING_FUNCTION),
    ):
        status[label] = importlib.util.find_spec(target[0]) is not None
    return status


def preprocess(series: pd.DataFrame, metadata: dict | None = None) -> tuple[pd.DataFrame, dict | None, bool]:
    """Run the team's preprocessing if present.

    Returns (series, report, was_applied). Without the module the series is
    returned unchanged; missing values stay ``NaN``.
    """
    import pandas as pd

    function = _find(PREPROCESSING_FUNCTION)
    if function is None:
        return series, None, False
    result = function(series, metadata)
    if hasattr(result, "analysis_data") and hasattr(result, "report"):
        return result.data, _as_dict(result.report), True
    if isinstance(result, tuple) and len(result) == 2:
        clean, report = result
    else:
        clean, report = result, None
    if not isinstance(clean, pd.DataFrame) or not {"date", "value"} <= set(clean.columns):
        raise IntegrationError(
            "The preprocessing function must return a DataFrame with 'date' and 'value'."
        )
    return clean, _as_dict(report) if report is not None else None, True


def analyze(series: pd.DataFrame, alpha: float, metadata: dict | None = None) -> dict | None:
    """Run the team's trend analysis if present; None when it is not."""
    function = _find(ANALYSIS_FUNCTION)
    if function is None:
        return None
    result = function(series, metadata, alpha=alpha)
    if isinstance(result, Mapping):
        return dict(result)
    regression = result.regression
    ci = regression.confidence_interval if regression else None
    trend_line = _linear_trend_line(series, result, metadata)
    return {
        **({"trend_line": trend_line} if trend_line else {}),
        "direction": regression.direction if regression else None,
        "slope": regression.slope if regression else None,
        "slope_unit": regression.slope_unit if regression else None,
        "p_value": regression.p_value if regression else None,
        "significant": regression.significant if regression else None,
        "alpha": result.alpha, "n_valid": result.n,
        # Number of annual values the significance test used (monthly data are tested on annual means).
        "test_years": result.diagnostics.get("annual_anomaly_years", result.n)
        if (metadata or {}).get("temporal_resolution") == "monthly" else result.n,
        "ci_low": ci[0] if ci else None, "ci_high": ci[1] if ci else None,
        "ci_level": 1 - result.alpha if ci else None,
        "method": regression.method if regression else "not assessed",
        "notes": list(result.warnings),
        "analysis_details": result.to_dict(),
    }


def _linear_trend_line(series, result, metadata) -> dict | None:
    """Fitted long-term trend at the analysed dates, in the observation unit.

    For the straight-line model (annual data) these are the model's own
    predictions, intercept + slope * years since the first analysed date. For
    the seasonal model the average seasonal effect is added instead of each
    month's effect, so the line is the trend with the seasonal cycle averaged
    out, not a fit to individual months.
    """
    import pandas as pd

    regression = result.regression
    if regression is None or result.origin is None or "OLS" not in regression.method:
        return None
    offset = 0.0
    if result.diagnostics.get("seasonal_period") == 12:
        offset = result.diagnostics.get("seasonal_mean_offset")
        if offset is None:
            return None
    dates = pd.DatetimeIndex(series.loc[series["value"].notna(), "date"])
    if len(dates) < 2:
        return None
    years = (dates - pd.Timestamp(result.origin)).total_seconds() / (86400 * 365.25)
    values = regression.intercept + offset + regression.slope * years
    return {
        "dates": [stamp.isoformat() for stamp in dates],
        "values": [float(value) for value in values],
        "unit": (metadata or {}).get("unit"),
    }


def make_figure(series: pd.DataFrame, trend: dict | None, title: str, **chart_context):
    """Build the team's Plotly figure if present; None when it is not."""
    function = _find(PLOTTING_FUNCTION)
    if function is None:
        return None
    return function(series, trend=trend, title=title, **chart_context)


def _as_dict(result: Any) -> dict:
    if isinstance(result, Mapping):
        return dict(result)
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        return dataclasses.asdict(result)
    if hasattr(result, "_asdict"):
        return dict(result._asdict())
    raise IntegrationError(
        f"Expected a dict or dataclass from the team module, got {type(result).__name__}."
    )
