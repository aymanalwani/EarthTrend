"""Rebuild data/processed/jordan_evap_monthly_2005_2025.csv from the raw Giovanni export.

Usage: python scripts/prepare_jordan_evap.py [path/to/g4.areaAvgTimeSeries.M2TMNXFLX_5_12_4_EVAP....csv]
(default: data/raw/giovanni/g4.areaAvgTimeSeries.M2TMNXFLX_5_12_4_EVAP.20050101-20251231.180W_90S_180E_90N.csv)

The original kg m-2 s-1 column is kept unchanged; evap_mm_day = value * 86400
(1 kg m-2 of water = 1 mm), rounded to 6 decimals. No filling or sorting.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/giovanni/g4.areaAvgTimeSeries.M2TMNXFLX_5_12_4_EVAP.20050101-20251231.180W_90S_180E_90N.csv"
OUT = ROOT / "data/processed/jordan_evap_monthly_2005_2025.csv"
FILL = 1e15


def convert(raw_path) -> pd.DataFrame:
    raw = pd.read_csv(raw_path, skiprows=8)  # 8 Giovanni metadata lines above the table
    raw.columns = ["time", "evap_kg_m2_s"]
    if (raw["evap_kg_m2_s"] >= FILL).any():
        raise ValueError("Fill values present; handle them explicitly before saving.")
    return pd.DataFrame({
        "date": pd.to_datetime(raw["time"].str.strip()).dt.strftime("%Y-%m-%d"),
        "evap_kg_m2_s": raw["evap_kg_m2_s"],
        "evap_mm_day": (raw["evap_kg_m2_s"] * 86400).round(6),
    })


if __name__ == "__main__":
    table = convert(sys.argv[1] if len(sys.argv) > 1 else RAW)
    table.to_csv(OUT, index=False)
    print(f"Wrote {len(table)} rows to {OUT}")
