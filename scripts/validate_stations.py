"""Station temperature cross-check (docs/STATION_VALIDATION_PROTOCOL.md).

Usage (from the repository root):

    python scripts/validate_stations.py download   # raw files into data/raw/stations/
                                                   # (add --candidates for the panel-selection check)
    python scripts/validate_stations.py blockers   # checks A2, A3, A10; writes blockers.json
    python scripts/validate_stations.py analyze    # runs the protocol if no blocker failed

Raw GSOD/GHCN-M/POWER files stay in data/raw/stations/ (git-ignored): GSOD
non-US data are distributed under WMO Resolution 40 and must not be
redistributed. Outputs written to docs/validation/ contain only
station-minus-MERRA-2 differences and summary statistics.

The trend test is EarthTrend's own analyze_timeseries, unchanged.
"""
from __future__ import annotations

import io
import json
import sys
import tarfile
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from earthtrend.analysis import analyze_timeseries  # noqa: E402
from earthtrend.data import power_client  # noqa: E402

RAW = ROOT / "data/raw/stations"
OUT = ROOT / "docs/validation"
YEARS = range(2005, 2025)
B = 0.24  # C/decade, protocol section 9
POWER_DAILY = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_HOURLY = "https://power.larc.nasa.gov/api/temporal/hourly/point"
GSOD_URL = "https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/{year}/{id}.csv"
GHCNM_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/v4/ghcnm.tavg.latest.{kind}.tar.gz"

# Protocol 4.1: fixed primary panel (GSOD USAF+WBAN, isd-history coordinates).
PANEL = {
    "Marka": ("40270099999", 31.973, 35.992),
    "Queen Alia": ("40272099999", 31.723, 35.993),
    "Aqaba": ("40340099999", 29.612, 35.018),
    "King Hussein": ("40265099999", 32.356, 36.259),
}
# Other GSOD candidates, used only by the presence-only panel-selection check (3.3).
CANDIDATES = {"Prince Hasan": "40260099999", "Irbid": "40255099999",
              "Ma'an": "40310099999", "Ghor Safi": "40296099999"}
# Protocol 8.3 S4: GHCN-M v4 panel (inventory coordinates).
GHCNM = {
    "King Hussein": ("JOM00040265", 32.356, 36.259),
    "Ma'an": ("JOM00040310", 30.167, 35.783),
    "Ghor Safi": ("JOM00040296", 31.033, 35.467),
}
A10_DATES = [f"{y}{m}15" for y in (2010, 2020) for m in ("01", "04", "07", "10")]


class DownloadError(RuntimeError):
    """A required file could not be downloaded."""


def _get(url, params=None, retries=3, allow_missing=False):
    """Return the response. HTTP 404 raises unless allow_missing (then None);
    any other failure raises after the retries, naming the URL and status."""
    problem = "no attempt made"
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=180)
        except requests.RequestException as error:  # timeout, connection reset
            problem = f"{type(error).__name__}: {error}"
        else:
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                if allow_missing:
                    return None
                raise DownloadError(f"Not found (HTTP 404): {r.url}")
            problem, url = f"HTTP {r.status_code}", r.url
        time.sleep(5 * (attempt + 1))
    raise DownloadError(f"Download failed ({problem}) after {retries} attempts: {url}")


def influence(tested, change, half_width):
    """Protocol 8.2: influential if the slope moves by more than half the
    primary interval half-width. None when the leave-one-out test was withheld."""
    if not tested or change is None or half_width is None:
        return None
    return abs(change) > half_width / 2


def _power_daily_params(lat, lon, start, end):
    return {"parameters": "T2M", "community": "ag", "latitude": lat, "longitude": lon,
            "start": start, "end": end, "time-standard": "utc", "format": "JSON"}


def _slug(name):
    return name.lower().replace(" ", "_").replace("'", "")


# ----------------------------------------------------------------- download
def download():
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log = {"downloaded_utc": stamp, "files": []}
    (RAW / "gsod").mkdir(parents=True, exist_ok=True)
    (RAW / "power").mkdir(parents=True, exist_ok=True)
    (RAW / "ghcnm").mkdir(parents=True, exist_ok=True)
    gsod_ids = [sid for sid, _, _ in PANEL.values()]
    if "--candidates" in sys.argv:  # only for scripts/station_presence_check.py
        gsod_ids += list(CANDIDATES.values())
    for sid in gsod_ids:
        for y in YEARS:
            path = RAW / "gsod" / f"{y}_{sid}.csv"
            if not path.exists():
                r = _get(GSOD_URL.format(year=y, id=sid), allow_missing=True)
                if r is None:  # a station-year with no file is expected and recorded
                    log["files"].append({"file": path.name, "status": "absent at source"})
                    continue
                path.write_bytes(r.content)
            log["files"].append({"file": path.name, "status": "ok"})
    points = {**{n: (lat, lon) for n, (_, lat, lon) in PANEL.items()},
              **{n: (lat, lon) for n, (_, lat, lon) in GHCNM.items()}}
    for name, (lat, lon) in points.items():
        path = RAW / "power" / f"daily_utc_{_slug(name)}.json"
        if not path.exists():  # one request per location (docs warn against repeats)
            path.write_bytes(_get(POWER_DAILY, _power_daily_params(lat, lon, "20050101", "20241231")).content)
        mpath = RAW / "power" / f"monthly_{_slug(name)}.json"
        if not mpath.exists() and name in PANEL:
            payload = power_client.fetch_monthly_point(["T2M"], lat, lon, 2005, 2024)
            mpath.write_text(json.dumps(payload))
    lat, lon = PANEL["Marka"][1:]
    for d in A10_DATES:
        path = RAW / "power" / f"hourly_utc_marka_{d}.json"
        if not path.exists():
            params = {**_power_daily_params(lat, lon, d, d)}
            path.write_bytes(_get(POWER_HOURLY, params).content)
    for kind in ("qcu", "qcf"):
        path = RAW / "ghcnm" / f"{kind}_JO.dat"
        if not path.exists():
            r = _get(GHCNM_URL.format(kind=kind))
            with tarfile.open(fileobj=io.BytesIO(r.content)) as tar:
                member = next(m for m in tar.getmembers() if m.name.endswith(".dat"))
                lines = tar.extractfile(member).read().decode().splitlines()
            path.write_text("\n".join(l for l in lines if l.startswith("JO")) + "\n")
            log["files"].append({"file": path.name, "status": "ok", "source_member": member.name})
    (RAW / "download_log.json").write_text(json.dumps(log, indent=1))
    print(f"Downloaded into {RAW}")


# ----------------------------------------------------------------- loaders
def load_gsod(sid):
    parts = [pd.read_csv(p, usecols=["DATE", "TEMP", "TEMP_ATTRIBUTES"])
             for y in YEARS if (p := RAW / "gsod" / f"{y}_{sid}.csv").exists()]
    d = pd.concat(parts)
    d["date"] = pd.to_datetime(d["DATE"])
    d["valid"] = (d["TEMP"] != 9999.9) & (d["TEMP_ATTRIBUTES"] >= 4)
    d["temp_c"] = np.where(d["valid"], (d["TEMP"] - 32) * 5 / 9, np.nan)  # A2: tenths of F
    return d.set_index("date")


def load_power_daily(name):
    payload = json.loads((RAW / "power" / f"daily_utc_{_slug(name)}.json").read_text())
    header = payload["header"]
    fill = float(header["fill_value"])
    raw = payload["properties"]["parameter"]["T2M"]
    s = pd.Series({pd.Timestamp(k): (np.nan if v is None or float(v) == fill else float(v))
                   for k, v in raw.items()}).sort_index()
    if not s.dropna().between(-40, 60).all():
        raise ValueError(f"POWER T2M outside -40..60 C for {name}")
    if payload["parameters"]["T2M"]["units"] != "C":
        raise ValueError("POWER T2M units are not C")
    return s, header, payload["geometry"]["coordinates"]


def load_power_monthly(name):
    payload = json.loads((RAW / "power" / f"monthly_{_slug(name)}.json").read_text())
    data = power_client.parse_monthly_response(payload).data
    return data.set_index("date")["value"]


def load_ghcnm(kind):
    rows = []
    for line in (RAW / "ghcnm" / f"{kind}_JO.dat").read_text().splitlines():
        if len(line) < 115 or line[15:19] != "TAVG":
            continue
        sid, year = line[:11], int(line[11:15])
        for m in range(12):
            chunk = line[19 + 8 * m: 27 + 8 * m]
            value, qc = int(chunk[:5]), chunk[6]
            ok = value != -9999 and qc == " "
            rows.append((sid, pd.Timestamp(year=year, month=m + 1, day=1), value / 100 if ok else np.nan))
    return pd.DataFrame(rows, columns=["id", "date", "tavg"]).pivot(index="date", columns="id", values="tavg")


# ----------------------------------------------------------------- blockers
def blockers():
    result = {"checked_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    # A2: documented units plus a physical plausibility check on July means.
    july = {n: float(load_gsod(sid).query("valid").loc[lambda d: d.index.month == 7, "TEMP"].mean())
            for n, (sid, _, _) in PANEL.items()}
    result["A2"] = {
        "documentation": "GSOD readme (ncei.noaa.gov/data/global-summary-of-the-day/doc/readme.txt, 10/28/2020): "
                         "csv header 'TEMP - Mean temperature (.1 Fahrenheit)', missing 9999.9, GMT day 0000Z-2359Z.",
        "july_mean_TEMP_raw_units": july,
        "plausibility": "Jordan July means must exceed 60 if in F (about 15.6 C); Celsius values would be 20-35.",
        "resolved": all(v > 60 for v in july.values()),
    }
    # A3: header.sources of every daily response covering 2005-2024.
    sources = {}
    for name in list(PANEL) + [n for n in GHCNM if n not in PANEL]:
        _, header, _ = load_power_daily(name)
        sources[name] = {"sources": header.get("sources"), "time_standard": header.get("time_standard"),
                         "start": header.get("start"), "end": header.get("end"),
                         "api_version": header.get("api", {}).get("version")}
    result["A3"] = {
        "evidence": "header.sources lists the products present in the requested span "
                    "(probe 2026-11-15: 20260801-20261110 returned ['MERRA2', 'GEOSIT']; 20241201-20241231 ['MERRA2']).",
        "responses": sources,
        "resolved": all(v["sources"] == ["MERRA2"] and v["start"] == "20050101" and v["end"] == "20241231"
                        for v in sources.values()),
    }
    # A10: daily UTC value vs mean of 24 hourly UTC values (protocol section 11).
    daily, _, _ = load_power_daily("Marka")
    checks = []
    for d in A10_DATES:
        payload = json.loads((RAW / "power" / f"hourly_utc_marka_{d}.json").read_text())
        hourly = [v for k, v in payload["properties"]["parameter"]["T2M"].items() if k.startswith(d)]
        checks.append({"date": d, "daily_utc": float(daily[pd.Timestamp(d)]), "hourly_mean": float(np.mean(hourly)),
                       "n_hours": len(hourly), "hourly_time_standard": payload["header"].get("time_standard")})
    for c in checks:
        c["abs_diff"] = abs(c["daily_utc"] - c["hourly_mean"])
    result["A10"] = {"checks": checks, "tolerance_C": 0.01,
                     "resolved": all(c["n_hours"] == 24 and c["abs_diff"] <= 0.01 + 1e-9 for c in checks)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "blockers.json").write_text(json.dumps(result, indent=1))
    for k in ("A2", "A3", "A10"):
        print(k, "resolved" if result[k]["resolved"] else "NOT resolved")
    return result


# ----------------------------------------------------------------- analysis helpers
def app_test(series: pd.Series):
    """EarthTrend's test on a monthly series (index = month start)."""
    s = series.dropna()
    frame = pd.DataFrame({"date": s.index, "value": s.to_numpy()})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = analyze_timeseries(frame, {"unit": "C", "temporal_resolution": "monthly"})
    reg = r.regression
    tested = reg is not None and reg.p_value is not None
    return {
        "status": r.status,
        "years": r.diagnostics.get("annual_anomaly_years"),
        "slope_per_decade": None if reg is None else 10 * reg.slope,
        "ci_per_decade": None if not tested or reg.confidence_interval is None else [10 * v for v in reg.confidence_interval],
        "p_value": reg.p_value if tested else None,
        "significant": reg.significant if tested else None,
        "tested": tested,
        "notes": [w for w in r.warnings if "withheld" in w.lower()],
    }


def annual_ols(series: pd.Series):
    """Descriptive OLS slope (C/decade) of annual means of years with >= 11 months."""
    s = series.dropna()
    g = s.groupby(s.index.year)
    ann = g.mean()[g.count() >= 11]
    if len(ann) < 3:
        return None, len(ann)
    return 10 * float(np.polyfit(ann.index.to_numpy(float), ann.to_numpy(), 1)[0]), len(ann)


def pettitt(x):
    x = np.asarray(x, float)
    n = len(x)
    u = [sum(np.sign(x[j] - x[i]) for i in range(t + 1) for j in range(t + 1, n)) for t in range(n - 1)]
    k = int(np.argmax(np.abs(u)))
    K = abs(u[k])
    return {"change_after_index": k, "K": float(K), "p_approx": float(min(1.0, 2 * np.exp(-6 * K ** 2 / (n ** 3 + n ** 2))))}


def verdict(ci):
    if ci is None:
        return "Inconclusive"
    lo, hi = ci
    inside = -B <= lo and hi <= B
    has0 = lo <= 0 <= hi
    if inside and has0:
        return "No difference beyond tolerance (four sites)"
    if inside:
        return "Small difference within tolerance (four sites)"
    if lo > B or hi < -B:
        return "Difference beyond tolerance (four sites)"
    if not has0:
        return "Difference detected, size uncertain (four sites)"
    return "Inconclusive"


def composite(A: pd.DataFrame, min_st):
    n = A.notna().sum(axis=1)
    return A.mean(axis=1).where(n >= min_st)


def offsets(D: pd.DataFrame):
    return D - D.groupby(D.index.month).transform("mean")


def composition_weights(mask: pd.DataFrame, min_st):
    """Protocol 5.3: slope response of the composite to synthetic linear trends (presence only)."""
    t = pd.Series(mask.index.year + (mask.index.month - 0.5) / 12, index=mask.index)
    def resp(cols):
        sig = pd.DataFrame({c: (t if c in cols else 0.0) for c in mask.columns}).where(mask)
        comp = composite(offsets(sig), min_st)
        g = comp.dropna().groupby(comp.dropna().index.year)
        ann = g.mean()[g.count() >= 11]
        return float(np.polyfit(ann.index.to_numpy(float), ann.to_numpy(), 1)[0])
    return {"common": resp(list(mask.columns)), **{c: resp([c]) for c in mask.columns}}


# ----------------------------------------------------------------- analysis
def analyze():
    bl = json.loads((OUT / "blockers.json").read_text())
    failed = [k for k in ("A2", "A3", "A10") if not bl[k]["resolved"]]
    if failed:
        print("Not run: assumption unresolved:", failed)
        (OUT / "results.json").write_text(json.dumps({"outcome": "Not run: assumption unresolved", "blockers": failed}, indent=1))
        return
    months = pd.date_range("2005-01-01", "2024-12-01", freq="MS")
    station_m, grid_m, valid_m, obs = {}, {}, {}, {}
    geometry = {}
    for name, (sid, _, _) in PANEL.items():
        g = load_gsod(sid)
        p, _, geom = load_power_daily(name)
        geometry[name] = geom
        both = pd.DataFrame({"st": g["temp_c"], "gr": p}).dropna()  # day-matched UTC days
        key = both.index.to_period("M").to_timestamp()
        agg = both.groupby(key).agg(st=("st", "mean"), gr=("gr", "mean"), n=("st", "size")).reindex(months)
        ok = agg["n"] >= 25
        station_m[name], grid_m[name], valid_m[name] = agg["st"].where(ok), agg["gr"].where(ok), ok.fillna(False)
        obs[name] = g.loc[g["valid"], "TEMP_ATTRIBUTES"].groupby(g.loc[g["valid"]].index.year).median().reindex(YEARS)
    D = pd.DataFrame(station_m) - pd.DataFrame(grid_m)
    A = offsets(D)
    mask = pd.DataFrame(valid_m).astype(bool)
    res = {"protocol_sha256_at_freeze": "3219d63c639bf676f2a8c043e28b66c616de71efac3c3f9d8221acb9f1705427",
           "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "blockers": "A2, A3, A10 resolved",
           "power_returned_geometry": geometry}
    counts = mask.sum(axis=1)
    res["final_mask"] = {"months_4": int((counts == 4).sum()), "months_3": int((counts == 3).sum()),
                         "months_lt3": int((counts < 3).sum()),
                         "valid_months": {c: int(mask[c].sum()) for c in mask},
                         "composition_weights": composition_weights(mask, 3)}
    # Primary.
    primary_series = composite(A, 3)
    primary = app_test(primary_series)
    primary["outcome"] = verdict(primary["ci_per_decade"]) if primary["tested"] else "Inconclusive"
    if primary["years"] is not None and primary["years"] < 15:
        primary["outcome"] = "Inconclusive"
    primary["annual_ols_per_decade"], _ = annual_ols(primary_series)
    res["primary"] = primary
    # Station level (section 6).
    stations = {}
    others_mean = lambda k: A.drop(columns=k).where(mask.all(axis=1), axis=0).mean(axis=1)
    for c in A:
        t = app_test(A[c])
        ols, ny = annual_ols(A[c])
        s = A[c].dropna()
        gy = s.groupby(s.index.year)
        ann = gy.mean()[gy.count() >= 11]
        pt = pettitt(ann.to_numpy())
        pt["candidate_year"] = int(ann.index[pt.pop("change_after_index")] + 1) if len(ann) > 1 else None
        gk = (A[c] - others_mean(c)).where(mask.all(axis=1)).dropna()
        stations[c] = {**t, "annual_ols_per_decade": ols, "usable_years": ny, "valid_months": int(mask[c].sum()),
                       "median_obs_per_day_by_year": {int(k): (None if pd.isna(v) else float(v)) for k, v in obs[c].items()},
                       "pettitt_annual": pt,
                       "g_k": {"min": float(gk.min()), "max": float(gk.max()), "mean": float(gk.mean()),
                               "sd": float(gk.std()), "implied_bias_bound_per_decade": 0.027 * float(gk.abs().max())},
                       "grid_elevation_m": geometry[c][2] if len(geometry[c]) > 2 else None}
    res["stations"] = stations
    slopes = {c: (v["slope_per_decade"] if v["tested"] else v["annual_ols_per_decade"]) for c, v in stations.items()}
    tested_excl0 = {c: v["ci_per_decade"] for c, v in stations.items()
                    if v["tested"] and not (v["ci_per_decade"][0] <= 0 <= v["ci_per_decade"][1])}
    signs = {np.sign(ci[0]) for ci in tested_excl0.values()}
    res["disagreement"] = {"slope_range": [min(slopes.values()), max(slopes.values())],
                           "n_positive": sum(v > 0 for v in slopes.values()), "n_negative": sum(v < 0 for v in slopes.values()),
                           "tested_excluding_zero": list(tested_excl0), "stations_disagree": len(signs) > 1}
    # C4 (8.1).
    c4_series = composite(A.where(mask.all(axis=1), axis=0), 4)
    c4_slope, c4_years = annual_ols(c4_series)
    resid = primary_series.dropna()
    tt = resid.index.year + (resid.index.month - 0.5) / 12
    sigma_m = float(np.std(resid - np.polyval(np.polyfit(tt, resid, 1), tt), ddof=2))
    delta = primary["annual_ols_per_decade"] - c4_slope
    sd_delta = 0.034 * sigma_m
    res["C4"] = {"app": app_test(c4_series), "annual_ols_per_decade": c4_slope, "usable_years": c4_years,
                 "delta_per_decade": delta, "sigma_m": sigma_m, "sd_delta": sd_delta,
                 "within_sampling_spread": abs(delta) <= 2 * sd_delta}
    # Leave-one-out (8.2).
    half = None if primary["ci_per_decade"] is None else (primary["ci_per_decade"][1] - primary["ci_per_decade"][0]) / 2
    loo = {}
    for c in A:
        t = app_test(composite(A.drop(columns=c), 2))
        change = None if t["slope_per_decade"] is None else t["slope_per_decade"] - primary["slope_per_decade"]
        loo[c] = {**t, "change_from_primary": change,
                  "influential": influence(t["tested"], change, half)}
    res["leave_one_out"] = loo
    # S2 Aqaba split.
    aq = A["Aqaba"].dropna()
    res["S2_aqaba_split"] = {"mean_2005_2017": float(aq[aq.index.year <= 2017].mean()),
                             "mean_2018_2024": float(aq[aq.index.year >= 2018].mean())}
    res["S2_aqaba_split"]["difference"] = res["S2_aqaba_split"]["mean_2018_2024"] - res["S2_aqaba_split"]["mean_2005_2017"]
    # S3 POWER monthly (local solar day, full calendar month).
    D3 = pd.DataFrame(station_m) - pd.DataFrame({n: load_power_monthly(n).reindex(months) for n in PANEL})
    res["S3_power_monthly"] = app_test(composite(offsets(D3), 3))
    # S4 GHCN-M panel, never merged with GSOD.
    s4 = {}
    for kind in ("qcu", "qcf"):
        tav = load_ghcnm(kind).reindex(months)
        Dg = {}
        for name, (gid, _, _) in GHCNM.items():
            p, _, _ = load_power_daily(name)
            full = p.groupby(p.index.to_period("M").to_timestamp()).mean().reindex(months)
            Dg[name] = tav[gid] - full if gid in tav else pd.Series(np.nan, index=months)
        Dg = pd.DataFrame(Dg)
        s4[kind] = {**app_test(composite(offsets(Dg), 2)), "valid_months": {c: int(Dg[c].notna().sum()) for c in Dg}}
    res["S4_ghcnm"] = s4
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(res, indent=1, default=float))
    figures(A, primary_series)
    print(json.dumps({"primary": primary, "C4": res["C4"]}, indent=1, default=float))


def figures(A, primary_series):
    import plotly.graph_objects as go
    fig = go.Figure()
    for c in A:
        s = A[c].dropna()
        fig.add_scatter(x=s.index, y=s, mode="lines", name=c, opacity=0.5)
    fig.add_scatter(x=primary_series.index, y=primary_series, mode="lines", name="Composite (>= 3 of 4)",
                    line={"color": "black", "width": 2})
    fig.update_layout(title="Station minus MERRA-2 (NASA POWER) T2M anomaly, 2005-2024",
                      yaxis_title="Difference anomaly (C)", xaxis_title="Month")
    fig.write_html(OUT / "station_minus_merra2.html", include_plotlyjs="cdn")


if __name__ == "__main__":
    {"download": download, "blockers": blockers, "analyze": analyze}[sys.argv[1]]()
