# Stackedclasses

Class `controller_stack` handles the parallelization, timing/triggering, data logging, and error handling of multiple `eFMU` controller modules.

## `__init__`

Initialize the controller stack. See `doc/fmlc_template.md` for the full parameter reference and stack template.

Key parameters:

| Parameter | Default | Description |
|---|---|---|
| `controller` | required | Dict of `{name: {'function': cls, 'sampletime': int\|str}}` |
| `mapping` | required | Dict of `{'{module}_{key}': value_or_link_string}` |
| `tz` | `-8` | UTC offset in hours |
| `name` | `'Zone1'` | Stack display name |
| `parallel` | `True` | Run controllers in parallel threads |
| `workers` | `cpu_count() * 5` | ThreadPoolExecutor pool size |
| `timestep` | `0.25` | Seconds between `query_control` ticks |
| `log_level` | `WARNING` | Python logging level |
| `log_clear_period` | `86400` | Seconds between clearing in-memory logs and writing `*_full.csv` |
| `log_dump_period` | `9999 h` | Seconds between intermediate `*_log.csv` dumps (disabled by default) |
| `log_path` | `'./log'` | Path for CSV log files |
| `align_ts` | `None` | Align `query_control` to even multiples of this interval (seconds) |
| `offset_query` | `0` | Extra seconds after alignment boundary before querying |

**`sampletime`** can be a number (independent schedule in seconds) or a module name string (fire immediately after that module completes).

**`mapping`** values can be literals, link strings (e.g. `'modA_output-data'`), or serialized JSON config blobs.

### Log files
Two file types are written to `log_path`:
- `*_log.csv` — intermediate cumulative dump (written every `log_dump_period`; disabled by default).
- `*_full.csv` — complete period file written at each `log_clear_period` when in-memory logs are cleared.

## \_\_initialize
A function to call initializers of the pythonDB, controller, mapping, and execution list. This function is a private method only called by the `__init__` method.   
Inputs:
* mapping(dict): A dictionary that maps the inputs to the controllers' input variables. Each key is in the format {controller name}_{input variable name}. Values can either be a numeric value or a string of format {controller name}_{input/output variable name}. A string indicates dependency or sharing of another controller's input/output. In the exmaple below, controller  `mpc1` 's input `a` depends on the output `c` of controller `forecast1`. The input `b` of `mpc1` shares the same value with controller `forecast1`'s input `a`.
   ```python
    mapping['forecast1_a'] = 10
    mapping['forecast1_b'] = 4
    mapping['forecast2_a'] = 20
    mapping['forecast2_b'] = 4
    mapping['forecast3_a'] = 30
    mapping['forecast3_b'] = 4
    mapping['mpc1_a'] = 'forecast1_c'
    mapping['mpc1_b'] = 'forecast1_a'
    mapping['control1_a'] = 'mpc1_c'
    mapping['control1_b'] = 'mpc1_a'
   ```
* now(float): The time in seconds since the epoch.
  
Implementation Logic:
## Public Methods

### `query_control(now)`
Triggers computations for all controllers whose sample time has elapsed. In parallel mode each execution loop runs in its own thread. `now` is a Unix timestamp — pass `time.time()` for real-time or a synthetic value for testing.

### `run_query_control_for(seconds, timestep, shutdown)`
Convenience run loop. Calls `query_control` every `timestep` seconds for `seconds` wall-clock seconds. Reads `align_ts` and `offset_query` from the stack instance to align execution to fixed time boundaries.

### `log_to_df(which)`
Returns `{module_name: pd.DataFrame}` with a datetime index. `which` selects columns: any subset of `['input', 'output', 'log']`.

### `log_to_csv(path, add_ts)` / `save_and_clear(path, add_ts)`
`log_to_csv` writes an intermediate `*_log.csv` dump. `save_and_clear` writes a complete `*_full.csv` and clears in-memory logs.

### `shutdown(dump_log)`
Shuts down the database and thread pool. Set `dump_log=True` to write a final CSV before exit.

### `set_input(inputs)` / `get_output(name, keys)` / `get_input(name, keys)`
Runtime input injection and per-module output/input retrieval.