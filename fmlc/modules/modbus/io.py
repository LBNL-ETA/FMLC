# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Modbus I/O helpers (register read/write, coil read/write, client factory).
"""

# pylint: disable=broad-except,too-many-arguments,too-many-positional-arguments,too-many-locals

import time

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.client.mixin import ModbusClientMixin
from pymodbus.framer import FramerType
from pymodbus import pymodbus_apply_logging_config

MAX_RETRY = 5
SLEEP = 0.5
TIMEOUT = 0.5


def address_to_tuple(address):
    """Parse an address string into a (ip, port, slave_id, baudrate) tuple."""
    parts = address.split(':')
    if len(parts) > 1:
        if len(parts[0]) < 6:
            parts[0] = None
        try:
            parts[1] = int(parts[1])
        except (ValueError, IndexError):
            pass
        if len(parts) >= 3:
            parts[2] = int(parts[2])
        else:
            parts.append(0)
        if len(parts) >= 4:
            parts[3] = int(parts[3])
        else:
            parts.append(None)
        return tuple(parts)
    return (None, address, 0, 9600)


def get_uniconn(addr):
    """Return the connection key (ip:port) for grouping channels by physical link."""
    return str(':'.join(addr.split(':')[:2]))


def modbus_client(port=None, ip=None, baudrate=9600, stopbits=1, timeout=TIMEOUT,
                  retries=0, name='mb1', connect=True, pmb_debug=False):
    """Create and optionally connect a pymodbus TCP or RTU client."""
    pymodbus_apply_logging_config(level=pmb_debug if pmb_debug else 'critical')
    if ip:
        port = port if port else 502
        client = ModbusTcpClient(ip, port=port, timeout=timeout, framer=FramerType.SOCKET,
                                 name=name, retries=retries)
    else:
        client = ModbusSerialClient(port=port, baudrate=int(baudrate),
                                    parity='N', bytesize=8, stopbits=int(stopbits),
                                    timeout=timeout, name=name, framer=FramerType.RTU,
                                    retries=retries)
    if connect:
        client.connect()
    return client


def _set_reading_method(client, holding=True):
    """Return the read function for holding or input registers."""
    if holding:
        return client.read_holding_registers
    return client.read_input_registers


def _swap_bytes_in_registers(registers):
    """Swap low and high bytes within each 16-bit register word."""
    return [((r & 0xFF) << 8) | ((r >> 8) & 0xFF) for r in registers]


def read_register(client, address, device_id, data_type='int16', decode_res=True,
                  sleep=SLEEP, holding=True, order=None, batch_data=False,
                  max_retry=MAX_RETRY):
    """Read one or more Modbus registers and decode the value.

    Returns (value, retry_count).
    """
    if order is None:
        order = ['big', 'little']
    reader = _set_reading_method(client, holding=holding)
    dtype = ModbusClientMixin.DATATYPE[data_type.upper()]
    count = dtype.value[1]
    res = reader(address, count=count, device_id=device_id)
    i = 0
    while res.isError() and i < max_retry:
        time.sleep(sleep)
        res = reader(address, count=count, device_id=device_id)
        i += 1
    if batch_data and decode_res:
        res_dec = []
        for rg in res.registers:
            value = client.convert_from_registers(registers=[rg], data_type=dtype,
                                                  word_order=order[1])
            res_dec.append(value)
        return res_dec, i
    if not decode_res:
        return res, i
    reg_values = res.registers
    if order[0] == 'little':
        reg_values = _swap_bytes_in_registers(reg_values)
    value = client.convert_from_registers(registers=reg_values, data_type=dtype,
                                          word_order=order[1])
    return value, i


def write_register(client, address, device_id, value, data_type='int16',
                   sleep=SLEEP, order=None, max_retry=MAX_RETRY):
    """Write a value to Modbus holding registers.

    Returns the number of retries performed.
    """
    if order is None:
        order = ['big', 'little']
    dtype = ModbusClientMixin.DATATYPE[data_type.upper()]
    payload = client.convert_to_registers(value=value, data_type=dtype,
                                          word_order=order[1])
    if order[0] == 'little':
        payload = _swap_bytes_in_registers(payload)
    res = client.write_registers(address, payload, device_id=device_id)
    i = 0
    while res.isError() and i < max_retry:
        time.sleep(sleep)
        res = client.write_registers(address, payload, device_id=device_id)
        i += 1
    return i


def read_coil(client, address, device_id, count=1, sleep=SLEEP, max_retry=MAX_RETRY):
    """Read one or more Modbus coils.

    Returns (value_or_list, retry_count).
    """
    res = client.read_coils(address=address, count=count, device_id=device_id)
    i = 0
    while res.isError() and i < max_retry:
        time.sleep(sleep)
        res = client.read_coils(address=address, count=count, device_id=device_id)
        i += 1
    bits = res.bits[:count]
    if len(bits) == 1:
        return bits[0], i
    return bits, i


def write_coil(client, address, device_id, value, sleep=SLEEP, max_retry=MAX_RETRY):
    """Write a value to one or more Modbus coils.

    Returns the number of retries performed.
    """
    res = client.write_coils(address=address, values=value, device_id=device_id)
    i = 0
    while res.isError() and i < max_retry:
        time.sleep(sleep)
        res = client.write_coils(address=address, values=value, device_id=device_id)
        i += 1
    return i
