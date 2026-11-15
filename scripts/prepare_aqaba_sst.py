"""Rebuild data/processed/aqaba_sst_night_monthly_2005_2025.csv from the raw Giovanni export.

Usage: python scripts/prepare_aqaba_sst.py path/to/g4.areaAvgTimeSeries.MODISA_L3m_NSST_Monthly_4km_R2019_0_sst....csv

Giovanni stamps each MODIS-Aqua monthly file with the start of its first data
day, which can fall on the evening before the month begins (for example
"2004-12-31 12:10:01" is January 2005, "2020-09-02 19:53:07" is September 2020).
The month is therefore the calendar month of (timestamp + 1 day). Values are
not changed, filled or rounded; months without a file stay absent.
"""
import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data/processed/aqaba_sst_night_monthly_2005_2025.csv"


def convert(raw_path: str) -> pd.DataFrame:
    raw = pd.read_csv(raw_path, skiprows=8)  # 8 Giovanni metadata lines above the table
    raw.columns = ["time", "sst_night_c"]
    stamps = pd.to_datetime(raw["time"].str.strip(), format="%Y-%m-%d %H:%M:%S")
    if (raw["sst_night_c"] == -32767).any():
        raise ValueError("Fill values present; handle them explicitly before saving.")
    table = pd.DataFrame({
        "date": (stamps + pd.Timedelta(days=1)).dt.to_period("M").dt.to_timestamp(),
        "sst_night_c": raw["sst_night_c"],
    })
    table = table[table["date"].between("2005-01-01", "2025-12-01")]
    if table["date"].duplicated().any():
        raise ValueError("Two files map to the same month; inspect the raw export.")
    return table.sort_values("date")


if __name__ == "__main__":
    convert(sys.argv[1]).to_csv(OUT, index=False, date_format="%Y-%m-%d")
    print(f"Wrote {OUT}")
