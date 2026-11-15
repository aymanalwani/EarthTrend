# Statistical analysis

`earthtrend.analysis.analyze_timeseries(frame, metadata, alpha=0.05)` accepts
the same DataFrame and metadata contract as preprocessing. It calls preprocessing
itself; use its complete `data` view if preprocessing was already performed, so
quality counts remain available. Optional `date_column`/`value_column` select
custom columns. No UI, NASA client, or chart changes are made.

The returned dataclasses support `result.to_dict()` for application consumers.
Metadata and source units are retained. All rates are source units per Julian
year (365.25 days), referenced to `origin`, the first valid observation. Use
elapsed years from that origin when reconstructing a line.

## Estimates and interpretation

- `regression`: OLS slope, intercept, direction and R-squared. Monthly complete
  sequences use seasonal fixed effects (period 12). The intercept is the fitted
  value at origin for the reference seasonal phase. R-squared includes seasonal
  effects; it is not the fraction explained by trend alone. The chart draws the
  long-term trend as intercept + `diagnostics.seasonal_mean_offset` + slope *
  years, i.e. with the seasonal cycle averaged out.
- `sen`: for monthly data, the seasonal Theil-Sen slope (Hirsch et al. 1982):
  the median of pairwise slopes computed within each calendar month only, using
  actual elapsed years, so the seasonal cycle does not bias it and a missing month
  is simply absent. For other cadences, the median of all pairwise slopes
  (SciPy `theilslopes`). Its independent-data confidence interval is
  deliberately not exposed for climate observations.
- `mann_kendall`: S, continuity-corrected normal Z, Kendall tau, two-sided p-value,
  significance and decision. Original MK is used for period 1; seasonal MK for
  longer periods. It tests monotonic association, not a specified linear rate.
- `diagnostics`: regularity, chosen period, seasonal effect range, residual lag-1
  correlation, Ljung-Box p-value and lag count, effective sample size, and the
  beyond-lag-1 dependence check (p-value, lags, level). Diagnostics are computed
  after fitting trend and seasonal effects, rather than on the trending raw data.
- `quality`, `n`, `warnings`, and `status`: explicit missing/invalid counts,
  retained finite observations, limitations, and availability of inference.

Direction is the sign of the estimate, independently of significance. At default
alpha 0.05, p < alpha rejects the relevant zero-trend null under its assumptions.
It is not the probability that the null is true. Nonsignificance does not prove
stability, and significance does not establish causation.

## Inference policy and assumptions

Monthly metadata defaults to period 12; annual/yearly defaults to 1. Other
resolutions require an explicit `seasonal_period`. Period 1 is an explicit
no-recurring-seasonality assertion; daily series need a scientifically chosen
policy, not an automatic 365-step calendar assumption.

Inference requires at least 15 annual observations (period 1), or
max(30, 3*period) observations otherwise. Annual series with fewer than 30
values carry a limited-power warning. Monthly series may contain missing
months: seasonal terms use calendar months and the slope uses actual elapsed
time, so a gap does not shift later values (the 2006-12 gap in the Aqaba SST
file is the real case). Other cadences require a complete regular sequence.
These are conservative engineering guards, not a guarantee of power or validity. Calendar regularity uses pandas `infer_freq`;
calendar month/year spacing is treated as regular sampling steps despite varying
day lengths. The caller must ensure that the inferred cadence matches intended
sampling: regularly spaced but systematically absent observations can still pass.

Regression uncertainty uses an AR(1) effective sample size (Santer et al.
2008, doi:10.1002/joc.1756). With residual lag-1 correlation r1, bias-corrected
as r1 + (1 + 4*r1)/n and limited to [0, 0.99], n_eff = n*(1 - r1)/(1 + r1). The
residual variance and Student-t degrees of freedom use n_eff minus the number
of fitted parameters; inference is withheld when that is below 1. Confidence
level is 1-alpha. This models lag-1 dependence only, not long memory,
structural breaks, an inadequate seasonal model, or selective missingness.

This replaced Newey-West HAC after the step 9 audit. On SYNTHETIC no-trend
series with 35 annual values (1000 runs each, nominal 5% error rate), HAC
declared a significant trend in 9% (independent noise), 16%, 24% and 37% of
runs for AR(1) coefficients 0, 0.3, 0.6 and 0.8. The effective-sample-size
method gave 4%, 8%, 6% and 7%. It is still approximate for short series.

Because that correction models lag-1 dependence only, a further check guards
it. The lag-1 component is removed from the residuals (e[t] - r1*e[t-1]) and a
Ljung-Box test is applied to what remains, through the lag count given below
(at least 2), with one degree of freedom removed for the fitted r1. If it
rejects at max(alpha, 0.10), significance is withheld (status
`descriptive_only`). The looser 0.10 level is deliberate: doubtful cases are
withheld. Ljung-Box lags are min(max(period, floor(4*(n/100)^(2/9))), n//4).

### Decision rule for annual data (final review, 2026-11-15)

A trend is reported as significant only if two tests both reject at alpha:

1. the AR(1) effective-sample-size t test above, and
2. a fixed-b test (Kiefer and Vogelsang 2002, doi:10.1111/1468-0262.00366):
   the OLS slope divided by a Bartlett-kernel long-run standard error with
   bandwidth equal to the series length. It assumes no autocorrelation model.
   Its p-value comes from 20,000 simulated series of the same length with
   independent Gaussian noise (fixed seed; Monte Carlo error about 0.0015 near
   0.05). Its fixed-b limit does not depend on short-range autocorrelation, but
   in short samples persistence still inflates it (see the table).

This is an intersection-union rule: its false-positive rate cannot exceed that
of either test. The reported p-value is the larger of the two; the reported
interval is the union of the two intervals, so the interval excludes zero
exactly when the result is significant. Both p-values are in `diagnostics`
(`ar1_p_value`, `fixed_b_p_value`).

### Monthly data use the same test

Monthly significance is tested on the annual means of the deseasonalized
values (observed value minus its fitted calendar-month effect, dated
mid-year), with the annual rule above. Months within a year are not
independent: treating 252 monthly values as 252 observations overstated the
evidence (up to 11% false positives with year-to-year persistence, below).
Monthly and annual resolutions therefore give the same slope, interval and
p-value (a test checks this). A year missing one month is kept, because a mean
of deseasonalized values has no seasonal bias; years missing more are left out.
The monthly seasonal-dummy slope is kept as `diagnostics.monthly_model_slope`.
The one remaining difference is the Aqaba SST file: its calendar annual means
drop 2006 (December missing), leaving a gap that withholds the annual result,
while the monthly route keeps 2006 with 11 months.

### Why the previous test exceeded 5%

Diagnosis on SYNTHETIC series (no trend, nominal 5%):

- The AR(1) correction uses only the lag-1 autocorrelation. Persistence that
  extends over several years (AR(2)-type, or dependence at lag 2) has a much
  larger long-run variance than its lag-1 value implies.
- The beyond-lag-1 check has little power at 15-35 values, so most such
  series pass it. (It still helps: without it, n=35 lag-2 rose from 5.7% to
  12.2%, so it is kept.)
- Lag-1 autocorrelation estimated from a short detrended series is biased low;
  the bias correction only partly fixes this.
- The annual minimum was lowered from 30 to 15 values in this audit, which
  exposes these small-sample problems; results with fewer than 30 values are
  labelled indicative.

Alternatives tried and rejected (n=21, same simulations): AR(p) effective
sample size with p chosen by AIC (AR(1) 0.5: 15%, AR(2): 32%); a sieve
bootstrap of the OLS t statistic (independent noise 8%, AR(2) 35%); REML
AR(1)/AR(2) GLS (8-11% on independent noise); Newey-West HAC with 12 lags on
monthly data (25-54%); fixed-b alone (AR(1) 0.8: 20%); an extra rule withholding
when the estimated lag-1 value exceeds 0.5 (little gain, because the false
positives come from series whose persistence looks low).

### Measured false-positive rates of the final rule

Out-of-sample check (seed 4242, not used to choose the method; 600 runs per
row; rates are out of all runs; "withheld" means no significance reported):

| SYNTHETIC annual series | n=15 | n=21 | n=35 | Withheld (n=15/21/35) |
|---|---|---|---|---|
| Independent noise | 3.5% | 2.3% | 1.0% | 20 / 18 / 13% |
| AR(1) 0.3 | 5.2% | 3.2% | 2.2% | 20 / 17 / 13% |
| AR(1) 0.5 | 6.7% | 4.7% | 2.5% | 26 / 20 / 12% |
| AR(1) 0.8 | 11.7% | 7.0% | 4.5% | 44 / 43 / 32% |
| Lag-2 only, 0.6 | 10.5% | 10.5% | 3.3% | 14 / 32 / 67% |
| AR(2) 0.5, 0.3 | 16.8% | 16.2% | 9.5% | 20 / 20 / 26% |
| No trend, one step of 1 SD mid-series | 13.3% | 20.7% | 37.2% | 20 / 15 / 10% |

Previous rule (n=21): independent 4.0%, AR(1) 0.5 6.7%, AR(1) 0.8 9.5%,
lag-2 17%, AR(2) 22%.

| SYNTHETIC monthly series, 21 years (seed 11, 300 runs) | Final rule | Withheld | Previous dual path |
|---|---|---|---|
| Independent noise | 1.7% | 19% | 5.0% |
| Month-to-month AR(1) 0.5 / 0.8 / 0.95 | 2.3 / 1.7 / 2.7% | 18 / 24 / 51% | 3.7 / 1.7 / 1.0% |
| Year-to-year (lag-12) 0.3 / 0.6 | 2.7 / 4.7% | 18 / 27% | 7.3 / 7.0% |
| AR(1) 0.5 plus lag-12 0.3 | 4.3% | 27% | 11.0% |

Power (slope 0.08 standard deviations per year, independent noise): n=21 28%
(previous 40%); n=35 81% (previous 86%). Fewer false alarms cost some power at
21 years.

### Short periods: why fewer than 15 years are not tested

**Where the minimum comes from.** The minimum of 15 annual values is the
team's own safeguard (`MIN_ANNUAL_INFERENCE` in `earthtrend/analysis.py`). The
challenge sets no minimum; it asks only for a rate and a significance test.
The value was 30 originally and was lowered to 15 in the 2026-11-15 audit,
with the simulations above.

**What happens below it.** A monthly selection is tested on one value per
year. So 132 monthly values (11 years) give 11 annual values, fewer than 15.
The seasonal OLS rate and Sen's slope are still reported, as descriptions. No
p-value or confidence interval is computed. The notes say "11 annual values
are available; at least 15 are required".

**What the unchanged test would do if the minimum were lowered.** SYNTHETIC
series, 400 runs per cell, seed 5150, nominal 5%; the Monte Carlo error is
about 1-2 points:

| Years | False positives: independent | AR(1) 0.5 | AR(2) 0.5/0.3 | Withheld | Power, trend 0.08 SD/yr | Power, trend 0.25 SD/yr | Median 95% half-width (SD/decade) |
|---|---|---|---|---|---|---|---|
| 5 | 1.5% | 3.8% | 4.5% | 42% | 1.8% | 3.2% | 10.8 |
| 8 | 2.5% | 5.2% | 8.2% | 34% | 2.5% | 8.2% | 4.7 |
| 10 | 2.2% | 7.0% | 13.5% | 25% | 3.2% | 22.8% | 3.2 |
| 11 | 3.0% | 7.0% | 17.0% | 25% | 6.0% | 28.5% | 2.8 |
| 12 | 0.5% | 6.0% | 13.2% | 27% | 3.5% | 40.5% | 2.4 |
| 15 | 2.2% | 5.8% | 17.2% | 20% | 7.0% | 60.5% | 1.7 |

**Reading.** Below 15 years the test would almost never detect a realistic
trend: power is 2-6% at 0.08 SD/yr, about the same as its false-positive
rate. "Not significant" would then carry no information, and "significant"
would be right about as often as wrong under multi-year persistence (13-17%
false positives at 10-12 years). The low false-positive rate at 5 years comes
only from the test almost never rejecting.

**Decision.** The minimum stays at 15. Lowering it, or adding a different
method for short monthly series, was reviewed and rejected:

- block or sieve bootstrap, AR GLS and HAC all had worse false-positive rates
  at 21 years (see above);
- a threshold chosen after seeing a user's data would be result-driven.

### Limitations that remain

- With 15-29 annual values and strong persistence over several years, the
  false-positive rate is 10-17% instead of 5%. No method tried holds 5% there;
  with so few years a slow natural oscillation cannot be told apart from a
  trend. Results with fewer than 30 values are labelled indicative.
- A sudden shift (a step change, for example a change of sensor or of
  reanalysis input) is reported as a trend 13-37% of the time. A linear trend
  test cannot tell a step from a trend; look at the chart.
- Rates were measured for Gaussian synthetic families only. Real series may
  have skewed values (precipitation), changing variance or other structures.
- No multiple-testing correction: testing several variables, places or periods
  raises the chance that one of them is significant by chance.
- "Withheld" is a third outcome, not "no trend": 13-20% of independent-noise
  series are withheld by the dependence check.

For period 1, Mann-Kendall is reported whenever regression inference is, and
its Z statistic is divided by sqrt((1 + r1)/(1 - r1)) using the same corrected
r1 (Yue and Wang 2004, doi:10.1023/B:WARM.0000043140.61082.60). It is a
secondary check and does not enter the decision. It is less robust than the
regression rule: 22.8% at n=21 for AR(2) 0.5/0.3. Seasonal Mann-Kendall is
used only for seasonal periods other than 12 (monthly data use the annual
route), and is withheld when the residual Ljung-Box test rejects at alpha.

Seasonal terms use the calendar month of each observation (period 12), so a
missing month does not shift later observations into the wrong season. When a
seasonal series has fewer than 3*period observations, or a season with fewer
than two observations, no rate is reported (status
`seasonal_adjustment_unavailable`): a straight line through part of a seasonal
cycle measures the cycle, not a long-term change.

Missing/invalid measurements are excluded with preprocessing counts; actual
elapsed dates are preserved. Irregular retained sequences receive descriptive
slopes only, except monthly series with missing months (see above).
Duplicates/invalid dates raise preprocessing errors. Fewer than
three finite observations return `insufficient_data`. Constant series return
zero slopes, MK S=Z=tau=0 and p=1 by tie-only convention; regression uncertainty
and R-squared are undefined. Near-perfect deterministic fits receive descriptive
estimates without residual-based inference. Series above 5000 valid points are
rejected to bound quadratic pairwise slope costs. No interpolation, unit
conversion or range masking is performed; the only aggregation is the annual
route for monthly data.

## Verification and references

All test observations are synthetic, with fixed random seeds. Tests cover known
rates, constant/noisy data, missing and invalid values, seasonality, dependence,
insufficient data, and configuration failures. Run:

```powershell
python -m unittest discover -s tests -v
```

Primary references:
- https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_hac.html
- https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.acorr_ljungbox.html
- https://github.com/mmhs013/pyMannKendall
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html
