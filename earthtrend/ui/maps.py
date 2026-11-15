"""Map of the analysed study point (step 8). Optional feature.

The map shows only WHERE the analysis was made: one marker at the coordinates
that NASA POWER reported for the request. It displays no measurements, no
colours derived from data and no region outline, because the application has
a single-point time series and no spatial dataset. Nothing is computed here.

Plotly is used (already a project dependency) with OpenStreetMap tiles, so no
extra package or API key is needed. The tiles are loaded from the internet by
the browser; without a connection the marker is drawn on an empty background.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import plotly.graph_objects as go

MARKER_COLOR = "#D55E00"
DEFAULT_ZOOM = 5
POINT_NOTE = (
    "The marker is the single analysed point. The data describe the reanalysis "
    "grid cell containing it, not the surrounding country or region."
)


class MapError(ValueError):
    """The location cannot be shown on a map."""


def study_point_map(
    latitude: float,
    longitude: float,
    *,
    location_label: str = "",
    variable_names: Sequence[str] = (),
    zoom: float = DEFAULT_ZOOM,
) -> go.Figure:
    """Return a map with one marker at the analysed coordinates."""
    for name, value, limit in (("latitude", latitude, 90), ("longitude", longitude, 180)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MapError(f"{name} must be a number.")
        if not math.isfinite(value) or abs(value) > limit:
            raise MapError(f"{name} must be between -{limit} and {limit}.")

    coordinates = f"Latitude {latitude:g}°, longitude {longitude:g}°"
    variables = ", ".join(variable_names)
    hover_lines = [line for line in (
        location_label,
        coordinates,
        f"Analysed: {variables}" if variables else "",
        "Single point, not a region",
    ) if line]

    figure = go.Figure(
        go.Scattermap(
            lat=[latitude],
            lon=[longitude],
            mode="markers",
            marker={"size": 16, "color": MARKER_COLOR},
            name="Analysed point",
            hovertemplate="<br>".join(hover_lines) + "<extra></extra>",
        )
    )
    title = "Study location"
    if variables:
        title += f" — {variables}"
    figure.update_layout(
        title={"text": f"{title}<br><sup>{coordinates}</sup>", "x": 0.01},
        map={
            "style": "open-street-map",
            "center": {"lat": latitude, "lon": longitude},
            "zoom": zoom,
        },
        height=420,
        margin={"l": 0, "r": 0, "t": 60, "b": 0},
        showlegend=False,
        meta={
            "latitude": latitude,
            "longitude": longitude,
            "variables": list(variable_names),
            "shows_measurements": False,
        },
    )
    return figure
