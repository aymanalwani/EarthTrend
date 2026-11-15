"""Step 6 entry point discovered by earthtrend.integration (Streamlit UI)."""

from collections.abc import Mapping

from earthtrend.visualization import VisualizationError, create_time_series_chart


def make_timeseries_figure(
    series, trend=None, title=None, *, variable, metadata,
    start_date, end_date, location_name=None,
):
    """Adapt the UI's analysis dictionary to an explicitly dated model trace.

    trend['trend_line'] = {'dates': [...], 'values': [...], 'unit': optional}
    Values must be predictions in the original variable's units, not a slope
    or a standardized/anomaly series. No coefficients are interpreted here.
    """
    if trend is not None and not isinstance(trend, Mapping):
        raise VisualizationError("Trend analysis must be a dictionary.")
    line = (trend or {}).get("trend_line")
    fitted = None
    fitted_unit = None
    if line is not None:
        if not isinstance(line, Mapping) or line.get("dates") is None or line.get("values") is None:
            raise VisualizationError("trend_line requires dates and values arrays.")
        try:
            dates, values = list(line["dates"]), list(line["values"])
        except TypeError as exc:
            raise VisualizationError("trend_line requires dates and values arrays.") from exc
        if len(dates) != len(values):
            raise VisualizationError("Trend dates and values must have equal lengths.")
        fitted = [{"date": d, "fitted_value": v} for d, v in zip(dates, values)]
        fitted_unit = line.get("unit", metadata.get("units", {}).get(variable))
    return create_time_series_chart(
        series, variable=variable, metadata=metadata,
        start_date=start_date, end_date=end_date, location_name=location_name,
        title=title, fitted_trend=fitted, fitted_unit=fitted_unit,
    )
