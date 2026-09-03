# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
LocalCsvWriter eFMU module.
"""

# pylint: disable=broad-except

import io
import os
import time

import pandas as pd

from fmlc.baseclasses import eFMU


class LocalCsvWriter(eFMU):
    """Write JSON-serialised DataFrame to a CSV file."""

    def __init__(self):
        super().__init__()
        self.input = {
            "input-data": None,
            "file-path": None,
            "append": None,
        }
        self.output = {
            "duration": None,
        }
        self.init = False

    def compute(self):
        st = time.time()
        msg = ""

        msg = self.check_data(self.input["input-data"], True)

        try:
            if not msg:
                data = pd.read_json(io.StringIO(self.input["input-data"]))
                data.index = pd.to_datetime(data.index)

                file_path = self.input["file-path"]
                append_mode = bool(self.input["append"])

                data.index = data.index.strftime("%Y-%m-%d %H:%M:%S")

                if append_mode:
                    file_exists = os.path.exists(file_path)
                    data.to_csv(
                        file_path,
                        mode="a" if file_exists else "w",
                        header=not file_exists,
                    )
                else:
                    data.to_csv(file_path)
        except Exception as e:
            msg += str(e)

        self.output["duration"] = time.time() - st

        if msg:
            return msg
        return "Done."
