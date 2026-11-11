# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
WeatherForecaster eFMU module.
"""

# pylint: disable=broad-except,too-many-instance-attributes,too-many-locals,too-many-branches,too-many-statements

import io
import sys
import time
import traceback

import pandas as pd

from fmlc.baseclasses import eFMU
from fmlc.modules.weather_forecast.hrrr_download import get_noaa_hrrr_forecast
from fmlc.modules.weather_forecast.utils import check_forecast, process_forecast


class WeatherForecaster(eFMU):
    """Gather weather forecasts from NOAA HRRR or a JSON source on each compute cycle."""

    def __init__(self):
        super().__init__()
        self.input = {
            'input-data': None,
            'config': None,
            'timeout': None,
        }
        self.output = {
            'output-data': None,
            'duration': None,
        }
        self.init = True
        self.forecaster = None
        self.processor = None
        self.last_valid_forecast = None
        self.last_valid_forecast_time = None
        self.msg = ''
        self.forecast = pd.DataFrame()
        self.data = pd.DataFrame()

    def _check_ranges(self, data, ranges):
        """Append error messages for columns outside their expected [min, max] range."""
        for k, r in ranges.items():
            if k in data.columns:
                if data[k].min() < r[0]:
                    self.msg += (
                        f'ERROR: Entry "{k}" is out of range '
                        f'{data[k].min()} >= {r[0]}.\n'
                    )
                if data[k].max() > r[1]:
                    self.msg += (
                        f'ERROR: Entry "{k}" is out of range '
                        f'{data[k].max()} <= {r[1]}.\n'
                    )
            else:
                self.msg += f'ERROR: Entry "{k}" is missing.\n'

    def compute(self):
        """Retrieve and process the weather forecast; return 'Done.' or an error message."""
        self.msg = ''
        st = time.time()

        config = self.input['config']
        tz = config['tz']

        now = self.input.get('time', None)
        if now is None:
            now = time.time()

        now_ts = pd.to_datetime(now, unit='s')
        now_ts = (
            now_ts.tz_localize('UTC')
            .tz_convert(tz)
            .replace(second=0, microsecond=0, nanosecond=0)
        )
        now_ts_with_minutes = pd.to_datetime(now_ts)
        now_ts = now_ts.replace(minute=0)
        start_time = pd.to_datetime(now_ts)
        final_time = start_time + pd.Timedelta(hours=config['horizon'])

        refresh_time = config['refresh_time']
        hour_match = (
            self.last_valid_forecast is not None
            and now_ts.hour == self.last_valid_forecast.index[0].hour
            and now_ts.date() == self.last_valid_forecast.index[0].date()
        )
        use_stored = (
            refresh_time is not None
            and self.last_valid_forecast is not None
            and (now - self.last_valid_forecast_time) < refresh_time
            and hour_match
        )

        self.forecast = pd.DataFrame()
        try:
            if use_stored:
                self.forecast = self.last_valid_forecast.copy()
            elif config['source'] == 'noaa_hrrr':
                self.forecast, self.forecaster, self.processor = (
                    get_noaa_hrrr_forecast(
                        config, start_time, tz, self.forecaster, self.processor
                    )
                )
            elif config['source'] == 'json':
                self.forecast = pd.read_json(
                    io.StringIO(self.input['input-data'])
                ).sort_index()
            else:
                self.msg += f'ERROR: Source option "{config["source"]}" not valid.\n'

            self.forecast, fc_msg = check_forecast(
                self.forecast, config, start_time, final_time
            )
            self.msg += fc_msg

        except Exception as e:
            self.msg += f'ERROR: {e}\n\n{traceback.format_exc()}\n'
            self.forecast = pd.DataFrame()

        self.data = pd.DataFrame()
        if self.msg == '' and config['source'] == 'json':
            self.data = self.forecast.copy()
        elif self.msg == '' and config['source'] == 'noaa_hrrr':
            try:
                self._check_ranges(self.forecast, config['forecast_cols'])
                if self.msg == '':
                    forecast_for_pvlib = self.forecast
                    if config['update_st_refresh']:
                        minute_offset = (
                            now_ts_with_minutes.tz_localize(None)
                            - start_time.tz_localize(None)
                        )
                        if pd.Timedelta(0) < minute_offset < pd.Timedelta(hours=1):
                            forecast_for_pvlib = self.forecast.copy()
                            forecast_for_pvlib.index += minute_offset
                    self.data = process_forecast(
                        forecast_for_pvlib, config, tz, self.processor
                    )
            except Exception as e:
                self.msg += f'ERROR: {e}.\n\n{traceback.format_exc()}\n'
                self.data = pd.DataFrame()

        if self.msg == '' and config['output_cols']:
            self._check_ranges(self.data, config['output_cols'])

        if self.msg == '':
            if not use_stored:
                self.last_valid_forecast = self.forecast.copy()
                self.last_valid_forecast_time = now
        elif self.last_valid_forecast is not None:
            self.forecast = self.last_valid_forecast.copy()
            if config['source'] == 'noaa_hrrr' and self.processor is not None:
                self.data = process_forecast(
                    self.forecast, config, tz, self.processor
                )

        self.init = False
        if config['json_return']:
            self.output['output-data'] = self.data.to_json()
        else:
            self.output['output-data'] = self.data
        self.output['duration'] = time.time() - st

        if self.msg == '':
            return 'Done.'
        return self.msg


if __name__ == '__main__':
    from fmlc.modules.weather_forecast.utils import get_default_config

    _config = get_default_config()

    forecaster = WeatherForecaster()
    forecaster.input['config'] = _config
    forecaster.input['time'] = time.time()

    # for json source: pass a CSV file as first argument
    if len(sys.argv) == 2:
        forecaster.input['config']['source'] = 'json'
        forecaster.input['input-data'] = pd.read_csv(sys.argv[1], index_col=0).to_json()

    msg = forecaster.compute()
    res = pd.read_json(io.StringIO(forecaster.output['output-data']))

    if msg != 'Done.':
        print(msg)
    else:
        print(res.round(1))
