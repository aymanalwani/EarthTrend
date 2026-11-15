# Raw data

## giovanni/ (in the repository)

These are NASA Giovanni area-averaged time-series exports, unchanged as
downloaded on 2026-11-14:

| File | Rebuilds | Script |
|---|---|---|
| `g4.areaAvgTimeSeries.M2TMNXFLX_5_12_4_EVAP.20050101-20251231.180W_90S_180E_90N.csv` | `data/processed/jordan_evap_monthly_2005_2025.csv` | `python scripts/prepare_jordan_evap.py` |
| `g4.areaAvgTimeSeries.MODISA_L3m_NSST_Monthly_4km_R2019_0_sst.20050101-20251231.34E_29N_35E_29N.csv` | `data/processed/aqaba_sst_night_monthly_2005_2025.csv` | `python scripts/prepare_aqaba_sst.py data/raw/giovanni/<file>` |

Both scripts reproduce the committed processed files byte for byte (checked
2026-11-15).

**Missing: the raw exports for Jordan T2M, PRECTOTCORR and GWETTOP.**

- They were not on the preparation machine.
- A re-run of the documented Giovanni queries without an Earthdata Login on
  2026-11-15 ended in "Workflow failed" for all three.
- Their processed CSVs in `data/processed/` are the retained form.

To restore them, sign in to Giovanni with an Earthdata account and open the
"URL to reproduce" for each file, given in DATA_SOURCES.md.

## stations/ (not in the repository)

This folder is created by `python scripts/validate_stations.py download`. It
holds:

- NOAA GSOD daily files;
- NOAA GHCN-Monthly v4 Jordan lines;
- NASA POWER daily, hourly and monthly JSON responses for the station
  cross-check.

It is git-ignored. GSOD non-US data are exchanged under WMO Resolution 40 and
must not be redistributed; the other files are re-downloadable and only used
offline.
