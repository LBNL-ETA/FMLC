# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Box OAuth utilities for token management and client creation.
"""

# pylint: disable=broad-except

import json

from box_sdk_gen import BoxClient, BoxOAuth, OAuthConfig
from box_sdk_gen.schemas.access_token import AccessToken


def load_json(path):
    """Load and return JSON from a file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, payload):
    """Serialise payload as JSON and write to a file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _safe_token_value(value):
    """Return a scalar token value, calling it first if callable."""
    if callable(value):
        try:
            value = value()
        except Exception:
            return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return None


def _extract_tokens(token_source):
    """Extract access and refresh token strings from a dict or object."""
    if token_source is None:
        return None, None

    if isinstance(token_source, dict):
        access = token_source["access_token"] if "access_token" in token_source else None
        refresh = token_source["refresh_token"] if "refresh_token" in token_source else None
        return _safe_token_value(access), _safe_token_value(refresh)

    access_token = _safe_token_value(getattr(token_source, "access_token", None))
    refresh_token = _safe_token_value(getattr(token_source, "refresh_token", None))
    return access_token, refresh_token


def build_auth(credentials_file):
    """Create a BoxOAuth instance from a credentials JSON file."""
    creds = load_json(credentials_file)
    return BoxOAuth(
        config=OAuthConfig(
            client_id=creds["clientID"],
            client_secret=creds["clientSecret"],
        )
    )


def create_token_payload(token_response=None, auth=None):
    """Build a serialisable token payload dict from a token response or auth object."""
    token_payload = {}

    if token_response is not None:
        for key in [
            "access_token",
            "refresh_token",
            "token_type",
            "expires_in",
            "restricted_to",
        ]:
            value = _safe_token_value(getattr(token_response, key, None))
            if value is not None:
                token_payload[key] = value

        extracted_access, extracted_refresh = _extract_tokens(token_response)
        if extracted_access:
            token_payload["access_token"] = extracted_access
        if extracted_refresh:
            token_payload["refresh_token"] = extracted_refresh

    if auth is not None:
        auth_access = _safe_token_value(getattr(auth, "access_token", None))
        auth_refresh = _safe_token_value(getattr(auth, "refresh_token", None))
        if auth_access:
            token_payload["access_token"] = auth_access
        if auth_refresh:
            token_payload["refresh_token"] = auth_refresh

    return token_payload


def get_oauth_client(credentials_file, token_file):
    """Return an initialised (auth, BoxClient) pair using stored tokens."""
    auth = build_auth(credentials_file)
    tokens = load_json(token_file)

    access_token = tokens["access_token"] if "access_token" in tokens else None
    refresh_token = tokens["refresh_token"] if "refresh_token" in tokens else None
    token_type = tokens["token_type"] if "token_type" in tokens else None
    expires_in = tokens["expires_in"] if "expires_in" in tokens else None
    restricted_to = tokens["restricted_to"] if "restricted_to" in tokens else None

    if not access_token:
        raise RuntimeError(
            "Token file does not contain access_token. Run box_auth first."
        )

    token_obj = AccessToken(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=token_type,
        expires_in=expires_in,
        restricted_to=restricted_to,
    )
    auth.token_storage.store(token_obj)

    client = BoxClient(auth=auth)
    return auth, client


def get_file_id(client, filename, folder_id):
    """Return the Box file ID for filename inside folder_id."""
    items = client.folders.get_folder_items(folder_id)
    for item in items.entries:
        if item.name == filename:
            return item.id
    raise FileNotFoundError(
        f"File '{filename}' not found in folder '{folder_id}'."
    )


def persist_tokens(auth, token_file):
    """Write the current auth tokens to token_file if a path is given."""
    if not token_file:
        return
    token_data = create_token_payload(auth=auth)
    if token_data:
        save_json(token_file, token_data)
