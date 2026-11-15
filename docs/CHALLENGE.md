# EarthTrend: challenge brief

## Challenge

NASA Space Apps Challenge 2026, "Be An Earth System Trend Detective!":
https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/

These facts were checked on the challenge pages on 2026-11-15:

- **Eligibility rule** (Project Submission Guide): a project must use at least
  one NASA data source or resource to be eligible for a Global Award.
- **Other data** may be used, and is listed under "Space Agency Partner Data
  and Other References".
- **NASA resources EarthTrend uses:** NASA Giovanni, which is on the
  challenge's Resources tab, and NASA POWER, which is not listed there but is
  NASA data.
- **External data:** the NOAA GSOD, GHCN-Monthly and NASA POWER data used in
  the offline station cross-check (docs/validation/) are listed as references
  in DATA_SOURCES.md. None of them is a Space Apps partner dataset.

The sections below are the team's original brief.

## Project Goal
Build an application that allows users to explore Earth science variables, analyze their changes over time, and determine whether observed trends are statistically significant.

## Core Questions
- What is changing?
- Where is it changing?
- How much is it changing?
- Is the trend statistically significant?

## Required Workflow

1. Select an Earth science variable.
2. Select a geographic region.
3. Select a time period.
4. Retrieve and visualize a time series.
5. Analyze the trend and test its statistical significance.

## Potential Variables
- Temperature
- Precipitation
- Soil Moisture
- Vegetation Index (NDVI)
- Evaporation
- Sea Surface Temperature
- Hydrological Variables

## Potential Data Sources
- NASA Giovanni
- NASA POWER
- NASA AppEEARS
- NASA GES DISC
- Other verified Earth science datasets

## MVP Requirements
- Real and documented Earth science data.
- Variable and location selection.
- Time-period selection.
- Time-series visualization.
- Trend direction and rate estimation.
- Statistical significance testing.
- Clear data source attribution.
- Explanation of results.

## Scientific Requirements
- Preserve original measurement units.
- Handle missing observations correctly.
- Document preprocessing decisions.
- Distinguish trend direction from statistical significance.
- Avoid unsupported scientific conclusions.

## Development Stack
- Python
- Streamlit
- Pandas
- NumPy
- SciPy
- PyMannKendall
- Statsmodels
- Plotly

## Important
The application must not present synthetic test data as real NASA observations.