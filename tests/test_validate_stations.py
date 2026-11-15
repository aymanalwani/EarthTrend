"""Offline tests of the station validation script's helpers (no network, no station data)."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_stations as vs  # noqa: E402


def response(status, url="https://example.test/file"):
    return SimpleNamespace(status_code=status, url=url, content=b"data")


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(vs.time, "sleep", lambda seconds: None)


def test_withheld_leave_one_out_is_not_classified():
    assert vs.influence(False, -0.05, 0.36) is None      # test withheld: no label
    assert vs.influence(True, None, 0.36) is None
    assert vs.influence(True, 0.10, None) is None
    assert vs.influence(True, 0.10, 0.36) is False       # 0.10 <= 0.18
    assert vs.influence(True, -0.20, 0.36) is True       # 0.20 > 0.18


def test_missing_file_raises_with_url_and_status(monkeypatch, no_sleep):
    monkeypatch.setattr(vs.requests, "get", lambda url, **kw: response(404, url))
    with pytest.raises(vs.DownloadError, match=r"404.*example\.test/ghcnm"):
        vs._get("https://example.test/ghcnm")


def test_expected_missing_gsod_year_returns_none(monkeypatch, no_sleep):
    monkeypatch.setattr(vs.requests, "get", lambda url, **kw: response(404, url))
    assert vs._get("https://example.test/gsod", allow_missing=True) is None


def test_other_http_failures_are_not_ignored(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(vs.requests, "get", lambda url, **kw: calls.append(url) or response(503, url))
    with pytest.raises(vs.DownloadError, match=r"503.*3 attempts.*example\.test/power"):
        vs._get("https://example.test/power", allow_missing=True)
    assert len(calls) == 3


def test_connection_errors_are_retried_then_reported(monkeypatch, no_sleep):
    attempts = []

    def flaky(url, **kw):
        attempts.append(url)
        if len(attempts) < 3:
            raise vs.requests.ConnectionError("Read timed out.")
        return response(200, url)

    monkeypatch.setattr(vs.requests, "get", flaky)
    assert vs._get("https://example.test/slow").status_code == 200

    def dead(url, **kw):
        raise vs.requests.ConnectionError("Read timed out.")

    monkeypatch.setattr(vs.requests, "get", dead)
    with pytest.raises(vs.DownloadError, match=r"ConnectionError.*example\.test/slow"):
        vs._get("https://example.test/slow")


def test_gsod_download_records_missing_year_and_continues(monkeypatch, tmp_path, no_sleep):
    monkeypatch.setattr(vs, "RAW", tmp_path)
    monkeypatch.setattr(vs, "YEARS", range(2005, 2007))
    monkeypatch.setattr(vs, "PANEL", {"Marka": ("40270099999", 31.973, 35.992)})
    monkeypatch.setattr(vs, "GHCNM", {})
    monkeypatch.setattr(vs, "A10_DATES", [])
    monkeypatch.setattr(vs.sys, "argv", ["validate_stations.py", "download"])
    monkeypatch.setattr(vs.power_client, "fetch_monthly_point", lambda *a, **k: {})
    for kind in ("qcu", "qcf"):  # pretend the GHCN-M extracts already exist
        (tmp_path / "ghcnm").mkdir(exist_ok=True)
        (tmp_path / "ghcnm" / f"{kind}_JO.dat").write_text("")
    monkeypatch.setattr(vs.requests, "get",
                        lambda url, **kw: response(404 if "/2006/" in url else 200, url))
    vs.download()
    assert (tmp_path / "gsod" / "2005_40270099999.csv").exists()
    assert not (tmp_path / "gsod" / "2006_40270099999.csv").exists()
    log = (tmp_path / "download_log.json").read_text()
    assert "absent at source" in log


def test_valid_day_rule(monkeypatch, tmp_path):
    """One rule for all scripts: TEMP present and at least 4 observations."""
    (tmp_path / "gsod").mkdir()
    pd.DataFrame({"DATE": ["2005-07-01", "2005-07-02", "2005-07-03"],
                  "TEMP": [86.0, 9999.9, 77.0], "TEMP_ATTRIBUTES": [24, 24, 3]}
                 ).to_csv(tmp_path / "gsod" / "2005_X.csv", index=False)
    monkeypatch.setattr(vs, "RAW", tmp_path)
    table = vs.load_gsod("X")
    assert table["valid"].tolist() == [True, False, False]
    assert table["temp_c"].iloc[0] == pytest.approx(30.0)
    assert table["temp_c"].iloc[1:].isna().all()
