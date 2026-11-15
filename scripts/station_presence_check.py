"""Presence-only feasibility for the station protocol (section 3.3, panel
selection). Reads ONLY the DATE, TEMP missing flag (9999.9) and
TEMP_ATTRIBUTES (observation count) columns of downloaded GSOD files. No
temperature values are used or printed.

Usage: python scripts/station_presence_check.py  (after
`python scripts/validate_stations.py download --candidates`)"""
import pandas as pd

# The valid-day rule and the station IDs come from the validation script, so
# this check always describes the analysis that is actually run.
from validate_stations import CANDIDATES, PANEL, YEARS, load_gsod

STATIONS = {**{name: sid for name, (sid, _, _) in PANEL.items()}, **CANDIDATES}
months = pd.period_range("2005-01", "2024-12", freq="M")
valid, obs = {}, {}
for name, sid in STATIONS.items():
    d = load_gsod(sid)
    ok = d[d["valid"]]
    days = ok.groupby(ok.index.to_period("M")).size().reindex(months, fill_value=0)
    valid[name] = days >= 25
    obs[name] = ok.groupby(ok.index.year)["TEMP_ATTRIBUTES"].median().reindex(YEARS)

V = pd.DataFrame(valid)
usable = lambda m: (m.groupby(m.index.year).sum() >= 11)
print("Individual usable years (2005-2024):")
for c in V:
    print(f"  {c:13s} {usable(V[c]).sum():2d}")
cand = [c for c in V if usable(V[c]).sum() >= 15]
print("Candidates (>=15 usable years):", cand)
bal = V[cand].all(axis=1)
print("Balanced panel usable years:", usable(bal).sum(), "of 20;",
      "balanced valid months:", bal.sum())
print("Balanced usable-year list:", [y for y, ok in usable(bal).items() if ok])
print("Median observations per valid day, by year:")
print(pd.DataFrame(obs).loc[:, cand].astype("Int64").to_string())

from itertools import combinations
def runs(ok):
    best = cur = 0; start = end = None; s = None
    for y, v in ok.items():
        if v:
            cur += 1; s = y if cur == 1 else s
            if cur > best: best, start, end = cur, s, y
        else:
            cur = 0
    return best, start, end
print("\nSubset / rule -> usable years, gap-free?, longest gap-free run")
for k in (4, 3, 2):
    for sub in combinations(cand, k):
        u = usable(V[list(sub)].all(axis=1))
        print(f"  all of {sub}: {u.sum()} yrs, gap-free={u.all() or (u.sum()==runs(u)[0])}, run={runs(u)}")
for k in (3, 2):
    u = usable(V[cand].sum(axis=1) >= k)
    print(f"  at least {k} of 4 panel stations: {u.sum()} yrs, run={runs(u)}")
for c in cand:
    u = usable(V[c]); print(f"  {c} alone: {u.sum()} yrs, run={runs(u)}, missing={[y for y,v in u.items() if not v]}")

cnt = V[cand].sum(axis=1)
print("\nPanel months by number of valid stations:", cnt.value_counts().sort_index().to_dict())
three = V[cand][cnt == 3]
print("Missing station in 3-of-4 months:", (~three).sum().to_dict())
print("3-of-4 months per year:", three.groupby(three.index.year).size().to_dict())
for c in cand:
    rest = [s for s in cand if s != c]
    u = usable(V[rest].sum(axis=1) >= 2)
    print(f"  leave out {c}: >=2 of 3 -> {u.sum()} yrs, run={runs(u)}")
