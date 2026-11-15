"""Tests for the NASA POWER client.

Two kinds of input are used and kept apart on purpose:

* REAL: tests/fixtures/power_monthly_cairo.json is an unmodified response
  from the NASA POWER API (see tests/fixtures/README.md).
* SYNTHETIC: payloads built by ``_synthetic_payload`` are made-up numbers used
  only to exercise edge cases. They are not NASA data.

No test contacts the network.
"""

import json
import math
from pathlib import Path

import pandas as pd
import pytest
import requests

from earthtrend.data import power_client as pc

FIXTURE = Path(__file__).parent / "fixtures" / "power_monthly_cairo.json"


@pytest.fixture
def real_payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _synthetic_payload(values, fill_value=-999.0):
    """SYNTHETIC payload in the POWER layout. Not NASA data."""
    return {
        "geometry": {"type": "Point", "coordinates": [10.0, 20.0, 5.0]},
        "properties": {"parameter": {"T2M": values}},
        "header": {"fill_value": fill_value, "sources": ["SYNTHETIC"]},
        "parameters": {"T2M": {"units": "C", "longname": "Synthetic temperature"}},
    }


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=None):
        self.status_code = status_code
        self._body = body
        self._text = text
        self.url = "https://example.invalid/request"

    def json(self):
        if self._text is not None:
            raise ValueError("not json")
        return self._body


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if self.error:
            raise self.error
        return self.response


# --- parsing a real response -------------------------------------------------

def test_real_response_has_standard_columns_and_types(real_payload):
    result = pc.parse_monthly_response(real_payload)
    assert list(result.data.columns) == pc.TIMESERIES_COLUMNS
    assert pd.api.types.is_datetime64_any_dtype(result.data["date"])
    assert result.data["value"].dtype == float
    assert set(result.data["variable"]) == {"T2M", "PRECTOTCORR"}


def test_real_response_row_counts_exclude_annual_key(real_payload):
    result = pc.parse_monthly_response(real_payload)
    # 12 months of 2025 + 11 months of 2026 were returned; "202513" is annual.
    for code in ("T2M", "PRECTOTCORR"):
        rows = result.data[result.data["variable"] == code]
        assert len(rows) == 23
        assert rows["date"].dt.month.between(1, 12).all()
        assert rows["date"].is_unique


def test_real_response_values_match_source(real_payload):
    result = pc.parse_monthly_response(real_payload)
    t2m = result.data[result.data["variable"] == "T2M"].set_index("date")["value"]
    assert t2m[pd.Timestamp("2025-01-01")] == 14.65
    assert t2m[pd.Timestamp("2026-09-01")] == 28.21


def test_real_response_fill_values_become_nan_not_zero(real_payload):
    result = pc.parse_monthly_response(real_payload)
    for code in ("T2M", "PRECTOTCORR"):
        series = result.data[result.data["variable"] == code].set_index("date")["value"]
        assert math.isnan(series[pd.Timestamp("2026-10-01")])
        assert math.isnan(series[pd.Timestamp("2026-11-01")])
        assert series.isna().sum() == 2
        assert result.metadata["missing_counts"][code] == 2
    assert not (result.data["value"] == -999.0).any()


def test_real_zero_precipitation_is_kept_as_zero(real_payload):
    result = pc.parse_monthly_response(real_payload)
    prec = result.data[result.data["variable"] == "PRECTOTCORR"].set_index("date")["value"]
    assert prec[pd.Timestamp("2025-08-01")] == 0.0  # a real dry month, not missing


def test_real_response_annual_values_are_separate(real_payload):
    result = pc.parse_monthly_response(real_payload)
    assert list(result.annual.columns) == pc.ANNUAL_COLUMNS
    t2m = result.annual[result.annual["variable"] == "T2M"]
    assert t2m["year"].tolist() == [2025]  # 2026 was incomplete: no annual value
    assert t2m["value"].tolist() == [22.54]


def test_real_response_preserves_units_source_and_location(real_payload):
    result = pc.parse_monthly_response(real_payload)
    units = result.data.groupby("variable")["unit"].unique().to_dict()
    assert units["T2M"].tolist() == ["C"]
    assert units["PRECTOTCORR"].tolist() == ["mm/day"]
    assert (result.data["source"] == "NASA POWER (MERRA2)").all()
    assert (result.data["latitude"] == 30.05).all()
    assert (result.data["longitude"] == 31.25).all()
    meta = result.metadata
    assert meta["fill_value"] == -999.0
    assert meta["temporal_resolution"] == "monthly"
    assert meta["sources"] == ["MERRA2"]
    assert meta["is_synthetic"] is False


# --- parsing edge cases (synthetic payloads) ---------------------------------

def test_fill_value_is_read_from_header_not_assumed():
    payload = _synthetic_payload({"200001": -999.0, "200002": -1.0}, fill_value=-1.0)
    values = pc.parse_monthly_response(payload).data["value"].tolist()
    assert values[0] == -999.0
    assert math.isnan(values[1])


def test_null_value_becomes_nan():
    payload = _synthetic_payload({"200001": None, "200002": 3.5})
    values = pc.parse_monthly_response(payload).data["value"].tolist()
    assert math.isnan(values[0]) and values[1] == 3.5


@pytest.mark.parametrize("values", [{"2000": 1.0}, {"200014": 1.0}, {"200001": "warm"}])
def test_unexpected_content_is_rejected(values):
    with pytest.raises(pc.PowerResponseError):
        pc.parse_monthly_response(_synthetic_payload(values))


def test_missing_fill_value_is_rejected():
    payload = _synthetic_payload({"200001": 1.0})
    del payload["header"]["fill_value"]
    with pytest.raises(pc.PowerResponseError):
        pc.parse_monthly_response(payload)


def test_missing_section_is_rejected():
    with pytest.raises(pc.PowerResponseError):
        pc.parse_monthly_response({"messages": []})


# --- request building and validation -----------------------------------------

def test_request_params_use_documented_names():
    params = pc.build_request_params(["t2m", "PRECTOTCORR"], 30.05, 31.25, 1990, 2020)
    assert params == {
        "parameters": "T2M,PRECTOTCORR",
        "community": "ag",
        "latitude": 30.05,
        "longitude": 31.25,
        "start": 1990,
        "end": 2020,
        "format": "JSON",
    }


@pytest.mark.parametrize(
    "args",
    [
        ([], 0, 0, 2000, 2001),
        (["T2M", "T2M"], 0, 0, 2000, 2001),
        (["T2M"], 91, 0, 2000, 2001),
        (["T2M"], 0, 181, 2000, 2001),
        (["T2M"], float("nan"), 0, 2000, 2001),
        (["T2M"], "30", 0, 2000, 2001),
        (["T2M"], 0, 0, 2001, 2000),
        (["T2M"], 0, 0, 2000.5, 2001),
    ],
)
def test_invalid_input_is_rejected_before_any_request(args):
    session = FakeSession(FakeResponse())
    with pytest.raises(pc.PowerInputError):
        pc.fetch_monthly_point(*args, session=session)
    assert session.calls == []


# --- HTTP behaviour (no network) ---------------------------------------------

def test_successful_fetch_and_parse(real_payload):
    session = FakeSession(FakeResponse(200, real_payload))
    result = pc.get_monthly_series(
        ["T2M", "PRECTOTCORR"], 30.05, 31.25, 2025, 2026, session=session, timeout=7
    )
    call = session.calls[0]
    assert call["url"] == "https://power.larc.nasa.gov/api/temporal/monthly/point"
    assert call["timeout"] == 7
    assert len(result.data) == 46
    assert result.metadata["retrieved_at_utc"]


def test_http_error_carries_power_messages():
    body = {"header": "failed", "messages": ["One of your parameters is incorrect: NOPE."]}
    session = FakeSession(FakeResponse(422, body))
    with pytest.raises(pc.PowerRequestError) as info:
        pc.fetch_monthly_point(["NOPE"], 0, 0, 2000, 2001, session=session)
    assert info.value.status_code == 422
    assert "NOPE" in str(info.value)


def test_http_error_without_json_body():
    session = FakeSession(FakeResponse(503, text="Service Unavailable"))
    with pytest.raises(pc.PowerRequestError) as info:
        pc.fetch_monthly_point(["T2M"], 0, 0, 2000, 2001, session=session)
    assert info.value.status_code == 503


def test_timeout_is_reported():
    session = FakeSession(error=requests.Timeout("slow"))
    with pytest.raises(pc.PowerTimeoutError):
        pc.fetch_monthly_point(["T2M"], 0, 0, 2000, 2001, session=session)


def test_connection_failure_is_reported():
    session = FakeSession(error=requests.ConnectionError("offline"))
    with pytest.raises(pc.PowerConnectionError):
        pc.fetch_monthly_point(["T2M"], 0, 0, 2000, 2001, session=session)


def test_non_json_success_body_is_rejected():
    session = FakeSession(FakeResponse(200, text="<html>"))
    with pytest.raises(pc.PowerResponseError):
        pc.fetch_monthly_point(["T2M"], 0, 0, 2000, 2001, session=session)
