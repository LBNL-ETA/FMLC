# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Tests for the SkySpark eFMU modules.
"""

# pylint: disable=broad-except

import io
import sys
import tempfile
from os import path

import pandas as pd

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.modules.skyspark.dummy import SkysparkDummy
from fmlc.modules.skyspark.scada_formatter import (
    SkysparkScadaFormatter,
    _align_index_to_sampling,
    _apply_math_template,
    _coerce_to_dataframe,
    _normalize_channel_list,
)

# 2024-06-21 15:00:00 UTC (midday solar time, US west coast afternoon)
TS_MIDDAY = 1718978400

# Minimal math template CSV with all required columns
_MATH_TEMPLATE_CSV = (
    "new_channel,operation,channel_a,channel_b,scalar,abs_value,clip_min,clip_max\n"
    "P_pv_total_W,sum,P_pv1_W,P_pv2_W,,,,"
    "\n"
)


def _make_scada_input_json(ts_unix=TS_MIDDAY, freq="5min", periods=13):
    """Return a JSON-serialised DataFrame with aligned 5-min timestamps."""
    idx = pd.date_range(
        end=pd.Timestamp(ts_unix, unit="s", tz="UTC"), periods=periods, freq=freq
    )
    df = pd.DataFrame(
        {
            "P_pv1_W": [100.0] * periods,
            "P_pv2_W": [200.0] * periods,
            "P_pv3_W": [150.0] * periods,
            "weather-ghi": [500.0] * periods,
        },
        index=idx,
    )
    return df.to_json(date_format="iso")


def _write_math_template(content=_MATH_TEMPLATE_CSV):
    """Write a math template CSV to a temp file; return its path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    tmp.write(content)
    tmp.flush()
    return tmp.name


# SkysparkDummy tests

def test_dummy_outputs_declared():
    mod = SkysparkDummy()
    assert "output-data" in mod.output
    assert "duration" in mod.output


def test_dummy_inputs_declared():
    mod = SkysparkDummy()
    for key in ("credentials-file", "uri", "project", "cmd", "channel-map", "timeout"):
        assert key in mod.input


def test_dummy_compute_success():
    mod = SkysparkDummy()
    mod.input["time"] = TS_MIDDAY
    msg = mod.compute()
    assert msg == "Done."
    assert mod.output["output-data"] is not None
    assert mod.output["duration"] >= 0.0


def test_dummy_output_has_pv_channels():
    mod = SkysparkDummy()
    mod.input["time"] = TS_MIDDAY
    mod.compute()
    df = pd.read_json(io.StringIO(mod.output["output-data"]))
    for col in ("P_pv1_W", "P_pv2_W", "P_pv3_W", "weather-ghi", "weather-dni", "weather-dhi"):
        assert col in df.columns


def test_dummy_output_has_13_rows():
    mod = SkysparkDummy()
    mod.input["time"] = TS_MIDDAY
    mod.compute()
    df = pd.read_json(io.StringIO(mod.output["output-data"]))
    assert len(df) == 13


def test_dummy_pv_zero_at_night():
    # 2024-06-21 03:00 UTC = well before sunrise
    ts_night = 1718935200
    mod = SkysparkDummy()
    mod.input["time"] = ts_night
    mod.compute()
    df = pd.read_json(io.StringIO(mod.output["output-data"]))
    assert (df["P_pv1_W"] == 0.0).all()


def test_dummy_do_step_interface():
    mod = SkysparkDummy()
    msg = mod.do_step(inputs={
        "credentials-file": None,
        "uri": None,
        "project": None,
        "cmd": None,
        "channel-map": None,
        "timeout": None,
        "time": TS_MIDDAY,
    })
    assert msg == "Done."


# _coerce_to_dataframe tests

def test_coerce_from_json_string():
    idx = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    df_in = pd.DataFrame({"val": [1.0, 2.0, 3.0]}, index=idx)
    df_out = _coerce_to_dataframe(df_in.to_json(date_format="iso"))
    assert isinstance(df_out.index, pd.DatetimeIndex)
    assert len(df_out) == 3


def test_coerce_from_dataframe():
    idx = pd.date_range("2024-01-01", periods=2, freq="5min", tz="UTC")
    df_in = pd.DataFrame({"val": [1.0, 2.0]}, index=idx)
    df_out = _coerce_to_dataframe(df_in)
    assert len(df_out) == 2


def test_coerce_from_dict():
    data = {"val": {0: 1.0, 1: 2.0}}
    df_out = _coerce_to_dataframe(data)
    assert "val" in df_out.columns


def test_coerce_invalid_type_raises():
    try:
        _coerce_to_dataframe(42)
        assert False, "Expected ValueError"
    except ValueError:
        pass


# _align_index_to_sampling tests

def test_align_keeps_aligned_rows():
    idx = pd.date_range("2024-01-01 00:00:00", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame({"v": [1, 2, 3]}, index=idx)
    result = _align_index_to_sampling(df, 300)
    assert len(result) == 3


def test_align_drops_unaligned_rows():
    idx = pd.to_datetime(["2024-01-01 00:00:00", "2024-01-01 00:01:00"], utc=True)
    df = pd.DataFrame({"v": [1, 2]}, index=idx)
    result = _align_index_to_sampling(df, 300)
    assert len(result) == 1


def test_align_none_returns_original():
    idx = pd.date_range("2024-01-01", periods=3, freq="1min", tz="UTC")
    df = pd.DataFrame({"v": [1, 2, 3]}, index=idx)
    result = _align_index_to_sampling(df, None)
    assert len(result) == 3


# _normalize_channel_list tests

def test_normalize_none_returns_empty():
    assert _normalize_channel_list(None) == []


def test_normalize_string_returns_list():
    assert _normalize_channel_list("ch1") == ["ch1"]


def test_normalize_list_returns_list():
    assert _normalize_channel_list(["ch1", "ch2"]) == ["ch1", "ch2"]


def test_normalize_invalid_raises():
    try:
        _normalize_channel_list(123)
        assert False, "Expected ValueError"
    except ValueError:
        pass


# _apply_math_template tests

def test_math_template_sum():
    ops = pd.DataFrame([{
        "new_channel": "total",
        "operation": "sum",
        "channel_a": "a",
        "channel_b": "b",
        "scalar": None,
        "abs_value": False,
        "clip_min": None,
        "clip_max": None,
    }])
    row = {"a": 3.0, "b": 4.0}
    result, msg = _apply_math_template(row, ops)
    assert result["total"] == 7.0
    assert msg == ""


def test_math_template_scale():
    ops = pd.DataFrame([{
        "new_channel": "scaled",
        "operation": "scale",
        "channel_a": "a",
        "channel_b": None,
        "scalar": 2.0,
        "abs_value": False,
        "clip_min": None,
        "clip_max": None,
    }])
    row = {"a": 5.0}
    result, _ = _apply_math_template(row, ops)
    assert result["scaled"] == 10.0


def test_math_template_clip():
    ops = pd.DataFrame([{
        "new_channel": "clipped",
        "operation": "copy",
        "channel_a": "a",
        "channel_b": None,
        "scalar": None,
        "abs_value": False,
        "clip_min": 2.0,
        "clip_max": 8.0,
    }])
    row = {"a": 15.0}
    result, _ = _apply_math_template(row, ops)
    assert result["clipped"] == 8.0


def test_math_template_unsupported_op_adds_msg():
    ops = pd.DataFrame([{
        "new_channel": "x",
        "operation": "unknown_op",
        "channel_a": "a",
        "channel_b": None,
        "scalar": None,
        "abs_value": False,
        "clip_min": None,
        "clip_max": None,
    }])
    row = {"a": 1.0}
    _, msg = _apply_math_template(row, ops)
    assert "Unsupported operation" in msg


def test_math_template_empty_ops():
    row = {"a": 1.0}
    result, msg = _apply_math_template(row, pd.DataFrame())
    assert result == row
    assert msg == ""


# SkysparkScadaFormatter tests

_SENTINEL = object()


def _make_formatter(ts=TS_MIDDAY, template_file=None, target_channels=None,
                    input_data=_SENTINEL, sample_seconds=300):
    """Return a SkysparkScadaFormatter with inputs pre-populated."""
    mod = SkysparkScadaFormatter()
    mod.input["input-data"] = _make_scada_input_json(ts) if input_data is _SENTINEL else input_data
    mod.input["sample-seconds"] = sample_seconds
    mod.input["target-channels"] = target_channels
    mod.input["math-template-file"] = template_file
    mod.input["time-zone"] = "America/Los_Angeles"
    mod.input["debug"] = None
    mod.input["time"] = ts
    return mod


def test_formatter_outputs_declared():
    mod = SkysparkScadaFormatter()
    assert "output-data" in mod.output
    assert "closest-timestamp" in mod.output
    assert "duration" in mod.output


def test_formatter_inputs_declared():
    mod = SkysparkScadaFormatter()
    for key in ("input-data", "sample-seconds", "target-channels",
                "math-template-file", "time-zone", "debug"):
        assert key in mod.input


def test_formatter_missing_input_data_returns_waiting():
    mod = _make_formatter(input_data=None)
    msg = mod.compute()
    assert "Waiting" in msg
    assert mod.output["output-data"] is not None
    assert mod.output["duration"] >= 0.0


def test_formatter_all_outputs_assigned_on_error():
    mod = _make_formatter(input_data=None)
    mod.compute()
    assert "output-data" in mod.output
    assert "closest-timestamp" in mod.output
    assert "duration" in mod.output


def test_formatter_compute_success_with_template():
    tpl = _write_math_template()
    mod = _make_formatter(template_file=tpl)
    msg = mod.compute()
    assert msg == "Done."
    assert mod.output["output-data"] is not None
    assert mod.output["duration"] >= 0.0


def test_formatter_closest_timestamp_set():
    tpl = _write_math_template()
    mod = _make_formatter(template_file=tpl)
    mod.compute()
    assert mod.output["closest-timestamp"] is not None


def test_formatter_target_channels_filters_output():
    tpl = _write_math_template()
    mod = _make_formatter(template_file=tpl, target_channels=["P_pv1_W", "P_pv2_W"])
    mod.compute()
    df = pd.read_json(io.StringIO(mod.output["output-data"]))
    names = list(df["name"])
    assert "P_pv1_W" in names
    assert "P_pv2_W" in names
    assert "weather-ghi" not in names


def test_formatter_math_template_adds_derived_channel():
    tpl = _write_math_template()
    mod = _make_formatter(template_file=tpl, target_channels=["P_pv_total_W"])
    mod.compute()
    df = pd.read_json(io.StringIO(mod.output["output-data"]))
    row = df[df["name"] == "P_pv_total_W"].iloc[0]
    assert row["value"] == 300.0  # P_pv1_W(100) + P_pv2_W(200)
    assert row["valid"]


def test_formatter_no_aligned_rows_returns_error():
    idx = pd.to_datetime(["2024-06-21T15:01:00Z", "2024-06-21T15:02:00Z"])
    df = pd.DataFrame({"P_pv1_W": [1.0, 2.0]}, index=idx)
    tpl = _write_math_template()
    mod = _make_formatter(
        input_data=df.to_json(date_format="iso"), template_file=tpl, sample_seconds=300
    )
    msg = mod.compute()
    assert "No timesteps align" in msg


def test_formatter_init_runs_only_once():
    tpl = _write_math_template()
    mod = _make_formatter(template_file=tpl)
    mod.compute()
    ops_after_first = mod._template_ops

    mod.input["time"] = TS_MIDDAY + 300
    mod.input["input-data"] = _make_scada_input_json(TS_MIDDAY + 300)
    mod.compute()
    assert mod._template_ops is ops_after_first


def test_formatter_do_step_interface():
    tpl = _write_math_template()
    mod = SkysparkScadaFormatter()
    msg = mod.do_step(inputs={
        "input-data": _make_scada_input_json(),
        "sample-seconds": 300,
        "target-channels": None,
        "math-template-file": tpl,
        "time-zone": "America/Los_Angeles",
        "debug": None,
        "time": TS_MIDDAY,
    })
    assert msg == "Done."
