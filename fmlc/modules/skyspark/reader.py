# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
SkysparkReader eFMU module.
"""

# pylint: disable=broad-except

import json
import time

import pandas as pd
import pyhaystack
from hszinc import jsondumper

from fmlc.baseclasses import eFMU


def _grid_to_pandas(g):
    """Parse a pyhaystack grid result into a pandas DataFrame."""
    d = json.loads(jsondumper.dump_grid(g))

    cols = ["date_time"] + [c["channelName"].replace("s:", "") for c in d["cols"][1:]]

    val = []
    for r in d["rows"]:
        val.append(
            [c.replace("t:", "").replace("n:", "").split(" ")[0] for c in r.values() if c]
        )

    df = pd.DataFrame(val, columns=cols)
    df = df.set_index("date_time")
    df.index = pd.to_datetime(df.index)
    df = df.apply(pd.to_numeric)
    return df


class SkysparkReader(eFMU):
    """Download time-series data from a SkySpark server via a Haystack eval command."""

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
        self._session = None

    def compute(self):
        st = time.time()
        msg = ""
        out_data = None

        try:
            if not self.init:
                with open(self.input["credentials-file"], encoding="utf-8") as f:
                    creds = json.loads(f.read())

                self._session = pyhaystack.connect(
                    implementation="skyspark",
                    uri=self.input["uri"],
                    project=self.input["project"],
                    username=creds["u"],
                    password=creds["p"],
                )
                self.init = True

            res = self._session.get_eval(self.input["cmd"]).result
            data = _grid_to_pandas(res)

            channel_map = self.input["channel-map"]
            if channel_map is not None:
                data = data.rename(columns=channel_map)
                data = data[list(channel_map.values())]

            out_data = data.to_json(date_format="iso")

        except Exception as e:
            msg += str(e)

        self.output["output-data"] = out_data
        self.output["duration"] = time.time() - st

        if not msg:
            return "Done."
        return msg
