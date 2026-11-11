# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Tests for the PiController eFMU module.
"""

# pylint: disable=broad-except

import json
import sys
from os import path

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.modules.pi_controller import DEFAULT_CONFIG, PiController, pv_summation

# Fixed Unix timestamp used as the FMLC-injected 'time' input
TS_BASE = 1718985600 # 2024-06-21 18:00:00 UTC

# Minimal payloads matching DEFAULT_CONFIG keys
_INPUT_DATA = {
    DEFAULT_CONFIG["sp_key"]: 100.0,
    "Pload_kW": 50.0,
}
_MEAS_DATA = {
    DEFAULT_CONFIG["pv_key"]: 105.0,
    DEFAULT_CONFIG["state_key"]: 50.0,
}
_EXT_SETPOINTS = {"Batt1_Pset_W": 0.0}

INPUT_DATA = json.dumps(_INPUT_DATA)
MEAS_DATA = json.dumps(_MEAS_DATA)
EXT_SETPOINTS = json.dumps(_EXT_SETPOINTS)


def _make_module(input_data=INPUT_DATA, meas_data=MEAS_DATA, ext=EXT_SETPOINTS,
                 config=None, debug=None, ts=TS_BASE):
    """Return a PiController instance with inputs pre-populated."""
    mod = PiController()
    mod.input["input-data"] = input_data
    mod.input["measured-data"] = meas_data
    mod.input["external-setpoints"] = ext
    mod.input["config"] = config
    mod.input["debug"] = debug
    mod.input["time"] = ts
    return mod


def test_outputs_declared():
    mod = PiController()
    for key in ("output-ctrl", "output-data", "pi-error", "pi-integral", "pi-correction", "duration"):
        assert key in mod.output


def test_inputs_declared():
    mod = PiController()
    for key in ("input-data", "measured-data", "external-setpoints", "config", "debug"):
        assert key in mod.input


def test_compute_success():
    mod = _make_module()
    msg = mod.compute()
    assert msg == "Done."
    assert mod.output["output-ctrl"] is not None
    assert mod.output["output-data"] is not None
    assert mod.output["duration"] >= 0.0


def test_all_outputs_assigned_on_success():
    mod = _make_module()
    mod.compute()
    for key in ("output-ctrl", "output-data", "pi-error", "pi-integral", "pi-correction", "duration"):
        assert key in mod.output


def test_all_outputs_assigned_on_error():
    """All outputs must be set even on a failed cycle."""
    mod = _make_module(input_data=None)
    mod.compute()
    for key in ("output-ctrl", "output-data", "pi-error", "pi-integral", "pi-correction", "duration"):
        assert key in mod.output


def test_missing_input_data_returns_waiting():
    mod = _make_module(input_data=None)
    msg = mod.compute()
    assert "Waiting" in msg
    assert mod.output["output-ctrl"] is None


def test_missing_meas_data_returns_waiting():
    mod = _make_module(meas_data=None)
    msg = mod.compute()
    assert "Waiting" in msg
    assert mod.output["output-ctrl"] is None


def test_missing_ext_setpoints_returns_waiting():
    mod = _make_module(ext=None)
    msg = mod.compute()
    assert "Waiting" in msg
    assert mod.output["output-ctrl"] is None


def test_output_ctrl_contains_cv_setpoint_name():
    mod = _make_module()
    mod.compute()
    ctrl = json.loads(mod.output["output-ctrl"])
    assert DEFAULT_CONFIG["cv_setpoint_name"] in ctrl


def test_output_ctrl_preserves_ext_setpoints():
    """output-ctrl must pass through all keys from external-setpoints."""
    ext = {"Batt1_Pset_W": 0.0, "OtherKey": 42.0}
    mod = _make_module(ext=json.dumps(ext))
    mod.compute()
    ctrl = json.loads(mod.output["output-ctrl"])
    assert "OtherKey" in ctrl


def test_pi_error_matches_pv_minus_sp():
    sp = 100.0
    pv = 110.0
    input_data = json.dumps({DEFAULT_CONFIG["sp_key"]: sp, "Pload_kW": 50.0})
    meas_data = json.dumps({DEFAULT_CONFIG["pv_key"]: pv, DEFAULT_CONFIG["state_key"]: 50.0})
    mod = _make_module(input_data=input_data, meas_data=meas_data)
    mod.compute()
    assert abs(mod.output["pi-error"] - (pv - sp)) < 1e-9


def test_pi_integral_accumulates():
    """Integral should grow across two cycles with persistent positive error."""
    mod = _make_module()
    mod.compute()
    integral_first = mod.output["pi-integral"]
    mod.input["time"] = TS_BASE + 1
    mod.compute()
    integral_second = mod.output["pi-integral"]
    # pv (105) > sp (100) => error > 0 => integral accumulates positively
    assert integral_second > integral_first


def test_integrator_resets_on_large_sp_step():
    """A setpoint jump exceeding reset_threshold must zero the integral."""
    mod = _make_module()
    mod.compute()
    for i in range(1, 5):
        mod.input["time"] = TS_BASE + i
        mod.compute()
    new_sp = _INPUT_DATA[DEFAULT_CONFIG["sp_key"]] + 100.0
    new_input = json.dumps({DEFAULT_CONFIG["sp_key"]: new_sp, "Pload_kW": 50.0})
    mod.input["input-data"] = new_input
    mod.input["time"] = TS_BASE + 5
    mod.compute()
    expected_error = _MEAS_DATA[DEFAULT_CONFIG["pv_key"]] - new_sp
    assert abs(mod.output["pi-integral"] - expected_error) < 1e-9


def test_cv_max_clips_output():
    """When cv_max is set the output must be clipped to that magnitude."""
    cfg = {**DEFAULT_CONFIG, "cv_max": 1.0, "cv_key": None, "state_key": None}
    mod = _make_module(config=json.dumps(cfg))
    mod.compute()
    ctrl = json.loads(mod.output["output-ctrl"])
    cv_new = ctrl[cfg["cv_setpoint_name"]]
    assert cv_new <= cfg["cv_max"]
    assert cv_new >= -cfg["cv_max"]


def test_cv_max_deviation_skips_cycle():
    """CV deviation beyond threshold should return a non-Done message."""
    cfg = {**DEFAULT_CONFIG, "cv_key": DEFAULT_CONFIG["pv_key"], "cv_max_deviation": 0.01, "state_key": None}
    mod = _make_module(config=json.dumps(cfg))
    mod.compute() # seeds _cv_last
    mod.input["time"] = TS_BASE + 1
    msg = mod.compute()
    assert "Skipping" in msg
    assert mod.output["output-ctrl"] is None


def test_state_guard_soc_too_high_blocks_charging():
    """When SOC >= state_max, cv_new must be <= 0."""
    meas = {DEFAULT_CONFIG["pv_key"]: 105.0, DEFAULT_CONFIG["state_key"]: 100.0}
    cfg = {**DEFAULT_CONFIG, "cv_key": None, "state_key": DEFAULT_CONFIG["state_key"],
           "state_max": 100, "state_min": 10}
    mod = _make_module(meas_data=json.dumps(meas), config=json.dumps(cfg))
    mod.compute()
    ctrl = json.loads(mod.output["output-ctrl"])
    assert ctrl[cfg["cv_setpoint_name"]] <= 0.0


def test_state_guard_soc_too_low_blocks_discharging():
    """When SOC <= state_min, cv_new must be >= 0."""
    meas = {DEFAULT_CONFIG["pv_key"]: 95.0, DEFAULT_CONFIG["state_key"]: 10.0}
    cfg = {**DEFAULT_CONFIG, "cv_key": None, "state_key": DEFAULT_CONFIG["state_key"],
           "state_max": 100, "state_min": 10}
    mod = _make_module(meas_data=json.dumps(meas), config=json.dumps(cfg))
    mod.compute()
    ctrl = json.loads(mod.output["output-ctrl"])
    assert ctrl[cfg["cv_setpoint_name"]] >= 0.0


def test_ki_deadband_freezes_integral_outside_band():
    """When error > ki_deadband, integral must not accumulate."""
    cfg = {**DEFAULT_CONFIG, "ki_deadband": 1.0, "state_key": None, "cv_key": None}
    # error = pv (105) - sp (100) = 5 > deadband (1)
    mod = _make_module(config=json.dumps(cfg))
    mod.compute()
    assert mod.output["pi-integral"] == 0.0


def test_ki_deadband_accumulates_inside_band():
    """When |error| <= ki_deadband, integral should accumulate normally."""
    cfg = {**DEFAULT_CONFIG, "ki_deadband": 10.0, "state_key": None, "cv_key": None}
    # error = pv (105) - sp (100) = 5 <= deadband (10)
    mod = _make_module(config=json.dumps(cfg))
    mod.compute()
    assert mod.output["pi-integral"] != 0.0


def test_output_data_is_valid_json():
    mod = _make_module()
    mod.compute()
    parsed = json.loads(mod.output["output-data"])
    assert isinstance(parsed, dict)


def test_output_data_contains_diag_keys():
    mod = _make_module()
    mod.compute()
    parsed = json.loads(mod.output["output-data"])
    for key in ("sp", "pv", "cv", "cv_new", "pi_error", "pi_integral", "pi_correction"):
        assert key in parsed


def test_duration_non_negative():
    mod = _make_module()
    mod.compute()
    assert mod.output["duration"] >= 0.0


def test_config_as_dict_accepted():
    """config input can be a plain dict (not just a JSON string)."""
    cfg = {**DEFAULT_CONFIG, "state_key": None}
    mod = _make_module(config=cfg)
    msg = mod.compute()
    assert msg == "Done."


def test_config_as_json_string_accepted():
    cfg = {**DEFAULT_CONFIG, "state_key": None}
    mod = _make_module(config=json.dumps(cfg))
    msg = mod.compute()
    assert msg == "Done."


def test_do_step_interface():
    mod = PiController()
    msg = mod.do_step(inputs={
        "input-data": INPUT_DATA,
        "measured-data": MEAS_DATA,
        "external-setpoints": EXT_SETPOINTS,
        "config": None,
        "debug": None,
        "time": TS_BASE,
    })
    assert msg == "Done."


def test_init_runs_only_once():
    """self.init must be True after first cycle and not reset on second cycle."""
    mod = _make_module()
    mod.compute()
    assert mod.init is True
    mod.input["time"] = TS_BASE + 1
    mod.compute()
    assert mod.init is True


def test_pv_summation_helper():
    """pv_summation should return the weighted sum of data_terms and meas_terms."""
    cfg = {}
    data = {"Pload_kW": 50.0}
    meas = {"Inv1_Pac_W": 1000.0}
    processor_config = {
        "data_terms": [["Pload_kW", 1.0]],
        "meas_terms": [["Inv1_Pac_W", -1 / 1000]],
    }
    result = pv_summation(cfg, data, meas, processor_config)
    assert abs(result - (50.0 - 1.0)) < 1e-9


def test_debug_mode_includes_traceback():
    """With debug=True an exception should include traceback info in the return message."""
    bad_meas = json.dumps({"wrong_key": 0.0}) # missing pv_key and state_key
    mod = _make_module(meas_data=bad_meas, debug=True)
    msg = mod.compute()
    assert "Traceback" in msg or "traceback" in msg.lower() or "KeyError" in msg
