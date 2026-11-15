"""Client for the NASA POWER "Monthly and Annual" point API.

Official source
---------------
NASA Prediction Of Worldwide Energy Resources (POWER), NASA Langley Research
Center. https://power.larc.nasa.gov/

Endpoint used: ``GET /api/temporal/monthly/point``
Machine-readable specification:
https://power.larc.nasa.gov/api/temporal/monthly/openapi.json

Design notes
------------
* Units, the fill value, the underlying source model and the coordinates are
  read from each response. Nothing about the data is hard-coded here.
* POWER marks missing values with a fill value (``-999.0`` at the time of
  writing, announced in ``header.fill_value``). Those become ``NaN``. They are
  never converted to zero, and genuine zeros (e.g. a dry month) are kept.
* For every complete year POWER also returns a key ending in ``13``. That is
  the annual value, not a month. It is returned separately in
  ``PowerResult.annual`` so it can never be mistaken for a 13th month.
* This module only retrieves and parses. Sorting, duplicate checks and other
  cleaning belong to the preprocessing module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import numpy as np
import pandas as pd
import requests

POWER_BASE_URL = "https://power.larc.nasa.gov"
MONTHLY_POINT_PATH = "/api/temporal/monthly/point"

# "ag" (agroclimatology) returns temperature in C and precipitation in mm/day.
# The API requires a community; it decides which units are returned.
DEFAULT_COMMUNITY = "ag"
DEFAULT_TIMEOUT_SECONDS = 30

# Parameter identifiers confirmed against
# /api/system/manager/parameters?community=ag&temporal=monthly (2026-11-14).
# The description is for the UI only; units always come from the response.
SUPPORTED_PARAMETERS = {
    "T2M": "Air temperature at 2 metres",
    "PRECTOTCORR": "Precipitation (MERRA-2 bias corrected)",
}

ANNUAL_KEY_SUFFIX = "13"

TIMESERIES_COLUMNS = [
    "date",
    "value",
    "unit",
    "variable",
    "variable_name",
    "latitude",
    "longitude",
    "source",
]
ANNUAL_COLUMNS = ["year", "value", "unit", "variable", "variable_name",
                  "latitude", "longitude", "source"]


class PowerAPIError(Exception):
    """Base class for every error raised by this client."""


class PowerInputError(PowerAPIError, ValueError):
    """The request arguments are invalid; no request was sent."""


class PowerTimeoutError(PowerAPIError):
    """The POWER server did not answer in time."""


class PowerConnectionError(PowerAPIError):
    """The POWER server could not be reached."""


class PowerRequestError(PowerAPIError):
    """POWER answered with an HTTP error status."""

    def __init__(self, status_code: int, messages: list[str]):
        self.status_code = status_code
        self.messages = messages
        detail = " ".join(messages) if messages else "No details returned."
        super().__init__(f"NASA POWER returned HTTP {status_code}: {detail}")


class PowerResponseError(PowerAPIError):
    """POWER answered, but the body is not in the expected format."""


@dataclass
class PowerResult:
    """Parsed POWER response.

    data:     monthly observations, one row per variable and month.
    annual:   annual values as delivered by POWER (complete years only).
    metadata: provenance read from the response (source, units, fill value...).
    """

    data: pd.DataFrame
    annual: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)


def build_request_params(
    parameters: Iterable[str],
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
    community: str = DEFAULT_COMMUNITY,
) -> dict[str, Any]:
    """Validate the arguments and return the query parameters for POWER.

    Only obviously invalid input is rejected here. The available period is not
    hard-coded: POWER itself rejects years outside its coverage and that
    message is passed on to the caller.
    """
    if isinstance(parameters, str):
        parameters = [parameters]
    codes = [str(p).strip().upper() for p in parameters]
    if not codes or any(not c for c in codes):
        raise PowerInputError("At least one parameter identifier is required.")
    if len(set(codes)) != len(codes):
        raise PowerInputError("Parameter identifiers must not be repeated.")

    for name, value in (("latitude", latitude), ("longitude", longitude)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PowerInputError(f"{name} must be a number.")
        if not np.isfinite(value):
            raise PowerInputError(f"{name} must be a finite number.")
    if not -90 <= latitude <= 90:
        raise PowerInputError("latitude must be between -90 and 90.")
    if not -180 <= longitude <= 180:
        raise PowerInputError("longitude must be between -180 and 180.")

    for name, value in (("start_year", start_year), ("end_year", end_year)):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise PowerInputError(f"{name} must be a whole year, e.g. 1995.")
    if start_year > end_year:
        raise PowerInputError("start_year must not be after end_year.")

    return {
        "parameters": ",".join(codes),
        "community": community,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "start": int(start_year),
        "end": int(end_year),
        "format": "JSON",
    }


def fetch_monthly_point(
    parameters: Iterable[str],
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
    *,
    community: str = DEFAULT_COMMUNITY,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Request monthly data for one point and return the decoded JSON body."""
    params = build_request_params(
        parameters, latitude, longitude, start_year, end_year, community
    )
    url = POWER_BASE_URL + MONTHLY_POINT_PATH
    http = session or requests

    try:
        response = http.get(url, params=params, timeout=timeout)
    except requests.Timeout as exc:
        raise PowerTimeoutError(
            f"NASA POWER did not respond within {timeout} seconds."
        ) from exc
    except requests.RequestException as exc:
        raise PowerConnectionError(f"Could not reach NASA POWER: {exc}") from exc

    if response.status_code != 200:
        raise PowerRequestError(response.status_code, _error_messages(response))

    try:
        payload = response.json()
    except ValueError as exc:
        raise PowerResponseError("NASA POWER returned a body that is not JSON.") from exc
    if not isinstance(payload, dict):
        raise PowerResponseError("NASA POWER returned an unexpected JSON structure.")

    # Provenance of this particular retrieval; not part of the NASA payload.
    payload["_earthtrend_request"] = {
        "url": getattr(response, "url", url),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return payload


def parse_monthly_response(payload: dict[str, Any]) -> PowerResult:
    """Convert a POWER monthly point response into standard DataFrames."""
    try:
        values_by_parameter = payload["properties"]["parameter"]
        header = payload["header"]
        parameter_info = payload["parameters"]
        coordinates = payload["geometry"]["coordinates"]
        longitude, latitude = float(coordinates[0]), float(coordinates[1])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PowerResponseError(
            f"NASA POWER response is missing an expected field: {exc!r}"
        ) from exc

    if "fill_value" not in header:
        # Without it missing values cannot be told apart from real ones.
        raise PowerResponseError("NASA POWER response does not state its fill value.")
    fill_value = float(header["fill_value"])

    sources = header.get("sources") or []
    source = "NASA POWER" + (f" ({', '.join(sources)})" if sources else "")
    elevation = float(coordinates[2]) if len(coordinates) > 2 else None

    monthly_rows: list[dict[str, Any]] = []
    annual_rows: list[dict[str, Any]] = []

    for code, series in values_by_parameter.items():
        info = parameter_info.get(code)
        if not isinstance(info, dict) or "units" not in info:
            raise PowerResponseError(f"NASA POWER response has no units for {code}.")
        if not isinstance(series, dict):
            raise PowerResponseError(f"NASA POWER response has no values for {code}.")
        common = {
            "unit": info["units"],
            "variable": code,
            "variable_name": info.get("longname", code),
            "latitude": latitude,
            "longitude": longitude,
            "source": source,
        }
        for key, raw in series.items():
            key = str(key)
            if len(key) != 6 or not key.isdigit():
                raise PowerResponseError(f"Unexpected time key {key!r} for {code}.")
            year, period = int(key[:4]), key[4:]
            value = _to_value(raw, fill_value, code, key)
            if period == ANNUAL_KEY_SUFFIX:
                annual_rows.append({"year": year, "value": value, **common})
            elif 1 <= int(period) <= 12:
                monthly_rows.append(
                    {"date": pd.Timestamp(year=year, month=int(period), day=1),
                     "value": value, **common}
                )
            else:
                raise PowerResponseError(f"Unexpected time key {key!r} for {code}.")

    data = pd.DataFrame(monthly_rows, columns=TIMESERIES_COLUMNS)
    annual = pd.DataFrame(annual_rows, columns=ANNUAL_COLUMNS)
    data["value"] = data["value"].astype(float)
    annual["value"] = annual["value"].astype(float)
    data["date"] = pd.to_datetime(data["date"])

    request_info = payload.get("_earthtrend_request", {})
    metadata = {
        "provider": "NASA POWER (NASA Langley Research Center)",
        "provider_url": POWER_BASE_URL,
        "dataset_title": header.get("title"),
        "api_name": (header.get("api") or {}).get("name"),
        "api_version": (header.get("api") or {}).get("version"),
        "sources": list(sources),
        "source": source,
        "temporal_resolution": "monthly",
        "date_convention": "date is the first day of the month the value covers",
        "time_standard": header.get("time_standard"),
        "fill_value": fill_value,
        "missing_value_handling": "fill value converted to NaN; never to zero",
        "latitude": latitude,
        "longitude": longitude,
        "elevation_m": elevation,
        "coverage_start": header.get("start"),
        "coverage_end": header.get("end"),
        "units": {c: i.get("units") for c, i in parameter_info.items()},
        "variable_names": {c: i.get("longname") for c, i in parameter_info.items()},
        "missing_counts": {
            c: int(data.loc[data["variable"] == c, "value"].isna().sum())
            for c in values_by_parameter
        },
        "api_messages": list(payload.get("messages") or []),
        "request_url": request_info.get("url"),
        "retrieved_at_utc": request_info.get("retrieved_at_utc"),
        "is_synthetic": False,
    }
    return PowerResult(data=data, annual=annual, metadata=metadata)


def get_monthly_series(
    parameters: Iterable[str],
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
    **kwargs: Any,
) -> PowerResult:
    """Fetch and parse monthly POWER data for one point."""
    payload = fetch_monthly_point(
        parameters, latitude, longitude, start_year, end_year, **kwargs
    )
    return parse_monthly_response(payload)


def _to_value(raw: Any, fill_value: float, code: str, key: str) -> float:
    """Return the observation as float, or NaN when POWER reports it missing."""
    if raw is None:
        return float("nan")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise PowerResponseError(f"Non-numeric value {raw!r} for {code} at {key}.")
    value = float(raw)
    if value == fill_value:
        return float("nan")
    return value


def _error_messages(response: Any) -> list[str]:
    """Extract POWER's own error messages from a failed response."""
    try:
        body = response.json()
    except ValueError:
        return []
    if not isinstance(body, dict):
        return []
    messages = body.get("messages") or body.get("detail") or []
    if isinstance(messages, str):
        return [messages]
    return [str(m) for m in messages]
