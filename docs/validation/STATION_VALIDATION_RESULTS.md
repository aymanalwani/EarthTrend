# Station temperature cross-check: results

- **Protocol:** docs/STATION_VALIDATION_PROTOCOL.md, revision 3, frozen
  2026-11-15T06:38Z (SHA-256 3219d63c…1705427).
- **Run:** 2026-11-15, by `python scripts/validate_stations.py analyze`.
- **Correction (2026-11-15, after code review).** The leave-one-out run
  without King Hussein was withheld by the app's dependence check, so it was
  never tested. It had been labelled "not influential"; it is now "n/a
  (withheld)". The data were downloaded again and the analysis re-run: the
  primary result and every other number are identical.
- **Machine-readable outputs:** docs/validation/results.json and
  docs/validation/blockers.json.
- **Figure:** docs/validation/station_minus_merra2.html.

## Outcome

**Inconclusive.**

At four Jordanian GSOD stations (Amman Marka, Queen Alia, Aqaba, King Hussein),
the trend of station minus MERRA-2 2 m temperature anomalies for 2005-2024 is
**+0.08 C/decade**, with a 95% union interval of **-0.28 to +0.44 C/decade**
(p = 0.59; 20 years).

The interval contains zero. It also extends beyond the +-0.24 C/decade
tolerance, so the station record cannot confirm or contradict the MERRA-2 trend
at that tolerance. The protocol predicted this outcome (section 9.4).

What this result does not mean:

- It is not evidence that MERRA-2 and the stations agree.
- It is not evidence that they disagree.
- It says nothing about the Jordan area-average trend, other variables or the
  cause of warming.

Complete-four-station check (C4): the descriptive slope is +0.09 C/decade over
15 years with gaps, so the app withholds inference. It agrees with the primary
within sampling spread (Delta = -0.009, 2 x SD = 0.018 C/decade).

## Blockers (protocol section 11)

| ID | Evidence | Result |
|---|---|---|
| A2 GSOD units | The GSOD readme lists the CSV header "TEMP - Mean temperature (.1 Fahrenheit)", missing 9999.9, GMT day. July station means in the raw files are 79-94, consistent with F only | Resolved |
| A3 POWER source | The daily API header `sources` lists the products in the requested span. A probe of 2026-08-01 to 2026-11-10 returned `['MERRA2', 'GEOSIT']`. All six 2005-01-01 to 2024-12-31 station responses returned `['MERRA2']` only | Resolved: all months are MERRA-2 |
| A10 POWER daily UTC | On 8 fixed dates at the Marka coordinates, the daily UTC value matched the mean of the 24 hourly UTC values within 0.0004-0.0042 C (tolerance 0.01) | Resolved |

## Data actually used

| Item | Value |
|---|---|
| Valid station-months | Marka 240, Queen Alia 228, Aqaba 240, King Hussein 219 |
| Composite months | 207 with 4 stations, 33 with 3, 0 dropped |
| Composition weights (final mask) | common trend 0.9993; Marka 0.255, Queen Alia 0.254, Aqaba 0.255, King Hussein 0.235 |
| POWER grid-cell elevation vs station elevation | Marka 733 vs 779 m; Queen Alia 764 vs 730 m; Aqaba 662 vs 53 m; King Hussein 773 vs 683 m |

Aqaba's grid cell is about 600 m higher than the station. The constant offset
is removed by the anomalies, but the cell represents mountains rather than the
Gulf coast (a limitation).

## Station level (protocol section 6)

| Station | App test | Slope (C/decade) | Pettitt (annual) | g_k SD (C) | Bias bound 0.027 x max abs(g_k) |
|---|---|---|---|---|---|
| Marka | withheld: dependence beyond lag 1 | +0.02 (descriptive) | 2014, p = 1.0 | 0.34 | 0.027 |
| Queen Alia | withheld: gap year (2013) | +0.29 (descriptive) | **2011, p = 0.013** | 0.32 | 0.023 |
| Aqaba | tested | -0.22 (-2.07 to +1.63), p = 0.63 | **2018, p = 0.036** | 0.56 | 0.054 |
| King Hussein | withheld: gap years | +0.31 (annual OLS, descriptive) | 2009, p = 0.08 | 0.38 | 0.030 |

- **Disagreement.** Slopes range from -0.22 to +0.31: 3 positive, 1 negative.
  No tested station has an interval that excludes 0, so the stations are not
  labelled "stations disagree".
- **Pettitt results.** These are descriptive and trigger investigation only
  (section 7.3).
  - **Aqaba 2018:** coincident with another indicator. In the same year the
    station's median observations per day rose from 17-20 to 24 (a change in
    hours of operation). S2 shows the mean anomaly fell by 0.48 C after 2018.
    No relocation record was found. The station stays in the primary analysis.
  - **Queen Alia 2011:** unexplained. No metadata were found. The station stays
    in the primary analysis.

## Sensitivity analyses (none can change the outcome)

| Analysis | Slope (C/decade) | 95% interval | Note |
|---|---|---|---|
| Primary | +0.08 | -0.28 to +0.44 | Inconclusive |
| C4, complete four-station months | +0.09 (annual OLS) | none (withheld: gaps) | Within sampling spread of primary |
| Leave out Marka | +0.10 | -0.42 to +0.63 | not influential |
| Leave out Queen Alia | +0.01 | -0.43 to +0.44 | not influential |
| Leave out Aqaba | +0.18 | -0.03 to +0.38 | not influential (change +0.10 < 0.18) |
| Leave out King Hussein | +0.03 (descriptive) | none (withheld: dependence beyond lag 1) | n/a (withheld) |
| S2 Aqaba split | step of -0.48 C after 2018 | none (descriptive) | coincides with observation-schedule change |
| S3 POWER monthly (local solar, full month) | +0.07 | -0.31 to +0.45 | day-matching choice immaterial |
| S4 GHCN-M qcu (King Hussein, Ma'an, Ghor Safi) | +0.39 | none (withheld: gap years) | descriptive; separate source, not merged |
| S4 GHCN-M qcf (homogenised) | +0.36 | none (withheld: gap years) | descriptive |

Every sensitivity interval that could be computed contains zero.

## Limitations to disclose with this result

- Four stations, mostly in the north-west and centre, plus Aqaba. The desert
  that dominates the Jordan average is represented only by King Hussein.
- GSOD is not homogenised. No station-history records were obtained, because
  OSCAR/Surface could not be read automatically and JMD was not contacted.
- Aqaba changed its observing schedule in 2018 and sits in a grid cell about
  600 m higher than the station.
- The interval's nominal 95% coverage may be lower under strong multi-year
  persistence (docs/ANALYSIS.md).
- **Data use:** GSOD non-US data fall under WMO Resolution 40. Raw station files
  are not redistributed; run the script to re-download them.
