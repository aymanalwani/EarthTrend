# EarthTrend

EarthTrend is a Streamlit app for exploring Earth science time series and
testing whether their long-term trends are statistically significant. You
choose a variable, a place and a period. EarthTrend then:

- loads real NASA data and plots it;
- estimates the direction and rate of the trend;
- tests its significance with a method designed for persistent
  (autocorrelated) climate data;
- explains the uncertainty, the data source and the limitations.

It was built for the **NASA Space Apps Challenge 2026** challenge
**"Be An Earth System Trend Detective!"**
([challenge page](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/);
brief and eligibility notes in [docs/CHALLENGE.md](docs/CHALLENGE.md)).

## Features

- **Two NASA data sources** (details below):
  - **NASA POWER (live):** monthly MERRA-2 values for any point on Earth, from
    1981 to the present.
  - **NASA Giovanni (saved files):** monthly area averages for 2005-2025, for
    Jordan and the Gulf of Aqaba.
- **Monthly or annual resolution.** Annual means use complete years only,
  weighted by days.
- **Interactive chart** (dark theme) of the series, as a line with markers,
  and its fitted long-term trend. The line breaks at absent months or years;
  gaps are never filled.
- **Trend results:**
  - rate, with a 95% confidence interval;
  - p-value;
  - decision: significant, not significant, or not tested (with the reason);
  - an "indicative" label when fewer than 30 years are tested.
- **Secondary checks:** Mann-Kendall test with Sen's slope, and a warning when
  the two tests disagree.
- **Understanding Your Results:** a plain-language guide to every reported
  number, with optional technical detail. It says why a rate can be shown while
  significance is "Not tested", and gives both sample sizes for monthly data
  (for example 132 monthly values, 11 annual values, 15 required).
- **EarthTrend Insights:** a short rule-based reading of each result in three
  parts: what the data show, what the statistics say, and cautious next steps.
  It uses only the computed result fields, never states a cause or an impact,
  and uses no AI model or API key.
- **Context panels:**
  - data information: source, units, coverage, missing months;
  - limitations;
  - CSV download of the analysed values.

## Data actually used

| Data | Provider | Used by | How |
|---|---|---|---|
| NASA POWER monthly point data: T2M (air temperature at 2 m), PRECTOTCORR (bias-corrected precipitation) | NASA LaRC POWER, from NASA GMAO MERRA-2 | The app (live API, no key) | Value of the grid cell at the chosen point |
| MERRA-2 Jordan area averages: T2M, PRECTOTCORR, GWETTOP (surface soil wetness), EVAP (evaporation), 2005-2025 | NASA GMAO MERRA-2, through NASA GES DISC / Giovanni | The app (saved CSVs in `data/processed/`) | Country-shape average |
| MODIS-Aqua 4 km night-time SST, Gulf of Aqaba, 2005-2025 | NASA OBPG / OB.DAAC, through Giovanni | The app (saved CSV) | Box average over water |
| NOAA GSOD daily and GHCN-Monthly v4 station temperatures (Jordan), NASA POWER daily/hourly T2M | NOAA NCEI; NASA POWER | The offline station cross-check only (`scripts/validate_stations.py`), not the app | Station versus MERRA-2 grid cell |

Sources that were investigated but NOT integrated are listed in DATA_SOURCES.md
under "Other Reviewed Resources (Not Currently Used)":

- ERA5 / ERA5-Land;
- CHIRPS v3;
- NOAA OISST;
- GHCN-Daily;
- AppEEARS;
- NOAA CDO;
- KNMI.

Full provenance, units, download dates and reproduce URLs for every file are
in [DATA_SOURCES.md](DATA_SOURCES.md).

## Install and run

Tested with CPython 3.14.6 on Windows 11. Other Python versions and operating
systems have not been verified.

```bash
python -m venv .venv
```

Activate the environment. On Windows:

```bash
.venv\Scripts\activate
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Then install the dependencies, check the environment and start the app:

```bash
python -m pip install -r requirements.txt
```

```bash
python -m earthtrend.health
```

```bash
python -m streamlit run app.py
```

`earthtrend.health` checks the interpreter and installed packages without
using the network. The exact package versions tested are in
[docs/tested-environment.txt](docs/tested-environment.txt).

## Run the tests

The test runner is in a separate file, so the app itself installs without it:

```bash
python -m pip install -r requirements-dev.txt
```

```bash
python -m pytest -q
```

The tests run offline. NASA POWER responses come from a saved fixture, and the
Giovanni data are the saved CSVs. `tests/test_false_positive_rates.py` runs
Monte Carlo checks of the significance test on synthetic series and takes a
few minutes.

## Reproduce the data processing and validation

| Step | Command | Needs |
|---|---|---|
| Rebuild the Aqaba SST CSV from the raw Giovanni export | `python scripts/prepare_aqaba_sst.py data/raw/giovanni/g4.areaAvgTimeSeries.MODISA_L3m_NSST_Monthly_4km_R2019_0_sst.20050101-20251231.34E_29N_35E_29N.csv` | repository only |
| Rebuild the Jordan evaporation CSV | `python scripts/prepare_jordan_evap.py` | repository only |
| Download station and POWER files for the cross-check | `python scripts/validate_stations.py download` | network |
| Check the protocol's blockers (A2, A3, A10) | `python scripts/validate_stations.py blockers` | the downloaded files |
| Run the station cross-check | `python scripts/validate_stations.py analyze` | the downloaded files |
| Presence-only and synthetic design checks used to fix the protocol | `python scripts/validate_stations.py download --candidates`, then `python scripts/station_presence_check.py`, `python scripts/station_composition_check.py`, `python scripts/station_design_check.py` | network (first command) |

Raw station files go to `data/raw/stations/`, which git ignores. GSOD non-US
data fall under WMO Resolution 40 and must not be redistributed. The raw
exports for Jordan T2M, PRECTOTCORR and GWETTOP were not retained; see
[data/raw/README.md](data/raw/README.md).

## Station cross-check (result)

A pre-registered protocol
([docs/STATION_VALIDATION_PROTOCOL.md](docs/STATION_VALIDATION_PROTOCOL.md))
compared MERRA-2 2 m temperature with four Jordanian GSOD stations for
2005-2024.

The trend of station minus MERRA-2 is **+0.08 C/decade (95% interval -0.28 to
+0.44)**, so the result is **Inconclusive**. The stations can neither confirm
nor contradict the MERRA-2 trend at the predefined tolerance of
+-0.24 C/decade.

Details are in
[docs/validation/STATION_VALIDATION_RESULTS.md](docs/validation/STATION_VALIDATION_RESULTS.md).

## Scientific limitations

- **Not ground truth.** Reanalysis (MERRA-2) and satellite (MODIS) values are
  model or retrieval estimates, not measurements. Point values (POWER) and area
  averages (Giovanni) are not interchangeable, and datasets define variables
  and periods differently.
- **Trend tests:**
  - A significant trend does not establish its cause.
  - A non-significant result does not prove there is no trend.
  - "Not tested" means the data did not meet the test's conditions.
- **Persistence.** The significance rule controls false positives for
  independent and moderately persistent noise. Strong multi-year persistence
  with 15-29 years can still give 10-17% false positives, and step changes can
  look like trends. Results from fewer than 30 years are labelled indicative.
  See [docs/ANALYSIS.md](docs/ANALYSIS.md).
- **Multiple comparisons.** No correction is applied across variables, places
  or periods.
- **Saved Giovanni data** are fixed files downloaded on 2026-11-14, not live
  data.

## Repository contents

| Path | Purpose |
|---|---|
| `app.py` | Streamlit entry point |
| `earthtrend/` | Application package: data clients (`data/`), preprocessing, analysis, plotting, UI (`ui/`), `health.py` environment check |
| `data/processed/` | Saved Giovanni series used by the app |
| `data/raw/giovanni/` | Raw Giovanni exports that the processed files are rebuilt from |
| `scripts/` | Data preparation and station cross-check scripts |
| `tests/` | Automated tests (pytest) |
| `docs/ANALYSIS.md`, `docs/PREPROCESSING.md`, `docs/VISUALIZATION.md` | Methods and module contracts |
| `docs/STATION_VALIDATION_PROTOCOL.md`, `docs/validation/` | Station cross-check protocol, metadata stage, results |
| `docs/AUDIT_2026-11-15.md` | Full audit and scientific review of the project |
| `docs/CHALLENGE.md` | Challenge brief and eligibility notes |
| `docs/AI_USE.md` | Disclosure of AI assistance (prompts used) |
| `docs/tested-environment.txt` | Package versions of the tested environment |
| `LICENSE` | MIT licence for the code |

## License and data attribution

The code is released under the MIT License (see LICENSE). The licence does
not cover the data.

NASA MERRA-2, MODIS-Aqua and POWER data, and the NOAA station data used by the
validation scripts, keep their providers' own terms. When you use or publish
results, cite and acknowledge them as described in
[DATA_SOURCES.md, "Citation and Attribution"](DATA_SOURCES.md#citation-and-attribution).
That section includes the dataset DOIs and the Giovanni and NASA POWER
acknowledgements.
