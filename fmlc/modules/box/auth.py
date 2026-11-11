# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Box OAuth bootstrap utility.
"""

# pylint: disable=broad-except

from box_sdk_gen import GetAuthorizeUrlOptions

from .oauth_utils import build_auth, create_token_payload, load_json, save_json


def box_auth(credentials_file, token_file):
    """Run the Box OAuth authorisation flow and persist tokens to token_file.

    Reads clientID, clientSecret, and optionally authCode from credentials_file.
    If authCode is absent the user is prompted to visit the authorisation URL.
    """
    auth = build_auth(credentials_file)

    creds = load_json(credentials_file)
    auth_code = creds["authCode"] if "authCode" in creds else ""

    if not auth_code:
        url = auth.get_authorize_url(options=GetAuthorizeUrlOptions())
        print("Open this URL in your browser and log in:")
        print(url)
        print(
            "\nThen copy the returned code value and either:\n"
            "1) paste it into credentials_file as authCode, or\n"
            "2) enter it when prompted."
        )
        entered = input("\nEnter authCode now (leave blank to exit): ").strip()
        if not entered:
            print("No authCode provided. Exiting.")
            return None
        auth_code = entered

    token_response = auth.get_tokens_authorization_code_grant(auth_code)
    token_payload = create_token_payload(token_response=token_response, auth=auth)

    if not token_payload.get("access_token"):
        raise RuntimeError(
            "Could not retrieve access token from Box OAuth response. "
            "Check app configuration and redirect URL."
        )

    save_json(token_file, token_payload)
    print(f"Saved token payload to: {token_file}")
    return token_payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap Box OAuth tokens.")
    parser.add_argument("credentials_file", help="Path to credentials JSON file.")
    parser.add_argument("token_file", help="Path where token JSON will be saved.")
    args = parser.parse_args()
    box_auth(args.credentials_file, args.token_file)
