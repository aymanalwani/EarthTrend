"""Trend estimates and guarded inference. See docs/ANALYSIS.md."""

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Mapping

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy.stats import norm, t as student_t, theilslopes
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.diagnostic import acorr_ljungbox

from earthtrend.preprocessing import QualityReport, preprocess_timeseries


@dataclass(frozen=True)
class TrendResult:
    slope: float
    slope_unit: str
    intercept: float
    direction: str
    method: str
    p_value: float | None = None
    significant: bool | None = None
    confidence_interval: tuple[float, float] | None = None
    r_squared: float | None = None


@dataclass(frozen=True)
class MannKendallResult:
    method: str
    statistic_s: float | None
    statistic_z: float | None
    tau: float | None
    p_value: float | None
    significant: bool | None
    decision: str


@dataclass(frozen=True)
class AnalysisResult:
    status: str
    alpha: float
    origin: str | None
    n: int
    quality: QualityReport
    metadata: dict[str, Any]
    regression: TrendResult | None
    sen: TrendResult | None
    mann_kendall: MannKendallResult
    diagnostics: dict[str, Any]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Level of the check for dependence beyond lag 1. It is deliberately looser
# than the usual 0.05 so that doubtful cases are withheld rather than reported.
DEPENDENCE_CHECK_LEVEL = 0.10


def _direction(slope: float, tolerance: float = 0.0) -> str:
    """Sign of the estimate; values within rounding error of zero are constant."""
    if abs(slope) <= tolerance:
        return "constant"
    return "increasing" if slope > 0 else "decreasing"


def _phases(dates: pd.DatetimeIndex, period: int) -> np.ndarray:
    """Seasonal position of each observation from its calendar date.

    Calendar months are used for monthly data so that a missing month cannot
    shift every later observation into the wrong season.
    """
    if period == 12:
        return np.asarray(dates.month - 1)
    return np.arange(len(dates)) % period


# Minimum number of annual values for significance testing. Below 30 the result
# is reported with a limited-power warning.
MIN_ANNUAL_INFERENCE = 15
FIXED_B_REPLICATES = 20000


def _fixed_b_statistics(values: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Slopes (per step) and Kiefer-Vogelsang fixed-b standard errors (Bartlett
    kernel, bandwidth = n) for each row of ``values`` (equally spaced).

    S_t is the running sum of the slope's influence terms; the variance
    estimate is 2 * sum(S_t^2) / n^3 (Kiefer and Vogelsang 2002)."""
    x = np.arange(n, dtype=float)
    X = np.column_stack([np.ones(n), x])
    g = np.linalg.solve(X.T @ X / n, X.T)[1]          # slope row of Q^-1 X_t
    coef = values @ np.linalg.pinv(X).T               # (rows, 2)
    resid = values - coef @ X.T
    s = np.cumsum(resid * g, axis=1)
    return coef[:, 1], np.sqrt(2 * np.sum(s ** 2, axis=1) / n ** 3)


@lru_cache(maxsize=64)
def _fixed_b_null(n: int) -> np.ndarray:
    """Sorted |statistic| under independent Gaussian noise, the finite-sample
    reference distribution for n equally spaced values (fixed seed)."""
    draws = np.random.default_rng(20261115).normal(size=(FIXED_B_REPLICATES, n))
    slope, se = _fixed_b_statistics(draws, n)
    return np.sort(np.abs(slope / se))


def _fixed_b_test(y: np.ndarray, alpha: float) -> tuple[float, float, float]:
    """Two-sided p-value, critical value and standard error (per step) of the
    fixed-b trend test (Kiefer and Vogelsang 2002, doi:10.1111/1468-0262.00366).

    The statistic does not depend on the noise variance and its fixed-b limit
    does not depend on short-range autocorrelation; the reference
    distribution is simulated, so the p-value carries Monte Carlo error of
    about 0.0015 near 0.05."""
    n = len(y)
    null = _fixed_b_null(n)
    slope, se = (float(v[0]) for v in _fixed_b_statistics(y[None, :], n))
    exceed = len(null) - np.searchsorted(null, abs(slope / se), side="left")
    return (1 + exceed) / (len(null) + 1), float(np.quantile(null, 1 - alpha)), se


def _seasonal_sen(x: np.ndarray, y: np.ndarray, phases: np.ndarray) -> float:
    """Seasonal Theil-Sen (Hirsch et al. 1982): median of the pairwise slopes
    computed within each calendar month only, using actual elapsed years, so
    the seasonal cycle and missing months do not bias the estimate."""
    slopes = []
    for phase in np.unique(phases):
        xi, yi = x[phases == phase], y[phases == phase]
        i, j = np.triu_indices(len(xi), 1)
        slopes.append((yi[j] - yi[i]) / (xi[j] - xi[i]))
    return float(np.median(np.concatenate(slopes)))


def _annual_anomaly_inference(dates, deseasonalized, metadata, alpha, regression, sen,
                              diagnostics, warnings, result):
    """Significance for monthly data, tested with the annual method on the
    annual means of the deseasonalized values. Months within a year are not
    independent; testing 12 values per year as if they were overstates the
    evidence (simulated false-positive rates up to 11% with year-to-year
    persistence, docs/ANALYSIS.md). Using years makes the monthly and annual
    results the same test. Deseasonalized values have no seasonal cycle, so a
    year missing one month still gives an unbiased (slightly noisier) mean;
    years missing more are left out."""
    table = pd.DataFrame({"year": dates.year, "value": deseasonalized}).groupby("year")["value"].agg(["mean", "size"])
    table = table[table["size"] >= 11]
    annual = analyze_timeseries(
        # Mid-year dates, the centre of each annual mean.
        pd.DataFrame({"date": pd.to_datetime(table.index.astype(str) + "-07-01"), "value": table["mean"].to_numpy()}),
        {**metadata, "temporal_resolution": "annual"}, alpha=alpha)
    diagnostics["annual_anomaly_status"] = annual.status
    diagnostics["annual_anomaly_years"] = annual.n
    tested_ok = annual.regression is not None and annual.regression.p_value is not None
    note = (f"Significance {'was' if tested_ok else 'is'} tested on annual means of the "
            f"deseasonalized values ({annual.n} annual values{'' if tested_ok else ' available'}), "
            "the same test used for annual data, because months within a year are not independent.")
    reasons = [w for w in annual.warnings if w not in warnings]
    warnings.extend([note] + reasons)
    if not tested_ok:
        if not any("withheld" in w for w in reasons):  # the annual step gave no specific reason
            warnings.append("Inference withheld: the annual test could not be carried out.")
        return result("descriptive_only", regression, sen)
    tested = annual.regression
    # Re-express the annual intercept at the first monthly date, so the trend line
    # drawn on the monthly chart is the tested line.
    shift = (pd.Timestamp(annual.origin) - dates[0]).total_seconds() / (86400 * 365.25)
    regression = TrendResult(tested.slope, tested.slope_unit, tested.intercept - tested.slope * shift,
                             tested.direction,
                             "Annual means of deseasonalized monthly values: " + tested.method,
                             tested.p_value, tested.significant,
                             tested.confidence_interval, tested.r_squared)
    for key in ("ar1_p_value", "fixed_b_p_value", "effective_sample_size",
                "residual_lag1_correlation", "beyond_lag1_ljung_box_p_value"):
        diagnostics["annual_" + key] = annual.diagnostics.get(key)
    return result(annual.status, regression, sen, annual.mann_kendall)


def analyze_timeseries(
    frame: pd.DataFrame, metadata: Mapping[str, Any], *, alpha: float = 0.05,
    seasonal_period: int | None = None, date_column: str = "date",
    value_column: str = "value",
) -> AnalysisResult:
    """Analyze one series. Explicit period=1 asserts no recurring seasonality.

    Monthly resolution defaults to period 12, annual/yearly to 1. Other
    resolutions require an explicit period for inference. Rates use elapsed
    Julian years (365.25 days); missing dates are never compressed into steps.
    """
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one.")
    if seasonal_period is not None and (
        isinstance(seasonal_period, bool) or not isinstance(seasonal_period, int)
        or seasonal_period < 1
    ):
        raise ValueError("seasonal_period must be a positive integer.")
    prepared = preprocess_timeseries(frame, metadata, date_column=date_column, value_column=value_column)
    data = prepared.analysis_data
    n = len(data)
    unavailable = MannKendallResult("not assessed", None, None, None, None, None, "not assessed")
    warnings = ["Association does not establish causation; nonsignificance does not establish no change."]
    if prepared.report.missing_measurements or prepared.report.invalid_measurements:
        warnings.append("Missing/invalid measurements excluded explicitly; gaps remain in actual dates.")
    period = seasonal_period
    if period is None:
        period = {"monthly": 12, "annual": 1, "yearly": 1}.get(metadata["temporal_resolution"].lower())
    diagnostics = {"seasonal_period": period, "regular_sampling": False,
                   "residual_ljung_box_p_value": None, "residual_lag1_correlation": None,
                   "seasonal_effect_range": None, "ljung_box_lags": None,
                   "effective_sample_size": None,
                   "beyond_lag1_ljung_box_p_value": None,
                   "beyond_lag1_lags": None, "beyond_lag1_level": None}

    def result(status, regression=None, sen=None, test=unavailable):
        return AnalysisResult(status, alpha, data[date_column].iloc[0].isoformat() if n else None,
                              n, prepared.report, prepared.metadata, regression, sen,
                              test, diagnostics, tuple(warnings))

    if n < 3:
        warnings.append("At least three finite observations at distinct dates are required for estimates.")
        return result("insufficient_data")
    if n > 5000:
        raise ValueError("Sen's slope is quadratic; restrict analysis to at most 5000 valid observations.")
    dates = pd.DatetimeIndex(data[date_column])
    x = np.asarray((dates - dates[0]).total_seconds(), dtype=float) / (86400 * 365.25)
    y = data[value_column].to_numpy(dtype=float)
    regular = pd.infer_freq(dates) is not None
    diagnostics["regular_sampling"] = regular
    unit = f"{metadata['unit']}/year"
    if np.all(y == y[0]):
        trend = TrendResult(0.0, unit, float(y[0]), "constant", "constant series")
        warnings.append("Constant series: zero descriptive slopes; inferential uncertainty is undefined.")
        return result("constant", trend, trend,
                      MannKendallResult("tie-only series", 0.0, 0.0, 0.0, 1.0, False, "not significant"))

    # Seasonal fixed effects are used only on a complete regular sequence.
    design = np.column_stack([np.ones(n), x])
    if period and period > 1:
        phases = _phases(dates, period)
        seasons_covered = all(np.sum(phases == i) >= 2 for i in range(period))
        if n < 3 * period or not seasons_covered or (period != 12 and not regular):
            # A straight line through a seasonal cycle mostly measures the
            # cycle, not a long-term change, so no rate is reported.
            warnings.append("Trend rate withheld: the series is too short or incomplete to separate "
                            f"the seasonal cycle from a long-term trend (at least {3 * period} "
                            "observations covering every season are required).")
            return result("seasonal_adjustment_unavailable")
        design = np.column_stack([design, *[(phases == i).astype(float) for i in range(1, period)]])
    fit = OLS(y, design).fit()
    slope = float(fit.params[1])
    # Average seasonal effect, so intercept + offset + slope * years is the
    # long-term trend with the seasonal cycle averaged out.
    diagnostics["seasonal_mean_offset"] = float(np.mean(np.r_[0, fit.params[2:]]))
    if design.shape[1] > 2:
        diagnostics["seasonal_effect_range"] = float(np.ptp(np.r_[0, fit.params[2:]]))
    # A slope this small is floating-point rounding, not a direction.
    tolerance = 1e-10 * float(np.ptp(y)) / float(x[-1] - x[0])
    regression = TrendResult(slope, unit, float(fit.params[0]), _direction(slope, tolerance),
                             "OLS with seasonal fixed effects" if design.shape[1] > 2 else "OLS",
                             r_squared=float(fit.rsquared))
    # Monthly data use calendar months and actual elapsed time, so a missing
    # month leaves a gap instead of shifting later values; other cadences
    # still need regular sampling.
    monthly = period == 12
    if monthly:
        sen_slope = _seasonal_sen(x, y, _phases(dates, period))
        sen = TrendResult(sen_slope, unit, float(np.median(y - sen_slope * x)),
                          _direction(sen_slope, tolerance),
                          "Seasonal Theil-Sen (median of within-month slopes)")
    else:
        sen_fit = theilslopes(y, x)
        sen = TrendResult(float(sen_fit.slope), unit, float(sen_fit.intercept),
                          _direction(float(sen_fit.slope), tolerance), "Theil-Sen median pairwise slope")
    min_n = MIN_ANNUAL_INFERENCE if period == 1 else max(30, 3 * (period or 1))
    if period is None or n < min_n or not (regular or monthly):
        if period == 1 and regular:
            warnings.append(f"Inference withheld: {n} annual values are available; at least {min_n} "
                            "are required for the significance test.")
        else:
            warnings.append(f"Inference withheld: require regular sampling (gaps are allowed for monthly data), "
                            f"a specified seasonal policy, and at least {min_n} observations.")
        return result("descriptive_only", regression, sen)
    if period == 1 and n < 30:
        warnings.append(f"Only {n} annual values: results are indicative. The tests have limited "
                        "power, so a nonsignificant result is weak evidence either way, a "
                        "significant one is less certain than its p-value suggests, and a "
                        "different start or end year may change the result.")
    if monthly:
        if not regular:
            warnings.append("Some months are missing; they are left as gaps (not filled).")
        diagnostics["monthly_model_slope"] = slope
        return _annual_anomaly_inference(dates, y - design[:, 2:] @ fit.params[2:], metadata,
                                         alpha, regression, sen, diagnostics, warnings, result)
    residual = np.asarray(fit.resid)
    if np.max(np.abs(residual)) <= 1e-12 * max(1.0, float(np.max(np.abs(y)))):
        warnings.append("Near-perfect deterministic fit: residual-based inference withheld.")
        return result("descriptive_only", regression, sen)
    lag = min(max(period, int(np.floor(4 * (n / 100) ** (2 / 9)))), n // 4)
    diagnostics["ljung_box_lags"] = lag
    r1 = float(np.corrcoef(residual[:-1], residual[1:])[0, 1])
    diagnostics["residual_lag1_correlation"] = r1
    lb_p = float(acorr_ljungbox(residual, lags=[lag], return_df=True)["lb_pvalue"].iloc[0])
    diagnostics["residual_ljung_box_p_value"] = lb_p
    # The uncertainty below models lag-1 dependence only. Check whether that is
    # enough: remove the lag-1 component and test what remains. If dependence
    # is still detected (for example at lag 2, or from year to year in monthly
    # data), the method's assumption fails and no significance is reported.
    whitened = residual[1:] - r1 * residual[:-1]
    extra_lags = max(lag, 2)
    extra_p = float(acorr_ljungbox(whitened, lags=[extra_lags], model_df=1,
                                   return_df=True)["lb_pvalue"].iloc[0])
    gate_level = max(alpha, DEPENDENCE_CHECK_LEVEL)
    diagnostics["beyond_lag1_ljung_box_p_value"] = extra_p
    diagnostics["beyond_lag1_lags"] = extra_lags
    diagnostics["beyond_lag1_level"] = gate_level
    if not extra_p >= gate_level:  # also true when the check is undefined
        warnings.append("Inference withheld: residual dependence beyond lag 1 was detected, which "
                        "the significance methods used here do not model.")
        return result("descriptive_only", regression, sen)
    # Uncertainty allowing for lag-1 autocorrelation: the residual variance and
    # degrees of freedom use an effective sample size (Santer et al. 2008).
    # The lag-1 estimate is bias-corrected for short series and negative
    # values are treated as zero, so the result is never less cautious than
    # ordinary least squares.
    r1_adjusted = min(max(r1 + (1 + 4 * r1) / n, 0.0), 0.99)
    effective_n = n * (1 - r1_adjusted) / (1 + r1_adjusted)
    diagnostics["effective_sample_size"] = float(effective_n)
    dof = effective_n - design.shape[1]
    if dof < 1:
        warnings.append("Inference withheld: residuals are so strongly autocorrelated that the "
                        "effective number of independent observations is too small.")
        return result("descriptive_only", regression, sen)
    se = float(np.sqrt(residual @ residual / dof * np.linalg.inv(design.T @ design)[1, 1]))
    p = float(2 * student_t.sf(abs(slope / se), dof))
    half_width = float(student_t.ppf(1 - alpha / 2, dof)) * se
    ci = (slope - half_width, slope + half_width)
    uncertainty = "; AR(1) effective-sample-size uncertainty"
    if period == 1 and regular:
        # Second, independent safeguard against autocorrelation: the fixed-b
        # test (no autocorrelation model). Significant only if BOTH reject
        # (intersection-union rule): p is the larger p-value and the interval is
        # the union of both intervals, so interval and decision always agree.
        p_fixed_b, critical, se_step = _fixed_b_test(y, alpha)
        se_fixed_b = se_step / (float(x[-1]) / (n - 1))  # per step -> per year
        diagnostics.update(ar1_p_value=p, fixed_b_p_value=p_fixed_b, fixed_b_standard_error=se_fixed_b)
        ci = (min(ci[0], slope - critical * se_fixed_b), max(ci[1], slope + critical * se_fixed_b))
        p = float(max(p, p_fixed_b))  # plain float: the UI checks `significant is True`
        uncertainty = ("; significant only if both the AR(1) effective-sample-size test and the "
                       "fixed-b test reject (p = larger p-value; interval = union of both)")
    regression = TrendResult(slope, unit, float(fit.params[0]), regression.direction,
                             regression.method + uncertainty, p, bool(p < alpha), ci, float(fit.rsquared))
    warnings.append("Significance allows for year-to-year persistence approximately. With strongly "
                    "persistent variability over several years, simulated false-positive rates reach "
                    "12-17% at 21 years instead of 5% (docs/ANALYSIS.md).")
    if period == 1:
        # Same lag-1 correction applied to the Mann-Kendall variance.
        test = mk.original_test(y, alpha=alpha)
        z = float(test.z) / float(np.sqrt((1 + r1_adjusted) / (1 - r1_adjusted)))
        mk_p = float(2 * norm.sf(abs(z)))
        mk_sig = bool(mk_p < alpha)
        decision = ("increasing" if z > 0 else "decreasing") if mk_sig else "not significant"
        mk_result = MannKendallResult("Mann-Kendall with lag-1 variance correction",
                                     float(test.s), z, float(test.Tau), mk_p, mk_sig, decision)
        warnings.append("Mann-Kendall variance is inflated for lag-1 autocorrelation; "
                        "higher-order dependence is not modelled.")
        return result("inference_available", regression, sen, mk_result)
    if lb_p < alpha:
        warnings.append("Residual autocorrelation detected: seasonal Mann-Kendall inference withheld; "
                        "the regression result already allows for autocorrelation.")
        return result("partial_inference", regression, sen)
    test = mk.seasonal_test(y, period=period, alpha=alpha)
    mk_result = MannKendallResult("seasonal Mann-Kendall",
                                 float(test.s), float(test.z), float(test.Tau), float(test.p),
                                 bool(test.h), str(test.trend) if test.h else "not significant")
    warnings.append("Seasonal Mann-Kendall is conditional on independent observations within seasonal strata; a nonsignificant residual diagnostic does not prove independence.")
    return result("inference_available", regression, sen, mk_result)
