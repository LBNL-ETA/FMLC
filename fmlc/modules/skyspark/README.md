# SkySpark Integration

Three eFMU modules for reading and formatting time-series SCADA data from a
[SkySpark](https://skyfoundry.com/product) server.

| Module | Class | File |
|---|---|---|
| Live reader | `SkysparkReader` | `reader.py` |
| Offline dummy | `SkysparkDummy` | `dummy.py` |
| SCADA formatter | `SkysparkScadaFormatter` | `scada_formatter.py` |

## Installation

`SkysparkReader` depends on
[pyhaystack](https://github.com/ChristianTremblay/pyhaystack), which is not
included in the core FMLC dependencies. Install it with:

```bash
pip install -r fmlc/modules/skyspark/requirements.txt
```

`SkysparkDummy` and `SkysparkScadaFormatter` have no extra dependencies beyond
the core FMLC requirements (`pandas`, `numpy`).

## Credentials file

`SkysparkReader` loads credentials from a JSON file at the path given by the
`credentials-file` input. The file must contain two keys:

```json
{
  "u": "<your-skyspark-username>",
  "p": "<your-skyspark-password>"
}
```

The credentials file is read once on the first call to `compute()` and the
session is reused for all subsequent calls. Store the file outside version
control.

## Module inputs and outputs

### SkysparkReader

Downloads a time-series grid from SkySpark by evaluating a Haystack Axon
expression and returns it as a JSON-serialised pandas DataFrame (ISO timestamps
as index, one column per channel).

**Inputs**

| Key | Description |
|---|---|
| `credentials-file` | Path to the JSON credentials file (see above) |
| `uri` | Base URL of the SkySpark server, e.g. `https://skyspark.example.com` |
| `project` | SkySpark project name |
| `cmd` | Axon expression passed to `get_eval`, e.g. `hisRead(...)` |
| `channel-map` | Optional `dict` mapping raw column names to output names; if set, only mapped columns are kept |
| `timeout` | Reserved for future use with parallel stacks |

**Outputs**

| Key | Description |
|---|---|
| `output-data` | JSON-serialised DataFrame with a DatetimeIndex and one numeric column per channel |
| `duration` | Wall-clock time of the compute call in seconds |

### SkysparkDummy

Drop-in offline replacement for `SkysparkReader`. Accepts the same input keys
(all ignored) and generates 60 minutes of synthetic PV power and irradiance
history at 5-minute intervals, ending at the FMLC-injected `time` timestamp.
Useful for testing pipelines without a live SkySpark connection.

Output channels: `P_pv1_W`, `P_pv2_W`, `P_pv3_W`, `weather-ghi`,
`weather-dni`, `weather-dhi`.

**Inputs** — same keys as `SkysparkReader` (all optional/ignored at runtime).

**Outputs** — same schema as `SkysparkReader`.

### SkysparkScadaFormatter

Takes a JSON-serialised time-series DataFrame (typically from `SkysparkReader`
or `SkysparkDummy`), aligns it to a fixed sampling grid, selects the row
closest to the current FMLC timestamp, optionally applies a CSV-driven math
template to derive new channels, and emits a named-channel output DataFrame.

The output DataFrame has columns `name`, `value`, `valid`, and `error` — one
row per channel — matching the SCADA payload convention used by downstream
modules.

**Inputs**

| Key | Description |
|---|---|
| `input-data` | JSON-serialised DataFrame from `SkysparkReader` or `SkysparkDummy` |
| `sample-seconds` | Sampling period in seconds (e.g. `300` for 5-minute data); rows whose timestamps are not aligned to this boundary are dropped |
| `target-channels` | Channel name string or list of names to include in the output; `None` passes all channels through |
| `math-template-file` | Path to the math template CSV (see below); if `None` or empty, looks for `skyspark_scada_math_template.csv` in the same directory |
| `time-zone` | IANA time-zone name used to localise timestamps, e.g. `America/Los_Angeles` |
| `debug` | If truthy, full tracebacks are appended to error messages |

**Outputs**

| Key | Description |
|---|---|
| `output-data` | JSON-serialised DataFrame with columns `name`, `value`, `valid`, `error` |
| `closest-timestamp` | ISO-formatted timestamp of the selected row |
| `duration` | Wall-clock time of the compute call in seconds |

## Math template CSV

`SkysparkScadaFormatter` can derive new channels from existing ones using a
CSV file. The file must contain the following columns:

| Column | Description |
|---|---|
| `new_channel` | Name of the derived channel to create or overwrite |
| `operation` | One of `copy`, `sum`, `diff`, `mul`, `div`, `scale`, `offset`, `threshold_zero` |
| `channel_a` | Primary input channel name |
| `channel_b` | Secondary input channel name (used by `sum`, `diff`, `mul`, `div`) |
| `scalar` | Numeric constant (used by `scale`, `offset`, `threshold_zero`) |
| `abs_value` | If truthy, take the absolute value of the result |
| `clip_min` | Lower bound to clip the result (leave blank for no clipping) |
| `clip_max` | Upper bound to clip the result (leave blank for no clipping) |

Operations:

| `operation` | Formula |
|---|---|
| `copy` | `a` |
| `sum` | `a + b` |
| `diff` | `a - b` |
| `mul` | `a * b` |
| `div` | `a / b` (returns `NaN` when `b == 0`) |
| `scale` | `a * scalar` |
| `offset` | `a + scalar` |
| `threshold_zero` | `0` if `a < scalar` else `a` |

Example:

```csv
new_channel,operation,channel_a,channel_b,scalar,abs_value,clip_min,clip_max
P_pv_total_W,sum,P_pv1_W,P_pv2_W,,,,
P_pv_net_W,diff,P_load_W,P_pv_total_W,,,,
P_pv_net_kW,scale,P_pv_net_W,,0.001,,,
```

## Usage example

```python
from fmlc.stackedclasses import controller_stack
from fmlc.modules.skyspark.reader import SkysparkReader
from fmlc.modules.skyspark.scada_formatter import SkysparkScadaFormatter

controller = {
    "skysparkReader": {
        "function": SkysparkReader,
        "sampletime": 300,
    },
    "scadaFormatter": {
        "function": SkysparkScadaFormatter,
        "sampletime": "skysparkReader",
    },
}

mapping = {
    "skysparkReader_credentials-file": "/path/to/credentials.json",
    "skysparkReader_uri": "https://skyspark.example.com",
    "skysparkReader_project": "myproject",
    "skysparkReader_cmd": "hisRead(site->meter, {range: lastMonth})",
    "skysparkReader_channel-map": {"raw_name": "clean_name"},
    "skysparkReader_timeout": None,
    "scadaFormatter_input-data": "skysparkReader_output-data",
    "scadaFormatter_sample-seconds": 300,
    "scadaFormatter_target-channels": ["clean_name"],
    "scadaFormatter_math-template-file": "/path/to/math_template.csv",
    "scadaFormatter_time-zone": "America/Los_Angeles",
    "scadaFormatter_debug": None,
}

stack = controller_stack(controller, mapping, name="SkySpark", parallel=True)
```

To use the offline dummy instead of the live reader, replace `SkysparkReader`
with `SkysparkDummy` — no other changes are needed.
