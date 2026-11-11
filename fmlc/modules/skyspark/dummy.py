# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
SkysparkDummy eFMU module.
"""

# pylint: disable=broad-except

import time

import numpy as np
import pandas as pd

from fmlc.baseclasses import eFMU


class SkysparkDummy(eFMU):
    """Offline replacement for SkysparkReader; returns synthetic PV and irradiance history."""

    # Per-circuit clear-sky peak power [W]
    PEAK_W = {"P_pv1_W": 5500.0, "P_pv2_W": 5000.0, "P_pv3_W": 4500.0}
    SUNRISE_H = 6.0
    SUNSET_H = 20.0

    def __init__(self):
        super().__init__()
        self.input = {
            "credentials-file": None,
            "uri": None,
            "project": None,
            "cmd": None,
            "channel-map": None,
            "timeout": None,
        }
        self.output = {
            "output-data": None,
            "duration": None,
        }
        self.init = False

    def _pv(self, h, peak_w):
        """Return synthetic PV power [W] for hour-of-day h."""
        if h < self.SUNRISE_H or h > self.SUNSET_H:
            return 0.0
        return peak_w * np.sin(
            np.pi * (h - self.SUNRISE_H) / (self.SUNSET_H - self.SUNRISE_H)
        )

    def compute(self):
        st = time.time()
        msg = ""
        out_data = None

        try:
            ts = float(self.input["time"])
            now_utc = pd.Timestamp(ts, unit="s", tz="UTC")

            # 60-min history at 5-min intervals ending at the simulated timestamp
            idx = pd.date_range(end=now_utc, periods=13, freq="5min")
            h = np.array([t.hour + t.minute / 60.0 for t in idx])

            span = self.SUNSET_H - self.SUNRISE_H
            ghi = np.clip(
                800.0 * np.sin(np.pi * np.clip(h - self.SUNRISE_H, 0.0, span) / span),
                0.0, 1000.0,
            )

            df = pd.DataFrame(
                {
                    "P_pv1_W": [self._pv(x, self.PEAK_W["P_pv1_W"]) for x in h],
                    "P_pv2_W": [self._pv(x, self.PEAK_W["P_pv2_W"]) for x in h],
                    "P_pv3_W": [self._pv(x, self.PEAK_W["P_pv3_W"]) for x in h],
                    "weather-ghi": ghi,
                    "weather-dni": ghi * 0.70,
                    "weather-dhi": ghi * 0.30,
                },
                index=idx,
            )
            out_data = df.to_json(date_format="iso")

        except Exception as e:
            msg += str(e)

        self.output["output-data"] = out_data
        self.output["duration"] = time.time() - st

        if not msg:
            return "Done."
        return msg
