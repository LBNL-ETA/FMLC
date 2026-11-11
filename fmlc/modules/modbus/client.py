# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
ModbusClient eFMU module.
"""

# pylint: disable=broad-except,too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches

import io
import json
import time
import traceback

import numpy as np
import pandas as pd

from fmlc.baseclasses import eFMU
import fmlc.modules.modbus.io as modbus_io


class _DummyConnection:  # pylint: disable=too-few-public-methods
    """No-op connection placeholder used before a real client is created."""

    def close(self):
        """No-op close."""


class ModbusClient(eFMU):
    """Read from or write to a Modbus device over TCP or RTU.

    Set ``mode`` to ``'get'`` to poll register values, or ``'set'`` to push
    values from ``input-data`` to the device.
    """

    def __init__(self):
        super().__init__()
        self.input = {
            'input-data': None,
            'channels': None,
            'mode': None,
            'sleep-between': None,
            'pmb-debug': None,
            'timeout': None,
        }
        self.output = {
            'output-data': None,
            'duration': None,
        }
        self.init = False

    def _result_to_msg(self, res):
        """Return a human-readable status string from a results DataFrame."""
        if 'error' not in res.columns:
            return 'No result returned. Check channels configuration.'
        if res['error'].str.contains('ERROR').any():
            return 'Communication error, see output-data.'
        return 'Done.'

    def _read_channel(self, channel, client, sleep=0.5, max_tries=1, dev_id=0):
        """Read a single channel; return (value, error_string)."""
        register = channel['register']
        mode = channel['mode']
        default = channel['default']
        holding = channel['holding'] if 'holding' in channel else True
        order = channel.get('order', ['big', 'little'])
        if isinstance(order, str):
            order = json.loads(order)
        try:
            if mode in ('int', 'uint', 'float'):
                data_type = {'int': 'int16', 'uint': 'uint16', 'float': 'float32'}[mode]
                r, i = modbus_io.read_register(client, register, dev_id,
                                               data_type=data_type, sleep=sleep,
                                               holding=holding, order=order)
            elif mode == 'coil':
                r, i = modbus_io.read_coil(client, register, dev_id, sleep=sleep)
            else:
                return default, f'ERROR: Mode "{mode}" not implemented.'
            if i > max_tries:
                return default, f'ERROR: Could not read value after {i} attempts.'
            return r, ''
        except Exception as e:
            return default, f'ERROR: {e}'

    def _write_channel(self, channel, value, client, sleep=0.5, max_tries=1, dev_id=0):
        """Write a single channel value; return an error string (empty on success)."""
        register = channel['register']
        mode = channel['mode']
        order = channel.get('order', ['big', 'little'])
        try:
            if mode in ('int', 'uint'):
                data_type = 'int16' if mode == 'int' else 'uint16'
                i = modbus_io.write_register(client, register, dev_id, int(value),
                                             data_type=data_type, sleep=sleep, order=order)
            elif mode == 'float':
                i = modbus_io.write_register(client, register, dev_id, float(value),
                                             data_type='float32', sleep=sleep, order=order)
            elif mode == 'coil':
                i = modbus_io.write_coil(client, register, dev_id, value, sleep=sleep)
            else:
                return f'ERROR: Mode "{mode}" not implemented.'
            if i > max_tries:
                return f'ERROR: Could not write value after {i} attempts.'
            return ''
        except Exception as e:
            return f'ERROR: {e}'

    def _get(self):
        """Poll all channels and return a results DataFrame."""
        res = []
        channels = json.loads(self.input['channels'])

        if pd.DataFrame(channels)['name'].duplicated().any():
            raise ValueError('Duplicated entries in channel names.')

        clients = {}
        for addr in sorted(np.unique([c['address'] for c in channels])):
            key = modbus_io.get_uniconn(addr)
            if key not in clients:
                parts = modbus_io.address_to_tuple(addr)
                clients[key] = modbus_io.modbus_client(
                    port=parts[1], ip=parts[0], baudrate=parts[3],
                    pmb_debug=self.input['pmb-debug']
                )

        try:
            for c in channels:
                st = time.time()
                addr = c['address']
                client = clients[modbus_io.get_uniconn(addr)]
                dev_id = modbus_io.address_to_tuple(addr)[2]
                r = {}
                if c['register'] == -1:
                    r['value'] = c['default']
                    r['error'] = ''
                    r['valid'] = 0
                else:
                    r['value'], r['error'] = self._read_channel(c, client, dev_id=dev_id)
                    r['valid'] = int(r['error'] == '')
                r['name'] = c['name']
                r['duration'] = time.time() - st
                res.append(r)
                if self.input['sleep-between']:
                    time.sleep(self.input['sleep-between'])
            df = pd.DataFrame(res)
        except Exception as e:
            err = f'ERROR: {e}\n\n{traceback.format_exc()}'
            df = pd.DataFrame(res)
            names_seen = df['name'].values if 'name' in df.columns else []
            for c in channels:
                if c['name'] not in names_seen:
                    df.loc[len(df), ['name', 'value', 'error', 'valid', 'duration']] = \
                        [c['name'], c['default'], err, int(False), 0]
        finally:
            for client in clients.values():
                client.close()

        if 'name' in df.columns:
            df.index = df['name']
        return df

    def _set(self):
        """Push values from input-data to all channels and return a results DataFrame."""
        inputs = pd.read_json(io.StringIO(self.input['input-data']))
        res = []
        channels = json.loads(self.input['channels'])
        client = _DummyConnection()

        if pd.DataFrame(channels)['name'].duplicated().any():
            raise ValueError('Duplicated entries in channel names.')

        addresses = np.unique([c['address'] for c in channels])
        if len(addresses) > 1:
            raise ValueError(
                f'Only a single address is supported for set mode. Got: {addresses}'
            )
        parts = modbus_io.address_to_tuple(addresses[0])
        client = modbus_io.modbus_client(port=parts[1], ip=parts[0], baudrate=parts[3],
                                         pmb_debug=self.input['pmb-debug'])
        try:
            for c in channels:
                name = c['name']
                st = time.time()
                r = {'name': name}
                if name in inputs['name'].values:
                    v = inputs['value'][inputs['name'] == name].values[-1]
                    r['value'] = v
                    r['error'] = self._write_channel(c, v, client, dev_id=parts[2])
                    r['valid'] = int(r['error'] == '')
                else:
                    r['value'] = None
                    r['error'] = f'ERROR: Channel "{name}" not in input-data.'
                    r['valid'] = int(False)
                r['duration'] = time.time() - st
                res.append(r)
                if self.input['sleep-between']:
                    time.sleep(self.input['sleep-between'])
            df = pd.DataFrame(res)
        except Exception as e:
            err = f'ERROR: {e}\n\n{traceback.format_exc()}'
            df = pd.DataFrame(res)
            names_seen = df['name'].values if 'name' in df.columns else []
            for c in channels:
                if c['name'] not in names_seen:
                    df.loc[len(df), ['name', 'value', 'error', 'valid', 'duration']] = \
                        [c['name'], None, err, int(False), 0]
        finally:
            client.close()

        if 'name' in df.columns:
            df.index = df['name']
        return df

    def compute(self):
        st = time.time()
        msg = ''
        out_data = None
        mode = self.input['mode']

        try:
            if mode == 'get':
                res = self._get()
                out_data = res.to_json()
                msg = self._result_to_msg(res)
                self.init = True
            elif mode == 'set':
                msg += self.check_data(self.input['input-data'], self.init)
                if not msg:
                    res = self._set()
                    out_data = res.to_json()
                    msg = self._result_to_msg(res)
                    self.init = True
            else:
                msg = f'ERROR: Unknown mode "{mode}". Use "get" or "set".'
        except Exception as e:
            msg += f'ERROR: {e}\n\n{traceback.format_exc()}'

        self.output['output-data'] = out_data
        self.output['duration'] = time.time() - st
        return msg
