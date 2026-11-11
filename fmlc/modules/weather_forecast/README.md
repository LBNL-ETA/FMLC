# Weather Forecast Integration

eFMU module for retrieving NOAA HRRR weather forecasts and processing them
into solar irradiance and meteorological time series via pvlib.

| Module | Class / function | File |
|---|---|---|
| Forecast eFMU | `WeatherForecaster` | `forecast.py` |
| HRRR download helpers | `get_hrrr_forecast`, `get_noaa_hrrr_forecast` | `hrrr_download.py` |
| pvlib processing | `HrrrProcessor` | `hrrr_processor.py` |
| Utilities | `check_forecast`, `process_forecast`, `get_default_config` | `utils.py` |

## Installation

Additional dependencies beyond the core FMLC requirements:

```bash
pip install pygrib requests numpy pvlib
```

`pygrib` requires the ECCODES library. On Ubuntu/Debian:

```bash
apt-get install libeccodes-dev
pip install pygrib
```

## Module inputs and outputs

### WeatherForecaster

**Inputs**

| Key | Description |
|---|---|
| `config` | Configuration dict (see `get_default_config()` for all keys) |
| `input-data` | JSON-serialised DataFrame used when `config['source'] == 'json'` |
| `timeout` | Reserved; not currently used |
| `time` | FMLC hidden input: current Unix timestamp (seconds since epoch) |

**Outputs**

| Key | Description |
|---|---|
| `output-data` | JSON-serialised forecast DataFrame (or raw DataFrame when `json_return=False`) |
| `duration` | Wall-clock time of the compute call in seconds |

### Configuration keys

| Key | Default | Description |
|---|---|---|
| `lat` | `37.8715` | Site latitude (degrees) |
| `lon` | `-122.2501` | Site longitude (degrees) |
| `alt` | `50` | Site altitude (m) |
| `tz` | `'US/Pacific'` | Local time zone (IANA string) |
| `horizon` | `16` | Forecast horizon (hours) |
| `tmp_dir` | `'tmp'` | Directory for GRIB2 download cache |
| `debug` | `False` | Verbose output; keep temp files |
| `source` | `'noaa_hrrr'` | Forecast source: `'noaa_hrrr'` or `'json'` |
| `refresh_time` | `900` | Minimum seconds between fresh downloads |
| `update_st_refresh` | `False` | Shift forecast index by intra-hour minutes |
| `json_return` | `True` | Return output as JSON string |
| `add_solpos` | `True` | Append solar-position columns |
| `forecast_cols` | `{}` | Expected raw forecast column ranges for validation |
| `output_cols` | see below | Expected output column ranges for validation |

Default `output_cols`:

```python
{
    'temp_air':    [-50, 50],
    'ghi':         [0, 1000],
    'dni':         [0, 1500],
    'dhi':         [0, 1000],
    'low_clouds':  [0, 100],
    'mid_clouds':  [0, 100],
    'high_clouds': [0, 100],
    'total_clouds':[0, 100],
    'wind_speed':  [0, 150],
}
```

## Usage example

```python
from fmlc.modules.weather_forecast.forecast import WeatherForecaster
from fmlc.modules.weather_forecast.utils import get_default_config
import time

config = get_default_config()

forecaster = WeatherForecaster()
forecaster.input['config'] = config
forecaster.input['time'] = time.time()

msg = forecaster.compute()
print(msg)
```

## JSON source example

Pass a pre-built forecast DataFrame (e.g. from a file or prior computation):

```python
import pandas as pd

forecaster.input['config']['source'] = 'json'
forecaster.input['input-data'] = pd.read_csv('forecast.csv', index_col=0).to_json()
msg = forecaster.compute()
```
