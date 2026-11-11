# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
PiControl eFMU module.
"""

# pylint: disable=broad-except,too-many-locals,too-many-branches,too-many-statements

import importlib
import json
import time
import traceback

import pandas as pd

from fmlc.baseclasses import eFMU


DEFAULT_CONFIG = {
    "kp": 0.5, # proportional gain
    "ki": 0.05, # integral gain (per error sample)
    "sp_key": "Pcc_setpoint_kW", # key in input-data for setpoint
    "pv_key": "Pcc_measured_kW", # measured-data key for PV (when pv_processor is None)
    "cv_key": None, # measured-data key to seed CV; None = use last computed CV
    "cv_setpoint_name": "Batt1_Pset_W", # external-setpoints key to write corrected CV
    "cv_scale": 1.0, # scale applied to correction; converts sp/pv units to cv units
    "cv_max_deviation": 250, # skip cycle if |measured_cv - last_cv| exceeds this; None = disabled
    "ki_deadband": None, # freeze integral when |error| > this; None = always integrate
    "state_key": "Batt1_SOC_%", # key in measured-data for output guard; None = disabled
    "state_min": 10, # lower guard limit (same units as state_key)
    "state_max": 100, # upper guard limit (same units as state_key)
    "cv_max": None, # symmetric CV output clip; None = no clip
    "reset_threshold": 1.0, # setpoint change magnitude that triggers integrator reset
    # pv_processor: dict with "module" and "name" keys, or None.
    # None = direct meas[pv_key] lookup.
    # Signature: pv_processor(cfg, data, meas, processor_config) -> float
    # Example using built-in pv_summation:
    #   "pv_processor": {"module": "fmlc.modules.pi_controller", "name": "pv_summation"},
    #   "pv_processor_config": {
    #       "data_terms": [["Pload_kW", 1.0]],
    #       "meas_terms": [["Inv1_Pac_W", -1/1000]],
    #   }
    "tz": "Etc/GMT+8", # time zone for the output-data index
    "pv_processor": None,
    "pv_processor_config": None, # passed as-is to pv_processor
}


def pv_summation(_cfg, data, meas, processor_config):
    """PV processor: weighted sum of data_terms and meas_terms."""
    result = 0.0
    for key, scale in processor_config["data_terms"]:
        result += float(data[key]) * scale
    for key, scale in processor_config["meas_terms"]:
        result += float(meas[key]) * scale
    return result


def _resolve_callable(spec):
    """Import and return a callable from a dict with 'module' and 'name' keys."""
    mod = importlib.import_module(spec["module"])
    return getattr(mod, spec["name"])


def _get_pv(cfg, data, meas):
    """Return the current process variable."""
    if cfg["pv_processor"] is not None:
        processor = _resolve_callable(cfg["pv_processor"])
        return processor(cfg, data, meas, cfg["pv_processor_config"])
    return float(meas[cfg["pv_key"]])


class PiController(eFMU):
    """PI controller that trims a command output each cycle to track a setpoint."""

    def __init__(self):
        super().__init__()
        self.input = {
            "input-data": None,
            "measured-data": None,
            "external-setpoints": None,
            "config": None,
            "debug": None,
        }
        self.output = {
            "output-ctrl": None,
            "output-data": None,
            "pi-error": None,
            "pi-integral": None,
            "pi-correction": None,
            "duration": None,
        }
        self.init = False
        self._integral = 0.0
        self._prev_setpoint = None
        self._cv_last = None

    def compute(self):
        """Compute PI correction and emit corrected command each cycle."""
        st = time.time()
        msg = ""
        out_ctrl = None
        out_data = None
        pi_error = None
        pi_integral = None
        pi_correction = None

        msg += self.check_data(self.input["input-data"], True)
        if not msg:
            msg += self.check_data(self.input["measured-data"], True)
        if not msg:
            msg += self.check_data(self.input["external-setpoints"], True)

        try:
            if not msg:
                cfg_raw = self.input["config"]
                if isinstance(cfg_raw, str):
                    cfg_raw = json.loads(cfg_raw)
                cfg = {**DEFAULT_CONFIG, **(cfg_raw or {})}

                data = self.input["input-data"]
                if isinstance(data, str):
                    data = json.loads(data)

                meas = self.input["measured-data"]
                if isinstance(meas, str):
                    meas = json.loads(meas)

                ext = self.input["external-setpoints"]
                if isinstance(ext, str):
                    ext = json.loads(ext)
                out_dict = dict(ext)

                if not self.init:
                    self._integral = 0.0
                    self._prev_setpoint = float(data[cfg["sp_key"]])
                    self.init = True

                sp = float(data[cfg["sp_key"]]) # setpoint
                pv = _get_pv(cfg, data, meas) # process variable
                if cfg["cv_key"] is not None:
                    cv = float(meas[cfg["cv_key"]]) # control variable
                else:
                    cv = self._cv_last if self._cv_last is not None else 0.0

                # Skip cycle if measured CV deviates too far from last commanded CV
                cv_max_dev = cfg["cv_max_deviation"]
                if cv_max_dev is not None and self._cv_last is not None:
                    deviation = abs(cv - self._cv_last)
                    if deviation > cv_max_dev:
                        msg += (
                            f"Skipping PI computation: measured cv={cv:.1f} deviates "
                            f"{deviation:.1f} from last commanded cv={self._cv_last:.1f} "
                            f"(threshold={cv_max_dev})."
                        )

                if not msg:
                    # Reset integrator on large setpoint step
                    if abs(sp - self._prev_setpoint) > cfg["reset_threshold"]:
                        self._integral = 0.0
                    self._prev_setpoint = sp

                    error = pv - sp
                    ki_deadband = cfg["ki_deadband"]
                    # conditional integration: only accumulate when error is within deadband
                    if ki_deadband is None or abs(error) <= ki_deadband:
                        self._integral += error
                    correction = cfg["kp"] * error + cfg["ki"] * self._integral
                    cv_new = cv - correction * cfg["cv_scale"]

                    # CV clip with anti-windup
                    if cfg["cv_max"] is not None:
                        if cv_new > cfg["cv_max"]:
                            cv_new = cfg["cv_max"]
                            self._integral = min(self._integral, 0.0)
                        elif cv_new < -cfg["cv_max"]:
                            cv_new = -cfg["cv_max"]
                            self._integral = max(self._integral, 0.0)

                    # Output guard with anti-windup
                    guard_pv = None
                    if cfg["state_key"] is not None:
                        guard_pv = float(meas[cfg["state_key"]])
                        if guard_pv >= cfg["state_max"]:
                            # SOC too high: block charging; prevent integral going more negative
                            cv_new = min(cv_new, 0.0)
                            self._integral = max(self._integral, 0.0)
                        if guard_pv <= cfg["state_min"]:
                            # SOC too low: block discharging; prevent integral going more positive
                            cv_new = max(cv_new, 0.0)
                            self._integral = min(self._integral, 0.0)

                    pi_error = error
                    pi_integral = self._integral
                    pi_correction = correction
                    self._cv_last = cv_new
                    out_dict[cfg["cv_setpoint_name"]] = cv_new
                    out_ctrl = json.dumps(out_dict)

                    diag = {
                        "sp": sp,
                        "pv": pv,
                        "cv": cv,
                        "cv_new": cv_new,
                        "pi_error": pi_error,
                        "pi_integral": pi_integral,
                        "pi_correction": pi_correction,
                        "guard_pv": guard_pv,
                    }
                    proc_cfg = cfg["pv_processor_config"] or {}
                    if "data_terms" in proc_cfg:
                        for key, _ in proc_cfg["data_terms"]:
                            diag[f"data_{key}"] = float(data[key])
                    if "meas_terms" in proc_cfg:
                        for key, _ in proc_cfg["meas_terms"]:
                            diag[f"meas_{key}"] = float(meas[key])
                    ts = (
                        pd.Timestamp(self.input["time"], unit="s", tz="UTC")
                        .tz_convert(cfg["tz"])
                        .tz_localize(None)
                    )
                    out_df = pd.DataFrame([diag], index=[ts])
                    out_data = out_df.to_json(date_format="iso")

        except Exception as e:
            msg += str(e)
            if self.input["debug"]:
                msg += f"\n\n{traceback.format_exc()}"

        self.output["output-ctrl"] = out_ctrl
        self.output["output-data"] = out_data
        self.output["pi-error"] = pi_error
        self.output["pi-integral"] = pi_integral
        self.output["pi-correction"] = pi_correction
        self.output["duration"] = time.time() - st

        if not msg:
            return "Done."
        return msg
