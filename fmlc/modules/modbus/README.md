# Modbus Integration

Three modules for communicating with Modbus TCP and RTU devices from an FMLC
controller stack.

| Module | Class / helpers | File |
|---|---|---|
| Low-level I/O | `read_register`, `write_register`, `read_coil`, `write_coil`, `modbus_client`, `address_to_tuple`, `get_uniconn` | `io.py` |
| Modbus TCP server | `ModbusServer` | `server.py` |
| Modbus client (read/write) | `ModbusClient` | `client.py` |

## Installation

These modules depend on [pymodbus](https://github.com/pymodbus-dev/pymodbus)
(>=3.10.0), which is included in the core FMLC dependencies:

```bash
pip install -r requirements.txt
```

## Channels configuration

Both `ModbusServer` and `ModbusClient` accept a JSON-serialised channels
DataFrame (or list of dicts) via the `channels` input key.

Each channel entry supports the following fields:

| Field | Required | Description |
|---|---|---|
| `name` | yes | Unique channel identifier |
| `address` | yes | TCP ``host:port[:slave_id]`` or RTU ``/dev/ttyX`` string |
| `register` | yes | Modbus register number; use ``-1`` as a passthrough dummy |
| `mode` | yes | Data type: ``int``, ``uint``, ``float``, or ``coil`` |
| `default` | yes | Value returned when communication fails |
| `access` | server only | ``'r'`` = readable by external clients, ``'w'`` = writable |
| `holding` | client only | ``True`` for holding registers (default), ``False`` for input registers |
| `order` | client only | Byte/word order list, e.g. ``["big", "little"]`` (default) |
| `slave_id` | server only | Slave device ID for multi-slave contexts |

## Module inputs and outputs

### ModbusServer

Maintains a Modbus TCP server as a subprocess.  On each compute call it syncs
the shared in-process channel store with the values carried in `input-data`,
then returns any writable channel values via `output-data`.

**Inputs**

| Key | Description |
|---|---|
| `channels` | JSON-serialised channels configuration |
| `input-data` | Optional JSON-serialised DataFrame with ``name``/``value`` rows to push into readable channels |
| `debug` | If truthy, start the server subprocess in debug log mode |
| `timeout` | Reserved for FMLC stack timeout handling |

**Outputs**

| Key | Description |
|---|---|
| `output-data` | Dict of ``{channel_name: value}`` for all writable channels |
| `duration` | Wall-clock time of the compute call in seconds |

### ModbusClient

Reads from (``mode='get'``) or writes to (``mode='set'``) Modbus registers.
Supports TCP and RTU transports, multiple simultaneous addresses (get mode
only), and all standard register data types.

**Inputs**

| Key | Description |
|---|---|
| `channels` | JSON string (list of channel dicts, see above) |
| `mode` | ``'get'`` to read, ``'set'`` to write |
| `input-data` | JSON-serialised DataFrame with ``name``/``value`` rows; required for ``'set'`` mode |
| `sleep-between` | Optional sleep in seconds between individual register operations |
| `pmb-debug` | pymodbus log level string (e.g. ``'DEBUG'``); falsy disables verbose logging |
| `timeout` | Reserved for FMLC stack timeout handling |

**Outputs**

| Key | Description |
|---|---|
| `output-data` | JSON-serialised DataFrame with columns ``name``, ``value``, ``error``, ``valid``, ``duration`` |
| `duration` | Wall-clock time of the compute call in seconds |

## io.py helpers

The `io` module exposes low-level helpers used by `ModbusClient` and
`ModbusServer`, and can also be used directly:

```python
from fmlc.modules.modbus.io import modbus_client, read_register, write_register

client = modbus_client(ip='192.168.1.10', port=502)
value, retries = read_register(client, address=100, device_id=1, data_type='float32')
write_register(client, address=200, device_id=1, value=42.0, data_type='float32')
client.close()
```

### `address_to_tuple(address)`

Parses a channel address string into a ``(ip, port, slave_id, baudrate)``
tuple.

| Format | Example | Result |
|---|---|---|
| TCP | ``192.168.1.10:502`` | ``('192.168.1.10', 502, 0, None)`` |
| TCP with slave | ``192.168.1.10:502:1`` | ``('192.168.1.10', 502, 1, None)`` |
| RTU | ``/dev/ttyUSB0`` | ``(None, '/dev/ttyUSB0', 0, 9600)`` |

## Usage example

```python
import json
from fmlc.stackedclasses import controller_stack
from fmlc.modules.modbus.client import ModbusClient

channels = json.dumps([
    {'name': 'power_kw', 'address': '192.168.1.10:502', 'register': 100,
     'mode': 'float', 'default': 0.0},
    {'name': 'status',   'address': '192.168.1.10:502', 'register': 102,
     'mode': 'int',   'default': -1},
])

controller = {
    'modbusReader': {'function': ModbusClient, 'sampletime': 10},
}

mapping = {
    'modbusReader_channels': channels,
    'modbusReader_mode': 'get',
    'modbusReader_input-data': None,
    'modbusReader_sleep-between': 0.1,
    'modbusReader_pmb-debug': None,
    'modbusReader_timeout': None,
}

stack = controller_stack(controller, mapping, name='ModbusStack')
```
