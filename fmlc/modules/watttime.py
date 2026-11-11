# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
WatttimeForecast eFMU module.
"""

# pylint: disable=broad-except,too-many-arguments,too-many-positional-arguments

import json
import os
import time
import traceback

import requests
from requests.auth import HTTPBasicAuth

from fmlc.baseclasses import eFMU

TIMEOUT = 5 # seconds

URLS = {
    "register_url": "https://api2.watttime.org/v2/register",
    "login_url": "https://api2.watttime.org/v2/login",
    "password_url": "https://api2.watttime.org/v2/password",
    "region_url": "https://api2.watttime.org/v2/ba-from-loc",
    "list_url": "https://api2.watttime.org/v2/ba-access",
    "index_url": "https://api2.watttime.org/index",
    "data_url": "https://api2.watttime.org/v2/data",
    "historical_url": "https://api2.watttime.org/v2/historical",
    "forecast_url": "https://api2.watttime.org/v2/forecast",
}


def check_response(response):
    """Return the response if successful (HTTP 200), else write error HTML and return None."""
    if response.status_code == 200:
        return response
    print(f"Error: {response.status_code}")
    with open("response_error.html", "w", encoding="utf8") as f:
        f.write(response.text)
    return None


class WatttimeClient:
    """Low-level client for the WattTime emission forecasting API."""

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
        """Register a new WattTime account."""
        params = {
            "username": self.username,
            "password": self.password,
            "email": self.email,
            "org": self.org,
        }
        response = requests.post(URLS["register_url"], json=params, timeout=TIMEOUT)
        if check_response(response):
            print(response.text)
        else:
            raise ValueError(
                "Registration was not successful. Check the response_error.html file."
            )

    def login(self):
        """Authenticate and store the bearer token."""
        response = requests.get(
            URLS["login_url"],
            auth=HTTPBasicAuth(self.username, self.password),
            timeout=TIMEOUT,
        )
        if check_response(response):
            self.token = response.json()["token"]

    def get_regions(self, all_regions=False):
        """Return a list of accessible balancing authority regions."""
        if not self.token:
            self.login()
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"all": str(all_regions)}
        response = requests.get(
            URLS["list_url"], headers=headers, params=params, timeout=TIMEOUT
        )
        if check_response(response):
            return json.loads(response.text)
        return None

    def get_emission_historic(self, ba="CAISO_NORTH",
                              cur_dir=os.path.dirname(os.path.realpath("__file__"))):
        """Download historical emissions zip for the given balancing authority."""
        if not self.token:
            self.login()
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"ba": str(ba)}
        response = requests.get(
            URLS["historical_url"], headers=headers, params=params, timeout=TIMEOUT
        )
        if check_response(response):
            file_path = os.path.join(cur_dir, f"{ba}_historical.zip")
            with open(file_path, "wb") as f:
                f.write(response.content)

    def get_emission_forecast(self, ba="CAISO_NORTH", extended_forecast=False):
        """Return the emission forecast dict for the given balancing authority."""
        if not self.token:
            self.login()
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"ba": str(ba), "extended_forecast": str(extended_forecast)}
        response = requests.get(
            URLS["forecast_url"], headers=headers, params=params, timeout=TIMEOUT
        )
        if check_response(response):
            return json.loads(response.text)
        return None


class WatttimeForecast(eFMU):
    """Fetch WattTime emission forecast data on each compute cycle."""

    def __init__(self):
        super().__init__()
        self.input = {
            "username": None,
            "password": None,
            "email": None,
            "org": None,
            "registered": None,
            "ba": None,
            "extended-forecast": None,
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
                kwargs = {
                    "username": self.input["username"],
                    "password": self.input["password"],
                    "registered": registered,
                }
                if self.input["email"] is not None:
                    kwargs["email"] = self.input["email"]
                if self.input["org"] is not None:
                    kwargs["org"] = self.input["org"]
                self._client = WatttimeClient(**kwargs)
                self.init = True

            if not msg:
                ba = self.input["ba"] if self.input["ba"] is not None else "CAISO_NORTH"
                extended_forecast = bool(self.input["extended-forecast"])
                data = self._client.get_emission_forecast(
                    ba=ba, extended_forecast=extended_forecast
                )
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
