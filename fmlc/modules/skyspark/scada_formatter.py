# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
SkysparkScadaFormatter eFMU module.
"""

# pylint: disable=broad-except,too-many-locals,too-many-branches,too-many-statements

import io
import os
import time
import traceback

import pandas as pd

from fmlc.baseclasses import eFMU


def _coerce_to_dataframe(payload):
    """Convert a JSON string, dict, or DataFrame payload into a DatetimeIndex DataFrame."""
    if isinstance(payload, pd.DataFrame):
        df = payload.copy()
    elif isinstance(payload, str):
        df = pd.read_json(io.StringIO(payload))
    elif isinstance(payload, dict):
        df = pd.DataFrame(payload)
    else:
        raise ValueError("input-data must be DataFrame, JSON string, or dict.")

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")

    df = df[~df.index.isna()].sort_index()
    return df


def _align_index_to_sampling(df, sample_seconds):
    """Drop rows whose timestamps are not aligned to sample_seconds boundaries."""
    if sample_seconds is None:
        return df

    sample_seconds = int(sample_seconds)
    if sample_seconds <= 0:
        raise ValueError("sample-seconds must be a positive integer.")

    epoch_s = (df.index.view("int64") // 10**9).astype("int64")
    mask = (epoch_s % sample_seconds) == 0
    return df.loc[mask]


def _normalize_channel_list(channels):
    """Return a list of non-empty channel name strings from various input types."""
    if channels is None:
        return []
    if isinstance(channels, str):
        return [channels]
    if isinstance(channels, (list, tuple, set)):
        return [str(c) for c in channels if c is not None and str(c).strip()]
    raise ValueError("target-channels must be string or list-like.")


def _apply_math_template(row_dict, ops):
    """Apply a math-operations DataFrame to a row dict; return (updated_dict, error_msg)."""
    msg = ""
    values = dict(row_dict)

    if ops is None or ops.empty:
        return values, msg

    required = {
        "new_channel",
        "operation",
        "channel_a",
        "channel_b",
        "scalar",
        "abs_value",
        "clip_min",
        "clip_max",
    }
    missing = required.difference(set(ops.columns))
    if missing:
        raise ValueError(f"math template missing columns: {sorted(missing)}")

    for _, r in ops.iterrows():
        name = str(r["new_channel"]).strip()
        op = str(r["operation"]).strip().lower()
        ch_a = str(r["channel_a"]).strip() if pd.notna(r["channel_a"]) else ""
        ch_b = str(r["channel_b"]).strip() if pd.notna(r["channel_b"]) else ""
        a = float(values.get(ch_a, 0.0)) if ch_a else 0.0
        b = float(values.get(ch_b, 0.0)) if ch_b else 0.0
        scalar = float(r["scalar"]) if pd.notna(r["scalar"]) else None

        v = None
        if op == "copy":
            v = a
        elif op == "sum":
            v = a + b
        elif op == "diff":
            v = a - b
        elif op == "mul":
            v = a * b
        elif op == "div":
            v = a / b if b != 0 else float("nan")
        elif op == "scale":
            v = a * (scalar if scalar is not None else 1.0)
        elif op == "offset":
            v = a + (scalar if scalar is not None else 0.0)
        elif op == "threshold_zero":
            th = scalar if scalar is not None else 0.0
            v = 0.0 if a < th else a
        else:
            msg += f"Unsupported operation '{op}' for '{name}'. "

        if v is not None:
            abs_value = bool(r["abs_value"]) if pd.notna(r["abs_value"]) else False
            if abs_value:
                v = abs(v)

            if pd.notna(r["clip_min"]):
                v = max(v, float(r["clip_min"]))
            if pd.notna(r["clip_max"]):
                v = min(v, float(r["clip_max"]))

            values[name] = float(v)

    return values, msg


class SkysparkScadaFormatter(eFMU):
    """Align, timestamp-match, and apply math transforms to a SkySpark SCADA payload."""

    def __init__(self):
        super().__init__()
        self.input = {
            "input-data": None,
            "sample-seconds": None,
            "target-channels": None,
            "math-template-file": None,
            "time-zone": None,
            "debug": None,
        }
        self.output = {
            "output-data": None,
            "closest-timestamp": None,
            "duration": None,
        }
        self.init = False
        self._template_ops = None

    def compute(self):
        st = time.time()
        msg = ""
        closest_timestamp = None

        output_cols = _normalize_channel_list(self.input["target-channels"])
        out_df = pd.DataFrame(
            {
                "name": output_cols,
                "value": [None] * len(output_cols),
                "valid": [False] * len(output_cols),
                "error": [""] * len(output_cols),
            }
        )

        msg += self.check_data(self.input["input-data"], True)
        if not msg:
            msg += self.check_data(self.input["sample-seconds"], True)

        try:
            if not msg:
                df = _coerce_to_dataframe(self.input["input-data"])

            if not msg:
                df = _align_index_to_sampling(df, self.input["sample-seconds"])
                if df.empty:
                    raise ValueError("No timesteps align with sample-seconds.")

            if not msg:
                ts_unix = self.input["time"]
                now = pd.Timestamp(ts_unix, unit="s", tz="UTC")
                tz = self.input["time-zone"]
                now = now.tz_convert(tz)
                df.index = df.index.tz_convert(tz)

                time_deltas = df.index - now
                closest_ix = abs(time_deltas).argmin()
                ts = df.index[closest_ix]
                row = df.iloc[closest_ix].to_dict()
                closest_timestamp = ts.isoformat()

            if not msg and not self.init:
                template_file = self.input["math-template-file"]
                if not template_file:
                    template_file = os.path.join(
                        os.path.dirname(__file__), "skyspark_scada_math_template.csv"
                    )
                self._template_ops = pd.read_csv(template_file)
                self.init = True

            if not msg:
                row, template_msg = _apply_math_template(row, self._template_ops)
                msg += template_msg

            if not msg:
                keys = output_cols if output_cols else list(row.keys())
                out_df = pd.DataFrame({"name": keys})
                out_df["value"] = [row.get(k, None) for k in keys]
                out_df["valid"] = [k in row and pd.notna(row[k]) for k in keys]
                out_df["error"] = ""

        except Exception as e:
            msg += str(e)
            out_df["error"] = str(e)
            if self.input["debug"]:
                msg += f"\n\n{traceback.format_exc()}"

        self.output["output-data"] = out_df.to_json()
        self.output["closest-timestamp"] = closest_timestamp
        self.output["duration"] = time.time() - st

        if not msg:
            return "Done."
        return msg
