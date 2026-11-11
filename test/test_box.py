# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Tests for the Box eFMU modules (BoxCsvReader and BoxCsvWriter).
"""

# pylint: disable=broad-except

import io
import json
import sys
import tempfile
from os import path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

pytest.importorskip("box_sdk_gen", reason="box-sdk-gen not installed; skipping Box tests.")

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.modules.box.csv_reader import BoxCsvReader
from fmlc.modules.box.csv_writer import BoxCsvWriter
from fmlc.modules.box.oauth_utils import (
    create_token_payload,
    load_json,
    persist_tokens,
    save_json,
)

# Minimal sample DataFrame serialised as CSV bytes and JSON
_DF = pd.DataFrame(
    {"value": [1.0, 2.0]},
    index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
)
_CSV_BYTES = _DF.to_csv().encode()
_JSON_DATA = _DF.to_json(date_format="iso")


def _make_reader(credentials_file="creds.json", token_file="tokens.json",
                 folder_id="123", file_name="data.csv"):
    """Return a BoxCsvReader with inputs pre-populated."""
    mod = BoxCsvReader()
    mod.input["credentials-file"] = credentials_file
    mod.input["token-file"] = token_file
    mod.input["folder-id"] = folder_id
    mod.input["file-name"] = file_name
    return mod


def _make_writer(input_data=_JSON_DATA, credentials_file="creds.json",
                 token_file="tokens.json", folder_id="123", file_name="data.csv",
                 delete_old=False, append=False):
    """Return a BoxCsvWriter with inputs pre-populated."""
    mod = BoxCsvWriter()
    mod.input["input-data"] = input_data
    mod.input["credentials-file"] = credentials_file
    mod.input["token-file"] = token_file
    mod.input["folder-id"] = folder_id
    mod.input["file-name"] = file_name
    mod.input["delete-old-versions"] = delete_old
    mod.input["append-to-existing"] = append
    return mod


def _mock_client(csv_bytes=_CSV_BYTES, file_id="file42"):
    """Return a MagicMock BoxClient that returns csv_bytes on download."""
    client = MagicMock()
    entry = MagicMock()
    entry.name = "data.csv"
    entry.id = file_id
    client.folders.get_folder_items.return_value.entries = [entry]
    client.downloads.download_file.return_value = io.BytesIO(csv_bytes)
    return client


# --- BoxCsvReader structural tests ---

def test_reader_inputs_declared():
    mod = BoxCsvReader()
    for key in ("credentials-file", "token-file", "folder-id", "file-name"):
        assert key in mod.input


def test_reader_outputs_declared():
    mod = BoxCsvReader()
    assert "output-data" in mod.output
    assert "duration" in mod.output


def test_reader_all_outputs_assigned_on_error():
    mod = _make_reader()
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", side_effect=RuntimeError("no creds")):
        mod.compute()
    assert "output-data" in mod.output
    assert "duration" in mod.output


def test_reader_returns_error_string_on_failure():
    mod = _make_reader()
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", side_effect=RuntimeError("auth error")):
        msg = mod.compute()
    assert "auth error" in msg


def test_reader_output_data_none_on_error():
    mod = _make_reader()
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", side_effect=RuntimeError("fail")):
        mod.compute()
    assert mod.output["output-data"] is None


def test_reader_duration_non_negative_on_error():
    mod = _make_reader()
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", side_effect=RuntimeError("fail")):
        mod.compute()
    assert mod.output["duration"] >= 0.0


def test_reader_compute_success():
    mod = _make_reader()
    client = _mock_client()
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_reader.persist_tokens"):
        msg = mod.compute()
    assert msg == "Done."
    assert mod.output["output-data"] is not None
    parsed = json.loads(mod.output["output-data"])
    assert isinstance(parsed, dict)


def test_reader_output_data_is_valid_json():
    mod = _make_reader()
    client = _mock_client()
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_reader.persist_tokens"):
        mod.compute()
    parsed = json.loads(mod.output["output-data"])
    assert "value" in parsed


def test_reader_duration_non_negative_on_success():
    mod = _make_reader()
    client = _mock_client()
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_reader.persist_tokens"):
        mod.compute()
    assert mod.output["duration"] >= 0.0


def test_reader_init_runs_only_once():
    mod = _make_reader()
    client = _mock_client()
    mock_get = MagicMock(return_value=(MagicMock(), client))
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", mock_get), \
         patch("fmlc.modules.box.csv_reader.persist_tokens"):
        mod.compute()
        mod.compute()
    assert mock_get.call_count == 1


def test_reader_file_not_found_returns_error():
    mod = _make_reader()
    client = MagicMock()
    client.folders.get_folder_items.return_value.entries = []
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_reader.persist_tokens"):
        msg = mod.compute()
    assert "not found" in msg.lower()


def test_reader_do_step_interface():
    mod = BoxCsvReader()
    client = _mock_client()
    with patch("fmlc.modules.box.csv_reader.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_reader.persist_tokens"):
        msg = mod.do_step(inputs={
            "credentials-file": "creds.json",
            "token-file": "tokens.json",
            "folder-id": "123",
            "file-name": "data.csv",
        })
    assert msg == "Done."


# --- BoxCsvWriter structural tests ---

def test_writer_inputs_declared():
    mod = BoxCsvWriter()
    for key in ("input-data", "credentials-file", "token-file", "folder-id",
                "file-name", "delete-old-versions", "append-to-existing"):
        assert key in mod.input


def test_writer_outputs_declared():
    mod = BoxCsvWriter()
    assert "duration" in mod.output


def test_writer_missing_input_data_returns_waiting():
    mod = _make_writer(input_data=None)
    msg = mod.compute()
    assert "Waiting" in msg


def test_writer_all_outputs_assigned_on_missing_data():
    mod = _make_writer(input_data=None)
    mod.compute()
    assert "duration" in mod.output


def test_writer_duration_non_negative_on_missing_data():
    mod = _make_writer(input_data=None)
    mod.compute()
    assert mod.output["duration"] >= 0.0


def test_writer_all_outputs_assigned_on_error():
    mod = _make_writer()
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", side_effect=RuntimeError("fail")):
        mod.compute()
    assert "duration" in mod.output


def test_writer_returns_error_string_on_failure():
    mod = _make_writer()
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", side_effect=RuntimeError("auth error")):
        msg = mod.compute()
    assert "auth error" in msg


def test_writer_compute_success():
    mod = _make_writer()
    client = _mock_client()
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_writer.persist_tokens"):
        msg = mod.compute()
    assert msg == "Done."


def test_writer_duration_non_negative_on_success():
    mod = _make_writer()
    client = _mock_client()
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_writer.persist_tokens"):
        mod.compute()
    assert mod.output["duration"] >= 0.0


def test_writer_init_runs_only_once():
    mod = _make_writer()
    client = _mock_client()
    mock_get = MagicMock(return_value=(MagicMock(), client))
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", mock_get), \
         patch("fmlc.modules.box.csv_writer.persist_tokens"):
        mod.compute()
        mod.compute()
    assert mock_get.call_count == 1


def test_writer_append_downloads_existing_file():
    mod = _make_writer(append=True)
    client = _mock_client()
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_writer.persist_tokens"):
        mod.compute()
    client.downloads.download_file.assert_called_once()


def test_writer_no_append_does_not_download():
    mod = _make_writer(append=False)
    client = _mock_client()
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_writer.persist_tokens"):
        mod.compute()
    client.downloads.download_file.assert_not_called()


def test_writer_delete_old_versions_calls_delete():
    mod = _make_writer(delete_old=True)
    client = _mock_client()
    version = MagicMock()
    version.id = "v1"
    client.file_versions.get_file_versions.return_value.entries = [version]
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_writer.persist_tokens"):
        mod.compute()
    client.file_versions.delete_file_version_by_id.assert_called_once()


def test_writer_no_delete_versions_skips_delete():
    mod = _make_writer(delete_old=False)
    client = _mock_client()
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_writer.persist_tokens"):
        mod.compute()
    client.file_versions.delete_file_version_by_id.assert_not_called()


def test_writer_do_step_interface():
    mod = BoxCsvWriter()
    client = _mock_client()
    with patch("fmlc.modules.box.csv_writer.get_oauth_client", return_value=(MagicMock(), client)), \
         patch("fmlc.modules.box.csv_writer.persist_tokens"):
        msg = mod.do_step(inputs={
            "input-data": _JSON_DATA,
            "credentials-file": "creds.json",
            "token-file": "tokens.json",
            "folder-id": "123",
            "file-name": "data.csv",
            "delete-old-versions": False,
            "append-to-existing": False,
        })
    assert msg == "Done."


# --- oauth_utils unit tests ---

def test_load_save_json_roundtrip():
    payload = {"access_token": "abc", "refresh_token": "xyz"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        tmp_path = f.name
    save_json(tmp_path, payload)
    loaded = load_json(tmp_path)
    assert loaded["access_token"] == "abc"
    assert loaded["refresh_token"] == "xyz"


def test_create_token_payload_from_response():
    mock_response = MagicMock()
    mock_response.access_token = "tok_access"
    mock_response.refresh_token = "tok_refresh"
    mock_response.token_type = "bearer"
    mock_response.expires_in = 3600
    mock_response.restricted_to = None
    payload = create_token_payload(token_response=mock_response)
    assert payload["access_token"] == "tok_access"
    assert payload["refresh_token"] == "tok_refresh"


def test_create_token_payload_empty_when_no_args():
    payload = create_token_payload()
    assert isinstance(payload, dict)


def test_persist_tokens_no_op_when_no_path():
    persist_tokens(MagicMock(), None)


def test_persist_tokens_writes_file():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    with patch(
        "fmlc.modules.box.oauth_utils.create_token_payload",
        return_value={"access_token": "tok"},
    ):
        persist_tokens(MagicMock(), tmp_path)
    loaded = load_json(tmp_path)
    assert loaded["access_token"] == "tok"
