"""Real committed Giovanni CSV integration tests; no network requests."""
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from earthtrend.analysis import analyze_timeseries
from earthtrend.data import giovanni
from earthtrend.pipeline import AnalysisRequest, run_analysis
from earthtrend.plotting import make_timeseries_figure

FULL_MONTHS = list(pd.date_range("2005-01-01", "2025-12-01", freq="MS"))


def request(variables=("T2M",), region="jordan", start=2005, end=2025, resolution="monthly"):
    return AnalysisRequest(tuple(variables), None, None, start, end, resolution,
                           giovanni.REGIONS[region], "giovanni_saved", region)


def test_load_committed_csv_and_preserve_values():
    result = giovanni.load_saved(["T2M"], "jordan", 2005, 2025)
    assert result.data.date.tolist() == FULL_MONTHS
    assert result.data.value.iloc[0] == 7.74990225
    assert result.metadata["download_date"] == "2026-11-14"
    assert result.data.latitude.isna().all()


@pytest.mark.parametrize("code", list(giovanni.DATASETS))
def test_every_saved_dataset_loads_and_gets_a_trend(code):
    """Every variable offered in the UI maps to a real file and yields estimates."""
    region = giovanni.DATASETS[code]["region"]
    output = run_analysis(request([code], region), fetch=Mock(side_effect=AssertionError("no POWER")))
    item = output.variables[0]
    assert item.n_valid >= 251 and item.unit == giovanni.DATASETS[code]["unit"]
    assert item.trend_error is None
    assert item.trend["slope"] is not None
    assert item.trend.get("trend_line"), "monthly charts draw the deseasonalized trend"
    # Tested, or withheld with the reason stated (EVAP: dependence beyond lag 1).
    assert item.trend["p_value"] is not None or any("Inference withheld" in n for n in item.trend["notes"])


def test_aqaba_sst_months_follow_giovanni_data_day_convention():
    """Regression: MODIS files are stamped with the data-day start (e.g. 2004-12-31 = January).
    A one-month shift moved the seasonal peak to July for 2005-2021."""
    sst = giovanni.load_saved(["SST_NIGHT"], "aqaba", 2005, 2025).data
    assert sst.date.min() == pd.Timestamp("2005-01-01") and sst.value.iloc[0] == 21.7604561
    assert [d for d in FULL_MONTHS if d not in set(sst.date)] == [pd.Timestamp("2006-12-01")]
    assert not sst.date.duplicated().any()
    for early in (True, False):
        part = sst[(sst.date.dt.year < 2022) == early]
        climatology = part.groupby(part.date.dt.month).value.mean()
        assert climatology.idxmax() == 8 and climatology.idxmin() in (2, 3)


def test_annual_means_are_day_weighted_complete_years_only():
    result = giovanni.load_saved(["SST_NIGHT"], "aqaba", 2005, 2025)
    assert 2006 not in set(result.annual.year)  # December 2006 is missing
    assert len(result.annual) == 20
    t2m = giovanni.load_saved(["T2M"], "jordan", 2010, 2010)
    days = t2m.data.date.dt.days_in_month
    assert t2m.annual.value.iloc[0] == pytest.approx((t2m.data.value * days).sum() / 365)


def test_annual_saved_series_is_tested_with_limited_power_note():
    item = run_analysis(request(resolution="annual")).variables[0]
    assert item.n_valid == 21
    assert item.trend["p_value"] is not None
    assert any("limited power" in note for note in item.trend["notes"])


@pytest.mark.parametrize("resolution", ["annual", "monthly"])
def test_tested_result_is_labelled_as_tested(resolution):
    """Regression: a NumPy bool decision made the UI show "Not tested" for tested results."""
    from earthtrend.ui import text
    trend = run_analysis(request(resolution=resolution)).variables[0].trend
    assert type(trend["significant"]) is bool
    assert text.significance_label(trend) == "Statistically significant (indicative: 21 years)"


def test_pipeline_uses_same_scientific_functions_without_power():
    fetch = Mock(side_effect=AssertionError("Saved source must not call POWER"))
    output = run_analysis(request(start=2010, end=2020), fetch=fetch)
    fetch.assert_not_called()
    item = output.variables[0]
    assert item.preprocessing_applied
    assert item.n_valid == 132
    direct = analyze_timeseries(item.series, {**output.metadata, "unit": "C"})
    assert item.trend["analysis_details"] == direct.to_dict()
    fig = make_timeseries_figure(item.series, item.trend, variable="T2M",
                                 metadata=output.metadata, start_date="2010-01-01", end_date="2020-12-31")
    assert "Jordan" in fig.layout.title.text
    assert "Point" not in fig.layout.title.text
    assert "NASA POWER" not in fig.to_json()
    assert "2026-11-14" in fig.to_json()


@pytest.mark.parametrize("codes,region,start,end", [
    (["T2M"], "jordan", 2004, 2025), (["T2M"], "jordan", 2005, 2026), (["T2M"], "jordan", 2020, 2010),
    (["SST_NIGHT"], "jordan", 2005, 2025), (["T2M"], "aqaba", 2005, 2025), ([], "jordan", 2005, 2025),
])
def test_reject_unsupported_selections(codes, region, start, end):
    with pytest.raises(ValueError):
        giovanni.load_saved(codes, region, start, end)


def test_saved_source_ui_hides_location_and_renders_results(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from earthtrend.data import power_client
    from earthtrend.ui.components import SAVED_SOURCE

    monkeypatch.setattr(power_client, "get_monthly_series", Mock(side_effect=AssertionError("No network")))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60).run()
    app.selectbox[0].select(SAVED_SOURCE).run()
    assert not app.exception
    assert [s.label for s in app.selectbox] == ["Data source", "Region"]
    assert app.multiselect[0].options == [giovanni.DATASETS[c]["name"] + f" ({giovanni.DATASETS[c]['unit']})"
                                          for c in giovanni.variables_for("jordan")]
    for control in app.number_input:
        assert (control.min, control.max) == (2005, 2025)
    app.button[0].click().run()
    assert not app.exception
    assert any("Jordan" in c.value for c in app.caption)
    assert any("not live" in info.value.lower() for info in app.info)
    assert any(m.label == "Trend rate" for m in app.metric)
    assert "Study location map" not in [e.label for e in app.expander]
    for element in [*app.caption, *app.markdown, *app.info, *app.warning]:
        assert "NASA POWER" not in element.value

    app.selectbox[1].select("aqaba").run()
    assert app.multiselect[0].options == ["Night-time sea surface temperature (C)"]
    app.button[0].click().run()
    assert not app.exception
    assert any("Gulf of Aqaba" in c.value for c in app.caption)
    assert any("1 month(s) absent from the source" in m.value for m in app.markdown)
