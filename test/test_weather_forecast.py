# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Tests for the WeatherForecaster eFMU module.
"""

# pylint: disable=broad-except

import io
import sys
import warnings
from os import path

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore', message='The forecast module algorithms and features are highly experimental.')
warnings.filterwarnings('ignore', message='The HRRR class was deprecated in pvlib 0.9.1 and will be removed in a future release.')
warnings.filterwarnings('ignore', category=DeprecationWarning, module='pvlib')
try:
    from pvlib._deprecation import pvlibDeprecationWarning
    warnings.filterwarnings('ignore', category=pvlibDeprecationWarning)
except Exception:
    pass

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.modules.weather_forecast.forecast import WeatherForecaster
from fmlc.modules.weather_forecast.utils import (
    check_forecast,
    compute_solar_position,
    get_default_config,
)
from fmlc.modules.weather_forecast.resources.pvlib.forecast import HRRR
from pvlib.location import Location

LAT = 37.8715
LON = -122.2501
ALT = 50
TZ = 'US/Pacific'
TS_MIDDAY = 1718985600  # 2024-06-21 18:00 UTC = 11:00 PDT


def _make_config(**overrides):
    """Return a default config dict with optional overrides applied."""
    cfg = get_default_config()
    cfg.update(overrides)
    return cfg


def _hourly_start(ts=TS_MIDDAY):
    """Return a tz-naive local Timestamp floored to the hour."""
    aware = (
        pd.to_datetime(ts, unit='s')
        .tz_localize('UTC')
        .tz_convert(TZ)
        .replace(second=0, microsecond=0, nanosecond=0, minute=0)
    )
    return pd.to_datetime(aware.tz_localize(None))


def _make_hourly_forecast(config, start_time):
    """Build a minimal valid forecast DataFrame matching config's horizon."""
    horizon = config['horizon']
    index = pd.date_range(start=start_time, periods=horizon + 1, freq='1h')
    cols = {
        'temp_air': 20.0,
        'ghi': 300.0,
        'dni': 400.0,
        'dhi': 100.0,
        'low_clouds': 10.0,
        'mid_clouds': 10.0,
        'high_clouds': 10.0,
        'total_clouds': 10.0,
        'wind_speed': 5.0,
    }
    return pd.DataFrame({k: np.full(horizon + 1, v) for k, v in cols.items()}, index=index)


# WeatherForecaster structural tests

def test_inputs_declared():
    mod = WeatherForecaster()
    for key in ('input-data', 'config', 'timeout'):
        assert key in mod.input


def test_outputs_declared():
    mod = WeatherForecaster()
    for key in ('output-data', 'duration'):
        assert key in mod.output


def test_invalid_source_returns_error():
    config = _make_config(source='unsupported_source')
    mod = WeatherForecaster()
    mod.input['config'] = config
    mod.input['time'] = TS_MIDDAY
    msg = mod.compute()
    assert 'ERROR' in msg
    assert 'not valid' in msg


def test_duration_always_set():
    config = _make_config(source='unsupported_source')
    mod = WeatherForecaster()
    mod.input['config'] = config
    mod.input['time'] = TS_MIDDAY
    mod.compute()
    assert mod.output['duration'] is not None
    assert mod.output['duration'] >= 0.0


# JSON source tests

def _make_json_forecaster(start_ts=TS_MIDDAY, json_return=True, add_solpos=False,
                          output_cols=None, horizon=4):
    """Return a WeatherForecaster wired to use the 'json' source."""
    config = _make_config(
        source='json',
        horizon=horizon,
        json_return=json_return,
        add_solpos=add_solpos,
        output_cols=output_cols or {},
    )
    forecast_df = _make_hourly_forecast(config, _hourly_start(start_ts))
    mod = WeatherForecaster()
    mod.input['config'] = config
    mod.input['time'] = start_ts
    mod.input['input-data'] = forecast_df.to_json()
    return mod


def test_json_source_success():
    mod = _make_json_forecaster()
    msg = mod.compute()
    assert msg == 'Done.', msg


def test_json_source_output_data_is_json():
    mod = _make_json_forecaster()
    mod.compute()
    out = mod.output['output-data']
    assert isinstance(out, str)
    df = pd.read_json(io.StringIO(out))
    assert not df.empty


def test_json_source_output_data_is_dataframe_when_json_return_false():
    mod = _make_json_forecaster(json_return=False)
    mod.compute()
    out = mod.output['output-data']
    assert isinstance(out, pd.DataFrame)
    assert not out.empty


def test_json_source_missing_input_data_raises():
    config = _make_config(source='json', horizon=4, output_cols={})
    mod = WeatherForecaster()
    mod.input['config'] = config
    mod.input['time'] = TS_MIDDAY
    mod.input['input-data'] = None
    msg = mod.compute()
    assert 'ERROR' in msg


def test_do_step_interface_json():
    config = _make_config(source='json', horizon=4, output_cols={})
    forecast_df = _make_hourly_forecast(config, _hourly_start())
    mod = WeatherForecaster()
    msg = mod.do_step(inputs={
        'input-data': forecast_df.to_json(),
        'config': config,
        'timeout': None,
        'time': TS_MIDDAY,
    })
    assert msg == 'Done.', msg



# Stored-forecast reuse test

def test_stored_forecast_reused_within_refresh_window():
    """Second compute within refresh_time should reuse the cached forecast."""
    config = _make_config(
        source='json', horizon=4, output_cols={}, refresh_time=900
    )
    forecast_df = _make_hourly_forecast(config, _hourly_start())

    mod = WeatherForecaster()
    mod.input['config'] = config
    mod.input['time'] = TS_MIDDAY
    mod.input['input-data'] = forecast_df.to_json()
    mod.compute()

    # 60 s later, still inside refresh window; poison input-data
    mod.input['time'] = TS_MIDDAY + 60
    mod.input['input-data'] = None
    msg = mod.compute()
    assert msg == 'Done.', msg


# get_default_config tests

def test_get_default_config_has_required_keys():
    cfg = get_default_config()
    for key in ('lat', 'lon', 'alt', 'tz', 'horizon', 'source',
                'refresh_time', 'json_return', 'add_solpos',
                'output_cols', 'forecast_cols'):
        assert key in cfg


def test_get_default_config_output_cols_ranges():
    cfg = get_default_config()
    for col, (lo, hi) in cfg['output_cols'].items():
        assert lo < hi, f"Range for {col} is inverted"


# check_forecast tests

def _make_check_forecast_input(horizon=4):
    """Build a minimal valid forecast for check_forecast."""
    config = _make_config(horizon=horizon, output_cols={})
    start_time = _hourly_start()
    final_time = start_time + pd.Timedelta(hours=horizon)
    df = _make_hourly_forecast(config, start_time)
    return df, config, start_time, final_time


def test_check_forecast_valid_input_returns_empty_msg():
    df, config, start_time, final_time = _make_check_forecast_input()
    _, msg = check_forecast(df, config, start_time, final_time)
    assert msg == ''


def test_check_forecast_wrong_length_returns_error():
    df, config, start_time, final_time = _make_check_forecast_input(horizon=4)
    df_short = df.iloc[:-2]
    _, msg = check_forecast(df_short, config, start_time, final_time)
    assert 'ERROR' in msg


def test_check_forecast_wrong_start_returns_error():
    df, config, start_time, final_time = _make_check_forecast_input(horizon=4)
    df_shifted = df.copy()
    df_shifted.index = df_shifted.index + pd.Timedelta(hours=1)
    _, msg = check_forecast(df_shifted, config, start_time, final_time)
    assert 'ERROR' in msg


# compute_solar_position tests

def test_compute_solar_position_returns_expected_keys():
    import pvlib
    location = pvlib.location.Location(LAT, LON, altitude=ALT, tz=TZ)
    index = pd.date_range(start=_hourly_start(), periods=4, freq='1h')
    df = pd.DataFrame({'dummy': np.zeros(4)}, index=index)
    result = compute_solar_position(location, df, TZ)
    for key in ('alt', 'azi', 'zenith', 'airmass', 'ghi_cs', 'dhi_cs'):
        assert key in result
        assert len(result[key]) == 4


def test_compute_solar_position_airmass_zero_at_night():
    import pvlib
    location = pvlib.location.Location(LAT, LON, altitude=ALT, tz=TZ)
    ts_night = 1718949600  # 2024-06-21 06:00 UTC = 2024-06-20 23:00 PDT
    start = _hourly_start(ts_night)
    index = pd.date_range(start=start, periods=1, freq='1h')
    df = pd.DataFrame({'dummy': np.zeros(1)}, index=index)
    result = compute_solar_position(location, df, TZ)
    assert result['airmass'][0] == 0.0


# HRRR pvlib processor tests

def _make_hrrr_processor():
    """Return a pvlib HRRR processor with location set to Berkeley."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        proc = HRRR()
    proc.location = Location(LAT, LON, altitude=ALT, tz=TZ)
    return proc


def _make_pvlib_fc(horizon=4):
    """Build a minimal pvlib-ready DataFrame for HRRR.process_data.

    Uses pvlib column names (after FC_TO_PVLIB_MAP rename) with a tz-aware index.
    """
    index = pd.date_range(
        start=_hourly_start(), periods=horizon + 1, freq='1h', tz=TZ
    )
    data = {
        'Temperature_height_above_ground': np.full(horizon + 1, 293.15),
        'wind_speed_u': np.full(horizon + 1, 3.0),
        'wind_speed_v': np.full(horizon + 1, 4.0),
        'total_clouds': np.full(horizon + 1, 20.0),
        'low_clouds': np.full(horizon + 1, 5.0),
        'mid_clouds': np.full(horizon + 1, 5.0),
        'high_clouds': np.full(horizon + 1, 5.0),
        'Pressure_surface': np.full(horizon + 1, 0),
    }
    return pd.DataFrame(data, index=index)


def test_hrrr_processor_location_set():
    proc = _make_hrrr_processor()
    assert proc.location is not None
    assert abs(proc.location.latitude - LAT) < 0.01


def test_hrrr_processor_process_data_returns_dataframe():
    proc = _make_hrrr_processor()
    fc = _make_pvlib_fc()
    result = proc.process_data(fc)
    assert isinstance(result, pd.DataFrame)
    assert not result.empty


def test_hrrr_processor_process_data_has_expected_columns():
    proc = _make_hrrr_processor()
    fc = _make_pvlib_fc()
    result = proc.process_data(fc)
    for col in ('temp_air', 'wind_speed', 'ghi', 'dni', 'dhi', 'total_clouds'):
        assert col in result.columns, f"Missing column: {col}"


def test_hrrr_processor_temp_in_celsius():
    """temp_air should be converted from Kelvin (293.15 K -> 20 C)."""
    proc = _make_hrrr_processor()
    fc = _make_pvlib_fc()
    result = proc.process_data(fc)
    assert abs(result['temp_air'].iloc[0] - 20.0) < 0.5


def test_hrrr_processor_wind_speed_computed():
    """wind_speed = sqrt(3^2 + 4^2) = 5.0 m/s."""
    proc = _make_hrrr_processor()
    fc = _make_pvlib_fc()
    result = proc.process_data(fc)
    assert abs(result['wind_speed'].iloc[0] - 5.0) < 0.1


def test_hrrr_processor_irradiance_non_negative():
    proc = _make_hrrr_processor()
    fc = _make_pvlib_fc()
    result = proc.process_data(fc)
    for col in ('ghi', 'dni', 'dhi'):
        assert (result[col] >= 0).all(), f"{col} has negative values"

