# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Tests for the WattTime eFMU modules.
"""

# pylint: disable=broad-except

import json
import sys
from os import path
from unittest.mock import MagicMock, patch

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.modules.watttime import URLS, WatttimeClient, WatttimeForecast, check_response

# Minimal forecast payload matching the WattTime v2 API shape
_FORECAST_PAYLOAD = {
    "forecast": [
        {"point_time": "2024-06-21T18:00:00Z", "value": 180.5, "version": "3.0"},
        {"point_time": "2024-06-21T18:05:00Z", "value": 179.2, "version": "3.0"},
    ],
    "generated_at": "2024-06-21T17:55:00Z",
    "ba": "CAISO_NORTH",
    "data_type": "MOER",
    "units": "lbs CO2/MWh",
}

_LOGIN_PAYLOAD = {"token": "test-bearer-token-abc123"}


def _make_response(status_code=200, json_data=None, content=b""):
    """Return a mock requests.Response with the given status code and body."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.text = json.dumps(json_data or {})
    mock_resp.content = content
    return mock_resp


def _make_client(username="testuser", password="testpass"):
    """Return a WatttimeClient with a pre-set token (skips login)."""
    client = WatttimeClient(username=username, password=password)
    client.token = "test-bearer-token-abc123"
    return client


# check_response tests

def test_check_response_ok():
    resp = _make_response(200, {"token": "abc"})
    result = check_response(resp)
    assert result is resp


def test_check_response_error_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resp = _make_response(401)
    result = check_response(resp)
    assert result is None


# URLS constant tests

def test_urls_has_expected_keys():
    for key in ("login_url", "register_url", "list_url", "historical_url", "forecast_url"):
        assert key in URLS


def test_urls_all_https():
    for url in URLS.values():
        assert url.startswith("https://")


# WatttimeClient tests

def test_client_init_stores_credentials():
    client = WatttimeClient(username="u", password="p", email="e@x.com", org="myorg")
    assert client.username == "u"
    assert client.password == "p"
    assert client.email == "e@x.com"
    assert client.org == "myorg"
    assert client.token is None


def test_client_login_stores_token():
    with patch("fmlc.modules.watttime.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, _LOGIN_PAYLOAD)
        client = WatttimeClient(username="u", password="p")
        client.login()
        assert client.token == "test-bearer-token-abc123"


def test_client_login_called_once_when_token_missing():
    with patch("fmlc.modules.watttime.requests.get") as mock_get:
        mock_get.side_effect = [
            _make_response(200, _LOGIN_PAYLOAD),
            _make_response(200, []),
        ]
        client = WatttimeClient(username="u", password="p")
        client.get_regions()
        assert mock_get.call_count == 2 # one login + one list


def test_client_login_not_repeated_when_token_present():
    with patch("fmlc.modules.watttime.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, [])
        client = _make_client()
        client.get_regions()
        assert mock_get.call_count == 1 # no login, only list call


def test_client_get_regions_returns_list():
    regions_data = [{"abbrev": "CAISO_NORTH", "name": "California ISO, North"}]
    with patch("fmlc.modules.watttime.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, regions_data)
        client = _make_client()
        result = client.get_regions()
        assert result == regions_data


def test_client_get_regions_returns_none_on_error():
    with patch("fmlc.modules.watttime.requests.get") as mock_get:
        mock_get.return_value = _make_response(403, {})
        client = _make_client()
        result = client.get_regions()
        assert result is None


def test_client_get_emission_forecast_returns_dict():
    with patch("fmlc.modules.watttime.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, _FORECAST_PAYLOAD)
        client = _make_client()
        result = client.get_emission_forecast(ba="CAISO_NORTH")
        assert result["ba"] == "CAISO_NORTH"
        assert "forecast" in result


def test_client_get_emission_forecast_returns_none_on_error():
    with patch("fmlc.modules.watttime.requests.get") as mock_get:
        mock_get.return_value = _make_response(403, {})
        client = _make_client()
        result = client.get_emission_forecast()
        assert result is None


def test_client_get_emission_historic_writes_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    zip_content = b"PK\x05\x06" + b"\x00" * 18
    with patch("fmlc.modules.watttime.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, {}, content=zip_content)
        client = _make_client()
        client.get_emission_historic(ba="CAISO_NORTH", cur_dir=str(tmp_path))
        out_file = tmp_path / "CAISO_NORTH_historical.zip"
        assert out_file.exists()
        assert out_file.read_bytes() == zip_content


def test_client_register_raises_on_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    import pytest
    with patch("fmlc.modules.watttime.requests.post") as mock_post:
        mock_post.return_value = _make_response(400, {})
        with pytest.raises(ValueError, match="Registration was not successful"):
            WatttimeClient(
                username="u", password="p",
                email="u@x.com", org="o", registered=False,
            )


# WatttimeForecast eFMU tests

def test_forecast_outputs_declared():
    mod = WatttimeForecast()
    assert "output-data" in mod.output
    assert "duration" in mod.output


def test_forecast_inputs_declared():
    mod = WatttimeForecast()
    for key in ("username", "password", "email", "org", "registered",
                "ba", "extended-forecast", "debug"):
        assert key in mod.input


def test_forecast_missing_username_returns_waiting():
    mod = WatttimeForecast()
    mod.input["password"] = "p"
    msg = mod.compute()
    assert "Waiting" in msg
    assert mod.output["output-data"] is None
    assert mod.output["duration"] >= 0.0


def test_forecast_missing_password_returns_waiting():
    mod = WatttimeForecast()
    mod.input["username"] = "u"
    msg = mod.compute()
    assert "Waiting" in msg


def test_forecast_compute_success():
    mod = WatttimeForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"

    with patch("fmlc.modules.watttime.WatttimeClient") as MockClient:
        instance = MockClient.return_value
        instance.get_emission_forecast.return_value = _FORECAST_PAYLOAD
        msg = mod.compute()

    assert msg == "Done."
    assert mod.output["output-data"] is not None
    assert mod.output["duration"] >= 0.0


def test_forecast_output_data_is_valid_json():
    mod = WatttimeForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"

    with patch("fmlc.modules.watttime.WatttimeClient") as MockClient:
        instance = MockClient.return_value
        instance.get_emission_forecast.return_value = _FORECAST_PAYLOAD
        mod.compute()

    data = json.loads(mod.output["output-data"])
    assert "forecast" in data
    assert data["ba"] == "CAISO_NORTH"


def test_forecast_client_created_once():
    """The WatttimeClient is only instantiated on the first compute call."""
    mod = WatttimeForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"

    with patch("fmlc.modules.watttime.WatttimeClient") as MockClient:
        instance = MockClient.return_value
        instance.get_emission_forecast.return_value = _FORECAST_PAYLOAD
        mod.compute()
        mod.compute()
        assert MockClient.call_count == 1


def test_forecast_ba_default():
    """When ba input is None the module defaults to CAISO_NORTH."""
    mod = WatttimeForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"
    mod.input["ba"] = None

    with patch("fmlc.modules.watttime.WatttimeClient") as MockClient:
        instance = MockClient.return_value
        instance.get_emission_forecast.return_value = _FORECAST_PAYLOAD
        mod.compute()
        instance.get_emission_forecast.assert_called_once_with(
            ba="CAISO_NORTH", extended_forecast=False
        )


def test_forecast_extended_forecast_flag():
    mod = WatttimeForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"
    mod.input["extended-forecast"] = True

    with patch("fmlc.modules.watttime.WatttimeClient") as MockClient:
        instance = MockClient.return_value
        instance.get_emission_forecast.return_value = _FORECAST_PAYLOAD
        mod.compute()
        instance.get_emission_forecast.assert_called_once_with(
            ba="CAISO_NORTH", extended_forecast=True
        )


def test_forecast_api_exception_returned_as_msg():
    mod = WatttimeForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"

    with patch("fmlc.modules.watttime.WatttimeClient") as MockClient:
        instance = MockClient.return_value
        instance.get_emission_forecast.side_effect = RuntimeError("network failure")
        msg = mod.compute()

    assert "network failure" in msg
    assert mod.output["output-data"] is None


def test_forecast_debug_adds_traceback():
    mod = WatttimeForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"
    mod.input["debug"] = True

    with patch("fmlc.modules.watttime.WatttimeClient") as MockClient:
        instance = MockClient.return_value
        instance.get_emission_forecast.side_effect = RuntimeError("boom")
        msg = mod.compute()

    assert "Traceback" in msg


def test_forecast_do_step_interface():
    mod = WatttimeForecast()
    with patch("fmlc.modules.watttime.WatttimeClient") as MockClient:
        instance = MockClient.return_value
        instance.get_emission_forecast.return_value = _FORECAST_PAYLOAD
        msg = mod.do_step(inputs={
            "username": "u",
            "password": "p",
            "email": None,
            "org": None,
            "registered": True,
            "ba": "CAISO_NORTH",
            "extended-forecast": False,
            "debug": None,
        })
    assert msg == "Done."

