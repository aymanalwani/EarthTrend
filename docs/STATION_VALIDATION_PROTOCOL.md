# Station temperature cross-check: pre-registered protocol (DRAFT, revision 3)

Status: draft, 2026-11-15. Not yet run. No station temperature value has been
read, and no station trend or station-minus-MERRA-2 difference has been
computed.

- Revision 2 addressed station composition, station-level analysis,
  GSOD/GHCN-M compatibility, station history, POWER comparability, the
  decision bound and the split between primary and sensitivity analyses.
- Revision 3 adds:
  - the mathematics of composition bias and a complete-four-station sensitivity
    analysis (section 5.3, C4);
  - exact POWER daily retrieval, aggregated by UTC day instead of local solar
    day (4.4);
  - the MERRA-2/GEOS-IT handling (A3);
  - wording that keeps the outcome categories from overstating the evidence
    (9).
- The station list is unchanged.

The EarthTrend trend test is used exactly as it is. This protocol does not
change it.

## 1. Question and what it can show

Question: at the grid cells containing four Jordanian surface stations, is the
MERRA-2 2 m temperature trend for 2005-2024 compatible, within a predefined
tolerance, with the trend measured by the stations' thermometers?

This is a reanalysis-fidelity cross-check at four points.

- It does NOT validate the Jordan area-average trend (+0.48 C/decade). That
  average is dominated by eastern and southern desert, where there is almost
  no station.
- It does NOT show that MERRA-2 is correct. It says nothing about
  precipitation, soil wetness, evaporation or SST, and nothing about the cause
  of the warming.
- Independence is partial. MERRA-2 assimilates surface pressure from land
  stations but, per a secondary source citing Gelaro et al. (2017), not their
  2 m temperature (A1). The same SYNOP sites report the pressure, and
  gauge-corrected precipitation drives the MERRA-2 land model.

## 2. Freeze, order of work and deviations

1. **Freeze.** Commit this protocol, together with the presence-only and
   synthetic scripts (sections 3.3, 5.3 and 9.4), before downloading any new
   data or reading any station temperature. The commit hash and date are the
   registration record.
2. **Metadata stage.** Station history review and station classification
   (sections 7 and 10) are completed and committed BEFORE any temperature value
   is read. Pending requests do not block the analysis. Whatever has arrived by
   the time the metadata stage is committed is used. Anything later is reported
   as an addendum and does not change the verdict.
3. **Blocker stage.** A2, A3 and A10 (section 11) must be resolved before any
   station temperature is processed. If A2 or A3 cannot be resolved, the
   analysis is not run. It is reported as "not run: assumption unresolved", and
   no grid product is substituted without a dated amendment that the user has
   approved.
4. **Data stage.** Download the station and POWER data, apply quality control
   (section 4) and produce the station-level tables (section 6) before the
   composite.
5. **Composite stage.** Compute the primary result (section 5), then the
   sensitivity analyses (section 8), and report everything (section 9).
6. **Deviations.** Any change after the freeze goes in section 12
   ("Amendments") with its date, reason and whether results had been seen. The
   original text stays.
7. Results are reported whatever they show, including "inconclusive" and "not
   run".

## 3. What was looked at before freezing (disclosure)

### 3.1 Known results

- MERRA-2 Jordan area-average T2M (Giovanni M2IMNXASM): +0.048 C/yr,
  p = 0.013 (docs/AUDIT_2026-11-15.md).
- The behaviour of the app's test on SYNTHETIC series
  (tests/test_false_positive_rates.py).

### 3.2 Metadata and documentation read

- NOAA isd-history.csv: GSOD station codes, coordinates and elevations. Every
  main Jordan GSOD record ends on 2025-08-24.
- GHCN-M v4 qcu inventory: station list and coordinates.
- Readmes and methodology pages:
  - GSOD readme;
  - GHCN-M v4 readme;
  - NASA POWER methodology pages;
  - NASA POWER API documentation (daily and hourly OpenAPI specifications and
    service pages; read 2026-11-15).
- earthtrend/data/power_client.py:
  - it implements only GET /api/temporal/monthly/point;
  - its parser expects 6-digit YYYYMM keys.

### 3.3 Presence-only feasibility (2026-11-15)

This check used GSOD files downloaded during the feasibility study. It read
only the date, the TEMP missing code (9999.9) and TEMP_ATTRIBUTES. No
temperature value was used. Window 2005-2024.

- **Usable years per station.** A month is valid with at least 25 valid days.
  A year is usable with at least 11 valid months.

  | Station | Usable years |
  |---|---|
  | Marka | 20 |
  | Queen Alia | 19 (2013 missing) |
  | Aqaba | 20 |
  | King Hussein | 16 (2009, 2014, 2020, 2024 missing) |
  | Prince Hasan | 14 |
  | Irbid | 10 |
  | Ma'an | 10 |
  | Ghor Safi | 9 |

- **Panel months by number of stations.** 207 months have all four stations
  and 33 have three.

  | Year | 3-station months | Station absent |
  |---|---|---|
  | 2005 | 1 | King Hussein |
  | 2009 | 2 | King Hussein |
  | 2013 | 12 | Queen Alia |
  | 2014 | 12 | King Hussein |
  | 2020 | 3 | King Hussein |
  | 2021 | 1 | King Hussein |
  | 2024 | 2 | King Hussein |

  In total King Hussein is absent in 21 of these months and Queen Alia in 12.

- **Complete-four-station months.** These give 15 usable years, with 2009,
  2013, 2014, 2020 and 2024 missing. The app withholds its test for annual
  series with missing years.
- **At least 3 of 4.** This gives 20 gap-free years.
- **Leave-one-out (at least 2 of the remaining 3).** Each gives 20 gap-free
  years.
- **Median observations per valid day.**
  - Marka: 23-24.
  - Queen Alia: 22-24.
  - Aqaba: 17-20 in 2005-2017, then 23-24 from 2018.
  - King Hussein: 6-8.

## 4. Data

### 4.1 Primary panel (fixed)

The rule is GSOD stations with at least 15 usable years in 2005-2024. It gives
exactly these four stations:

| Station | GSOD USAF-WBAN | Lat | Lon | Elev (m) |
|---|---|---|---|---|
| Amman Marka | 402700-99999 | 31.973 | 35.992 | 778.8 |
| Queen Alia | 402720-99999 | 31.723 | 35.993 | 730.0 |
| Aqaba King Hussein Intl | 403400-99999 | 29.612 | 35.018 | 53.3 |
| King Hussein (Mafraq) | 402650-99999 | 32.356 | 36.259 | 682.8 |

No station is added, removed or reweighted after data are seen.

### 4.2 Window

2005-01 to 2024-12. GSOD ends on 2025-08-24, so 2025 cannot be a usable year.

### 4.3 Station values (GSOD)

- **Definition.** TEMP is the daily mean temperature in F to tenths, with
  missing = 9999.9. It is computed from the observations available for the
  day, and the day is the UTC day (00-23Z). At least 4 observations are
  required; TEMP_ATTRIBUTES gives the count (GSOD readme).
- **Conversion.** C = (F - 32) x 5/9. Whether the CSV files are in F is
  assumption A2, a blocker.
- **Valid day.** TEMP is not 9999.9 and TEMP_ATTRIBUTES is at least 4.
- **Valid month.** At least 25 valid days.

### 4.4 Grid values (NASA POWER, MERRA-2): retrieval and aggregation

**Existing code.** earthtrend/data/power_client.py does NOT support daily
data. It implements only the monthly point endpoint, and its parser expects
6-digit keys. The daily request and its parser are written in the offline
validation script. No app code is changed.

**Request.** One request per station:

    GET https://power.larc.nasa.gov/api/temporal/daily/point
        ?parameters=T2M&community=ag
        &latitude=<GSOD lat>&longitude=<GSOD lon>
        &start=20050101&end=20241231
        &time-standard=utc&format=JSON

- The parameters, the YYYYMMDD dates and the time-standard option (lst or utc)
  are documented in the daily OpenAPI specification
  (power.larc.nasa.gov/api/temporal/daily/openapi.json, API v2.10.3).
- No maximum date span is documented. If a 20-year request is refused, the
  script splits it into calendar years. That split is recorded as an amendment.
- The docs warn that repeated requests for the same cell may be blocked, so
  each station is requested once and the raw JSON is saved unchanged under
  data/raw/stations/power/ with the download date.
- Recorded from each response: the full header (title, api version,
  fill_value, start, end), the messages, and the returned geometry
  (coordinates and elevation).

**Parsing.**

- Keys are YYYYMMDD. Each key is parsed as a UTC calendar date.
- The fill value is read from header.fill_value (documented as -999). It, and
  any non-finite value, means missing.
- Values must be in C. A value outside -40 to 60 C stops the script.

**Day matching.**

- GSOD days and POWER days with time-standard=utc both cover 00-23Z UTC. They
  are paired on the same calendar date.
- A day missing in either series is dropped from both.
- **Monthly grid value:** the mean of the POWER values on the station's paired
  valid days.
- **Monthly station value:** the mean of the same days.
- A month is valid only with at least 25 paired days.

**UTC versus local solar day.**

- POWER's default daily aggregation is in local solar time. At 35-36 E the
  local solar day starts about 2.4 h before 00Z.
- Revision 2 paired GSOD UTC days with POWER local-solar days. Revision 3
  requests time-standard=utc so that both day windows coincide.
- What POWER's daily value means with time-standard=utc is not documented
  (assumption A10). Until A10 is confirmed the alignment is assumed, not shown.
- Whatever the outcome of A10, the local-solar alternative is kept as
  sensitivity S3 (POWER monthly, local solar).

**Grid cell.**

- POWER's native grid is 0.5 x 0.625 deg. Whether a point request returns the
  containing cell or an interpolation is not documented (A4).
- If two stations return identical POWER series (possible for Marka and Queen
  Alia, which are 28 km apart), this is reported. The panel does not change.

### 4.5 Source product (MERRA-2 versus GEOS-IT): blocker A3

**What the docs say.** The POWER sources page gives MERRA-2 from 1981 to about a
month behind real time, and GEOS-IT appended after the end of MERRA-2. GEOS-IT
values are overwritten when MERRA-2 becomes available. The exact switch date is
not stated.

**What the API returns.** The daily response header documents no source field
per period. So the API metadata may never confirm the product for each month.

**A3 stays unresolved, and blocks the analysis, until one of these confirms that
every month of 2005-2024 is MERRA-2:**

- source or version information in the actual responses (header or messages);
- written confirmation from the POWER team (larc-power-project@mail.nasa.gov).
  Sending that message is the user's decision.

The documentation statement alone is not treated as confirmation.

**If any month in 2005-2024 is GEOS-IT:**

- A change of source creates a step in the grid series only, which would show
  up as an artificial trend in station-minus-grid. Mixed periods are therefore
  never analysed as one series.
- GEOS-IT is appended only at the end, so the primary window is cut at the last
  complete MERRA-2 year. No internal gap is created.
- The GEOS-IT months are analysed separately and descriptively: the mean
  station-minus-grid difference compared with the MERRA-2 period. They never
  enter the verdict.
- If fewer than 15 usable years remain, the verdict is "Inconclusive". This is
  an accepted outcome.
- No other grid product (for example MERRA-2 files from GES DISC) is
  substituted without a dated amendment that the user has approved.

## 5. Primary analysis

### 5.1 Difference series and offsets

For each station s and valid month t:

    D_s(t) = station_s(t) - grid_s(t)                       (day-matched, C)
    c_s(m) = mean of D_s over the station's own valid months with calendar month m
    A_s(t) = D_s(t) - c_s(m(t))

### 5.2 Composite

    A(t) = mean of A_s(t) over the stations valid in month t

A(t) is kept only when at least 3 of the 4 stations are valid. Equal weights
are used. The app's test then runs on A(t) unchanged.

### 5.3 Why offset removal is not enough on its own

**Model.**

    D_s(t) = a_s + g_s(m) + f_s(t) + e_s(t)

- a_s is a constant offset.
- g_s(m) is a seasonal offset.
- f_s(t) is the slowly varying part: a trend, steps or drifts.
- e_s(t) is noise.

**What removing the offset leaves.**

    A_s(t) = f_s(t) - fbar_s(m) + noise

Here fbar_s(m) is the mean of f_s over station s's own valid months with
calendar month m.

**Bias when a station is missing.** If station k is absent in month t, the
composite departs from the four-station value by

    b(t) = (1/4) * [ mean over s != k of (f_s(t) - fbar_s(m))  -  (f_k(t) - fbar_k(m)) ]

So removing offsets handles constant and seasonal level differences only.
b(t) is not zero when the stations' time-varying parts differ: different
trends, steps or drifts. It is also not zero, even with identical trends, when
the stations' valid months are centred on different times, because each offset
then absorbs a different part of the trend.

**How large it can be, for this presence pattern.**

- **Worst-case bound.** If |b(t)| <= delta in the affected months, the bias of
  the slope of the annual composite is at most

      delta * sum_y |y - ybar| * k_y / 12  /  sum_y (y - ybar)^2  =  delta * 86.5 / 12 / 665
                                                                  =  0.108 * delta  per decade

  where k_y is the number of 3-station months in year y. 2013 and 2014 are
  near the centre of the window and contribute little: 2005, 2009, 2020, 2021
  and 2024 give 62.5 of the 86.5. With delta = g/4, where g is the gap between
  the absent station's anomaly and the others' mean, the bias is at most
  0.027 x g C/decade.
- **Exact response to linear trends.** A synthetic run on the presence mask
  used no temperatures (scratchpad composition_response.py, to be committed as
  scripts/station_composition_check.py).
  - A trend shared by all four stations is recovered as 0.9993 of its value.
    This is the equal-trend term, and it is negligible.
  - A trend at one station alone enters the composite slope with weights
    0.2552 (Marka), 0.2540 (Queen Alia), 0.2552 (Aqaba) and 0.2350 (King
    Hussein), instead of 0.25 each. The primary therefore estimates a
    near-equal weighted mean of the four station difference trends. King
    Hussein is underweighted by about 6%.
- **Common baseline.** Offsets computed over the 207 complete months instead
  give 1.0000 and almost identical weights. The difference is immaterial, so
  the primary definition is not changed.

**What these numbers do not cover.** Steps or drifts at the times when a
station is absent are not linear trends. They are not covered by the weights
above. They are measured by the C4 and leave-one-out analyses (8.1, 8.2) and
by the divergence diagnostic g_k (6).

The worst-case bound assumes b(t) has the same sign in every affected month.
Different stations are absent in 2013 and 2014, so the actual bias may be
smaller.

**Final mask.** Day-matching with POWER (4.4) can make further station-months
invalid, which changes which months have 3 stations. Before any difference
value is examined, the composition check is rerun on the final paired
presence mask. This uses presence only. The weights and the bound in this
section are then reported for that mask.

**One run only.** The primary is computed once. If the app withholds the
result, the outcome is "Inconclusive". No alternative choice is tried to obtain
a tested result.

## 6. Station-level analysis (before aggregation)

These outputs are produced for every panel station and always reported:

- monthly A_s(t) and its annual means (plots);
- the numbers of valid months and usable years;
- the app's test on A_s. Queen Alia and King Hussein have gap years, so the
  app withholds their tests. Their OLS slopes are descriptive only;
- the median observations per day by year;
- a Pettitt statistic, descriptive only (7.2);
- the divergence diagnostic. For each station k, using complete months only:

      g_k(t) = A_k(t) - mean of the other three A_s(t)

  Report its range and its mean in the calendar months in which station k is
  absent elsewhere. The implied composition bias is then

      0.027 x max|g_k|  C/decade  (worst case)

Disagreement is reported as:

- the range of slopes;
- the number of positive and negative slopes;
- the number of tested stations whose interval excludes 0;
- the label "stations disagree" when two stations have intervals that exclude
  0 with opposite signs. This label is shown beside the verdict and does not
  change it.

No station is dropped, downweighted or highlighted because it agrees or
disagrees with MERRA-2.

## 7. Station history and discontinuities

### 7.1 Sources

These are reviewed at the metadata stage, unless noted otherwise:

- isd-history.csv (one location per station, no relocation history);
- WMO OSCAR/Surface;
- the Jordan Meteorological Department (optional, non-blocking);
- GSOD observation counts by year (the Aqaba change in 2018 is already known);
- coordinate and elevation differences between the GSOD and GHCN-M lists:
  Amman 778.8 m vs 766 m, Aqaba 53.3 vs 51 m, Queen Alia 730 vs 722 m;
- satellite imagery, and population and land-cover change;
- GHCN-M v4 qcf-minus-qcu adjustments. These are read at the data stage,
  because they are derived from temperatures.

### 7.2 Pettitt test

- It is applied to the annual means of each A_s.
- It is descriptive only. It does not account for autocorrelation and has
  little power with 20 values, and a drift can also trigger it.
- A result with p < 0.05 means "a step or a drift may be present". It triggers
  the investigation in 7.3. It never removes a station.

### 7.3 Investigating a break

1. Look for a metadata event within 1 year of the candidate year.
2. Compare with the other stations' A_s.
3. Compare with GHCN-M qcf-minus-qcu.
4. Report one of three findings:
   - documented cause;
   - coincident with another indicator;
   - unexplained.

The station stays in the primary analysis in all cases.

## 8. Analysis hierarchy (fixed; only the primary gives the verdict)

| Level | Analysis | Inference | Can change the verdict? |
|---|---|---|---|
| Primary | Composite A(t), at least 3 of 4 stations, 2005-2024 (section 5) | App test, 95% union interval | Yes: it alone decides |
| Complete-four sensitivity (C4) | Composite on months with all 4 stations | Descriptive only: 15 years with gaps, so the app withholds | No |
| Leave-one-out (L1-L4) | Four composites, each omitting one station, at least 2 of the remaining 3 | App test (20 gap-free years each) | No |
| Other predeclared checks | S2 Aqaba split at 2018; S3 POWER monthly (local solar day); S4 GHCN-M panel | Descriptive, or app test where the series is gap-free | No |

All results are shown in one table beside the primary.

- No sensitivity result can replace the primary, change its category or become
  the headline.
- Sensitivity results that differ from the primary are reported with how many
  differ and in which direction.
- There are 1 + 1 + 4 + 3 analyses. Some disagreement among them is expected
  by chance alone. Because only the primary gives a verdict, no
  multiple-testing correction is applied.

### 8.1 Complete-four sensitivity (C4)

- **Definition.** Months in which all four stations are valid, with the same
  offsets c_s(m) as the primary. 207 months; 15 usable years; 2009, 2013,
  2014, 2020 and 2024 missing.
- **Feasibility.** The app withholds inference for annual series with gaps, so
  C4 gives an OLS slope and no interval.
- **Composition.** All four stations are present in every month used, so the
  weights are equal (0.2496 each in the synthetic run).
- **What a difference from the primary means.** C4 differs from the primary
  in two ways at once: it removes the 33 three-station months, and with them
  five whole years. A difference therefore cannot be attributed to composition
  alone.
- **Comparison.** Compute

      Delta = slope(primary, OLS on annual means) - slope(C4)

  and its expected spread under no composition effect. From the presence-only
  synthetic run with independent monthly noise of standard deviation 1,
  SD0 = 0.034 per decade. Scale it as

      SD(Delta) ~= 0.034 x sigma_m  per decade

  where sigma_m is the standard deviation of the primary's monthly A(t)
  residuals. Independent noise understates the spread under persistence.
- **Interpretation rule.**
  - If |Delta| <= 2 x SD(Delta): report "C4 agrees with the primary within
    sampling spread."
  - If |Delta| > 2 x SD(Delta): report "The primary differs from the
    complete-four-station estimate by Delta. This may reflect composition, the
    five excluded years, or persistence." Then show L1-L4 and g_k to identify
    which station or years drive it.
  - In either case the primary verdict is unchanged. The C4 sentence is printed
    directly under it, and the primary may not be quoted without it.

### 8.2 Leave-one-out (L1-L4)

- Each composite omits one station. All four keep 20 gap-free years, so the
  app's test applies.
- Report each slope and interval, and the change from the primary.
- If removing one station moves the slope by more than half the primary's
  interval half-width, that station is reported as influential, with its
  history findings (7.3). The verdict is unchanged.
- L-Aqaba also covers Aqaba's urban, coastal and Rift setting and its 2018
  schedule change. L-Marka covers the urban Amman site. L-King Hussein covers
  partial-day sampling.

### 8.3 Other predeclared checks

| ID | Check |
|---|---|
| S2 | Aqaba: annual mean of A_Aqaba in 2005-2017 against 2018-2024 (descriptive) |
| S3 | POWER MONTHLY T2M (local solar day, full calendar month, not day-matched) in place of day-matched daily UTC |
| S4 | GHCN-M v4 panel (King Hussein, Ma'an, Ghor Safi; qcu and qcf), its own composite under the same rules, never merged with GSOD |

## 9. Decision rule and interpretation (fixed)

**Primary quantity.** The trend of A(t), in C/decade, with its 95% union
interval [L, U]. Tolerance B = 0.24 C/decade.

### 9.1 Outcome categories

Every outcome carries the scope "four sites, MERRA-2 T2M at their grid cells,
2005-2024, tolerance +-0.24 C/decade".

| Outcome | Condition | What it means | What it does NOT mean |
|---|---|---|---|
| No difference beyond tolerance (four sites) | -B <= L, U <= B, and L <= 0 <= U | The station-minus-MERRA-2 trend is compatible with zero, and any difference larger than 0.24 C/decade is excluded at these sites | MERRA-2 is correct; the Jordan average is validated; the trends are identical |
| Small difference within tolerance (four sites) | -B <= L, U <= B, and 0 outside [L, U] | A difference is detected, and it is smaller than 0.24 C/decade | Agreement |
| Difference beyond tolerance (four sites) | L > B or U < -B | The station and MERRA-2 trends differ by more than 0.24 C/decade at these sites | That MERRA-2 is wrong: station trends include urban growth, site changes and point-versus-cell effects |
| Difference detected, size uncertain (four sites) | 0 outside [L, U], and the interval is not wholly inside or wholly outside +-B | A difference is detected; its size is not determined | Its direction or size relative to the tolerance |
| Inconclusive | 0 inside [L, U] and the interval extends beyond +-B; or the test is withheld; or fewer than 15 usable years | The data cannot settle the question at this tolerance | No difference; support for MERRA-2 |

Assumption checks are not outcomes. "Not run: assumption unresolved" (A2 or A3)
is reported separately.

### 9.2 Consistency, equivalence and absence of a detectable difference

- **No detectable difference.** The interval contains 0. On its own this is
  absence of evidence. With a wide interval it is compatible with large
  differences, so it is classed as "Inconclusive", never as agreement.
- **Equivalence within a tolerance.** The whole interval lies inside +-B, so
  differences larger than B are excluded. This protocol checks this
  conservatively. It requires the 95% union interval, while a standard 5%
  two-one-sided test would use a 90% interval.
- **"No difference beyond tolerance"** is this protocol's label for
  equivalence plus an interval that contains 0. It means compatibility within
  a predefined tolerance at four sites. It is not proof that MERRA-2 is
  correct. It is conditional on assumptions A1-A10, on the app's test, and on
  the interval's nominal 95% coverage. Coverage may be lower under strong
  persistence (docs/ANALYSIS.md). About 20% of series are withheld by the
  app's dependence check.

### 9.3 Tolerance B

- **Where it comes from.** B is half the MERRA-2 area-average trend
  (0.48 C/decade). A smaller difference at these sites would leave the sign
  and order of magnitude of "roughly half a degree per decade" unchanged.
- **What it is not.** It is a decision tolerance chosen for this claim, not an
  established scientific threshold. It is fixed at 0.24 and not recomputed.
- **Tolerance comparisons.** The full interval is always shown, so other
  tolerances can be read off it. Only B decides the category.

### 9.4 Expected outcome (stated in advance)

A synthetic design check used the app's test (seed 777, 400 series per case,
to be committed as scripts/station_design_check.py). For 20 annual values, the
median 95% half-width per decade is 1.04 sigma for independent noise, 1.35
sigma for AR(1) 0.3 and 1.61 sigma for AR(1) 0.5. Here sigma is the standard
deviation of the annual means of A(t).

"No difference beyond tolerance" is therefore reachable only if sigma is about
0.23 C or less (independent noise). "Inconclusive" is a likely outcome and will
be reported as such.

### 9.5 Citation rule and follow-up

- **Citation rule.** Any citation of the result must include the outcome
  label, the difference and its interval, the four-site scope, the tolerance,
  and the C4 sentence (8.1).
- **Where results go.** docs/ANALYSIS.md and DATA_SOURCES.md (under "Space
  Agency Partner Data and Other References", with NOAA NCEI attribution).
- **The app.** Its MERRA-2 result and wording are not changed by this protocol.
  If the outcome is "Difference beyond tolerance" or "Difference detected", a
  caveat is proposed as a separate change for the user to approve.

## 10. Classification of stations (fixed; descriptive labels only)

Criteria:

- **Urban:** within, or within 5 km of, the contiguous built-up area of a city
  of more than 100,000 people.
- **Coastal:** within 10 km of the sea.
- **Rift:** on the floor of the Jordan Rift Valley or Wadi Araba, or below 0 m.

| Station | Urban | Coastal | Rift |
|---|---|---|---|
| Amman Marka | yes | no | no |
| Queen Alia | no (unverified; imagery check at the metadata stage) | no | no |
| Aqaba | yes | yes | yes |
| King Hussein (Mafraq) | no (unverified; population check at the metadata stage) | no | no |

No analysis selects stations by class.

## 11. Unresolved assumptions

| ID | Assumption | Status | Blocks the analysis? |
|---|---|---|---|
| A1 | MERRA-2 does not assimilate station 2 m temperature | Secondary source only | No (affects the independence wording) |
| A2 | GSOD access CSV TEMP is in F | Not stated for the CSV | **Yes.** Verify from the file documentation or header before processing |
| A3 | POWER T2M for every month of 2005-2024 is MERRA-2, not GEOS-IT | The docs give no switch date; the daily header has no per-period source field | **Yes.** Resolved only per 4.5; otherwise not run |
| A4 | A POWER point request returns the containing grid cell | Not documented | No. Record returned geometry; limitation |
| A5 | POWER fill value is -999 (header.fill_value) | Documented example; read from each response | No |
| A6 | GHCN-M v4 monthly TAVG method for Jordan | Not stated | No. S4 only, never merged |
| A7 | Station relocations or instrument changes | Unknown | No. Section 7 |
| A8 | Queen Alia and King Hussein urban class | Unverified | No. Labels only |
| A9 | Partial-day GSOD sampling at King Hussein is stable over time | Counts stable (6-8); hours unknown | No. L-King Hussein |
| A10 | With time-standard=utc, POWER daily T2M is the mean of that UTC day's 24 hourly values | Not documented | **Yes, for the day alignment.** Check before any station temperature is processed: compare POWER daily-UTC with the mean of POWER hourly-UTC T2M at the Marka coordinates on 15 Jan, 15 Apr, 15 Jul and 15 Oct of 2010 and 2020 (8 days, POWER values only). If all agree within 0.01 C, A10 is confirmed. Otherwise daily UTC means are computed from POWER hourly UTC (available from 2001), recorded as an amendment |

## 12. Amendments

**Amendment 1 (2026-11-15T06:38Z, before any data were downloaded).** The
freeze is recorded as the SHA-256 of this file at that time
(3219d63c639bf676f2a8c043e28b66c616de71efac3c3f9d8221acb9f1705427), not as a
git commit. The user asked for no commits because the project moves to a new
repository. The text above this section is unchanged since the freeze. The
metadata stage is recorded in docs/validation/METADATA_STAGE.md and the
results in docs/validation/STATION_VALIDATION_RESULTS.md.

Revisions 2 and 3 are pre-freeze drafts, written after the
presence-only checks (3.3) and before any temperature value was read.

Revision 3:

- changes the POWER day definition from local solar to UTC;
- adds C4 and the g_k diagnostic;
- renames the outcome categories.

A common offset baseline was considered after the presence pattern was seen.
It was found immaterial (5.3) and not adopted.

## 13. Known limitations

- Four stations, mostly in the north-west and centre, plus Aqaba. The check
  concerns MERRA-2 at these cells, not the country average.
- GSOD is not homogenised. Station moves and instrument changes may be
  undocumented.
- Point versus grid box: urban growth or elevation-dependent warming cannot be
  told apart from MERRA-2 error.
- About 20 years and correlated stations: power is limited (9.4).
- The composite is a near-equal (0.235-0.255) weighted mean of station
  difference trends. Non-linear composition effects are bounded only through
  C4, L1-L4 and g_k.
- The stations form one GTS SYNOP network. S4 is a second source for
  overlapping stations, not an independent replication.

## 14. Deliverables (after approval and freeze)

- **scripts/validate_stations.py.** An offline script with no new
  dependencies. It contains its own daily POWER request and parser; the app's
  POWER client is unchanged. It saves raw files under data/raw/stations/ with
  download dates and writes data/processed/station_t2m_check.csv and a results
  table.
- **Scripts committed with the protocol** (drafts in the session scratchpad
  until approval):
  - scripts/station_presence_check.py;
  - scripts/station_composition_check.py;
  - scripts/station_design_check.py.
- **Citations:**
  - GHCN-Daily: Menne et al. 2012, doi:10.1175/JTECH-D-11-00103.1;
  - GSOD dataset citation;
  - GHCN-M v4 (Menne et al. 2018) and PHA (Menne and Williams 2009);
  - NASA POWER.
