"""SYNTHETIC design check for the station protocol: typical 95% interval
half-width of the app's trend test, in units of the annual noise SD.
No station data used (protocol section 9.4).

Usage: python scripts/station_design_check.py"""
import sys, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.simplefilter("ignore")
import numpy as np, pandas as pd
from earthtrend.analysis import analyze_timeseries

def ar1(rng, n, phi, burn=200):
    e = rng.normal(size=n + burn); s = np.zeros(n + burn)
    for t in range(1, n + burn):
        s[t] = phi * s[t - 1] + e[t]
    s = s[-n:]
    return s / s.std(ddof=0) if phi else e[-n:]

for n in (15, 20):
    for phi in (0.0, 0.3, 0.5):
        rng = np.random.default_rng(777)
        hw, wh = [], 0
        for _ in range(400):
            y = ar1(rng, n, phi)
            y = y / y.std(ddof=1)  # unit sample SD
            f = pd.DataFrame({"date": pd.date_range("2005-07-01", periods=n, freq="12MS"), "value": y})
            r = analyze_timeseries(f, {"unit": "C", "temporal_resolution": "annual"}).regression
            if r.p_value is None:
                wh += 1; continue
            lo, hi = r.confidence_interval
            hw.append((hi - lo) / 2 * 10)  # per decade, in SD units
        hw = np.array(hw)
        print(f"n={n} phi={phi}: median half-width {np.median(hw):.3f} SD/decade "
              f"(IQR {np.percentile(hw,25):.3f}-{np.percentile(hw,75):.3f}); withheld {wh/400:.0%}; "
              f"max SD for half-width<=0.24 at median: {0.24/np.median(hw):.3f} C")
