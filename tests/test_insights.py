"""Explanations and EarthTrend Insights: wording must follow the actual result fields."""
import pytest

from earthtrend.analysis import MIN_ANNUAL_INFERENCE
from earthtrend.data import giovanni
from earthtrend.pipeline import AnalysisRequest, run_analysis
from earthtrend.ui import text

BANNED = ("climate change", "drought", "caused by", "because of human", "ecosystem", "global warming")


def trend(significant, slope=0.05, direction="increasing", p=0.01, ci=(0.01, 0.09), years=35, notes=()):
    tested = significant is not None
    return {"slope": slope, "slope_unit": "C/year", "direction": direction,
            "significant": significant, "p_value": p if tested else None,
            "ci_low": ci[0] if tested else None, "ci_high": ci[1] if tested else None,
            "ci_level": 0.95 if tested else None, "test_years": years, "notes": list(notes),
            "analysis_details": {"sen": {"slope": 0.04, "slope_unit": "C/year"},
                                 "mann_kendall": {"significant": significant, "p_value": p if tested else None}}}


def read(t, **kw):
    options = dict(variable_name="Air temperature", source_label="NASA POWER (MERRA2)", place="Cairo",
                   period="1991–2025", resolution="annual", n_valid=35, n_total=35,
                   required_years=MIN_ANNUAL_INFERENCE)
    options.update(kw)
    return text.insights(t, **options)


def flat(reading):
    return " ".join(line for group in reading.values() for line in group)


def test_significant_increasing_and_decreasing():
    up = flat(read(trend(True)))
    assert "data support an increasing trend" in up and "+0.05 C/year" in up and "p-value 0.010" in up
    down = flat(read(trend(True, slope=-0.05, direction="decreasing", ci=(-0.09, -0.01))))
    assert "data support a decreasing trend" in down and "-0.05 C/year" in down
    for message in (up, down):
        assert "Compare with another data source" in message
        assert "does not show its cause" in message


def test_short_tested_record_is_called_indicative():
    assert "21 annual values, so treat it as indicative" in flat(read(trend(True, years=21)))
    assert "indicative" not in flat(read(trend(True, years=35)))


def test_non_significant_is_not_proof_of_no_change():
    message = flat(read(trend(False, p=0.4, ci=(-0.02, 0.12))))
    assert "did not find sufficient statistical evidence" in message
    assert "does not prove that nothing changed" in message
    assert "data support" not in message


def test_withheld_gives_reason_and_no_invented_numbers():
    note = "Inference withheld: 11 annual values are available; at least 15 are required for the significance test."
    reading = read(trend(None, years=11, notes=[note]), resolution="monthly", n_valid=132, n_total=132)
    message = flat(reading)
    assert "132 of 132 monthly values are valid" in message
    assert "Significance was not tested" in message and "not statistically established" in message
    assert "11 annual values; at least 15 are required" in message
    assert "Extend the period to at least 15 years" in message
    assert "p-value" not in message and "confidence interval" not in message
    assert "data support" not in message and "significant" not in message.replace("Significance was not tested", "")


def test_withheld_for_dependence_quotes_the_analysis_reason():
    note = "Inference withheld: residual dependence beyond lag 1 was detected, which the significance methods used here do not model."
    message = flat(read(trend(None, years=21, notes=[note])))
    assert "Reason: residual dependence beyond lag 1 was detected" in message
    assert "Extend the period" not in message


def test_insufficient_data_and_missing_values():
    note = "Trend rate withheld: the series is too short or incomplete to separate the seasonal cycle from a long-term trend (at least 36 observations covering every season are required)."
    reading = read({"slope": None, "significant": None, "notes": [note]}, resolution="monthly",
                   n_valid=20, n_total=24, n_missing=4)
    message = flat(reading)
    assert "A reliable trend cannot be estimated" in message and "at least 36 observations" in message
    assert "4 value(s) are missing" in message and "Check the missing values" in message
    assert "A reliable trend cannot be estimated" in flat(read(None))


def test_no_unsupported_claims_in_any_case():
    cases = [trend(True), trend(True, slope=-0.05, direction="decreasing"), trend(False), trend(None, years=11), None]
    for case in cases:
        message = flat(read(case)).lower()
        assert not any(word in message for word in BANNED)
    assert "need not match" in flat(read(trend(True)))  # sources are not expected to agree


def test_explanations_cover_every_reported_term():
    terms = {term for term, _, _ in text.GLOSSARY}
    for required in ("Trend direction", "Trend rate", "Significance (regression)", "P-value",
                     "Confidence interval", "Valid observations", "OLS with seasonal fixed effects",
                     "Mann–Kendall decision", "Mann–Kendall p-value", "Sen’s slope",
                     "Inference withheld", "Missing observations and gaps"):
        assert required in terms
    plain = dict((term, simple) for term, simple, _ in text.GLOSSARY)
    assert "it is not zero" in plain["P-value"]
    assert "does not prove that nothing changed" in plain["Significance (regression)"]


def test_explain_result_for_each_status():
    tested = text.explain_result(trend(True), 35, 35, "annual", 15)
    assert "test was run" in tested and "at least 15 annual values" in tested
    withheld = text.explain_result(trend(None, years=11), 132, 132, "monthly", 15)
    assert "132 of 132 monthly values" in withheld and "11 annual values" in withheld
    assert "no p-value and no confidence interval" in withheld and "description only" in withheld
    assert "No trend rate could be estimated" in text.explain_result(None, 0, 12, "monthly", 15)


@pytest.mark.parametrize("resolution,n", [("monthly", 132), ("annual", 11)])
def test_short_real_series_gives_rate_but_no_inference(resolution, n):
    """2015-2025: enough data for a descriptive rate, too few years for the test."""
    request = AnalysisRequest(("T2M",), None, None, 2015, 2025, resolution,
                              giovanni.REGIONS["jordan"], "giovanni_saved", "jordan")
    item = run_analysis(request).variables[0]
    t = item.trend
    assert item.n_valid == n and t["slope"] is not None
    assert t["p_value"] is None and t["significant"] is None and t["ci_low"] is None and t["ci_high"] is None
    assert t["test_years"] == 11
    withheld = [note for note in t["notes"] if "withheld" in note]
    assert withheld == ["Inference withheld: 11 annual values are available; at least 15 are required "
                        "for the significance test."]
    assert not any("was tested" in note for note in t["notes"])
    assert text.significance_label(t) == "Not tested (see notes)"
    assert text.format_p_value(t["p_value"]) == text.NOT_REPORTED
    message = flat(text.insights(t, variable_name=item.name, source_label="NASA Giovanni", place="Jordan",
                                 period="2015–2025", resolution=resolution, n_valid=item.n_valid,
                                 n_total=item.n_total, required_years=MIN_ANNUAL_INFERENCE))
    assert "11 annual values; at least 15 are required" in message


def test_app_shows_both_sections_for_a_short_range(monkeypatch):
    from pathlib import Path
    from unittest.mock import Mock
    from streamlit.testing.v1 import AppTest
    from earthtrend.data import power_client
    from earthtrend.ui.components import SAVED_SOURCE

    monkeypatch.setattr(power_client, "get_monthly_series", Mock(side_effect=AssertionError("No network")))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60).run()
    app.selectbox[0].select(SAVED_SOURCE).run()
    for control in app.number_input:
        if control.label == "Start year":
            control.set_value(2015)
    app.run()
    app.button[0].click().run()
    assert not app.exception
    assert "Understanding Your Results" in [e.label for e in app.expander]
    shown = " ".join(m.value for m in app.markdown) + " ".join(i.value for i in app.info)
    assert "EarthTrend Insights" in shown
    assert "132 of 132 monthly values are valid" in shown
    assert "11 annual values" in shown and "at least 15" in shown
