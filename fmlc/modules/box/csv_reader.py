# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
BoxCsvReader eFMU module.
"""

# pylint: disable=broad-except

import io
import time

import pandas as pd

from fmlc.baseclasses import eFMU

from .oauth_utils import get_oauth_client, get_file_id, persist_tokens


class BoxCsvReader(eFMU):
    """Download a CSV file from Box and expose its contents as JSON."""

    def __init__(self):
        super().__init__()
        self.input = {
            "credentials-file": None,
            "token-file": None,
            "folder-id": None,
            "file-name": None,
        }
        self.output = {
            "output-data": None,
            "duration": None,
        }
        self.init = False
        self.client = None
        self.auth = None
        self._token_file = None

    def compute(self):
        st = time.time()
        msg = ""
        out_data = None

        try:
            if not self.init:
                self._token_file = self.input["token-file"]
                self.auth, self.client = get_oauth_client(
                    self.input["credentials-file"], self.input["token-file"]
                )
                self.init = True

            file_id = get_file_id(
                self.client, self.input["file-name"], self.input["folder-id"]
            )

            content = self.client.downloads.download_file(file_id).read()
            df = pd.read_csv(io.BytesIO(content), index_col=0)
            df.index = pd.to_datetime(df.index)
            out_data = df.to_json(date_format="iso")

            persist_tokens(self.auth, self._token_file)

        except Exception as e:
            msg += str(e)

        self.output["output-data"] = out_data
        self.output["duration"] = time.time() - st

        if msg:
            return msg
        return "Done."
