"""Presence-only composition analysis for the station protocol (section 5.3).
Usage: python scripts/station_composition_check.py  (after the download step). Reads only
DATE, the TEMP missing code and TEMP_ATTRIBUTES of already-downloaded GSOD
files. No temperature value is used. Station signals below are SYNTHETIC."""
import numpy as np, pandas as pd

# Same valid-day rule and panel as the validation script.
from validate_stations import PANEL, load_gsod

months = pd.period_range("2005-01", "2024-12", freq="M")
V = {}
for name, (sid, _, _) in PANEL.items():
    d = load_gsod(sid)
    days = d.index[d["valid"]].to_period("M").value_counts().reindex(months, fill_value=0)
    V[name] = (days >= 25).to_numpy()
V = pd.DataFrame(V, index=months)
t = np.array([p.year + (p.month - 0.5) / 12 for p in months])
mon = np.array([p.month for p in months])
yr = np.array([p.year for p in months])

def slope_of(signal, mask, baseline="own", min_st=3):
    """signal: months x stations array. Returns OLS slope per year of annual
    means of the composite (years with >= 11 composite months; None if gaps)."""
    A = np.where(mask, signal, np.nan)
    base = mask if baseline == "own" else np.repeat(mask.all(1, keepdims=True), mask.shape[1], 1)
    for j in range(A.shape[1]):
        for m in range(1, 13):
            sel = mon == m
            c = np.nanmean(np.where(base[sel, j], signal[sel, j], np.nan))
            A[sel, j] -= c
    n = mask.sum(1)
    comp = np.where(n >= min_st, np.nanmean(A, 1), np.nan)
    s = pd.Series(comp).groupby(yr)
    ann = s.mean()[s.count() >= 11]
    gaps = len(ann) < 20
    x = ann.index.to_numpy(float)
    return np.polyfit(x, ann.to_numpy(), 1)[0], len(ann), gaps

M = V.to_numpy()
full = np.ones_like(M, bool)
cols = list(V.columns)
print("Response of the composite slope to SYNTHETIC station trends (1 unit/yr), presence pattern of 2005-2024")
print("Expected with complete data: common trend -> 1.000; trend at one station only -> 0.250")
for label, base, mask, mn in [("primary (own-month offsets, >=3 of 4)", "own", M, 3),
                              ("common-baseline offsets, >=3 of 4", "common", M, 3),
                              ("complete-4 months only", "own", M & M.all(1, keepdims=True), 4)]:
    common = slope_of(np.tile(t[:, None], (1, 4)), mask, base, mn)
    row = [f"common {common[0]:.4f} (years {common[1]}, gaps {common[2]})"]
    for j, c in enumerate(cols):
        sig = np.zeros_like(M, float); sig[:, j] = t
        row.append(f"{c} {slope_of(sig, mask, base, mn)[0]:.4f}")
    print(f"  {label}: " + "; ".join(row))

# Null spread of (primary slope - complete-4 slope), iid station noise of unit SD.
rng = np.random.default_rng(20261115)
diff = []
for _ in range(2000):
    e = rng.normal(size=M.shape)
    p = slope_of(e, M, "own", 3)[0]
    c = slope_of(e, M & M.all(1, keepdims=True), "own", 4)[0]
    diff.append(p - c)
diff = np.array(diff) * 10
print(f"Null SD of (primary - complete-4) slope, iid monthly station noise SD=1: {diff.std():.4f} per decade "
      f"(95% range {np.percentile(diff, 2.5):.4f} to {np.percentile(diff, 97.5):.4f})")
