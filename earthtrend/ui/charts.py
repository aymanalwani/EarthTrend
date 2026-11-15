"""Basic time-series chart used until the team plotting module is merged.

It draws only what it is given: observed values (gaps stay gaps) and, when
the analysis module supplies one, the fitted trend line. It computes nothing.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

OBSERVED_COLOR = "#1f6f8b"
TREND_COLOR = "#c8553d"


def basic_timeseries_figure(
    series: pd.DataFrame,
    *,
    variable_name: str,
    unit: str,
    title: str,
    source: str,
    trend_line: dict | None = None,
) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=series["date"],
            y=series["value"],
            mode="lines+markers",
            name="Observed",
            connectgaps=False,  # never draw a line across missing observations
            line={"color": OBSERVED_COLOR, "width": 1.5},
            marker={"size": 4},
            hovertemplate="%{x|%b %Y}: %{y} " + unit + "<extra></extra>",
        )
    )
    if trend_line and trend_line.get("dates") is not None and trend_line.get("values") is not None:
        figure.add_trace(
            go.Scatter(
                x=list(trend_line["dates"]),
                y=list(trend_line["values"]),
                mode="lines",
                name="Fitted trend",
                line={"color": TREND_COLOR, "width": 2, "dash": "dash"},
                hoverinfo="skip",
            )
        )
    figure.update_layout(
        title={"text": title, "font": {"size": 16}},
        xaxis_title="Date",
        yaxis_title=f"{variable_name} ({unit})" if unit else variable_name,
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.0, "x": 0},
        margin={"l": 60, "r": 20, "t": 80, "b": 70},
        hovermode="x unified",
        annotations=[
            {
                "text": f"Source: {source}",
                "xref": "paper", "yref": "paper", "x": 0, "y": -0.2,
                "showarrow": False, "font": {"size": 11},
            }
        ],
    )
    return figure
