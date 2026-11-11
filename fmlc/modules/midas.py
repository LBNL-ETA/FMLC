# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
MidasForecast eFMU module.
"""

# pylint: disable=broad-except,too-many-arguments,too-many-positional-arguments

import base64
import json
import time
import traceback

import requests

from fmlc.baseclasses import eFMU

TIMEOUT = 5 # seconds

URLS = {
    "register_url": "https://midasapi.energy.ca.gov/api/registration",
    "login_url": "https://midasapi.energy.ca.gov/api/token",
    "rin_url": "https://midasapi.energy.ca.gov/api/valuedata?signaltype=",
    "value_url": "https://midasapi.energy.ca.gov/api/valuedata?id=",
}


def check_response(response):
    """Return the response if successful (HTTP 200), else write error HTML and return None."""
    if response.status_code == 200:
        return response
    print(f"Error: {response.status_code}")
    with open("response_error.html", "w", encoding="utf8") as f:
        f.write(response.text)
    return None


def _str_to_b64(s):
    """Encode a plain string as a base64 UTF-8 string."""
    encoded_bytes = base64.b64encode(s.encode("utf-8"))
    return str(encoded_bytes, "utf-8")


class MidasClient:
    """Low-level client for the MIDAS emission forecasting API."""

    def __init__(self, registered=True, username="freddo", password="the_frog!",
                 email="freddo@frog.org", org="freds world"):
        self.registered = registered
        self.username = username
        self.password = password
        self.email = email
        self.org = org
        self.token = None

        if not self.registered:
            self.register()

    def register(self):
        """Register a new MIDAS account."""
        registration_info = {
            "organization": _str_to_b64(self.org),
            "username": _str_to_b64(self.username),
            "password": _str_to_b64(self.password),
            "emailaddress": _str_to_b64(self.email),
            "fullname": _str_to_b64(self.username),
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            URLS["register_url"],
            data=json.dumps(registration_info),
            headers=headers,
            timeout=TIMEOUT,
        )
        if check_response(response):
            print(response.text)
        else:
            raise ValueError(
                "Registration was not successful. Check the response_error.html file."
            )

    def login(self):
        """Authenticate and store the bearer token."""
        credentials = f"{self.username}:{self.password}"
        encoded_bytes = base64.b64encode(credentials.encode("utf-8"))
        headers = {b"Authorization": b"BASIC " + encoded_bytes}
        response = requests.get(URLS["login_url"], headers=headers, timeout=TIMEOUT)
        if check_response(response):
            self.token = response.headers["Token"]

    def get_rins(self, signal_type=0):
        """Return all Rate Identification Numbers (RINs) for the given signal type.

        signal_type: 0=all, 1=Tariffs, 2=GHG, 3=Flex Alerts.
        """
        if not self.token:
            self.login()
        headers = {"accept": "application/json", "Authorization": f"Bearer {self.token}"}
        url = f"{URLS['rin_url']}{signal_type}"
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        if check_response(response):
            return json.loads(response.text)
        return None

    def get_values(self, rate_id="USCA-FLEX-FXFC-0000", query_type="alldata"):
        """Return value data for a Rate Identification Number (RIN).

        rate_id: The rate ID; see get_rins().
        query_type: 'alldata' or 'realtime'.
        """
        if not self.token:
            self.login()
        headers = {"accept": "application/json", "Authorization": f"Bearer {self.token}"}
        url = f"{URLS['value_url']}{rate_id}&querytype={query_type}"
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        if check_response(response):
            return json.loads(response.text)
        return None


class MidasForecast(eFMU):
    """Fetch MIDAS emission or flex-alert values for a RIN on each compute cycle."""

    def __init__(self):
        super().__init__()
        self.input = {
            "username": None,
            "password": None,
            "email": None,
            "org": None,
            "registered": None,
            "rate-id": None,
            "query-type": None,
            "debug": None,
        }
        self.output = {
            "output-data": None,
            "duration": None,
        }
        self.init = False
        self._client = None

    def compute(self):
        st = time.time()
        msg = ""
        out_data = None

        msg += self.check_data(self.input["username"], True)
        msg += self.check_data(self.input["password"], True)

        try:
            if not msg and not self.init:
                registered = self.input["registered"]
                registered = True if registered is None else bool(registered)
                email = self.input["email"] or "freddo@frog.org"
                org = self.input["org"] or "freds world"
                self._client = MidasClient(
                    username=self.input["username"],
                    password=self.input["password"],
                    email=email,
                    org=org,
                    registered=registered,
                )
                self.init = True

            if not msg:
                rate_id = self.input["rate-id"] or "USCA-FLEX-FXFC-0000"
                query_type = self.input["query-type"] or "alldata"
                data = self._client.get_values(rate_id=rate_id, query_type=query_type)
                out_data = json.dumps(data)

        except Exception as e:
            msg += str(e)
            if self.input["debug"]:
                msg += f"\n\n{traceback.format_exc()}"

        self.output["output-data"] = out_data
        self.output["duration"] = time.time() - st

        if not msg:
            return "Done."
        return msg
