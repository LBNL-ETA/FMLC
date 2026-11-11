# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
SolarPosition eFMU module.
"""

# pylint: disable=broad-except,too-many-locals

import io
import time
import traceback

import pandas as pd
import pvlib

from fmlc.baseclasses import eFMU


class SolarPosition(eFMU):
    """Append pvlib solar-position columns to a JSON-encoded SCADA DataFrame."""

    def __init__(self):
        super().__init__()
        self.input = {
            "input-data": None,
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "time-zone": None,
            "debug": None,
        }
        self.output = {
            "output-data": None,
            "duration": None,
        }
        self.init = False

    def compute(self):
        st = time.time()
        msg = ""
        out_data = None

        msg += self.check_data(self.input["input-data"], True)

        try:
            if not msg:
                ts = pd.Timestamp(self.input["time"], unit="s", tz="UTC")
                tz = self.input["time-zone"]
                ts = ts.tz_convert(tz)

                lat = float(self.input["latitude"])
                lon = float(self.input["longitude"])
                alt = float(self.input["altitude"])

                location = pvlib.location.Location(
                    latitude=lat,
                    longitude=lon,
                    altitude=alt,
                    tz=tz or "UTC",
                )
                times = pd.DatetimeIndex([ts])
                solpos = location.get_solarposition(times)
                airmass_df = location.get_airmass(times)

                elevation = float(solpos["apparent_elevation"].iloc[0])
                sun_up = elevation > 0.0
                azimuth = float(solpos["azimuth"].iloc[0])
                apparent_zenith = float(solpos["apparent_zenith"].iloc[0])
                airmass_val = (
                    float(airmass_df["airmass_relative"].iloc[0]) if sun_up else 0.0
                )

                new_rows = pd.DataFrame([
                    {"name": "weather-alt", "value": elevation, "valid": True, "error": ""},
                    {"name": "weather-azi", "value": azimuth, "valid": True, "error": ""},
                    {"name": "weather-zenith", "value": apparent_zenith,
                     "valid": True, "error": ""},
                    {"name": "weather-airmass", "value": airmass_val, "valid": True, "error": ""},
                ])

                df = pd.read_json(io.StringIO(self.input["input-data"]))
                df = pd.concat([df, new_rows], ignore_index=True)
                out_data = df.to_json()

        except Exception as e:
            msg += str(e)
            if self.input["debug"]:
                msg += f"\n\n{traceback.format_exc()}"

        self.output["output-data"] = out_data
        self.output["duration"] = time.time() - st

        if not msg:
            return "Done."
        return msg
