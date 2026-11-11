# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Tests for the Modbus eFMU modules.
"""

# pylint: disable=broad-except

import io
import json
import sys
from os import path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.modules.modbus.client import ModbusClient, _DummyConnection
from fmlc.modules.modbus.server import (
    ModbusDataBlock,
    ModbusHandler,
    ModbusServer,
    _make_dynamic_registers,
)
import fmlc.modules.modbus.io as modbus_io


_CHANNELS = [
    {
        'name': 'power_kw',
        'address': '127.0.0.1:502',
        'register': 100,
        'mode': 'float',
        'default': 0.0,
        'holding': True,
        'order': ['big', 'little'],
    },
    {
        'name': 'status',
        'address': '127.0.0.1:502',
        'register': 102,
        'mode': 'int',
        'default': -1,
        'holding': True,
        'order': ['big', 'little'],
    },
]

_CHANNELS_JSON = json.dumps(_CHANNELS)

_SERVER_CHANNELS = [
    {'name': 'ch_r', 'address': '127.0.0.1:502', 'register': 1,
     'mode': 'int', 'default': 0, 'access': 'r'},
    {'name': 'ch_w', 'address': '127.0.0.1:502', 'register': 2,
     'mode': 'int', 'default': 5, 'access': 'w'},
]

_SERVER_CHANNELS_JSON = json.dumps(_SERVER_CHANNELS)


# io helpers

def test_address_to_tuple_tcp():
    result = modbus_io.address_to_tuple('192.168.1.10:502')
    assert result[0] == '192.168.1.10'
    assert result[1] == 502
    assert result[2] == 0


def test_address_to_tuple_tcp_with_slave():
    result = modbus_io.address_to_tuple('192.168.1.10:502:3')
    assert result[2] == 3


def test_address_to_tuple_rtu():
    result = modbus_io.address_to_tuple('/dev/ttyUSB0')
    assert result[0] is None
    assert result[1] == '/dev/ttyUSB0'
    assert result[2] == 0
    assert result[3] == 9600


def test_get_uniconn_tcp():
    assert modbus_io.get_uniconn('192.168.1.10:502:1') == '192.168.1.10:502'


def test_get_uniconn_simple():
    assert modbus_io.get_uniconn('192.168.1.10:502') == '192.168.1.10:502'


# ModbusHandler

def test_modbus_handler_get_int():
    store = {'ch': 42}
    handler = ModbusHandler('ch', 'int', store)
    mock_client = MagicMock()
    mock_client.convert_to_registers.return_value = [42]
    handler._client = mock_client
    handler.get_value()
    mock_client.convert_to_registers.assert_called_once_with(value=42, data_type='int16')


def test_modbus_handler_set_int():
    store = {'ch': 0}
    handler = ModbusHandler('ch', 'int', store)
    mock_client = MagicMock()
    mock_client.convert_from_registers.return_value = 7
    handler._client = mock_client
    handler.set_value(7)
    mock_client.convert_from_registers.assert_called_once_with(registers=[7], data_type='int16')


def test_modbus_handler_passthrough():
    store = {'ch': 'raw'}
    handler = ModbusHandler('ch', 'other', store)
    assert handler.get_value() == 'raw'


# ModbusDataBlock

def test_data_block_get_plain_values():
    block = ModbusDataBlock(1, [10, 20, 30])
    assert block.getValues(1, count=3) == [10, 20, 30]


def test_data_block_set_plain_values():
    block = ModbusDataBlock(1, [0, 0, 0])
    block.setValues(2, [99])
    assert block.values[1] == 99


def test_make_dynamic_registers_builds_block():
    channels = pd.DataFrame(_SERVER_CHANNELS)
    store = {r['name']: r['default'] for _, r in channels.iterrows()}
    block = _make_dynamic_registers(channels, store)
    assert isinstance(block, ModbusDataBlock)
    assert isinstance(block.values[1], ModbusHandler)
    assert isinstance(block.values[2], ModbusHandler)


# ModbusServer

def _make_server(input_data=None, channels_json=None):
    mod = ModbusServer()
    mod.input['channels'] = channels_json or _SERVER_CHANNELS_JSON
    mod.input['input-data'] = input_data
    mod.input['debug'] = None
    mod.input['timeout'] = None
    return mod


def test_server_inputs_declared():
    mod = ModbusServer()
    for key in ('input-data', 'channels', 'debug', 'timeout'):
        assert key in mod.input


def test_server_outputs_declared():
    mod = ModbusServer()
    for key in ('output-data', 'duration'):
        assert key in mod.output


def test_server_missing_channels_returns_error():
    mod = ModbusServer()
    mod.input['channels'] = None
    mod.input['input-data'] = None
    mod.input['debug'] = None
    mod.input['timeout'] = None
    with patch.object(mod, '_ensure_server', return_value=''):
        msg = mod.compute()
    assert 'Waiting' in msg or 'ERROR' in msg


def test_server_all_outputs_assigned_on_error():
    mod = ModbusServer()
    mod.input['channels'] = None
    mod.input['input-data'] = None
    mod.input['debug'] = None
    mod.input['timeout'] = None
    with patch.object(mod, '_ensure_server', return_value=''):
        mod.compute()
    assert 'output-data' in mod.output
    assert 'duration' in mod.output


def test_server_compute_success():
    mod = _make_server()
    with patch.object(mod, '_ensure_server', return_value=''):
        msg = mod.compute()
    assert msg == 'Done.'
    assert mod.output['duration'] >= 0.0


def test_server_compute_initialises_store_from_defaults():
    mod = _make_server()
    with patch.object(mod, '_ensure_server', return_value=''):
        mod.compute()
    assert mod._store['ch_r'] == 0
    assert mod._store['ch_w'] == 5


def test_server_compute_writes_readable_channels():
    input_data = pd.DataFrame([{'name': 'ch_r', 'value': 99}]).to_json()
    mod = _make_server(input_data=input_data)
    with patch.object(mod, '_ensure_server', return_value=''):
        mod.compute()
    assert mod._store['ch_r'] == 99


def test_server_compute_returns_writable_channels():
    mod = _make_server()
    with patch.object(mod, '_ensure_server', return_value=''):
        mod.compute()
    out = mod.output['output-data']
    assert 'ch_w' in out
    assert 'ch_r' not in out


def test_server_init_runs_once():
    mod = _make_server()
    with patch.object(mod, '_ensure_server', return_value=''):
        mod.compute()
        store_ref = mod._store
        mod.compute()
    assert mod._store is store_ref


# ModbusClient

def _make_client(mode='get', channels=None, input_data=None):
    mod = ModbusClient()
    mod.input['channels'] = channels or _CHANNELS_JSON
    mod.input['mode'] = mode
    mod.input['input-data'] = input_data
    mod.input['sleep-between'] = None
    mod.input['pmb-debug'] = None
    mod.input['timeout'] = None
    return mod


def test_client_inputs_declared():
    mod = ModbusClient()
    for key in ('input-data', 'channels', 'mode', 'sleep-between', 'pmb-debug', 'timeout'):
        assert key in mod.input


def test_client_outputs_declared():
    mod = ModbusClient()
    for key in ('output-data', 'duration'):
        assert key in mod.output


def test_client_unknown_mode_returns_error():
    mod = _make_client(mode='invalid')
    msg = mod.compute()
    assert 'ERROR' in msg
    assert mod.output['duration'] >= 0.0


def test_client_all_outputs_assigned_on_error():
    mod = _make_client(mode='invalid')
    mod.compute()
    assert 'output-data' in mod.output
    assert 'duration' in mod.output


def test_client_result_to_msg_no_error_col():
    mod = ModbusClient()
    res = pd.DataFrame({'name': ['ch'], 'value': [1]})
    assert 'No result' in mod._result_to_msg(res)


def test_client_result_to_msg_with_error():
    mod = ModbusClient()
    res = pd.DataFrame({'name': ['ch'], 'value': [0], 'error': ['ERROR: timeout']})
    assert 'Communication error' in mod._result_to_msg(res)


def test_client_result_to_msg_done():
    mod = ModbusClient()
    res = pd.DataFrame({'name': ['ch'], 'value': [1], 'error': ['']})
    assert mod._result_to_msg(res) == 'Done.'


def test_client_read_channel_unknown_mode():
    mod = ModbusClient()
    channel = {'register': 1, 'mode': 'unknown', 'default': -1,
                'holding': True, 'order': ['big', 'little']}
    value, err = mod._read_channel(channel, MagicMock())
    assert 'ERROR' in err
    assert value == -1


def test_client_write_channel_unknown_mode():
    mod = ModbusClient()
    channel = {'register': 1, 'mode': 'unknown', 'order': ['big', 'little']}
    err = mod._write_channel(channel, 1, MagicMock())
    assert 'ERROR' in err


def test_client_get_uses_modbus_io(monkeypatch):
    mock_mb = MagicMock()
    mock_mb.close = MagicMock()
    monkeypatch.setattr(modbus_io, 'modbus_client', lambda **kw: mock_mb)
    monkeypatch.setattr(modbus_io, 'read_register', lambda *a, **kw: (1.5, 0))

    mod = _make_client(mode='get')
    msg = mod.compute()
    assert msg == 'Done.'
    df = pd.read_json(io.StringIO(mod.output['output-data']))
    assert 'power_kw' in df['name'].values


def test_client_get_dummy_register(monkeypatch):
    dummy_channels = [
        {'name': 'dummy_ch', 'address': '127.0.0.1:502', 'register': -1,
         'mode': 'int', 'default': 999, 'holding': True, 'order': ['big', 'little']},
    ]
    mock_mb = MagicMock()
    mock_mb.close = MagicMock()
    monkeypatch.setattr(modbus_io, 'modbus_client', lambda **kw: mock_mb)

    mod = _make_client(mode='get', channels=json.dumps(dummy_channels))
    msg = mod.compute()
    assert msg == 'Done.'
    df = pd.read_json(io.StringIO(mod.output['output-data']))
    assert df[df['name'] == 'dummy_ch'].iloc[0]['value'] == 999


def test_client_set_missing_input_data_returns_error():
    mod = _make_client(mode='set', input_data=None)
    msg = mod.compute()
    assert msg != 'Done.'


def test_client_set_uses_modbus_io(monkeypatch):
    mock_mb = MagicMock()
    mock_mb.close = MagicMock()
    monkeypatch.setattr(modbus_io, 'modbus_client', lambda **kw: mock_mb)
    monkeypatch.setattr(modbus_io, 'write_register', lambda *a, **kw: 0)

    input_data = pd.DataFrame([
        {'name': 'power_kw', 'value': 10.0},
        {'name': 'status', 'value': 1},
    ]).to_json()
    mod = _make_client(mode='set', input_data=input_data)
    msg = mod.compute()
    assert msg == 'Done.'


def test_dummy_connection_close():
    _DummyConnection().close()
