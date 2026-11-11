# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Tests for the DeviationWatchdog eFMU module.
"""

# pylint: disable=broad-except

import json
import sys
import tempfile
import warnings
from os import path

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.modules.deviation_watchdog import DeviationWatchdog

# Fixed Unix timestamp used as the FMLC-injected 'time' input
TS_BASE = 1718985600  # 2024-06-21 18:00:00 UTC

# A minimal input-data payload with one measured and one predicted channel
_PAYLOAD = {"power_measured": 100.0, "power_predicted": 102.0}
INPUT_DATA = json.dumps(_PAYLOAD)

# Minimal watchdog config CSV (threshold=10, so no alert at deviation=2)
_CONFIG_CSV = (
    "measured_name,predicted_name,threshold,notification_level,time_lag_s,enabled\n"
    "power_measured,power_predicted,10.0,warning,0,1\n"
)


def _make_module(input_data=INPUT_DATA, config_file=None, ts=TS_BASE):
    """Return a DeviationWatchdog instance with inputs pre-populated."""
    mod = DeviationWatchdog()
    mod.input["input-data"] = input_data
    mod.input["config-file"] = config_file
    mod.input["log-file"] = None
    mod.input["email-config"] = None
    mod.input["email-cooldown"] = None
    mod.input["timezone"] = None
    mod.input["debug"] = None
    mod.input["time"] = ts
    return mod


def _write_config(content):
    """Write CSV content to a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    tmp.write(content)
    tmp.flush()
    return tmp.name


def test_outputs_declared():
    mod = DeviationWatchdog()
    assert "output-data" in mod.output
    assert "alerts" in mod.output
    assert "duration" in mod.output


def test_inputs_declared():
    mod = DeviationWatchdog()
    for key in ("input-data", "config-file", "log-file", "email-config",
                "email-cooldown", "timezone", "debug"):
        assert key in mod.input


def test_missing_input_data_returns_waiting():
    mod = _make_module(input_data=None)
    msg = mod.compute()
    assert "Waiting" in msg
    assert mod.output["output-data"] is None
    assert mod.output["duration"] >= 0.0


def test_all_outputs_assigned_on_error():
    """All three outputs must be set even when compute fails."""
    mod = _make_module(input_data=None)
    mod.compute()
    assert "output-data" in mod.output
    assert "alerts" in mod.output
    assert "duration" in mod.output


def test_first_cycle_no_history_returns_done():
    """First call seeds history but cannot compare yet; should return Done."""
    cfg_path = _write_config(_CONFIG_CSV)
    mod = _make_module(config_file=cfg_path)
    msg = mod.compute()
    assert msg == "Done."
    result = json.loads(mod.output["output-data"])
    assert result["n_alerts"] == 0
    assert result["deviations"] == {}


def test_second_cycle_below_threshold_no_alert():
    """Two cycles with deviation below threshold should produce no alert."""
    cfg_path = _write_config(_CONFIG_CSV)
    mod = _make_module(config_file=cfg_path, ts=TS_BASE)
    mod.compute()
    mod.input["time"] = TS_BASE + 1
    msg = mod.compute()
    assert msg == "Done."
    result = json.loads(mod.output["output-data"])
    assert result["n_alerts"] == 0
    alerts = json.loads(mod.output["alerts"])
    assert alerts == []


def test_second_cycle_above_threshold_triggers_alert():
    """Deviation above threshold must produce an alert entry."""
    tight_config = (
        "measured_name,predicted_name,threshold,notification_level,time_lag_s,enabled\n"
        "power_measured,power_predicted,1.0,warning,0,1\n"
    )
    cfg_path = _write_config(tight_config)
    mod = _make_module(config_file=cfg_path, ts=TS_BASE)
    mod.compute()

    mod.input["time"] = TS_BASE + 1
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        msg = mod.compute()

    assert msg == "Done."
    result = json.loads(mod.output["output-data"])
    assert result["n_alerts"] == 1
    alerts = json.loads(mod.output["alerts"])
    assert len(alerts) == 1
    assert alerts[0]["channel"] == "power_measured"
    assert alerts[0]["deviation"] > 1.0
    assert any("deviation" in str(w.message).lower() for w in caught)


def test_disabled_channel_not_checked():
    """Rows with enabled=0 must be skipped."""
    disabled_config = (
        "measured_name,predicted_name,threshold,notification_level,time_lag_s,enabled\n"
        "power_measured,power_predicted,1.0,warning,0,0\n"
    )
    cfg_path = _write_config(disabled_config)
    mod = _make_module(config_file=cfg_path, ts=TS_BASE)
    mod.compute()
    mod.input["time"] = TS_BASE + 1
    msg = mod.compute()
    assert msg == "Done."
    result = json.loads(mod.output["output-data"])
    assert result["n_alerts"] == 0


def test_no_config_file_returns_done():
    """No config-file input should still run successfully with empty config."""
    mod = _make_module(config_file=None)
    msg = mod.compute()
    assert msg == "Done."


def test_output_data_contains_timestamp():
    mod = _make_module()
    mod.compute()
    result = json.loads(mod.output["output-data"])
    assert "timestamp" in result


def test_alerts_output_is_valid_json():
    mod = _make_module()
    mod.compute()
    parsed = json.loads(mod.output["alerts"])
    assert isinstance(parsed, list)


def test_duration_non_negative():
    mod = _make_module()
    mod.compute()
    assert mod.output["duration"] >= 0.0


def test_timezone_formats_timestamp():
    mod = _make_module(ts=TS_BASE)
    mod.input["timezone"] = "America/Los_Angeles"
    msg = mod.compute()
    assert msg == "Done."
    result = json.loads(mod.output["output-data"])
    assert "T" in result["timestamp"]


def test_do_step_interface():
    mod = DeviationWatchdog()
    msg = mod.do_step(inputs={
        "input-data": INPUT_DATA,
        "config-file": None,
        "log-file": None,
        "email-config": None,
        "email-cooldown": None,
        "timezone": None,
        "debug": None,
        "time": TS_BASE,
    })
    assert msg == "Done."


def test_log_level_writes_file():
    """level='log' must write alert to the JSON log file."""
    tight_config = (
        "measured_name,predicted_name,threshold,notification_level,time_lag_s,enabled\n"
        "power_measured,power_predicted,1.0,log,0,1\n"
    )
    cfg_path = _write_config(tight_config)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as lf:
        log_path = lf.name

    mod = _make_module(config_file=cfg_path, ts=TS_BASE)
    mod.input["log-file"] = log_path
    mod.compute()

    mod.input["time"] = TS_BASE + 1
    mod.compute()

    with open(log_path) as fh:
        entries = json.load(fh)
    assert len(entries) >= 1
    assert entries[0]["channel"] == "power_measured"


def test_init_runs_only_once():
    """_load_config should not be called again after the first successful cycle."""
    cfg_path = _write_config(_CONFIG_CSV)
    mod = _make_module(config_file=cfg_path, ts=TS_BASE)
    mod.compute()
    config_after_first = mod._config

    mod.input["time"] = TS_BASE + 1
    mod.compute()
    assert mod._config is config_after_first
