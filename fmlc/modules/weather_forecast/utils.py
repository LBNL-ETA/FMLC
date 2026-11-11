# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
WeatherForecast eFMU module.
"""

# pylint: disable=broad-except

import re

import pandas as pd

_DATETIME_MASK = r'20[0-9][0-9]-[0-1][0-9]-[0-3][0-9] [0-2][0-9]:[0-5][0-9]:[0-5][0-9]'

# Maps raw HRRR GRIB2 field names to pvlib column names expected by HRRR.process_data.
# String values are column renames; integer values are constant fill defaults.
FC_TO_PVLIB_MAP = {
    'Total Cloud Cover:% (instant):lambert:atmosphere:level 0 -': 'total_clouds',
    '2 metre temperature:K (instant):lambert:heightAboveGround:level 2 m':
        'Temperature_height_above_ground',
    'Low cloud cover:% (instant):lambert:lowCloudLayer:level 0': 'low_clouds',
    'Medium cloud cover:% (instant):lambert:middleCloudLayer:level 0': 'mid_clouds',
    'High cloud cover:% (instant):lambert:highCloudLayer:level 0': 'high_clouds',
    '10 metre U wind component:m s**-1 (instant):lambert:heightAboveGround:level 10 m':
        'wind_speed_u',
    '10 metre V wind component:m s**-1 (instant):lambert:heightAboveGround:level 10 m':
        'wind_speed_v',
    'Pressure_surface': 0,
}


def check_forecast(forecast, config, start_time, final_time):
    """Validate forecast index format, numeric values, and time alignment.

    Returns (forecast, msg) where msg is an empty string on success.
    """
    msg = ''

    for i, ix in enumerate(forecast.index):
        if not bool(re.match(_DATETIME_MASK, str(ix))):
            msg += f'ERROR: External forecast date format incorrect "{ix}" at position {i}.\n'

    forecast = forecast.copy()
    for c in forecast.columns:
        forecast[c] = pd.to_numeric(forecast[c], errors='coerce')
    if forecast.isnull().values.any():
        msg += (
            f'ERROR: NaNs in forecast at: '
            f'{forecast.index[forecast.isnull().any(axis=1)]}.\n'
        )

    if msg == '':
        forecast.index = pd.to_datetime(forecast.index, format='%Y-%m-%d %H:%M:%S')
        if not (len(forecast) - 1) == config['horizon']:
            msg += (
                f'ERROR: Forecast length {len(forecast)-1} '
                f'is not horizon {config["horizon"]}.\n'
            )
        if not forecast.index[0] == start_time.tz_localize(None):
            msg += (
                f'ERROR: Forecast start "{forecast.index[0]}" '
                f'not start_time "{start_time.tz_localize(None)}".\n'
            )
        if not forecast.index[-1] == final_time.tz_localize(None):
            msg += (
                f'ERROR: Forecast final "{forecast.index[-1]}" '
                f'not final_time "{final_time.tz_localize(None)}".\n'
            )
        if forecast.resample('1h').asfreq().isnull().values.any():
            msg += 'ERROR: Missing timestamp in forecast.\n'

    return forecast, msg


def compute_solar_position(location, data, tz):
    """Compute solar position and clear-sky irradiance for a given location and time index.

    Returns a dict of column name -> numpy array.
    """
    times = data.index.tz_localize(tz)
    solpos = location.get_solarposition(times)
    airmass = location.get_airmass(times)
    clearsky = location.get_clearsky(times, model='ineichen', solar_position=solpos)
    return {
        'alt': solpos['apparent_elevation'].values,
        'azi': solpos['azimuth'].values,
        'zenith': solpos['apparent_zenith'].values,
        'airmass': airmass['airmass_relative'].mask(
            solpos['apparent_elevation'] < 1, 0.0
        ).values,
        'ghi_cs': clearsky['ghi'].values,
        'dhi_cs': clearsky['dhi'].values,
    }


def process_forecast(forecast, config, tz, processor):
    """Process a raw HRRR forecast DataFrame through the pvlib pipeline.

    Returns a DataFrame with output columns from config['output_cols'], plus
    optional solar-position columns if config['add_solpos'] is True.
    """
    # map raw grib field names to pvlib variable names
    direct = {
        k: v for k, v in FC_TO_PVLIB_MAP.items()
        if isinstance(v, str) and k in forecast.columns
    }
    pvlib_fc = forecast[list(direct.keys())].copy(deep=True).rename(columns=direct)

    # fill scalar-valued fields with their default constant
    computed = {k: v for k, v in FC_TO_PVLIB_MAP.items() if not isinstance(v, str)}
    for k, v in computed.items():
        pvlib_fc[k] = v
    pvlib_fc.index = pvlib_fc.index.tz_localize(tz)

    # duplicate last row (pvlib bug workaround)
    pvlib_fc.loc[pvlib_fc.index[-1] + pd.DateOffset(hours=1), :] = pvlib_fc.iloc[-1]
    data = processor.process_data(pvlib_fc)
    data = data.loc[pvlib_fc.index[:-1]]
    data.index = data.index.tz_localize(None)
    data = data[list(config['output_cols'].keys())]

    if config['add_solpos']:
        solpos_cols = compute_solar_position(processor.location, data, tz)
        for col, values in solpos_cols.items():
            data[col] = values

    return data


def get_default_config():
    """Return a default configuration dict for WeatherForecaster."""
    config = {}
    config['lat'] = 37.8715
    config['lon'] = -122.2501
    config['alt'] = 50
    config['tz'] = 'US/Pacific'
    config['horizon'] = 16
    config['tmp_dir'] = 'tmp'
    config['debug'] = False
    config['source'] = 'noaa_hrrr'
    config['refresh_time'] = 15 * 60
    config['update_st_refresh'] = False
    config['json_return'] = True
    config['add_solpos'] = True
    config['forecast_cols'] = {}
    config['output_cols'] = {
        'temp_air': [-50, 50],
        'ghi': [0, 1000],
        'dni': [0, 1500],
        'dhi': [0, 1000],
        'low_clouds': [0, 100],
        'mid_clouds': [0, 100],
        'high_clouds': [0, 100],
        'total_clouds': [0, 100],
        'wind_speed': [0, 150],
    }
    return config
