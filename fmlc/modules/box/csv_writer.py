# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
BoxCsvWriter eFMU module.
"""

# pylint: disable=broad-except

import io
import time

import pandas as pd
from box_sdk_gen import UploadFileVersionAttributes

from fmlc.baseclasses import eFMU

from .oauth_utils import get_oauth_client, get_file_id, persist_tokens


class BoxCsvWriter(eFMU):
    """Upload a JSON-serialised DataFrame as a CSV file version on Box."""

    def __init__(self):
        super().__init__()
        self.input = {
            "input-data": None,
            "credentials-file": None,
            "token-file": None,
            "folder-id": None,
            "file-name": None,
            "delete-old-versions": None,
            "append-to-existing": None,
        }
        self.output = {
            "duration": None,
        }
        self.init = False
        self.client = None
        self.auth = None
        self._token_file = None

    def compute(self):
        st = time.time()
        msg = ""

        msg += self.check_data(self.input["input-data"], True)

        try:
            if not msg:
                if not self.init:
                    self._token_file = self.input["token-file"]
                    self.auth, self.client = get_oauth_client(
                        self.input["credentials-file"], self.input["token-file"]
                    )
                    self.init = True

                file_id = get_file_id(
                    self.client, self.input["file-name"], self.input["folder-id"]
                )

                data = pd.read_json(io.StringIO(self.input["input-data"]))
                data.index = pd.to_datetime(data.index)

                if self.input["append-to-existing"]:
                    content = self.client.downloads.download_file(file_id).read()
                    existing = pd.read_csv(io.BytesIO(content), index_col=0)
                    existing.index = pd.to_datetime(existing.index)
                    data = pd.concat([existing, data])

                buffer = io.BytesIO()
                data.to_csv(buffer)
                buffer.seek(0)

                if self.input["delete-old-versions"]:
                    versions = self.client.file_versions.get_file_versions(file_id)
                    for version in versions.entries:
                        self.client.file_versions.delete_file_version_by_id(
                            file_id, version.id
                        )

                self.client.uploads.upload_file_version(
                    file_id=file_id,
                    attributes=UploadFileVersionAttributes(name=self.input["file-name"]),
                    file=buffer,
                )

                persist_tokens(self.auth, self._token_file)

        except Exception as e:
            msg += str(e)

        self.output["duration"] = time.time() - st

        if msg:
            return msg
        return "Done."
