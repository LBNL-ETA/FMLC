# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
DeviationWatchdog eFMU module.
"""

# pylint: disable=broad-except,too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements,too-many-nested-blocks

import datetime
import json
import os
import smtplib
import time
import traceback
import warnings
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import pandas as pd

from fmlc.baseclasses import eFMU


def _write_log(log_file, entry):
    """Append a single alert dict to the JSON log file."""
    if not log_file:
        return
    existing = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        except Exception:
            existing = []
    existing.append(entry)
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2, default=str)


def _send_email(email_cfg, subject, body, cooldown_key, last_email_time, cooldown_s):
    """Send an alert email, honouring per-channel cooldown; mutates last_email_time."""
    now = time.time()
    last = last_email_time[cooldown_key] if cooldown_key in last_email_time else 0
    if now - last < cooldown_s:
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = email_cfg["from_addr"]
        msg["To"] = ", ".join(email_cfg["to_addrs"])
        prefix = email_cfg["subject_prefix"] if "subject_prefix" in email_cfg else "[WatchdogAlert]"
        msg["Subject"] = f"{prefix} {subject}"
        msg.attach(MIMEText(body, "plain"))
        port = int(email_cfg["smtp_port"] if "smtp_port" in email_cfg else 587)
        with smtplib.SMTP(email_cfg["smtp_host"], port) as server:
            server.starttls()
            smtp_user = email_cfg["smtp_user"] if "smtp_user" in email_cfg else None
            if smtp_user:
                server.login(smtp_user, email_cfg["smtp_password"])
            server.sendmail(email_cfg["from_addr"], email_cfg["to_addrs"], msg.as_string())
        last_email_time[cooldown_key] = now
    except Exception as e:
        warnings.warn(f"DeviationWatchdog: email failed for {cooldown_key}: {e}")


class DeviationWatchdog(eFMU):
    """Compare measurements to lagged predictions and fire alerts on threshold breach.

    Config CSV columns: measured_name, predicted_name, threshold, notification_level,
    time_lag_s, enabled. notification_level options: 'warning', 'log', 'email'.
    Email config keys: smtp_host, smtp_port, smtp_user, smtp_password, from_addr,
    to_addrs (list), subject_prefix (optional).
    """

    def __init__(self):
        super().__init__()
        self.input = {
            "input-data": None,
            "config-file": None,
            "log-file": None,
            "email-config": None,
            "email-cooldown": None,
            "timezone": None,
            "debug": None,
        }
        self.output = {
            "output-data": None,
            "alerts": None,
            "duration": None,
        }
        self.init = False
        self._config = None
        self._prediction_history = None
        self._last_email_time = {}

    def _load_config(self):
        """Load and normalise the watchdog CSV config."""
        f = self.input["config-file"]
        if not f:
            return pd.DataFrame(
                columns=["measured_name", "predicted_name", "threshold",
                         "notification_level", "time_lag_s", "enabled"]
            )
        df = pd.read_csv(f)
        df.columns = [c.strip() for c in df.columns]
        df["measured_name"] = df["measured_name"].str.strip()
        df["predicted_name"] = df["predicted_name"].str.strip()
        df["threshold"] = df["threshold"].astype(float)
        df["notification_level"] = df["notification_level"].str.strip().str.lower()
        df["time_lag_s"] = df["time_lag_s"].astype(float)
        df["enabled"] = df["enabled"].astype(int)
        return df

    def compute(self):
        st = time.time()
        msg = ""
        out_data = None
        alerts = []

        msg += self.check_data(self.input["input-data"], True)

        try:
            if not msg:
                data = json.loads(self.input["input-data"])

                if not self.init:
                    self._config = self._load_config()
                    self.init = True

                cooldown_s = float(self.input["email-cooldown"] or 300)
                email_cfg = None
                email_raw = self.input["email-config"]
                if email_raw:
                    email_cfg = json.loads(email_raw) if isinstance(email_raw, str) else email_raw
                log_file = self.input["log-file"]

                current_ts = float(self.input["time"])
                tz_name = self.input["timezone"]
                if tz_name:
                    ts = datetime.datetime.fromtimestamp(
                        current_ts, tz=ZoneInfo(tz_name)
                    ).strftime("%Y-%m-%dT%H:%M:%S")
                else:
                    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(current_ts))

                deviations = {}

                if self._prediction_history is not None:
                    for _, row in self._config[self._config["enabled"] == 1].iterrows():
                        mname = row["measured_name"]
                        pname = row["predicted_name"]
                        threshold = float(row["threshold"])
                        level = row["notification_level"]
                        time_lag_s = float(row["time_lag_s"])

                        measured = data[mname] if mname in data else None
                        target_ts = current_ts - time_lag_s
                        idx = (self._prediction_history["unix_ts"] - target_ts).abs().idxmin()
                        col_exists = pname in self._prediction_history.columns
                        predicted = self._prediction_history.at[idx, pname] if col_exists else None

                        if measured is None or predicted is None or pd.isna(predicted):
                            deviations[mname] = {
                                "measured": measured,
                                "predicted": None,
                                "deviation": None,
                                "threshold": threshold,
                                "exceeded": False,
                            }
                            continue

                        deviation = abs(float(measured) - float(predicted))
                        exceeded = deviation > threshold
                        deviations[mname] = {
                            "measured": float(measured),
                            "predicted": float(predicted),
                            "deviation": deviation,
                            "threshold": threshold,
                            "exceeded": exceeded,
                        }

                        if exceeded:
                            alert_entry = {
                                "timestamp": ts,
                                "channel": mname,
                                "measured": float(measured),
                                "predicted": float(predicted),
                                "deviation": deviation,
                                "threshold": threshold,
                                "level": level,
                            }
                            alerts.append(alert_entry)

                            alert_msg = (
                                f"DeviationWatchdog [{ts}]: {mname} deviation "
                                f"{deviation:.3f} exceeds threshold {threshold} "
                                f"(measured={float(measured):.3f}, "
                                f"predicted={float(predicted):.3f}, lag={time_lag_s:.0f}s)"
                            )

                            if level == "warning":
                                warnings.warn(alert_msg)
                            elif level == "log":
                                _write_log(log_file, alert_entry)
                            elif level == "email" and email_cfg:
                                body = (
                                    f"Timestamp: {ts}\n"
                                    f"Measured channel: {mname}\n"
                                    f"Predicted channel: {pname}\n"
                                    f"Time lag: {time_lag_s:.0f} s\n"
                                    f"Measured value: {float(measured):.3f}\n"
                                    f"Predicted ({time_lag_s:.0f}s ago): {float(predicted):.3f}\n"
                                    f"Absolute deviation: {deviation:.3f}\n"
                                    f"Threshold: {threshold}\n"
                                )
                                _send_email(
                                    email_cfg, f"{mname} deviation alert",
                                    body, mname, self._last_email_time, cooldown_s,
                                )
                            elif level == "email" and not email_cfg:
                                warnings.warn(
                                    f"DeviationWatchdog: level=email but no email-config "
                                    f"provided for channel {mname}."
                                )

                current_preds = {"unix_ts": current_ts}
                for _, row in self._config.iterrows():
                    pname = row["predicted_name"]
                    current_preds[pname] = data[pname] if pname in data else None
                new_row = pd.DataFrame([current_preds])
                if self._prediction_history is None:
                    self._prediction_history = new_row
                else:
                    self._prediction_history = pd.concat(
                        [self._prediction_history, new_row], ignore_index=True
                    )

                if len(self._config):
                    max_lag = float(self._config["time_lag_s"].max())
                    cutoff = current_ts - max_lag - 120
                    self._prediction_history = self._prediction_history[
                        self._prediction_history["unix_ts"] > cutoff
                    ].reset_index(drop=True)

                out_data = json.dumps({
                    "timestamp": ts,
                    "deviations": deviations,
                    "n_alerts": len(alerts),
                }, default=str)

        except Exception as e:
            msg += str(e)
            if self.input["debug"]:
                msg += f"\n\n{traceback.format_exc()}"

        self.output["output-data"] = out_data
        self.output["alerts"] = json.dumps(alerts)
        self.output["duration"] = time.time() - st

        if not msg:
            return "Done."
        return msg
