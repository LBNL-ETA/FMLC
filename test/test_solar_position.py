# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Tests for the SolarPosition eFMU module.
"""

# pylint: disable=broad-except

import io
import sys
from os import path

import pandas as pd

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.modules.solar_position import SolarPosition

# Berkeley, CA - midday summer timestamp (2024-06-21 18:00 UTC = 11:00 PDT)
LAT = 37.8716
LON = -122.2727
ALT = 52.0
TZ = "America/Los_Angeles"
TS_MIDDAY = 1718985600 # 2024-06-21 18:00:00 UTC

# A minimal SCADA DataFrame serialised to JSON
_BASE_DF = pd.DataFrame([
    {"name": "weather-temp", "value": 20.0, "valid": True, "error": ""},
])
INPUT_DATA = _BASE_DF.to_json()


def _make_module(ts=TS_MIDDAY, debug=None):
    """Return a SolarPosition instance with inputs pre-populated."""
    mod = SolarPosition()
    mod.input["input-data"] = INPUT_DATA
    mod.input["latitude"] = LAT
    mod.input["longitude"] = LON
    mod.input["altitude"] = ALT
    mod.input["time-zone"] = TZ
    mod.input["debug"] = debug
    mod.input["time"] = ts
    return mod


def test_outputs_declared():
    mod = SolarPosition()
    assert "output-data" in mod.output
    assert "duration" in mod.output


def test_inputs_declared():
    mod = SolarPosition()
    for key in ("input-data", "latitude", "longitude", "altitude", "time-zone", "debug"):
        assert key in mod.input


def test_compute_success():
    mod = _make_module()
    msg = mod.compute()
    assert msg == "Done."
    assert mod.output["output-data"] is not None
    assert mod.output["duration"] >= 0.0


def test_output_contains_solar_rows():
    mod = _make_module()
    mod.compute()
    df = pd.read_json(io.StringIO(mod.output["output-data"]))
    names = list(df["name"])
    assert "weather-alt" in names
    assert "weather-azi" in names
    assert "weather-zenith" in names
    assert "weather-airmass" in names


def test_original_rows_preserved():
    mod = _make_module()
    mod.compute()
    df = pd.read_json(io.StringIO(mod.output["output-data"]))
    assert "weather-temp" in list(df["name"])


def test_elevation_positive_at_midday():
    mod = _make_module()
    mod.compute()
    df = pd.read_json(io.StringIO(mod.output["output-data"]))
    elevation = float(df.loc[df["name"] == "weather-alt", "value"].iloc[0])
    assert elevation > 0.0


def test_airmass_zero_at_night():
    # 2024-06-21 06:00 UTC = 2024-06-20 23:00 PDT - well past sunset
    ts_night = 1718949600
    mod = _make_module(ts=ts_night)
    mod.compute()
    df = pd.read_json(io.StringIO(mod.output["output-data"]))
    airmass = float(df.loc[df["name"] == "weather-airmass", "value"].iloc[0])
    assert airmass == 0.0


def test_missing_input_data_returns_waiting():
    mod = _make_module()
    mod.input["input-data"] = None
    msg = mod.compute()
    assert "Waiting" in msg
    assert mod.output["output-data"] is None


def test_do_step_interface():
    mod = SolarPosition()
    msg = mod.do_step(inputs={
        "input-data": INPUT_DATA,
        "latitude": LAT,
        "longitude": LON,
        "altitude": ALT,
        "time-zone": TZ,
        "debug": None,
        "time": TS_MIDDAY,
    })
    assert msg == "Done."
