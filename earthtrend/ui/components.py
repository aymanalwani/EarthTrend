"""Reusable Streamlit sections of the EarthTrend interface."""

from __future__ import annotations

from datetime import date

import streamlit as st

from earthtrend import integration
from earthtrend.data import giovanni, power_client
from earthtrend.pipeline import (
    RESOLUTIONS,
    AnalysisOutput,
    AnalysisRequest,
    VariableOutput,
)
from earthtrend.analysis import MIN_ANNUAL_INFERENCE as MIN_ANNUAL_YEARS
from earthtrend.ui import charts, maps, text

# First year of the POWER monthly API (see DATA_SOURCES.md). The API remains
# the authority: a request outside its coverage returns its own error message.
FIRST_YEAR = 1981

POWER_SOURCE = "NASA POWER (live point query, 1981–present)"
SAVED_SOURCE = "NASA Giovanni (saved area averages, 2005–2025)"
CUSTOM_LOCATION = "Custom coordinates"
# Approximate city-centre coordinates, for convenience only.
PRESET_LOCATIONS = {
    "Cairo, Egypt": (30.04, 31.24),
    "Nairobi, Kenya": (-1.29, 36.82),
    "New Delhi, India": (28.61, 77.21),
    "São Paulo, Brazil": (-23.55, -46.63),
    "Reykjavik, Iceland": (64.15, -21.94),
}


def render_header() -> None:
    st.title("EarthTrend")
    st.markdown(
        "**Earth System Trend Detective.** Choose a variable, a location and a "
        "period to retrieve NASA Earth science data, view the time series and "
        "see whether the change over time is statistically significant."
    )


def render_configuration() -> tuple[AnalysisRequest | None, bool]:
    """Sidebar inputs. Returns (request or None if invalid, analyze clicked)."""
    with st.sidebar:
        source = st.selectbox("Data source", [POWER_SOURCE, SAVED_SOURCE])
    if source == SAVED_SOURCE:
        return render_saved_configuration()
    with st.sidebar:
        st.header("Analysis configuration")

        variables = st.multiselect(
            "Variable",
            options=list(power_client.SUPPORTED_PARAMETERS),
            default=["T2M"],
            format_func=lambda code: power_client.SUPPORTED_PARAMETERS[code],
            help="Select one or more variables. Each is analysed separately.",
        )

        location = st.selectbox(
            "Location", options=[*PRESET_LOCATIONS, CUSTOM_LOCATION]
        )
        if location == CUSTOM_LOCATION:
            latitude = st.number_input(
                "Latitude (°N)", min_value=-90.0, max_value=90.0, value=0.0,
                step=0.01, format="%.4f",
            )
            longitude = st.number_input(
                "Longitude (°E)", min_value=-180.0, max_value=180.0, value=0.0,
                step=0.01, format="%.4f",
            )
            label = f"{latitude:.4f}°, {longitude:.4f}°"
        else:
            latitude, longitude = PRESET_LOCATIONS[location]
            label = location
            st.caption(f"Latitude {latitude}°, longitude {longitude}°")
        st.caption(
            "Data are for the single grid cell containing this point, not a region."
        )

        this_year = date.today().year
        left, right = st.columns(2)
        start_year = left.number_input(
            "Start year", min_value=FIRST_YEAR, max_value=this_year,
            value=1991, step=1,
        )
        end_year = right.number_input(
            "End year", min_value=FIRST_YEAR, max_value=this_year,
            value=this_year - 1, step=1,
        )

        resolution = st.radio(
            "Temporal resolution",
            options=list(RESOLUTIONS),
            index=1,
            format_func=lambda key: RESOLUTIONS[key],
        )
        st.caption(
            f"Significance is tested for at least {MIN_ANNUAL_YEARS} years (monthly data are "
            "tested on their annual means); with fewer than 30 years results are indicative. "
            "Shorter selections show the data and descriptive values only."
        )

        problems = []
        if not variables:
            problems.append("Select at least one variable.")
        if start_year > end_year:
            problems.append("The start year must not be after the end year.")
        for problem in problems:
            st.error(problem)

        clicked = st.button(
            "Analyze", type="primary", use_container_width=True,
            disabled=bool(problems),
        )

    if problems:
        return None, False
    request = AnalysisRequest(
        variables=tuple(variables),
        latitude=float(latitude),
        longitude=float(longitude),
        start_year=int(start_year),
        end_year=int(end_year),
        resolution=resolution,
        location_label=label,
    )
    return request, clicked


def render_saved_configuration() -> tuple[AnalysisRequest | None, bool]:
    with st.sidebar:
        st.header("Analysis configuration")
        region = st.selectbox("Region", options=list(giovanni.REGIONS),
                              format_func=lambda key: giovanni.REGIONS[key])
        options = giovanni.variables_for(region)
        variables = st.multiselect(
            "Variable", options=options, default=options[:1], key=f"saved_variables_{region}",
            format_func=lambda code: f"{giovanni.DATASETS[code]['name']} ({giovanni.DATASETS[code]['unit']})",
            help="Only variables downloaded for this region are offered. Each is analysed separately.",
        )
        st.info(f"Saved NASA Giovanni files, downloaded {giovanni.DOWNLOAD_DATE}. Not live data.")
        left, right = st.columns(2)
        start = left.number_input("Start year", min_value=giovanni.FIRST_YEAR, max_value=giovanni.LAST_YEAR,
                                  value=giovanni.FIRST_YEAR, step=1, key="saved_start")
        end = right.number_input("End year", min_value=giovanni.FIRST_YEAR, max_value=giovanni.LAST_YEAR,
                                 value=giovanni.LAST_YEAR, step=1, key="saved_end")
        resolution = st.radio("Temporal resolution", options=list(RESOLUTIONS), index=0,
                              format_func=lambda key: RESOLUTIONS[key], key="saved_resolution")
        st.caption(
            "Annual means are computed by EarthTrend from the monthly files (days-weighted, "
            f"complete years only). Significance is tested for at least {MIN_ANNUAL_YEARS} years "
            "(monthly data are tested on their annual means); with fewer than 30 years results "
            "are indicative."
        )
        problems = []
        if not variables:
            problems.append("Select at least one variable.")
        if start > end:
            problems.append("The start year must not be after the end year.")
        for problem in problems:
            st.error(problem)
        clicked = st.button("Analyze", type="primary", use_container_width=True, disabled=bool(problems))
    if problems:
        return None, False
    return AnalysisRequest(tuple(variables), None, None, int(start), int(end), resolution,
                           giovanni.REGIONS[region], "giovanni_saved", region), clicked


def render_error(error: Exception) -> None:
    """Explain a failed retrieval in plain language."""
    if isinstance(error, power_client.PowerTimeoutError):
        st.error("NASA POWER took too long to respond. Please try again in a moment.")
    elif isinstance(error, power_client.PowerConnectionError):
        st.error(
            "NASA POWER could not be reached. Check the internet connection and try again."
        )
    elif isinstance(error, power_client.PowerRequestError):
        if error.status_code >= 500:
            st.error(
                f"NASA POWER is temporarily unavailable (HTTP {error.status_code}). "
                "Please try again in a few minutes."
            )
        elif error.status_code == 429:
            st.error("NASA POWER is limiting requests. Please wait a minute and try again.")
        else:
            st.error(f"NASA POWER rejected the request: {' '.join(error.messages) or error}")
    elif isinstance(error, power_client.PowerInputError):
        st.error(f"Invalid input: {error}")
    elif isinstance(error, integration.IntegrationError):
        st.error(f"A project module does not match the expected interface: {error}")
    else:
        st.error(f"The data could not be processed: {error}")
    st.caption("No results are shown because no valid data were obtained.")


def render_output(output: AnalysisOutput) -> None:
    request = output.request
    st.subheader(f"Results for {request.location_label}")
    if request.source == "giovanni_saved":
        st.caption(
            f"NASA Giovanni · {request.location_label} · "
            f"{request.start_year}–{request.end_year} · {RESOLUTIONS[request.resolution]}"
        )
        st.info(f"Saved files — downloaded {output.metadata.get('download_date')}; not live data.")
    else:
        st.caption(
            f"Latitude {output.metadata.get('latitude')}°, longitude "
            f"{output.metadata.get('longitude')}° · {request.start_year}–{request.end_year} · "
            f"{RESOLUTIONS[request.resolution]}"
        )
    render_location_map(output)
    if len(output.variables) == 1:
        render_variable(output.variables[0], output)
    else:
        tabs = st.tabs([item.name for item in output.variables])
        for tab, item in zip(tabs, output.variables):
            with tab:
                render_variable(item, output)


def render_location_map(output: AnalysisOutput) -> None:
    """Optional map of the analysed point. Never blocks the analysis results."""
    latitude = output.metadata.get("latitude")
    longitude = output.metadata.get("longitude")
    if latitude is None or longitude is None:
        return  # e.g. a dataset that is not tied to a single point
    with st.expander("Study location map", expanded=True):
        try:
            figure = maps.study_point_map(
                latitude,
                longitude,
                location_label=output.request.location_label,
                variable_names=[item.name for item in output.variables],
            )
            st.plotly_chart(
                figure, width="stretch", theme=None, key="location-map",
                config={"displaylogo": False, "scrollZoom": False},
            )
        except Exception as exc:  # the map is optional; results must still show
            st.caption(f"The location map could not be displayed: {exc}")
            return
        st.caption(maps.POINT_NOTE + " The map shows the location only, not measurements.")


def render_variable(item: VariableOutput, output: AnalysisOutput) -> None:
    if item.n_total == 0:
        st.warning(
            "The data source has no values for this selection. Annual means "
            "exist only for complete years; try monthly resolution or a longer period."
        )
        return
    if item.n_valid == 0:
        st.warning(
            "All values for this selection are missing in the source data, "
            "so there is nothing to plot or analyse."
        )
        return
    render_chart(item, output)
    render_statistics(item, output)
    render_interpretation(item, output)
    render_data_information(item, output)


def render_chart(item: VariableOutput, output: AnalysisOutput) -> None:
    request = output.request
    source = output.metadata.get("source", "NASA POWER")
    title = (
        f"{item.name} — {request.location_label}, "
        f"{request.start_year}–{request.end_year} ({request.resolution})"
    )
    try:
        figure = integration.make_figure(
            item.series, item.trend, title,
            variable=item.variable, metadata=_item_metadata(item, output),
            start_date=date(request.start_year, 1, 1),
            end_date=date(request.end_year, 12, 31),
            location_name=request.location_label,
        )
    except (ValueError, integration.IntegrationError) as exc:
        st.error(f"The time-series chart could not be drawn: {exc}")
        return
    if figure is None:
        figure = charts.basic_timeseries_figure(
            item.series,
            variable_name=item.name,
            unit=item.unit,
            title=title,
            source=source,
            trend_line=(item.trend or {}).get("trend_line"),
        )
    st.plotly_chart(figure, width="stretch", theme=None, key=f"chart-{item.variable}",
                    config={"displaylogo": False, "scrollZoom": False,
                            "toImageButtonOptions": {"format": "svg", "filename": "earthtrend"}})
    if item.n_missing:
        st.caption(
            f"{item.n_missing} of {item.n_total} values are missing in the source "
            "data and appear as gaps. They were not filled in."
        )
    if item.trend is None:
        st.caption("No trend line is drawn because no trend analysis is available.")
    elif not item.trend.get("trend_line"):
        st.caption("No trend line is drawn because no trend rate was estimated.")
    elif request.resolution == "monthly":
        st.caption(
            "The dashed line is the fitted long-term trend with the seasonal cycle "
            "averaged out; it is not a fit to individual months."
        )


def render_statistics(item: VariableOutput, output: AnalysisOutput) -> None:
    st.markdown("#### Statistical results")
    trend = item.trend
    if trend is None:
        if item.trend_error:
            st.warning(f"The trend analysis could not be completed: {item.trend_error}")
        else:
            st.info(text.ANALYSIS_UNAVAILABLE)
        st.metric("Valid observations", f"{item.n_valid} of {item.n_total}")
        return

    direction = trend.get("direction")
    n_used = trend.get("n_valid", item.n_valid)
    row = st.columns(3)
    row[0].metric("Trend direction", str(direction).capitalize() if direction else text.NOT_REPORTED)
    row[1].metric("Trend rate", text.format_rate(trend))
    disagreement = text.disagreement_note(trend)
    # The regression test is the pre-declared primary test; Mann-Kendall is a
    # secondary check whose disagreement is shown as a warning below.
    row[2].metric("Significance (regression)", text.significance_label(trend))
    row = st.columns(3)
    row[0].metric("P-value", text.format_p_value(trend.get("p_value")))
    row[1].metric("Confidence interval of rate", text.format_confidence_interval(trend))
    row[2].metric("Valid observations", f"{n_used} of {item.n_total}")

    details = []
    if trend.get("method"):
        details.append(f"Method: {trend['method']}.")
    if text.is_number(trend.get("alpha")):
        details.append(f"Significance level (alpha): {trend['alpha']:g}.")
    details.append(
        "Direction and significance are separate: the direction describes "
        "the estimated change in these data, and the significance test "
        "indicates whether there is sufficient statistical evidence of a trend."
    )
    st.caption(" ".join(details))
    if disagreement:
        st.warning(disagreement)
    for note in trend.get("notes") or []:
        st.caption(f"Note: {note}")
    render_understanding(item, output)

    scientific = trend.get("analysis_details")
    if scientific:
        with st.expander("Mann–Kendall, Sen’s slope and diagnostics"):
            mk = scientific.get("mann_kendall") or {}
            sen = scientific.get("sen") or {}
            columns = st.columns(3)
            columns[0].metric("Mann–Kendall decision", mk.get("decision", "not assessed"))
            columns[1].metric("Mann–Kendall p-value", text.format_p_value(mk.get("p_value")))
            columns[2].metric("Sen’s slope", text.format_rate(sen))
            st.caption(
                "The summary above uses regression. Mann–Kendall tests monotonic "
                "change; Sen’s slope is descriptive. A missing decision means "
                "inference was not assessed under the documented safeguards."
            )
            st.json({
                "status": scientific.get("status"),
                "mann_kendall": mk, "sen": sen,
                "diagnostics": scientific.get("diagnostics"),
            }, expanded=False)


def render_understanding(item: VariableOutput, output: AnalysisOutput) -> None:
    """Plain-language guide to the numbers above, with optional technical detail."""
    request = output.request
    with st.expander("Understanding Your Results"):
        st.info(text.explain_result(item.trend, item.n_valid, item.n_total,
                                    request.resolution, MIN_ANNUAL_YEARS),
                title="Why this result looks the way it does")
        technical = st.toggle("Show technical details", key=f"technical-{item.variable}")
        for term, plain, detail in text.GLOSSARY:
            st.markdown(f"**{term}.** {plain}" + (f" *Technical: {detail}*" if technical else ""))


def render_interpretation(item: VariableOutput, output: AnalysisOutput) -> None:
    request = output.request
    st.markdown("#### EarthTrend Insights")
    reading = text.insights(
        item.trend,
        variable_name=item.name,
        source_label=_item_metadata(item, output).get("source") or "the selected source",
        place=request.location_label,
        period=f"{request.start_year}–{request.end_year}",
        resolution=request.resolution,
        n_valid=item.n_valid, n_total=item.n_total, n_missing=item.n_missing,
        absent=_absent_months(item, request), required_years=MIN_ANNUAL_YEARS,
    )
    for heading, key in (("What the data show", "observations"),
                         ("What the statistics say", "findings"),
                         ("Suggested next steps", "next_steps")):
        st.markdown(f"**{heading}**\n" + "\n".join(f"- {line}" for line in reading[key]))
    st.caption("Generated by fixed rules from the results above; no AI model is used.")
    st.warning(text.CAUSATION_WARNING)
    limitations = list(text.GENERAL_LIMITATIONS)
    if request.source == "giovanni_saved":
        limitations[0] = (
            f"{output.metadata.get('provider')}. Values are an average over "
            f"{request.location_label.split(' — ')[0]}, not a station or point measurement; "
            "local differences are hidden. Saved files, not live data."
        )
        note = (output.metadata.get("variable_notes") or {}).get(item.variable)
        if note:
            limitations.insert(1, note)
    if request.resolution == "monthly":
        limitations.insert(0, text.SEASONALITY_NOTE)
    with st.expander("Limitations"):
        for limitation in limitations:
            st.markdown(f"- {limitation}")


def render_data_information(item: VariableOutput, output: AnalysisOutput) -> None:
    meta = output.metadata
    request = output.request
    description = power_client.SUPPORTED_PARAMETERS.get(item.variable, item.name)
    rows = {
        "Dataset source": _item_metadata(item, output).get("source"),
        "Dataset": meta.get("dataset_title"),
        "Provider": f"{meta.get('provider')} — {meta.get('provider_url')}",
        "Variable": f"{item.name} (`{item.variable}`): {description}",
        "Measurement unit": item.unit or "Not stated by the source",
        "Temporal resolution": RESOLUTIONS[request.resolution],
        "Requested period": f"{request.start_year}–{request.end_year}",
        "Data coverage": (
            f"{_format_date(item.first_valid, request.resolution)} to "
            f"{_format_date(item.last_valid, request.resolution)} "
            f"({item.n_valid} valid, {item.n_missing} missing"
            + (f", {absent} month(s) absent from the source" if (absent := _absent_months(item, request)) else "")
            + ")"
        ),
        "Location": (
            f"Latitude {meta.get('latitude')}°, longitude {meta.get('longitude')}°"
            + (f", elevation {meta['elevation_m']} m" if meta.get("elevation_m") is not None else "")
        ),
        "Missing values": meta.get("missing_value_handling"),
        "Preprocessing": (
            "Team preprocessing module applied"
            if item.preprocessing_applied
            else "None beyond marking missing values"
        ),
        "Retrieved (UTC)": meta.get("retrieved_at_utc"),
    }
    if request.source == "giovanni_saved":
        rows["Dataset"] = giovanni.DATASETS[item.variable]["product"]
        rows["Provider"] = f"{giovanni.DATASETS[item.variable]['provider']} — {meta.get('provider_url')}"
        rows["Location"] = meta["spatial_description"]
        rows["Data access"] = meta["delivery"]
        rows["Download date"] = meta["download_date"]
        rows["Saved file"] = meta["files"][item.variable]
        rows["Variable note"] = (meta.get("variable_notes") or {}).get(item.variable)
        if request.resolution == "annual":
            rows["Temporal resolution"] = "Annual means computed by EarthTrend from monthly values "                                           "(days-weighted, complete years only)"
        rows["Provenance limitation"] = meta["provenance_note"]
    with st.expander("Data information", expanded=True):
        for label, value in rows.items():
            if value:
                st.markdown(f"**{label}:** {value}")
        if item.preprocessing_report:
            st.markdown("**Preprocessing report:**")
            st.json(item.preprocessing_report, expanded=False)
        if meta.get("request_url"):
            st.markdown(f"**Request:** `{meta['request_url']}`")
        st.download_button(
            "Download this series (CSV)",
            data=item.series.to_csv(index=False).encode("utf-8"),
            file_name=(
                f"earthtrend_{item.variable}_{request.resolution}_"
                f"{request.start_year}_{request.end_year}.csv"
            ),
            mime="text/csv",
            key=f"download-{item.variable}",
        )


def _absent_months(item: VariableOutput, request: AnalysisRequest) -> int:
    """Months inside the covered period that have no row at all (not NaN rows)."""
    if request.resolution != "monthly" or item.first_valid is None:
        return 0
    first, last = item.series["date"].min(), item.series["date"].max()
    return (last.year - first.year) * 12 + last.month - first.month + 1 - item.n_total


def _item_metadata(item: VariableOutput, output: AnalysisOutput) -> dict:
    """Metadata for one variable's chart: saved files differ in source per variable."""
    sources = item.series["source"].dropna().unique() if "source" in item.series else []
    return {**output.metadata, "source": sources[0]} if len(sources) == 1 else output.metadata


def _format_date(value, resolution: str) -> str:
    if value is None:
        return "n/a"
    return f"{value:%Y}" if resolution == "annual" else f"{value:%b %Y}"
