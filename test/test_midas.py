# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Tests for the Midas eFMU module.
"""

# pylint: disable=broad-except

import json
import sys
from os import path
from unittest.mock import MagicMock, patch

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.modules.midas import URLS, MidasClient, MidasForecast, check_response

# Minimal RIN list payload
_RINS_PAYLOAD = [
    {"ID": "USCA-FLEX-FXFC-0000", "SignalType": "Flex Alerts"},
    {"ID": "USCA-SGIP-SGFC-PGE", "SignalType": "GHG"},
]

# Minimal value payload
_VALUES_PAYLOAD = {
    "ID": "USCA-FLEX-FXFC-0000",
    "ValueInformation": [
        {"StartTime": "2024-06-21T18:00:00Z", "EndTime": "2024-06-21T19:00:00Z", "Value": 1},
    ],
}

_LOGIN_TOKEN = "test-midas-token-abc123"


def _make_response(status_code=200, json_data=None, headers=None):
    """Return a mock requests.Response with the given status code and body."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.text = json.dumps(json_data or {})
    mock_resp.headers = headers or {}
    return mock_resp


def _make_client(username="testuser", password="testpass"):
    """Return a MidasClient with a pre-set token (skips login)."""
    client = MidasClient(username=username, password=password)
    client.token = _LOGIN_TOKEN
    return client


# check_response tests

def test_check_response_ok():
    resp = _make_response(200, {"foo": "bar"})
    result = check_response(resp)
    assert result is resp


def test_check_response_error_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resp = _make_response(401)
    result = check_response(resp)
    assert result is None


def test_check_response_error_writes_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resp = _make_response(500)
    resp.text = "<html>error</html>"
    check_response(resp)
    assert (tmp_path / "response_error.html").exists()


# URLS constant tests

def test_urls_has_expected_keys():
    for key in ("register_url", "login_url", "rin_url", "value_url"):
        assert key in URLS


def test_urls_all_https():
    for url in URLS.values():
        assert url.startswith("https://")


# MidasClient init tests

def test_client_init_stores_credentials():
    client = MidasClient(username="u", password="p", email="e@x.com", org="myorg")
    assert client.username == "u"
    assert client.password == "p"
    assert client.email == "e@x.com"
    assert client.org == "myorg"
    assert client.token is None


def test_client_registered_true_skips_register():
    with patch("fmlc.modules.midas.requests.post") as mock_post:
        MidasClient(registered=True, username="u", password="p")
        mock_post.assert_not_called()


def test_client_registered_false_calls_register():
    with patch("fmlc.modules.midas.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, {"message": "ok"})
        MidasClient(registered=False, username="u", password="p")
        mock_post.assert_called_once()


# MidasClient.login tests

def test_client_login_stores_token():
    with patch("fmlc.modules.midas.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, headers={"Token": _LOGIN_TOKEN})
        client = MidasClient(username="u", password="p")
        client.login()
        assert client.token == _LOGIN_TOKEN


def test_client_login_called_once_when_token_missing():
    with patch("fmlc.modules.midas.requests.get") as mock_get:
        mock_get.side_effect = [
            _make_response(200, headers={"Token": _LOGIN_TOKEN}),
            _make_response(200, json_data=_RINS_PAYLOAD),
        ]
        client = MidasClient(username="u", password="p")
        client.get_rins()
        assert mock_get.call_count == 2 # one login + one get_rins


def test_client_login_not_called_when_token_set():
    with patch("fmlc.modules.midas.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, json_data=_RINS_PAYLOAD)
        client = _make_client()
        client.get_rins()
        assert mock_get.call_count == 1 # only the get_rins call


# MidasClient.get_rins tests

def test_get_rins_returns_list():
    with patch("fmlc.modules.midas.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, json_data=_RINS_PAYLOAD)
        client = _make_client()
        result = client.get_rins()
        assert isinstance(result, list)
        assert len(result) == 2


def test_get_rins_uses_signal_type_in_url():
    with patch("fmlc.modules.midas.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, json_data=_RINS_PAYLOAD)
        client = _make_client()
        client.get_rins(signal_type=2)
        called_url = mock_get.call_args[0][0]
        assert called_url.endswith("2")


def test_get_rins_returns_none_on_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("fmlc.modules.midas.requests.get") as mock_get:
        mock_get.return_value = _make_response(403)
        client = _make_client()
        result = client.get_rins()
        assert result is None


# MidasClient.get_values tests

def test_get_values_returns_dict():
    with patch("fmlc.modules.midas.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, json_data=_VALUES_PAYLOAD)
        client = _make_client()
        result = client.get_values()
        assert isinstance(result, dict)
        assert "ValueInformation" in result


def test_get_values_uses_rate_id_and_query_type_in_url():
    with patch("fmlc.modules.midas.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, json_data=_VALUES_PAYLOAD)
        client = _make_client()
        client.get_values(rate_id="USCA-SGIP-SGFC-PGE", query_type="realtime")
        called_url = mock_get.call_args[0][0]
        assert "USCA-SGIP-SGFC-PGE" in called_url
        assert "realtime" in called_url


def test_get_values_returns_none_on_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("fmlc.modules.midas.requests.get") as mock_get:
        mock_get.return_value = _make_response(500)
        client = _make_client()
        result = client.get_values()
        assert result is None


# MidasForecast eFMU tests

def test_forecast_outputs_declared():
    mod = MidasForecast()
    assert "output-data" in mod.output
    assert "duration" in mod.output


def test_forecast_inputs_declared():
    mod = MidasForecast()
    for key in ("username", "password", "email", "org", "registered",
                "rate-id", "query-type", "debug"):
        assert key in mod.input


def test_forecast_missing_username_returns_waiting():
    mod = MidasForecast()
    mod.input["password"] = "p"
    msg = mod.compute()
    assert "Waiting" in msg
    assert mod.output["output-data"] is None
    assert mod.output["duration"] >= 0.0


def test_forecast_missing_password_returns_waiting():
    mod = MidasForecast()
    mod.input["username"] = "u"
    msg = mod.compute()
    assert "Waiting" in msg
    assert mod.output["output-data"] is None


def test_forecast_all_outputs_assigned_on_waiting():
    mod = MidasForecast()
    mod.compute()
    assert "output-data" in mod.output
    assert "duration" in mod.output


def test_forecast_compute_success():
    mod = MidasForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"

    with patch("fmlc.modules.midas.MidasClient") as MockClient:
        instance = MockClient.return_value
        instance.get_values.return_value = _VALUES_PAYLOAD
        msg = mod.compute()

    assert msg == "Done."
    assert mod.output["output-data"] is not None
    assert mod.output["duration"] >= 0.0


def test_forecast_output_data_is_valid_json():
    mod = MidasForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"

    with patch("fmlc.modules.midas.MidasClient") as MockClient:
        instance = MockClient.return_value
        instance.get_values.return_value = _VALUES_PAYLOAD
        mod.compute()

    data = json.loads(mod.output["output-data"])
    assert "ValueInformation" in data


def test_forecast_client_created_once():
    """MidasClient is only instantiated on the first compute call."""
    mod = MidasForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"

    with patch("fmlc.modules.midas.MidasClient") as MockClient:
        instance = MockClient.return_value
        instance.get_values.return_value = _VALUES_PAYLOAD
        mod.compute()
        mod.compute()
        assert MockClient.call_count == 1


def test_forecast_rate_id_default():
    """When rate-id is None the module defaults to USCA-FLEX-FXFC-0000."""
    mod = MidasForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"
    mod.input["rate-id"] = None

    with patch("fmlc.modules.midas.MidasClient") as MockClient:
        instance = MockClient.return_value
        instance.get_values.return_value = _VALUES_PAYLOAD
        mod.compute()
        instance.get_values.assert_called_once_with(
            rate_id="USCA-FLEX-FXFC-0000", query_type="alldata"
        )


def test_forecast_custom_rate_id_and_query_type():
    mod = MidasForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"
    mod.input["rate-id"] = "USCA-SGIP-SGFC-PGE"
    mod.input["query-type"] = "realtime"

    with patch("fmlc.modules.midas.MidasClient") as MockClient:
        instance = MockClient.return_value
        instance.get_values.return_value = _VALUES_PAYLOAD
        mod.compute()
        instance.get_values.assert_called_once_with(
            rate_id="USCA-SGIP-SGFC-PGE", query_type="realtime"
        )


def test_forecast_api_exception_returned_as_msg():
    mod = MidasForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"

    with patch("fmlc.modules.midas.MidasClient") as MockClient:
        instance = MockClient.return_value
        instance.get_values.side_effect = RuntimeError("network failure")
        msg = mod.compute()

    assert "network failure" in msg
    assert mod.output["output-data"] is None


def test_forecast_debug_adds_traceback():
    mod = MidasForecast()
    mod.input["username"] = "u"
    mod.input["password"] = "p"
    mod.input["debug"] = True

    with patch("fmlc.modules.midas.MidasClient") as MockClient:
        instance = MockClient.return_value
        instance.get_values.side_effect = RuntimeError("boom")
        msg = mod.compute()

    assert "Traceback" in msg


def test_forecast_do_step_interface():
    mod = MidasForecast()

    with patch("fmlc.modules.midas.MidasClient") as MockClient:
        instance = MockClient.return_value
        instance.get_values.return_value = _VALUES_PAYLOAD
        msg = mod.do_step(inputs={
            "username": "u",
            "password": "p",
            "email": None,
            "org": None,
            "registered": True,
            "rate-id": "USCA-FLEX-FXFC-0000",
            "query-type": "alldata",
            "debug": None,
        })

    assert msg == "Done."
