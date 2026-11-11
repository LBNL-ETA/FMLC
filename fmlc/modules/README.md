# FMLC Modules

Ready-to-use `eFMU` controller modules for common tasks are available. Each module follows
the standard FMLC interface where a `compute()` method reads from `self.input` and
writes to `self.output`.

## Dummy modules — [`dummy_modules.py`](dummy_modules.py)

Lightweight stubs used for testing and as stack configuration examples.
`GetData` simulates reading from an external source, `DoControl` applies a
trivial setpoint calculation, and `SetData` simulates writing a control action.
`Multiplier` multiplies two inputs with an optional sleep delay, and
`TimeoutDummy` deliberately overshoots its timeout to exercise stack
timeout-and-restart behaviour.

## Local CSV reader — [`csv_reader.py`](csv_reader.py)

`LocalCsvReader` reads a CSV file from disk and exposes its contents as a
JSON-serialised pandas DataFrame on each compute cycle.

## Local CSV writer — [`csv_writer.py`](csv_writer.py)

`LocalCsvWriter` writes a JSON-serialised DataFrame to a local CSV file,
with an optional append mode for accumulating time-series logs.

## Solar position — [`solar_position.py`](solar_position.py)

`SolarPosition` uses [pvlib](https://pvlib-python.readthedocs.io/) to compute
solar elevation, azimuth, zenith, and air-mass for a given site coordinate and
appends those columns to an incoming SCADA DataFrame.

## PI controller — [`pi_controller.py`](pi_controller.py)

`PiController` implements a discrete proportional-integral controller that
trims a command output each cycle to track a setpoint. Supports configurable
gains, integral anti-windup, output clipping, an optional state guard (e.g.
battery SOC limits), and pluggable process-variable processors.

## Deviation watchdog — [`deviation_watchdog.py`](deviation_watchdog.py)

`DeviationWatchdog` compares live measurements to lagged predictions and fires
alerts when the absolute deviation exceeds a per-channel threshold. Alert
channels can be routed to Python `warnings`, a JSON log file, or email.

## MIDAS forecast — [`midas.py`](midas.py)

`MidasForecast` fetches emission and flex-alert signal values from the
California Energy Commission [MIDAS API](https://midasapi.energy.ca.gov/) on
each compute cycle, returning the raw JSON payload. A `MidasClient` helper
handles authentication and token management.

## WattTime forecast — [`watttime.py`](watttime.py)

`WatttimeForecast` retrieves marginal carbon emission forecast data from the
[WattTime API](https://www.watttime.org/) for a given balancing authority. A
`WatttimeClient` helper handles login, region lookup, and token refresh.

## Box integration — [`box/`](box/)

`BoxCsvReader` and `BoxCsvWriter` read and write CSV files stored in
[Box](https://www.box.com/) cloud storage using the Box OAuth 2.0 SDK. See the
[Box README](box/README.md) for credential setup and input key reference.

## Modbus — [`modbus/`](modbus/)

`ModbusClient` polls or writes Modbus TCP/RTU registers, and `ModbusServer`
runs a Modbus TCP server as a managed subprocess that exposes SCADA channel
values to external clients. Low-level register helpers live in `io.py`. See the
[Modbus README](modbus/README.md) for channel configuration details and usage
examples.

## SkySpark integration — [`skyspark/`](skyspark/)

`SkysparkReader` downloads time-series SCADA data from a
[SkySpark](https://skyfoundry.com/product) server via a Haystack eval command.
`SkysparkDummy` is a drop-in offline replacement that generates synthetic data
for pipeline testing. `SkysparkScadaFormatter` aligns the time series to a
fixed sampling grid and applies an optional CSV-driven math template to derive
new channels. See the [SkySpark README](skyspark/README.md) for full details.

## Weather forecast — [`weather_forecast/`](weather_forecast/)

`WeatherForecaster` downloads NOAA HRRR GRIB2 forecasts and processes them
through pvlib into solar irradiance and meteorological time series. A local
JSON source mode is also supported for testing without a network connection. See
the [Weather Forecast README](weather_forecast/README.md) for configuration
keys and usage examples.
