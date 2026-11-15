"""EarthTrend — Streamlit entry point.

Run with:  streamlit run app.py

This file only arranges the page. Data retrieval, analysis and wording live
in the ``earthtrend`` package.
"""

import streamlit as st

from earthtrend import integration
from earthtrend.data import power_client
from earthtrend.pipeline import run_analysis
from earthtrend.ui import components

st.set_page_config(page_title="EarthTrend", page_icon="🌍", layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def cached_fetch(parameters, latitude, longitude, start_year, end_year):
    """Identical requests within an hour reuse the NASA POWER response."""
    return power_client.get_monthly_series(
        list(parameters), latitude, longitude, start_year, end_year
    )


def fetch(parameters, latitude, longitude, start_year, end_year):
    return cached_fetch(tuple(parameters), latitude, longitude, start_year, end_year)


components.render_header()
request, clicked = components.render_configuration()

if clicked and request is not None:
    st.session_state.pop("output", None)
    with st.spinner("Loading saved NASA Giovanni files…" if request.source == "giovanni_saved" else "Retrieving data from NASA POWER…"):
        try:
            st.session_state["output"] = run_analysis(request, fetch=fetch)
        except (power_client.PowerAPIError, integration.IntegrationError, ValueError, OSError) as error:
            components.render_error(error)

output = st.session_state.get("output")
if output is not None:
    if request is not None and request != output.request:
        st.info("The configuration has changed. Press Analyze to update the results below.")
    components.render_output(output)
elif not clicked:
    st.info("Set the analysis configuration in the sidebar, then press **Analyze**.")
