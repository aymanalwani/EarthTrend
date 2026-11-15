"""Wording used by the interface. Pure functions, no Streamlit."""

from __future__ import annotations

import math
from typing import Any

NOT_REPORTED = "Not reported"

CAUSATION_WARNING = (
    "A statistical trend describes how the values changed over the selected "
    "period. It does not establish what caused the change. Attributing a trend "
    "to a specific cause requires additional evidence and analysis."
)

GENERAL_LIMITATIONS = [
    "Values are NASA POWER (MERRA-2 reanalysis) estimates for the grid cell "
    "containing the selected point, not station measurements, and they do not "
    "represent a wider region.",
    "Reanalysis and satellite products are model or retrieval estimates, not "
    "ground-truth observations, and datasets differ in how they define "
    "variables, areas and time periods; results from different sources are "
    "not directly interchangeable.",
    "The result applies only to the selected period; a different start or end "
    "year can give a different trend.",
    "Year-to-year persistence and missing observations affect significance "
    "tests. With strong multi-year persistence and fewer than 30 years, about "
    "10-17% of trendless series can still test as significant (see "
    "docs/ANALYSIS.md). \"Not tested\" means the data did not meet the test's "
    "conditions; it is neither a trend nor its absence.",
    "Testing several variables, places or periods increases the chance that one "
    "of them is significant by chance; no correction for multiple comparisons "
    "is applied.",
]

SEASONALITY_NOTE = (
    "Monthly values contain a seasonal cycle. EarthTrend removes each calendar "
    "month's average before estimating the trend, and tests significance on "
    "annual means of these deseasonalized values, so monthly and annual "
    "resolutions use the same test."
)

ANALYSIS_UNAVAILABLE = (
    "No trend analysis is available for this series. No trend direction, rate "
    "or significance is reported, and none should be read from the chart by eye."
)


INTERPRETATION_UNAVAILABLE = (
    "No interpretation is given because no trend analysis is available. The "
    "chart shows the retrieved observations only."
)


def is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def format_number(value: Any, digits: int = 3) -> str:
    return f"{value:.{digits}g}" if is_number(value) else NOT_REPORTED


def format_p_value(p: Any) -> str:
    if not is_number(p):
        return NOT_REPORTED
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def format_rate(trend: dict) -> str:
    slope = trend.get("slope")
    if not is_number(slope):
        return NOT_REPORTED
    unit = trend.get("slope_unit") or ""
    return f"{slope:+.3g} {unit}".strip()


def format_confidence_interval(trend: dict) -> str:
    low, high = trend.get("ci_low"), trend.get("ci_high")
    if not (is_number(low) and is_number(high)):
        return "Not available"
    level = trend.get("ci_level")
    prefix = f"{level:.0%}: " if is_number(level) else ""
    return f"{prefix}{low:+.3g} to {high:+.3g}"


def significance_label(trend: dict) -> str:
    significant = trend.get("significant")
    years = trend.get("test_years")
    suffix = f" (indicative: {years} years)" if is_number(years) and years < 30 else ""
    if significant is True:
        return "Statistically significant" + suffix
    if significant is False:
        return "Not statistically significant" + suffix
    return "Not tested (see notes)"


def disagreement_note(trend: dict | None) -> str | None:
    """Caution text when regression and Mann-Kendall reach different decisions."""
    if not trend:
        return None
    regression = trend.get("significant")
    mann_kendall = ((trend.get("analysis_details") or {}).get("mann_kendall") or {})
    rank_based = mann_kendall.get("significant")
    if regression is None or rank_based is None or regression == rank_based:
        return None
    mk_p = format_p_value(mann_kendall.get("p_value"))
    reg_p = format_p_value(trend.get("p_value"))
    if regression:
        return (
            f"The two tests disagree: the regression is significant (p-value {reg_p}) "
            f"but the Mann–Kendall test is not (p-value {mk_p}). Regression is more "
            "sensitive to a few extreme values, so treat this trend as uncertain."
        )
    return (
        f"The two tests disagree: the Mann–Kendall test is significant (p-value {mk_p}) "
        f"but the regression is not (p-value {reg_p}). The change may be monotonic "
        "without following a straight line, so treat this result as uncertain."
    )


def interpret(trend: dict | None, variable_name: str, period: str, place: str) -> str:
    """Plain-language summary built only from the values in ``trend``."""
    if trend is None:
        return INTERPRETATION_UNAVAILABLE
    caution = disagreement_note(trend)
    if caution:
        rate = format_rate(trend)
        estimate = f" The estimated rate is {rate}." if rate != NOT_REPORTED else ""
        return (
            f"For {variable_name} at {place} over {period}, the evidence of a "
            f"trend is mixed.{estimate} {caution}"
        )

    direction = trend.get("direction")
    significant = trend.get("significant")
    rate = format_rate(trend)
    p_text = format_p_value(trend.get("p_value"))
    alpha = trend.get("alpha")
    alpha_text = f" at the {alpha:g} significance level" if is_number(alpha) else ""
    subject = f"{variable_name} at {place} over {period}"

    if significant is True:
        text = (
            f"{subject} shows a statistically significant "
            f"{direction or 'monotonic'} trend{alpha_text} (p-value {p_text})."
        )
        if rate != NOT_REPORTED:
            text += f" The estimated rate of change is {rate}."
        return text
    if significant is False:
        text = (
            f"For {subject}, no statistically significant trend was "
            f"detected{alpha_text} (p-value {p_text})."
        )
        if rate != NOT_REPORTED:
            text += (
                f" The estimated rate is {rate}, but the selected test found "
                "insufficient evidence of a trend in this series."
            )
        text += " This is not proof that nothing is changing."
        return text
    return (
        f"The analysis for {subject} did not report a significance decision, "
        "so no conclusion about a trend is drawn."
    )


# --- Understanding your results ------------------------------------------------

# (term, plain explanation, technical explanation). Wording follows the methods
# in earthtrend/analysis.py; see docs/ANALYSIS.md.
GLOSSARY = [
    ("Trend direction",
     "Whether the values went up or down overall in the selected period. It only "
     "describes these data; it does not say whether the change is statistically reliable.",
     "The sign of the fitted slope. Direction and significance are separate results."),
    ("Trend rate",
     "How fast the values changed on average, per year (for example +0.05 C/year).",
     "The slope of a straight line fitted by ordinary least squares (OLS). For monthly "
     "data each calendar month's own average is removed first."),
    ("Significance (regression)",
     "Whether the trend is clear enough that it is unlikely to be a chance pattern in "
     "these data. \"Not significant\" does not prove that nothing changed. \"Not tested\" "
     "means the data did not meet the test's conditions, so there is no answer either way.",
     "Significant only if two tests both reject at the 5% level: a t test with an AR(1) "
     "effective sample size, and a fixed-b test. Monthly data are tested on annual means "
     "of deseasonalized values, because months within a year are not independent."),
    ("P-value",
     "A number between 0 and 1. A small value (below 0.05) means a trend this strong would "
     "be unlikely if there were no real trend. \"Not reported\" means no test was run; it "
     "is not zero.",
     "The larger of the two tests' p-values. It is not the probability that the trend is real."),
    ("Confidence interval",
     "A range of rates that fits the data reasonably well. If the range includes zero, "
     "\"no change\" cannot be ruled out.",
     "A 95% interval: the union of the two tests' intervals, so it excludes zero exactly "
     "when the result is significant."),
    ("Valid observations",
     "How many data values were usable. For monthly data the significance test uses one "
     "value per year, so 132 months give only 11 values for the test.",
     "Rows with a finite value. Annual values used by the test come from years with at "
     "least 11 valid months."),
    ("OLS with seasonal fixed effects",
     "The method behind the trend rate for monthly data: a straight line plus a separate "
     "average level for each calendar month, so the yearly cycle is not mistaken for a trend.",
     "Ordinary least squares with one intercept shift per calendar month."),
    ("Mann–Kendall decision",
     "A second, separate trend test. It asks whether the values tend to keep rising or keep "
     "falling, without assuming a straight line. \"Not assessed\" means it was not run.",
     "A rank-based test with a lag-1 variance correction, run on the same annual values. "
     "It is a secondary check and does not decide the headline significance."),
    ("Mann–Kendall p-value",
     "The p-value of that second test, read the same way as the p-value above.",
     "Two-sided p-value of the corrected Mann–Kendall Z statistic."),
    ("Sen’s slope",
     "A second estimate of the rate that is less affected by a few unusual values. It is a "
     "description, not a test, so it can be shown even when significance is not tested.",
     "The median of pairwise slopes; for monthly data, pairs are taken within the same "
     "calendar month."),
    ("Inference withheld",
     "EarthTrend did not run the significance test because its conditions were not met, "
     "most often too few years. The direction and rate are still shown, as a description only.",
     "The annual test needs a regular series of at least the minimum number of annual "
     "values and no dependence beyond one year that the method cannot model."),
    ("Missing observations and gaps",
     "Months or years with no value. They are left empty: never filled in, never treated as "
     "zero. Many gaps make a trend less reliable.",
     "A year needs at least 11 valid months to count; a missing year in annual data stops "
     "the significance test."),
]


def withheld_reasons(trend: dict | None) -> list[str]:
    """Reasons given by the analysis for not testing significance."""
    return [note.split(":", 1)[1].strip() for note in (trend or {}).get("notes") or []
            if note.startswith(("Inference withheld:", "Trend rate withheld:"))]


def sample_counts(trend: dict | None, n_valid: int, n_total: int, resolution: str,
                  required_years: int) -> str:
    """Monthly and annual sample sizes in one sentence."""
    unit = "monthly" if resolution == "monthly" else "annual"
    counts = f"{n_valid} of {n_total} {unit} values are valid."
    years = (trend or {}).get("test_years")
    if resolution == "monthly" and is_number(years):
        counts += (f" The significance test uses one value per year: {years} annual values "
                   f"are available, and at least {required_years} are required.")
    elif resolution != "monthly":
        counts += f" The significance test requires at least {required_years} annual values."
    return counts


def explain_result(trend: dict | None, n_valid: int, n_total: int, resolution: str,
                   required_years: int) -> str:
    """Why this particular result looks the way it does, in plain words."""
    counts = sample_counts(trend, n_valid, n_total, resolution, required_years)
    reasons = withheld_reasons(trend)
    if trend is None or not is_number(trend.get("slope")):
        return counts + " No trend rate could be estimated" + (f": {reasons[0]}" if reasons else ".")
    if trend.get("significant") is None:
        years = trend.get("test_years")
        if is_number(years) and years < required_years:
            reason = f"there are {years} annual values and the test needs at least {required_years}"
        else:
            reason = reasons[0].rstrip(".") if reasons else "the test's conditions were not met"
        return (f"{counts} A trend rate is shown because a line can always be fitted to the "
                f"data. Its significance was not tested because {reason}. So there is no "
                "p-value and no confidence interval, and the rate is a description only.")
    return counts + " The significance test was run, so a p-value and a confidence interval are shown."


# --- EarthTrend Insights ---------------------------------------------------------

def insights(trend: dict | None, *, variable_name: str, source_label: str, place: str,
             period: str, resolution: str, n_valid: int, n_total: int, n_missing: int = 0,
             absent: int = 0, required_years: int = 15) -> dict[str, list[str]]:
    """Rule-based reading of one result: what the data show, what the statistics
    say, and cautious next steps. Uses only the fields of ``trend``; it never
    states a cause, an impact, or a value that was not computed."""
    unit = "monthly" if resolution == "monthly" else "annual"
    observations = [f"{variable_name} for {place}, {period}, from {source_label}: "
                    f"{n_valid} of {n_total} {unit} values are valid."]
    gaps = n_missing + absent
    if gaps:
        observations.append(f"{gaps} value(s) are missing or absent in the source. They are left "
                            "as gaps and were not filled in.")
    findings: list[str] = []
    steps: list[str] = []
    reasons = withheld_reasons(trend)
    if trend is None or not is_number(trend.get("slope")):
        findings.append("A reliable trend cannot be estimated from this selection"
                        + (f": {reasons[0]}" if reasons else "."))
        steps.append("Choose a longer period: at least 3 full years of monthly values to estimate "
                     f"a rate, and at least {required_years} years to test its significance.")
        if gaps:
            steps.append("Check the missing values listed under Data information.")
        return {"observations": observations, "findings": findings, "next_steps": steps}

    direction = trend.get("direction") or "no clear direction"
    observations.append(f"The fitted rate is {format_rate(trend)} ({direction}).")
    sen = (trend.get("analysis_details") or {}).get("sen") or {}
    if is_number(sen.get("slope")):
        observations.append("Sen’s slope, a second estimate that is less sensitive to unusual "
                            f"values, is {format_rate(sen)}.")
    significant = trend.get("significant")
    years = trend.get("test_years")
    evidence = f"p-value {format_p_value(trend.get('p_value'))}"
    interval = format_confidence_interval(trend)
    if interval != "Not available":
        evidence += f"; confidence interval {interval} {trend.get('slope_unit') or ''}".rstrip()
    caution = disagreement_note(trend)
    if significant is True and not caution:
        article = "an" if direction[:1] in "aeiou" else "a"
        findings.append(f"The data support {article} {direction} trend over this period ({evidence}).")
        if is_number(years) and years < 30:
            findings.append(f"This rests on {years} annual values, so treat it as indicative: a "
                            "different start or end year may change the result.")
        steps.append("Compare with another data source or a nearby place to see whether the "
                     "trend appears there too.")
        steps.append("Look at related variables in EarthTrend for the same place and period.")
    elif significant is True:
        findings.append(caution)
        steps.append("Inspect the chart for a few extreme values or a sudden step, and compare "
                     "another source.")
    elif significant is False:
        findings.append("The test did not find sufficient statistical evidence of a trend "
                        f"({evidence}). This does not prove that nothing changed.")
        if caution:
            findings.append(caution)
        steps.append("A longer period may give a clearer answer.")
        steps.append("Compare with another data source or a nearby place.")
    else:
        findings.append("Significance was not tested. The direction and rate above describe "
                        "these data only and are not statistically established.")
        if is_number(years) and years < required_years:
            findings.append("Reason: the test uses one value per year. This selection gives "
                            f"{years} annual values; at least {required_years} are required.")
            steps.append(f"Extend the period to at least {required_years} years (30 or more gives "
                         "firmer results).")
        else:
            findings.append("Reason: " + (reasons[0] if reasons else "the test's conditions were not met."))
            steps.append("Try a different period or the other temporal resolution, and inspect "
                         "the chart for steps, cycles or gaps.")
        steps.append("Compare with another data source to see whether the direction is similar.")
    if gaps:
        steps.append("Check the missing values listed under Data information before relying on "
                     "the result.")
    steps.append("Results from different sources or places need not match: a country average "
                 "and a single grid cell measure different things.")
    steps.append("A trend does not show its cause; explaining it needs other evidence.")
    return {"observations": observations, "findings": findings, "next_steps": steps}
