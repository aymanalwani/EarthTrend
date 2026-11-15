# EarthTrend — Data Sources

This file describes what EarthTrend **actually uses**. Resources that were
considered during planning but are not used are listed separately at the end.
Every statement about a dataset below was checked against the code, the
committed files or the live API; anything that could not be verified says so.

## Sources Actually Used

| Variable (app label) | Code | Region / location | Period | Original producer | Archive / distributor | Access tool or API | App path |
|---|---|---|---|---|---|---|---|
| Air temperature at 2 m | `T2M` | Any point (grid cell) | 1981–present | NASA GMAO MERRA-2 (as reported by the API in `header.sources`) | NASA POWER, NASA Langley Research Center | POWER monthly point API (live) | Data source "NASA POWER" |
| Precipitation (bias corrected) | `PRECTOTCORR` | Any point (grid cell) | 1981–present | NASA GMAO MERRA-2 | NASA POWER | POWER monthly point API (live) | Data source "NASA POWER" |
| Air temperature at 2 m | `T2M` | Jordan, country-wide average | 2005–2025 | NASA GMAO MERRA-2 | NASA GES DISC | NASA Giovanni area-averaged time series (saved CSV) | "NASA Giovanni" → Jordan |
| Precipitation rate (bias corrected) | `PRECTOTCORR` | Jordan, country-wide average | 2005–2025 | NASA GMAO MERRA-2 | NASA GES DISC | NASA Giovanni (saved CSV) | "NASA Giovanni" → Jordan |
| Surface soil wetness | `GWETTOP` | Jordan, country-wide average | 2005–2025 | NASA GMAO MERRA-2 | NASA GES DISC | NASA Giovanni (saved CSV) | "NASA Giovanni" → Jordan |
| Evaporation | `EVAP` | Jordan, country-wide average | 2005–2025 | NASA GMAO MERRA-2 | NASA GES DISC | NASA Giovanni (saved CSV) | "NASA Giovanni" → Jordan |
| Night-time sea surface temperature | `SST_NIGHT` | Gulf of Aqaba, head of the gulf | 2005–2025 | NASA Ocean Biology Processing Group, MODIS-Aqua | NASA OB.DAAC | NASA Giovanni (saved CSV) | "NASA Giovanni" → Gulf of Aqaba |

Notes on roles:

- **NASA POWER** is both the distributor and the API. EarthTrend calls it live
  (`earthtrend/data/power_client.py`); no key is needed.
- **NASA Giovanni** is a data access and visualization tool. EarthTrend does not
  call it; the team ran area-averaged time series in Giovanni, downloaded the
  CSV exports on 2026-11-14 and committed processed copies in
  `data/processed/`. The app reads them through `earthtrend/data/giovanni.py`.
- **MERRA-2** (NASA GMAO) and **MODIS-Aqua** (NASA OBPG) are the products the
  values come from. NASA POWER and Giovanni both serve MERRA-2 values, but they
  are not interchangeable here: POWER returns one grid cell at a point, with
  POWER's own processing and units for the `ag` community; the Giovanni files
  are averages over the Jordan country shape. Sharing an identifier
  (`T2M`, `PRECTOTCORR`) does not make the two series comparable.
  - **Checked example** (2026-11-15, T2M, monthly, 2015-2025, 132 values each):

    | Series | Rate (C/yr) | Sen's slope (C/yr) |
    |---|---|---|
    | Giovanni Jordan average | +0.0475 | +0.0439 |
    | POWER Cairo (30.04 N, 31.24 E) | +0.0781 | +0.0912 |
    | POWER Amman (31.95 N, 35.93 E) | +0.0668 | +0.0687 |
    | POWER 32.3 N, 37.5 E (eastern Jordan) | +0.0483 | +0.0615 |
    | POWER 30.2 N, 36.5 E (southern Jordan) | +0.0590 | +0.0540 |

  - The differences follow the place: one grid cell against a country
    average, and Cairo is in another country. Monthly anomalies correlate
    0.95-0.98 between the Jordan average and the Jordan points, and 0.79 with
    Cairo.
  - With 11 years none of these rates is tested for significance, so the
    differences between them are not established either.
  - Not determined: how much of the remaining difference comes from the
    products themselves. Giovanni serves the instantaneous monthly collection
    M2IMNXASM; POWER does not state which MERRA-2 collection it uses.
- All 7 series above are reachable from the app. No downloaded dataset is
  unused.
- Raw Giovanni exports kept in `data/raw/giovanni/`: EVAP and SST. The
  processed EVAP and SST files rebuild from them byte for byte with
  `scripts/prepare_jordan_evap.py` and `scripts/prepare_aqaba_sst.py`. The raw
  T2M, PRECTOTCORR and GWETTOP exports were not retained. Each section below
  gives its "URL to reproduce".

## Dataset Details and Provenance

### NASA POWER Monthly (point)

Implemented in `earthtrend/data/power_client.py`. Everything below was checked
against the live API and its OpenAPI specification on 2026-11-14, except the
items listed under "Not verified through the API".

- Dataset name: NASA POWER "Source Native Resolution Monthly and Annual"
- Data provider: NASA Langley Research Center, POWER Project
- Official dataset URL: https://power.larc.nasa.gov/
- Documentation: https://power.larc.nasa.gov/docs/
- API specification: https://power.larc.nasa.gov/api/temporal/monthly/openapi.json
- Endpoint: `GET https://power.larc.nasa.gov/api/temporal/monthly/point`
- Authentication: none; no API key is required
- Underlying source reported by the API: MERRA2 (`header.sources`)
- License or usage conditions: NASA data, no use restrictions; acknowledgement
  wording in "Citation and Attribution" below
- Citation or attribution: shown in the app as "NASA POWER (MERRA2)", taken
  from each response

#### Variables

| Identifier | Name returned by API | Unit returned by API |
|---|---|---|
| `T2M` | Temperature at 2 Meters | C |
| `PRECTOTCORR` | Precipitation Corrected | mm/day |

Units are for the `ag` community with the default metric units. The client
reads the unit from every response and does not hard-code it.

#### Query parameters

| Parameter | Required | Meaning |
|---|---|---|
| `parameters` | yes | Comma-separated identifiers |
| `community` | yes | `ag`, `sb` or `re`; decides the returned units |
| `latitude` | yes | -90 to 90 |
| `longitude` | yes | -180 to 180 |
| `start`, `end` | yes | Years as `YYYY` (whole years only) |
| `format` | no | The client requests `JSON` |

A regional endpoint (`/api/temporal/monthly/regional`, with `latitude-min`,
`latitude-max`, `longitude-min`, `longitude-max`) exists in the specification.
It is not used and has not been tested.

#### Coverage and resolution

- Temporal resolutions offered by POWER for these variables: hourly, daily,
  monthly, climatology. EarthTrend uses monthly.
- Temporal coverage: the monthly API's configuration endpoint reported
  1981-01-01 to 2026-11-30 on 2026-11-14. Requests starting before 1981 are
  rejected with HTTP 422. The end date moves forward over time, so the client
  does not hard-code the period and passes on the API's own error message.
- Geographic coverage: global, single point per request.

#### Missing-data conventions

- Missing values are returned as the fill value given in
  `header.fill_value` (`-999.0`). The client converts them to `NaN`, never to
  zero. Real zeros, such as a month without precipitation, are kept.
- The most recent months can be missing: on 2026-11-14, October and November
  2026 were returned as fill values.
- Each complete year has an extra key ending in `13` (for example `202513`).
  This is the annual value, not a month. The client returns it in a separate
  table. Incomplete years have no such key.

#### Processing performed by the client

- Fill value to `NaN`.
- Time key `YYYYMM` to a date on the first day of that month.
- Annual (`13`) values separated from monthly values.
- No sorting, gap filling, de-duplication, unit conversion or rounding.

#### Data limitations

- The values are MERRA-2 reanalysis (model-based) estimates for a grid cell,
  not station measurements at the exact point.
- `PRECTOTCORR` is a bias-corrected model product and is a monthly mean rate
  in mm/day, not a monthly total.
- Errors from the API (invalid parameter, coordinates or years) arrive as
  HTTP 422 with a `messages` list, which the client surfaces.

#### Not verified through the API

- Grid resolution: the POWER documentation describes the meteorological data
  as 0.5 x 0.625 degrees (latitude x longitude). Confirm in the documentation
  before quoting it.
- Request rate limits.

### NASA Giovanni, Jordan Monthly T2M

File: `data/processed/jordan_t2m_monthly_2005_2025.csv` (committed to git;
`data/raw/` stays untracked, so the original download is not in the repository).

- Dataset name: MERRA-2 `M2IMNXASM` v5.12.4, "2-meter air temperature monthly
  0.5 x 0.625 deg"
- Data provider: NASA GES DISC, accessed through NASA Giovanni
- Official dataset URL: https://giovanni.gsfc.nasa.gov/
- Variable: `T2M`, 2-meter air temperature
- Measurement unit: C (Giovanni was asked for `units=C`)
- Geographic coverage: Jordan, area-averaged over the country shape
  (`state_dept_countries_2017/shp_113`); one value per month, not per city
- Temporal coverage: 2005-01 to 2025-12 (252 monthly values, no gaps)
- Temporal resolution: monthly
- Download date: 2026-11-14
- License or usage conditions: NASA Earth science data are freely available with no
  use restrictions; citation is requested (see "Citation and Attribution" below)
- Citation or attribution: see "Citation and Attribution" below (MERRA-2 DOI
  and Giovanni acknowledgement)
- URL to reproduce: `https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime=2005-01-01T00:00:00Z&endtime=2025-12-31T23:59:59Z&shape=state_dept_countries_2017/shp_113&&data=M2IMNXASM_5_12_4_T2M(units%3DC)&variableFacets=dataProductTimeInterval%3Amonthly%3B&dataKeyword=2-meter%20air%20temperature&portal=GIOVANNI&format=json`

#### Columns

| Column | Meaning |
|---|---|
| `date` | First day of the month, `YYYY-MM-DD` |
| `t2m_c` | Area-averaged monthly mean air temperature, C |

#### Processing performed

- Removed the 8 metadata lines Giovanni writes above the table.
- Renamed `time` to `date` (time of day dropped) and
  `mean_M2IMNXASM_5_12_4_T2M` to `t2m_c`.
- Checked for the fill value (`1e15`): none present. No values were changed,
  rounded, sorted or filled.

#### Data limitations

- MERRA-2 is a reanalysis (model-based), not station measurements.
- The value is a country-wide average, so it hides differences between regions
  such as the Jordan Valley and the highlands. Comparing it with a NASA POWER
  point series compares a national mean with a single grid cell.

### NASA Giovanni, Jordan Monthly Precipitation

File: `data/processed/jordan_prectotcorr_monthly_2005_2025.csv`. Same region,
period and source family as the Jordan T2M file above.

- Dataset name: MERRA-2 `M2TMNXFLX` v5.12.4, "Bias corrected total surface
  precipitation monthly 0.5 x 0.625 deg"
- Data provider: NASA GES DISC, accessed through NASA Giovanni
- Official dataset URL: https://giovanni.gsfc.nasa.gov/
- Variable: `PRECTOTCORR`, the same identifier NASA POWER uses
- Measurement unit: mm/day (Giovanni was asked for `units=mm/day`)
- Geographic coverage: Jordan, area-averaged over the country shape
  (`state_dept_countries_2017/shp_113`)
- Temporal coverage: 2005-01 to 2025-12 (252 monthly values, no gaps)
- Temporal resolution: monthly
- Download date: 2026-11-14
- License or usage conditions: NASA Earth science data are freely available with no
  use restrictions; citation is requested (see "Citation and Attribution" below)
- Citation or attribution: see "Citation and Attribution" below (MERRA-2 DOI
  and Giovanni acknowledgement)
- URL to reproduce: `https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime=2005-01-01T00:00:00Z&endtime=2025-12-31T23:59:59Z&shape=state_dept_countries_2017/shp_113&&data=M2TMNXFLX_5_12_4_PRECTOTCORR(units%3Dmm%2Fday)&dataKeyword=PRECTOTCORR&portal=GIOVANNI&format=json`

#### Columns

| Column | Meaning |
|---|---|
| `date` | First day of the month, `YYYY-MM-DD` |
| `prectotcorr_mm_day` | Area-averaged mean precipitation rate for the month, mm/day |

#### Processing performed

- Removed the 8 metadata lines Giovanni writes above the table.
- Renamed `time` to `date` (time of day dropped) and
  `mean_M2TMNXFLX_5_12_4_PRECTOTCORR` to `prectotcorr_mm_day`.
- Checked for the fill value (`1e15`): none present. No values were changed,
  rounded, sorted or filled. Very small values (for example `5.8e-06` in
  summer) are real model output and are kept as written.

#### Data limitations

- The value is a mean rate in mm/day, not a monthly total. Multiply by the
  number of days in the month to get mm per month.
- MERRA-2 is a bias-corrected reanalysis product, not rain-gauge data, and
  the value is a country-wide average.
- Jordan is arid: near-zero values from June to September are expected.

### NASA Giovanni, Jordan Monthly Surface Soil Wetness

File: `data/processed/jordan_gwettop_monthly_2005_2025.csv`. Same region,
period and source family as the Jordan T2M and precipitation files above.

- Dataset name: MERRA-2 `M2TMNXLND` v5.12.4, "Surface soil wetness monthly
  0.5 x 0.625 deg"
- Data provider: NASA GES DISC, accessed through NASA Giovanni
- Official dataset URL: https://giovanni.gsfc.nasa.gov/
- Variable: `GWETTOP`, the same identifier NASA POWER uses
- Measurement unit: unitless fraction, 0 (dry) to 1 (saturated); no unit
  conversion applied
- Geographic coverage: Jordan, area-averaged over the country shape
  (`state_dept_countries_2017/shp_113`)
- Temporal coverage: 2005-01 to 2025-12 (252 monthly values, no gaps)
- Temporal resolution: monthly
- Download date: 2026-11-14
- License or usage conditions: NASA Earth science data are freely available with no
  use restrictions; citation is requested (see "Citation and Attribution" below)
- Citation or attribution: see "Citation and Attribution" below (MERRA-2 DOI
  and Giovanni acknowledgement)
- URL to reproduce: `https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime=2005-01-01T00:00:00Z&endtime=2025-12-31T23:59:59Z&shape=state_dept_countries_2017/shp_113&&data=M2TMNXLND_5_12_4_GWETTOP&dataKeyword=soil%20wetness&portal=GIOVANNI&format=json`

#### Columns

| Column | Meaning |
|---|---|
| `date` | First day of the month, `YYYY-MM-DD` |
| `gwettop_fraction` | Area-averaged monthly mean surface soil wetness, 0 to 1 |

#### Processing performed

- Removed the 8 metadata lines Giovanni writes above the table.
- Renamed `time` to `date` (time of day dropped) and
  `mean_M2TMNXLND_5_12_4_GWETTOP` to `gwettop_fraction`.
- Checked for the fill value (`1e15`) and for values outside 0 to 1: none
  present. No values were changed, rounded, sorted or filled.

#### Data limitations

- Soil wetness is a relative index of the top soil layer, not volumetric
  water content (m3/m3).
- MERRA-2 is a model-based reanalysis, not in-situ or satellite soil
  moisture, and the value is a country-wide average.
- A clear seasonal cycle is expected: highest in winter, lowest from July to
  September.

### NASA Giovanni, Jordan Monthly Evaporation

File: `data/processed/jordan_evap_monthly_2005_2025.csv`. Same region, period
and source family as the other Jordan MERRA-2 files above.

- Dataset name: MERRA-2 `M2TMNXFLX` v5.12.4, "Evaporation from turbulence
  monthly 0.5 x 0.625 deg"
- Data provider: NASA GES DISC, accessed through NASA Giovanni
- Official dataset URL: https://giovanni.gsfc.nasa.gov/
- Variable: `EVAP`
- Measurement unit as downloaded: kg m-2 s-1 (no unit conversion was applied
  in Giovanni)
- Geographic coverage: Jordan, area-averaged over the country shape
  (`state_dept_countries_2017/shp_113`). The download's file name mentions a
  global box (`180W_90S_180E_90N`), but the header shows the Jordan shape and
  an empty bounding box, so the values are for Jordan.
- Temporal coverage: 2005-01 to 2025-12 (252 monthly values, no gaps)
- Temporal resolution: monthly
- Download date: 2026-11-14
- License or usage conditions: NASA Earth science data are freely available with no
  use restrictions; citation is requested (see "Citation and Attribution" below)
- Citation or attribution: see "Citation and Attribution" below (MERRA-2 DOI
  and Giovanni acknowledgement)
- URL to reproduce: `https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime=2005-01-01T00:00:00Z&endtime=2025-12-31T23:59:59Z&shape=state_dept_countries_2017/shp_113&&data=M2TMNXFLX_5_12_4_EVAP&dataKeyword=evaporation&portal=GIOVANNI&format=json`

#### Columns

| Column | Meaning |
|---|---|
| `date` | First day of the month, `YYYY-MM-DD` |
| `evap_kg_m2_s` | Area-averaged monthly mean evaporation flux, exactly as downloaded |
| `evap_mm_day` | The same value as mm/day: `evap_kg_m2_s * 86400` (1 kg m-2 = 1 mm of water), so it is comparable with the precipitation file |

#### Processing performed

- Removed the 8 metadata lines Giovanni writes above the table.
- Renamed `time` to `date` (time of day dropped).
- Added `evap_mm_day` as a unit conversion of the original column, which is
  kept unchanged. Rounded to 6 decimals.
- Checked for the fill value (`1e15`): none present. No values were
  rounded (original column), sorted or filled.

#### Data limitations

- This is the model's surface evaporation flux (it includes evaporation from
  land and from plants), not a measurement and not potential evaporation.
- A country-wide average from a reanalysis; it follows rainfall, so it peaks
  in late winter and spring and is lowest from July to October.

### NASA Giovanni, Gulf of Aqaba Monthly Night Sea Surface Temperature

File: `data/processed/aqaba_sst_night_monthly_2005_2025.csv`. This is a
**different region** from the Jordan files: a small sea area at the head of
the Gulf of Aqaba, not the whole country.

- Dataset name: MODIS-Aqua L3m night-time SST, monthly, 4 km, R2019.0
  (`MODISA_L3m_NSST_Monthly_4km_R2019_0_sst`), "Sea Surface Temperature at 11
  microns (Night) (water only)"
- Data provider: NASA Ocean Biology Processing Group, accessed through NASA
  Giovanni
- Official dataset URL: https://giovanni.gsfc.nasa.gov/
- Variable: `sst`
- Measurement unit: not stated in the download; the values (20 to 30) are
  consistent with degrees Celsius
- Geographic coverage: bounding box `34.8845, 29.3606, 35.0037, 29.5458`
  (west, south, east, north). Giovanni used the grid cells inside it,
  `34.8958, 29.3958, 34.9792, 29.5208`, and only water cells (a 4 km grid, so
  only a few cells). The box may include water outside Jordan.
- Temporal coverage: 2005-01 to 2025-12; 251 of 252 months present (2006-12 missing)
- Temporal resolution: monthly
- Download date: 2026-11-14
- License or usage conditions: NASA Earth science data are freely available with no
  use restrictions; citation is requested (see "Citation and Attribution" below)
- Citation or attribution: see "Citation and Attribution" below (MODIS-Aqua SST DOI
  and Giovanni acknowledgement)
- URL to reproduce: `https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime=2005-01-01T00:00:00Z&endtime=2025-12-31T23:59:59Z&bbox=34.8845,29.3606,35.0037,29.5458&data=MODISA_L3m_NSST_Monthly_4km_R2019_0_sst&portal=GIOVANNI&format=json`
  (the tracking parameter present in the original link was removed)

#### Columns

| Column | Meaning |
|---|---|
| `date` | First day of the month the value belongs to, `YYYY-MM-DD` |
| `sst_night_c` | Area-averaged monthly mean night-time SST, in C |

#### Processing performed

- Removed the 8 metadata lines Giovanni writes above the table.
- Giovanni stamps each MODIS-Aqua monthly file with the start time of its
  first data day. Up to November 2021 that start falls on the evening before the
  month begins (for example `2004-12-31 12:10:01` is January 2005,
  `2005-01-31 12:05:00` is February 2005, `2020-09-02 19:53:07` is September
  2020); from December 2021 the stamps are the first of the month at 00:00. The
  month of each value is therefore the calendar month of (timestamp + 1 day).
  This is done by `scripts/prepare_aqaba_sst.py`, which rebuilds the processed
  file from the raw export.
- No row was dropped and no value changed or filled. The fill value
  (`-32767`) does not occur.
- **Correction made on 2026-11-15.** The first processed version read the
  pre-2022 stamps as the month named in the stamp. That moved every value from
  January 2005 to November 2021 one month too early, dropped the real January
  2005 value (stamped `2004-12-31`) and the September 2020 value (stamped
  `2020-09-02`), and created false gaps at 2020-08 and 2021-11. Evidence: under
  that reading the 2005-2021 climatology peaked in July and was lowest in
  February, while 2022-2025 (unambiguous first-of-month stamps) peaked in August
  and was lowest in March. Under the corrected reading both periods peak in
  August and are lowest in March. A test (`tests/test_giovanni.py`) checks this.

#### Missing months

Only `2006-12` has no file (satellite data gap); 251 of 252 months are present.
It is left out, not filled. Annual means are not computed for 2006.

#### Data limitations

- Very small area and few 4 km cells, so a single cell or cloud-free day count
  can shift the mean. Night-time SST only.
- Satellite-derived skin temperature, not a bulk temperature measured by a
  buoy.
- Not comparable one-to-one with the country-average Jordan files.

## External Data Used for Validation (offline, not in the app)

These data are used only by `scripts/validate_stations.py` for the station
cross-check (docs/STATION_VALIDATION_PROTOCOL.md; results in
docs/validation/). The app does not use them.

- **NOAA NCEI Global Summary of the Day (GSOD)**
  - URL: https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/
  - Stations: Amman Marka 402700, Queen Alia 402720, Aqaba 403400 and King
    Hussein 402650 (all WBAN 99999).
  - Variable: daily mean temperature TEMP, in tenths of a degree F; missing
    value 9999.9; GMT day; the count of observations is in TEMP_ATTRIBUTES
    (readme ncei.noaa.gov/data/global-summary-of-the-day/doc/readme.txt,
    10/28/2020).
  - Not NASA data.
  - Data use: non-US data are exchanged under WMO Resolution 40. They are for
    non-commercial research and education and must not be redistributed, so
    the raw files are not in the repository.
  - Downloaded 2026-11-15.
- **NOAA NCEI GHCN-Monthly v4 TAVG**, qcu (unadjusted) and qcf (homogenised
  with the Pairwise Homogenization Algorithm)
  - URL: https://www.ncei.noaa.gov/pub/data/ghcn/v4/
  - Stations: King Hussein JOM00040265, Ma'an JOM00040310 and Ghor Safi
    JOM00040296.
  - Values in hundredths of a degree C; missing -9999.
  - Citation: Menne et al. (2018) and Menne and Williams (2009).
  - Not NASA data. Downloaded 2026-11-15.
- **NASA POWER daily and hourly point API, T2M**
  - Requested with time-standard UTC at the station coordinates, 2005-2024.
  - Every response header lists `sources: ["MERRA2"]`.
  - NASA data. It is used here offline for the comparison, not in the app.

## Supporting Data Portals

- **NASA GES DISC** — https://disc.gsfc.nasa.gov/ — archive that distributes
  MERRA-2; the Giovanni MERRA-2 series come from it. Not accessed directly by
  the app.
- **NASA OB.DAAC** — https://oceancolor.gsfc.nasa.gov/ — archive for the
  MODIS-Aqua SST product used through Giovanni. Not accessed directly by the
  app. Citation: see "Citation and Attribution" below.

## Other Reviewed Resources (Not Currently Used)

These were considered during planning. EarthTrend does not use any data from
them.

### NASA AppEEARS
URL: https://appeears.earthdatacloud.nasa.gov/

Purpose: Access and transform geospatial data from supported archives (for
example a vegetation index such as NDVI, which the app does not offer).

### NOAA Climate Data Online
URL: https://www.ncei.noaa.gov/cdo-web/

Purpose: Historical weather and climate observations (station data). Not NASA
data; it would need its own attribution if added.

### KNMI Climate Explorer
URL: https://climexp.knmi.nl/

Purpose: Explore and analyze climate time series. Not NASA data.

### Investigated as independent validation sources (2026-11-15), not integrated

- **Copernicus ERA5 / ERA5-Land** (ECMWF/C3S)
  - It is a reanalysis that shares most observations with MERRA-2, so
    agreement would only show that two reanalyses agree.
  - ERA5-Land monthly precipitation and evaporation are documented as wrong
    for 2022-09 to 2024-02.
  - Access needs a CDS account.
- **CHIRPS v3** (UCSB Climate Hazards Center)
  - It is a precipitation product that likely shares station gauges with the
    gauge data used to correct MERRA-2 precipitation, so it would be only
    semi-independent.
  - Each month is a separate global file of about 20 MB.
- **NOAA OISST v2.1**
  - Its 0.25-degree cells barely resolve the Gulf of Aqaba: only one ocean
    cell overlaps the MODIS box.
- **NOAA GHCN-Daily**
  - For Jordan it repeats GSOD, and its precipitation records are incomplete.

## Data that could not be integrated

- **Raw Giovanni exports for Jordan T2M, PRECTOTCORR and GWETTOP.** Only the
  processed CSVs are kept.
  - The exports were not on the preparation machine.
  - A re-run of the documented Giovanni queries without an Earthdata Login on
    2026-11-15 failed: the workflow returned "Workflow failed" for all three.
    The Giovanni user guide states that Earthdata Login is required for full
    functionality, including downloads.
  - To restore them, sign in to Giovanni with an Earthdata account, open the
    "URL to reproduce" given in each section above, and export the CSV into
    `data/raw/giovanni/`.
- **WMO OSCAR/Surface station histories** for the GSOD stations (not readable
  automatically).

## Citation and Attribution

Checked against official pages on 2026-11-15.

- **NASA data use**
  ([Earthdata data-use guidance](https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance)):
  NASA Earth science data are freely accessible with no restrictions on use.
  Users are strongly urged to cite the data, and NASA should be acknowledged as
  the source. The project's MIT licence (LICENSE) covers the code only.
- **MERRA-2** (NASA GMAO, distributed by NASA GES DISC). Dataset DOIs, from
  NASA CMR metadata:

  | Collection | DOI |
  |---|---|
  | M2IMNXASM v5.12.4 (T2M) | 10.5067/5ESKGQTZG7FO |
  | M2TMNXFLX v5.12.4 (PRECTOTCORR, EVAP) | 10.5067/0JRLVL8YV2Y4 |
  | M2TMNXLND v5.12.4 (GWETTOP) | 10.5067/8S35XF81C28F |

- **MODIS-Aqua L3 night SST R2019.0** (NASA OBPG / OB.DAAC). NASA CMR lists
  `MODISA_L3m_NSST` R2019.0 and says its DOI is assigned by PO.DAAC: MODIS Aqua
  Level 3 SST Thermal IR Monthly 4km Nighttime V2019.0, DOI 10.5067/MODSA-MO4N9.
  No separate OB.DAAC acknowledgement wording was found (the OB.DAAC citation
  page now redirects to a general overview).
- **Giovanni** (user guide, "How to cite datasets and acknowledge Giovanni").
  Acknowledge it with: "Analyses and visualizations used in this study were
  produced with the Giovanni online data system, developed and maintained by
  the NASA GES DISC." Reference: Acker, J. G. and Leptoukh, G. (2007), Eos 88(2),
  doi:10.1029/2007EO020003. The guide also asks that GES DISC be acknowledged
  and dataset DOIs cited.
- **NASA POWER** ([referencing page](https://power.larc.nasa.gov/docs/referencing/)).
  The page asks for an acknowledgement beginning "The data was obtained from
  National Aeronautics and Space Administration ...", plus a data reference
  giving the service name, version and access date (for example, POWER Monthly
  API v2.x, accessed 2026-11-15). Copy the full sentence from the referencing
  page. Only its opening was verified here. The project also asks to be sent
  a reference to any resulting publication.
- **NOAA GSOD and GHCN-Monthly** (station cross-check only). GSOD non-US data
  fall under WMO Resolution 40 (non-commercial use, no redistribution).
  GHCN-Monthly: cite Menne et al. (2018) and Menne and Williams (2009).

## Important Rules
- Do not claim third-party data is NASA data.
- Record the original source of every dataset.
- Preserve dataset metadata.
- Check data-use conditions.
- Clearly label synthetic test data.
