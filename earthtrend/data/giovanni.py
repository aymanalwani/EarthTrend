"""Saved NASA Giovanni area-average series (2005-2025); never a live request.

Provenance of every file is in DATA_SOURCES.md. Values are read as saved; the
only derived values are annual means (see ``_annual``).
"""
from pathlib import Path

import pandas as pd

from earthtrend.data.power_client import ANNUAL_COLUMNS, TIMESERIES_COLUMNS, PowerResult

DATA_DIR = Path(__file__).resolve().parents[2] / "data/processed"
FIRST_YEAR, LAST_YEAR = 2005, 2025
DOWNLOAD_DATE = "2026-11-14"
GIOVANNI_URL = "https://giovanni.gsfc.nasa.gov/"
MERRA2 = "NASA GMAO MERRA-2 reanalysis, distributed by NASA GES DISC, accessed through NASA Giovanni"

REGIONS = {
    "jordan": "Jordan — country-wide average",
    "aqaba": "Gulf of Aqaba — sea surface at the head of the gulf",
}

# code -> region, file, column, unit, display name, product, provider, note
DATASETS = {
    "T2M": dict(region="jordan", file="jordan_t2m_monthly_2005_2025.csv", column="t2m_c", unit="C",
                name="Air temperature at 2 metres", product="MERRA-2 M2IMNXASM v5.12.4 T2M", provider=MERRA2),
    "PRECTOTCORR": dict(region="jordan", file="jordan_prectotcorr_monthly_2005_2025.csv",
                        column="prectotcorr_mm_day", unit="mm/day",
                        name="Precipitation rate (bias corrected)",
                        product="MERRA-2 M2TMNXFLX v5.12.4 PRECTOTCORR", provider=MERRA2,
                        note="Monthly mean rate in mm/day, not a monthly total."),
    "GWETTOP": dict(region="jordan", file="jordan_gwettop_monthly_2005_2025.csv",
                    column="gwettop_fraction", unit="fraction",
                    name="Surface soil wetness (0 = dry, 1 = saturated)",
                    product="MERRA-2 M2TMNXLND v5.12.4 GWETTOP", provider=MERRA2,
                    note="Unitless relative wetness of the top soil layer, not volumetric water content."),
    "EVAP": dict(region="jordan", file="jordan_evap_monthly_2005_2025.csv", column="evap_mm_day",
                 unit="mm/day", name="Evaporation from the land surface",
                 product="MERRA-2 M2TMNXFLX v5.12.4 EVAP", provider=MERRA2,
                 note="Downloaded in kg m-2 s-1 and converted to mm/day (x 86400); the original column is kept in the file."),
    "SST_NIGHT": dict(region="aqaba", file="aqaba_sst_night_monthly_2005_2025.csv", column="sst_night_c",
                      unit="C", name="Night-time sea surface temperature",
                      product="MODIS-Aqua L3m night SST (11 µm), monthly 4 km, R2019.0",
                      provider="NASA Ocean Biology Processing Group (OB.DAAC), accessed through NASA Giovanni",
                      note="Satellite skin temperature over a few 4 km water pixels. The download does not state "
                           "the unit; values are consistent with degrees Celsius. December 2006 is missing."),
}


def _source(code: str) -> str:
    return f"NASA Giovanni / {DATASETS[code]['product']}"


def variables_for(region: str) -> list[str]:
    return [code for code, info in DATASETS.items() if info["region"] == region]


def load_saved(codes, region: str, start_year: int, end_year: int) -> PowerResult:
    """Monthly series (and day-weighted annual means of complete years) for one region."""
    if region not in REGIONS:
        raise ValueError(f"Unknown saved region: {region!r}")
    codes = list(codes)
    if not codes or any(DATASETS.get(c, {}).get("region") != region for c in codes):
        raise ValueError(f"Saved data for {REGIONS[region]} supports only: {', '.join(variables_for(region))}.")
    if not FIRST_YEAR <= start_year <= end_year <= LAST_YEAR:
        raise ValueError(f"Saved Giovanni data supports years {FIRST_YEAR}–{LAST_YEAR} only.")
    frames = []
    for code in codes:
        info = DATASETS[code]
        raw = pd.read_csv(DATA_DIR / info["file"])
        if "date" not in raw or info["column"] not in raw:
            raise ValueError(f"{info['file']} must contain date and {info['column']} columns.")
        raw["date"] = pd.to_datetime(raw["date"], format="%Y-%m-%d", errors="raise")
        table = pd.DataFrame({"date": raw["date"], "value": raw[info["column"]].astype(float)})
        table = table.loc[table.date.dt.year.between(start_year, end_year)]
        table = table.assign(unit=info["unit"], variable=code, variable_name=info["name"],
                             latitude=None, longitude=None, source=_source(code))
        frames.append(table[TIMESERIES_COLUMNS])
    data = pd.concat(frames, ignore_index=True)
    data["date"] = pd.to_datetime(data["date"])
    used = [DATASETS[c] for c in codes]
    metadata = {
        "source": "; ".join(_source(c) for c in codes),
        "provider": "; ".join(sorted({i["provider"] for i in used})),
        "provider_url": GIOVANNI_URL,
        "dataset_title": "; ".join(i["product"] for i in used),
        "units": {c: DATASETS[c]["unit"] for c in codes},
        "variable_names": {c: DATASETS[c]["name"] for c in codes},
        "variable_notes": {c: DATASETS[c].get("note") for c in codes},
        "temporal_resolution": "monthly", "spatial_scope": "area_average",
        "spatial_description": REGIONS[region],
        "delivery": "Saved file (not live data)", "download_date": DOWNLOAD_DATE,
        "files": {c: "data/processed/" + DATASETS[c]["file"] for c in codes},
        "missing_value_handling": "Missing months remain gaps; no interpolation or zero filling.",
        "provenance_note": "Raw Giovanni exports are included in data/raw/giovanni/ for EVAP and SST only; "
                           "those for T2M, PRECTOTCORR and GWETTOP are not available. DATA_SOURCES.md "
                           "gives the reproduction URLs and every processing step.",
        "is_synthetic": False,
    }
    return PowerResult(data, _annual(data), metadata)


def _annual(data: pd.DataFrame) -> pd.DataFrame:
    """Annual mean of each calendar year with all 12 months present, weighting
    each month by its number of days. Incomplete years are left out."""
    rows = []
    for (code, year), group in data.dropna(subset=["value"]).groupby(["variable", data.date.dt.year]):
        if len(group) == 12:
            days = group.date.dt.days_in_month
            rows.append({**group.iloc[0][ANNUAL_COLUMNS[2:]].to_dict(), "year": int(year),
                         "value": float((group.value * days).sum() / days.sum())})
    return pd.DataFrame(rows, columns=ANNUAL_COLUMNS)
