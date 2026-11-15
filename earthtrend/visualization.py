"""Scientific Plotly charts; trend fitting belongs to the analysis module.

Accept a DataFrame or records with the NASA client's date/value schema.
No pandas import is needed by this presentation layer.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from html import escape
from math import isfinite, isnan
from numbers import Real
from textwrap import wrap
from typing import Any, Mapping

import plotly.graph_objects as go

# Dark theme: navy background, teal observations, orange model trend.
BACKGROUND, GRID, TEXT, MUTED = "#0b1a2c", "#2a3d55", "#e6edf3", "#9fb0c3"
OBSERVED, OBSERVED_MARKER, TREND = "#3cc4d4", "#2ec4a6", "#f59e0b"


class VisualizationError(ValueError):
    """Input cannot be plotted without ambiguity or changing its meaning."""


def _date(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time())
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise VisualizationError("Dates must be valid ISO dates or datetimes.") from exc
    else:
        raise VisualizationError("Dates must be valid ISO dates or datetimes.")
    if parsed != parsed:  # pandas NaT, when called with a DataFrame
        raise VisualizationError("Missing dates cannot be plotted.")
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise VisualizationError("Measurements must be numeric; preprocess invalid values first.")
    number = float(value)
    if isnan(number):
        return None
    if not isfinite(number):
        raise VisualizationError("Infinite measurements cannot be plotted.")
    return number


def _records(data: Any) -> list[dict]:
    # Pandas converts nullable values to None when exporting records.
    if hasattr(data, "to_dict"):
        data = data.to_dict(orient="records")
    try:
        rows = list(data)
    except TypeError as exc:
        raise VisualizationError("Supply a DataFrame or a sequence of records.") from exc
    if any(not isinstance(row, Mapping) for row in rows):
        raise VisualizationError("Each record must map column names to values.")
    return [dict(row) for row in rows]


def _single(rows: list[dict], column: str, fallback: Any = None) -> Any:
    values = [row[column] for row in rows if row.get(column) is not None]
    if fallback is not None:
        values.append(fallback)
    if not values:
        raise VisualizationError(f"Missing {column}; provide source metadata.")
    if any(value != values[0] for value in values):
        raise VisualizationError(f"Conflicting {column}; use a separate chart for each series.")
    if isinstance(values[0], str) and not values[0].strip():
        raise VisualizationError(f"{column} must not be empty.")
    return values[0]


def _series(rows: list[dict], value_column: str) -> list[tuple[datetime, float | None]]:
    points = []
    for row in rows:
        if "date" not in row or value_column not in row:
            raise VisualizationError(f"Each record requires date and {value_column}.")
        points.append((_date(row["date"]), _number(row[value_column])))
    points.sort(key=lambda point: point[0])
    if len({point[0] for point in points}) != len(points):
        raise VisualizationError("Duplicate timestamps: resolve them during preprocessing.")
    return points


def _html(text: Any, width: int = 95) -> str:
    return "<br>".join(escape(line) for line in wrap(str(text), width))


def create_time_series_chart(
    data: Any,
    *,
    variable: str,
    metadata: Mapping[str, Any],
    start_date: date | str,
    end_date: date | str,
    location_name: str | None = None,
    title: str | None = None,
    fitted_trend: Any = None,
    fitted_unit: str | None = None,
) -> go.Figure:
    """Build one chart per variable and point using original measurement units.

    ``data``: DataFrame or records containing date/value and optionally the
    NASA client's variable/unit/variable_name/source/latitude/longitude columns.
    ``metadata``: PowerResult.metadata (or the same documented fields).
    ``fitted_trend``: optional date/fitted_value records from module 5. Supply
    fitted_unit explicitly. No regression or significance calculation occurs here.
    Selection includes both calendar dates. Aware timestamps are normalized to UTC.
    """
    if not isinstance(variable, str) or not variable.strip():
        raise VisualizationError("Choose a variable identifier.")
    start = _date(start_date).replace(hour=0, minute=0, second=0, microsecond=0)
    end = _date(end_date).replace(hour=0, minute=0, second=0, microsecond=0)
    if start > end:
        raise VisualizationError("Start date must not be after end date.")
    stop = end + timedelta(days=1)
    rows = _records(data)
    if any("variable" in row for row in rows):
        if any(not row.get("variable") for row in rows):
            raise VisualizationError("Every row needs a variable when mixing variables.")
        rows = [row for row in rows if row["variable"] == variable]
    unit = _single(rows, "unit", metadata.get("units", {}).get(variable))
    name = _single(rows, "variable_name", metadata.get("variable_names", {}).get(variable))
    source = _single(rows, "source", metadata.get("source"))
    country_average = metadata.get("spatial_scope") in ("country_average", "area_average")
    lat, lon = None, None
    if country_average:
        if not metadata.get("spatial_description"):
            raise VisualizationError("Area averages require a spatial description.")
    else:
        latitude = _single(rows, "latitude", metadata.get("latitude"))
        longitude = _single(rows, "longitude", metadata.get("longitude"))
        lat, lon = _number(latitude), _number(longitude)
        if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise VisualizationError("Provide valid latitude and longitude for the study point.")
    resolution = metadata.get("temporal_resolution")
    if not isinstance(resolution, str) or not resolution.strip():
        raise VisualizationError("Provide the original temporal_resolution.")
    points = [(d, v) for d, v in _series(rows, "value") if start <= d < stop]
    valid = [(d, v) for d, v in points if v is not None]
    location = metadata["spatial_description"] if country_average else f"Point {lat:g}, {lon:g}"
    if location_name and not country_average:
        location = f"{location_name} — {location}"
    synthetic = metadata.get("is_synthetic") is True
    prefix = "SYNTHETIC TEST DATA — " if synthetic else ""
    fig = go.Figure()
    # Consecutive observations are joined; a None breaks the line wherever a
    # timestamp is absent, so no value is implied across a gap. Other cadences stay markers.
    step_days = {"monthly": 32, "annual": 367}.get(resolution)
    drawn = []
    for d, v in points:
        if step_days and drawn and (d - drawn[-1][0]).days > step_days:
            drawn.append((drawn[-1][0] + (d - drawn[-1][0]) / 2, None))
        drawn.append((d, v))
    fig.add_trace(go.Scatter(
        x=[d.isoformat() for d, _ in drawn], y=[v for _, v in drawn],
        mode="lines+markers" if step_days else "markers",
        name="Observed data" if not synthetic else "Synthetic test data",
        line={"color": OBSERVED, "width": 2.5},
        marker={"color": OBSERVED_MARKER, "size": 6}, connectgaps=False, cliponaxis=False,
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.6g} " + escape(str(unit)) + "<extra>%{fullData.name}</extra>",
    ))
    if fitted_trend is not None:
        if fitted_unit != unit:
            raise VisualizationError("fitted_unit must match the observed measurement unit.")
        trend_rows = _records(fitted_trend)
        for row in trend_rows:
            if "variable" in row and row["variable"] != variable:
                raise VisualizationError("Trend variable does not match the chart.")
        fitted = _series(trend_rows, "fitted_value")
        if len(valid) < 2:
            raise VisualizationError("A trend needs at least two valid observed timestamps.")
        fitted = [(d, v) for d, v in fitted if valid[0][0] <= d <= valid[-1][0]]
        if sum(v is not None for _, v in fitted) < 2:
            raise VisualizationError("Supply at least two fitted values within observed coverage.")
        fig.add_trace(go.Scatter(
            x=[d.isoformat() for d, _ in fitted], y=[v for _, v in fitted],
            mode="lines", name="Fitted trend (model)", connectgaps=False,
            line={"color": TREND, "width": 2.5, "dash": "dash"},
            hovertemplate="%{x|%Y-%m-%d}<br>Fitted: %{y:.6g} " + escape(str(unit)) + "<extra>%{fullData.name}</extra>",
        ))
    period = f"Selected period: {start:%Y-%m-%d} to {end:%Y-%m-%d} (inclusive)"
    access = (
        f" | {metadata.get('delivery')} | Downloaded {metadata.get('download_date')}"
        if metadata.get("download_date") else ""
    )
    notes = [f"Source: {source}{access}", period,
             f"Resolution: {resolution} | Valid observations: {len(valid)} | Missing values in supplied rows: {len(points) - len(valid)}",
             "Absent timestamps are not filled. Y-axis is linear and auto-scaled; it may not start at zero."]
    if fitted_trend is not None:
        notes.append("Fitted values are model estimates; the chart does not establish statistical significance.")
    axis = {"gridcolor": GRID, "linecolor": GRID, "zeroline": False, "showgrid": True}
    fig.update_layout(
        template="plotly_dark", height=680, paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        font={"color": TEXT},
        title={"text": "<b>" + _html(f"{prefix}{title or name} ({variable})", 70) + "</b><br><sup>" + _html(location, 90) + "</sup>",
               "x": 0.02, "font": {"size": 20}},
        xaxis={**axis, "title": "Date", "type": "date", "range": [start.isoformat(), stop.isoformat()]},
        yaxis={**axis, "title": f"{escape(str(name))} ({escape(str(unit))})", "type": "linear", "autorange": True, "exponentformat": "none"},
        showlegend=True, legend={"orientation": "h", "x": 0, "y": 1.08, "bgcolor": "rgba(0,0,0,0)"},
        margin={"l": 95, "r": 35, "t": 145, "b": 180}, hovermode="closest",
        annotations=[{"text": "<br>".join(_html(note) for note in notes),
                      "xref": "paper", "yref": "paper", "x": 0, "y": -0.24,
                      "xanchor": "left", "yanchor": "top", "showarrow": False,
                      "align": "left", "font": {"size": 11, "color": MUTED}}],
        meta={"variable": variable, "unit": unit, "source": source,
              "latitude": lat, "longitude": lon, "temporal_resolution": resolution,
              "is_synthetic": synthetic, "valid_count": len(valid),
              "missing_count": len(points) - len(valid)},
    )
    if not valid:
        fig.add_annotation(text="No valid observations in the selected period",
                           x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    return fig


def render_time_series_chart(data: Any, *, key: str | None = None, **kwargs: Any) -> go.Figure:
    """Streamlit integration for module 7. Validation errors are left to the UI."""
    import streamlit as st

    figure = create_time_series_chart(data, **kwargs)
    st.plotly_chart(figure, width="stretch", theme=None, key=key,
                    config={"displaylogo": False, "scrollZoom": False,
                            "toImageButtonOptions": {"format": "svg", "filename": "earthtrend"}})
    return figure
