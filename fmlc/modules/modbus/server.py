# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
ModbusServer eFMU module.
"""

# pylint: disable=broad-except

import io
import sys
import logging
import subprocess as sp
import time
import traceback

import pandas as pd

from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusDeviceContext,
    ModbusServerContext,
)
from pymodbus.client.mixin import ModbusClientMixin

from fmlc.baseclasses import eFMU


class ModbusHandler:
    """Manages a single SCADA register backed by a dict store."""

    def __init__(self, name, rtype, store):
        self.name = name
        self.rtype = rtype
        self._store = store
        self._client = ModbusClientMixin()

    def get_value(self):
        """Read the current register value from the store."""
        v = self._store[self.name]
        if self.rtype.lower() == 'float':
            return self._client.convert_to_registers(value=v, data_type='float32')
        if self.rtype.lower() == 'int':
            return self._client.convert_to_registers(value=v, data_type='int16')
        return v

    def set_value(self, v):
        """Write a new register value into the store."""
        if self.rtype.lower() == 'float':
            v = self._client.convert_from_registers(registers=v, data_type='float32')
        elif self.rtype.lower() == 'int':
            v = self._client.convert_from_registers(registers=[v], data_type='int16')
        self._store[self.name] = v


class ModbusDataBlock(ModbusSequentialDataBlock):
    """Sequential data block whose get/set delegate to ModbusHandler instances."""

    def __init__(self, address, values):
        values_list = list(values) if hasattr(values, '__iter__') else [values]
        # Pass a safe all-zero placeholder to the base class so it can initialise
        # its SimData store without rejecting non-integer ModbusHandler entries.
        super().__init__(address, [0] * len(values_list))
        self.address = address
        self.values = values_list
        self.default_value = -1

    def getValues(self, address, count=1):  # pylint: disable=invalid-name
        """Return register values, delegating to ModbusHandler where present."""
        start = address - self.address
        res = []
        store_next = False
        pending = []
        for i in range(start, start + count):
            if store_next:
                res.append(pending[1])
                store_next = False
                pending = None
            else:
                entry = self.values[i]
                if isinstance(entry, ModbusHandler):
                    v = entry.get_value()
                    if isinstance(v, list):
                        res.append(v[0])
                        store_next = True
                        pending = v
                    else:
                        res.append(v)
                else:
                    res.append(entry)
        return res

    def setValues(self, address, values):  # pylint: disable=invalid-name
        """Write register values, delegating to ModbusHandler where present."""
        if not isinstance(values, list):
            values = [values]
        start = address - self.address
        store_next = False
        accumulator = None
        for i, v in zip(range(start, start + len(values)), values):
            if store_next:
                store_next = False
                accumulator.append(v)
                self.values[i - 1].set_value(accumulator)
                accumulator = None
            else:
                entry = self.values[i]
                if isinstance(entry, ModbusHandler):
                    if 'float' in entry.rtype:
                        store_next = True
                        accumulator = [v]
                    else:
                        entry.set_value(v)
                else:
                    self.values[i] = v


def _make_dynamic_registers(channels, store):
    """Build a ModbusDataBlock from a channels DataFrame and a dict-like store."""
    max_reg = channels['register'].max()
    registers = []
    for r in range(0, max_reg + 2):
        if r in channels['register'].values:
            row = channels[channels['register'] == r]
            registers.append(
                ModbusHandler(row['name'].values[0], row['mode'].values[0], store)
            )
        else:
            registers.append(0)
    return ModbusDataBlock(1, registers)


def run_modbus_tcp_server(channels_json, log_level=logging.WARNING):
    """Start a blocking Modbus TCP server driven by a channels configuration JSON.

    Intended to be called from a subprocess spawned by ModbusServer.compute().
    """
    channels = pd.read_json(io.StringIO(channels_json)).sort_values('register')
    store = {r['name']: r['default'] for _, r in channels.iterrows()}

    if 'slave_id' in channels.columns:
        slaves = {}
        for slave_id in sorted(channels['slave_id'].unique()):
            hr = _make_dynamic_registers(channels[channels['slave_id'] == slave_id], store)
            slaves[slave_id] = ModbusDeviceContext(hr=hr)
        single = False
    else:
        hr = _make_dynamic_registers(channels, store)
        slaves = ModbusDeviceContext(hr=hr)
        single = True

    context = ModbusServerContext(devices=slaves, single=single)

    logging.basicConfig()
    log = logging.getLogger('pymodbus')
    log.setLevel(log_level)

    address_parts = channels['address'].iloc[0].split(':')
    host = address_parts[0]
    port = int(address_parts[1])
    StartTcpServer(context=context, address=(host, port))


class ModbusServer(eFMU):
    """Launch and sync a Modbus TCP server as a subprocess.

    The server subprocess is started on the first compute call and restarted
    automatically if it exits unexpectedly.  Channel values are exchanged via
    the standard SCADA name/value JSON format.
    """

    def __init__(self):
        super().__init__()
        self.input = {
            'input-data': None,
            'channels': None,
            'debug': None,
            'timeout': None,
        }
        self.output = {
            'output-data': None,
            'duration': None,
        }
        self.init = False
        self._server_proc = None
        self._store = {}
        self._channels = None

    def _ensure_server(self):
        """Start the server subprocess if it is not running."""
        if self._server_proc is not None and self._server_proc.poll() is None:
            return ''
        debug_flag = 'debug' if self.input['debug'] else ''
        channels_json = self._channels.to_json()
        cmd = (
            f"exec python3 -u -m fmlc.modules.modbus.server "
            f"'{channels_json}' {debug_flag}"
        )
        self._server_proc = sp.Popen([cmd], shell=True)  # pylint: disable=consider-using-with
        return ''

    def compute(self):
        st = time.time()
        msg = ''
        out_data = None

        try:
            channels_raw = self.input['channels']
            msg += self.check_data(channels_raw, True)

            if not msg:
                self._channels = pd.read_json(io.StringIO(channels_raw))

            if not msg and not self.init:
                self._store = {r['name']: r['default'] for _, r in self._channels.iterrows()}
                self.init = True

            if not msg:
                msg += self._ensure_server()

            if not msg:
                input_data_raw = self.input['input-data']
                if input_data_raw:
                    write_channels = set(
                        self._channels['name'][self._channels['access'] == 'r'].values
                    )
                    incoming = pd.read_json(io.StringIO(input_data_raw))
                    for _, row in incoming.iterrows():
                        if row['name'] in write_channels:
                            self._store[row['name']] = row['value']

                read_channels = set(
                    self._channels['name'][self._channels['access'] == 'w'].values
                )
                out_data = {k: v for k, v in self._store.items() if k in read_channels}

        except Exception as e:
            msg += f'ERROR: {e}\n\n{traceback.format_exc()}'

        self.output['output-data'] = out_data
        self.output['duration'] = time.time() - st

        if not msg:
            return 'Done.'
        return msg


if __name__ == '__main__':
    _channels_json = sys.argv[1]
    _LOG_LEVEL = logging.DEBUG if len(sys.argv) > 2 and sys.argv[2] == 'debug' else logging.WARNING
    run_modbus_tcp_server(_channels_json, log_level=_LOG_LEVEL)
