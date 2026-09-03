# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
LocalCsvReader eFMU module.
"""

# pylint: disable=broad-except

import time

import pandas as pd

from fmlc.baseclasses import eFMU


class LocalCsvReader(eFMU):
    """Read a CSV file and expose its contents as JSON."""

    def __init__(self):
        super().__init__()
        self.input = {
            "file-path": None,
        }
        self.output = {
            "output-data": None,
            "duration": None,
        }
        self.init = False

    def compute(self):
        st = time.time()
        out_data = None
        msg = ""

        try:
            df = pd.read_csv(self.input["file-path"], index_col=0)
            df.index = pd.to_datetime(df.index)
            out_data = df.to_json(date_format="iso")
        except Exception as e:
            msg += str(e)

        self.output["output-data"] = out_data
        self.output["duration"] = time.time() - st

        if msg:
            return msg
        return "Done."
