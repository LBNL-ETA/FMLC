# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
WeatherForecast eFMU module.
"""

# pylint: disable=broad-except,too-many-arguments,too-many-positional-arguments

import os
import time
import urllib.request
import warnings

import numpy as np
import pandas as pd
import requests

from pvlib.location import Location

try:
    import pygrib
    _PYGRIB_AVAILABLE = True
except ImportError:
    _PYGRIB_AVAILABLE = False

warnings.filterwarnings(
    'ignore',
    message='The forecast module algorithms and features are highly experimental.'
)
warnings.filterwarnings(
    'ignore',
    message='The HRRR class was deprecated in pvlib 0.9.1 and will be removed in a future release.'
)

try:
    from fmlc.modules.weather_forecast.resources.pvlib.forecast import HRRR
except Exception:
    HRRR = None


def download_latest_hrrr(lat, lon, dt, hour, tmp_dir='', debug=False, store_file=False):
    """Download a single HRRR GRIB2 file from the NOAA NOMADS API.

    Returns the file path (if store_file=True) or raw bytes, or None on failure.
    Documentation: https://nomads.ncep.noaa.gov/gribfilter.php?ds=hrrr_2d
    """
    url = 'https://nomads.ncep.noaa.gov/cgi-bin/filter_hrrr_2d.pl?dir=%2F'
    fname = f'hrrr.t{dt.strftime("%H")}z.wrfsfcf{hour:02}.grib2'
    url += f'hrrr.{dt.strftime("%Y%m%d")}%2Fconus&file={fname}'
    url += '&var_TMP=on&lev_2_m_above_ground=on'
    url += '&var_TCDC=on&var_HCDC=on&var_LCDC=on&var_MCDC=on&all_lev=on'
    url += '&var_UGRD=on&var_VGRD=on&lev_10_m_above_ground=on'
    url += (
        f'&subregion=&toplat={int(lat+1)}&leftlon={int(lon-1)}'
        f'&rightlon={int(lon+1)}&bottomlat={int(lat-1)}'
    )

    fname = os.path.join(tmp_dir, fname)
    try:
        if store_file:
            urllib.request.urlretrieve(url, fname)
        else:
            fname = requests.get(url, timeout=60).content
        return fname
    except Exception as e:
        if debug:
            print(url)
            print(e)
        return None


def get_nearest_data(lat, lon, fname):
    """Extract the grid point nearest to (lat, lon) from a HRRR GRIB2 file.

    Returns a dict of variable name -> value at the nearest grid point.
    """
    grib = pygrib.open(fname)  # pylint: disable=no-member

    lat_grib = grib[1].latlons()[0]
    lon_grib = grib[1].latlons()[1]

    abslat = np.abs(lat_grib - lat)
    abslon = np.abs(lon_grib - lon)
    c = np.maximum(abslon, abslat)
    x, y = np.where(c == np.min(c))
    x, y = x[0], y[0]

    res = {'lat': lat_grib[x, y], 'lon': lon_grib[x, y], 'x': x, 'y': y}
    for g in grib:
        name = str(g).split(':fcst time', maxsplit=1)[0]
        name = name.split(':', 1)[1]
        res[name] = g.values[x, y]

    return res


def get_hrrr_forecast(lat, lon, dt, tz='America/Los_Angeles', max_hour=16,
                      tmp_dir='', debug=False, store_file=False, forecast_age=2):
    """Download and assemble NOAA HRRR forecast data for a single location.

    Returns a DataFrame indexed by local time with one row per forecast hour.
    """
    dt = dt.replace(minute=0, second=0, microsecond=0, nanosecond=0).tz_localize(None)
    dt_utc = dt.tz_localize(tz).tz_convert('UTC').tz_localize(None)
    dt_utc = dt_utc - pd.DateOffset(hours=forecast_age)

    # pygrib 2.1.5 bug: does not support in-memory objects as input
    store_file = True

    res = {}
    for h in range(forecast_age, max_hour + forecast_age + 1):
        st = time.time()

        fc_obj = download_latest_hrrr(
            lat, lon, dt_utc, h,
            tmp_dir=tmp_dir, debug=debug, store_file=store_file
        )

        if fc_obj:
            r = get_nearest_data(lat, lon, fc_obj)
            try:
                if not debug:
                    os.remove(fc_obj)
            except Exception:
                pass
        else:
            r = {}

        r['duration'] = time.time() - st
        res[dt_utc + pd.DateOffset(hours=h)] = r

    res = pd.DataFrame(res).transpose()
    res.index = (
        pd.to_datetime(res.index).tz_localize('UTC').tz_convert(tz).tz_localize(None)
    )
    return res


def get_noaa_hrrr_forecast(config, start_time, tz, forecaster=None, processor=None):
    """Download NOAA HRRR forecast; initialise the forecaster and processor on first call.

    Returns (forecast_df, forecaster_fn, processor) tuple.
    """
    if not forecaster:
        forecaster = get_hrrr_forecast
        processor = HRRR()
        processor.location = Location(
            config['lat'], config['lon'],
            altitude=config['alt'], tz=start_time.tz
        )

    if not os.path.exists(config['tmp_dir']):
        os.mkdir(config['tmp_dir'])

    forecast = forecaster(
        config['lat'], config['lon'], start_time,
        tz=tz, max_hour=config['horizon'],
        tmp_dir=config['tmp_dir'], debug=config['debug']
    )

    return forecast, forecaster, processor
