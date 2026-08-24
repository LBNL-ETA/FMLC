# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Dummy eFMU modules.
"""

import time
import json

from fmlc.baseclasses import eFMU


class Multiplier(eFMU):
    """Computes c = a * b after an optional delay."""

    def __init__(self):
        super().__init__()
        self.input = {'a': None, 'b': None, 'delay': None, 'timeout': None}
        self.output = {'c': None}
        self.init = False

    def compute(self):
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        delay = self.input['delay']
        if delay:
            time.sleep(float(delay))
        return 'Done.'

class TimeoutDummy(eFMU):
    """Sleeps past its timeout to test stack timeout/restart behaviour."""

    def __init__(self):
        super().__init__()
        self.input = {'delay': None, 'timeout': None}
        self.output = {'a': None}

    def compute(self):
        delay = self.input['delay'] if self.input['delay'] else 2.1
        time.sleep(float(delay))
        self.output['a'] = 'seen due to late computation'
        return 'Done.'

class GetData(eFMU):
    """Simulates reading data from an external source."""

    def __init__(self):
        super().__init__()
        self.input = {'mode': None}
        self.output = {'data': None, 'duration': None}
        self.init = False

    def compute(self):
        st = time.time()
        msg = ''
        out_data = None

        time.sleep(0.05) # simulate I/O delay

        try:
            payload = {
                'timestamp': time.time(),
                'temperature': round(20.0 + 5.0 * (time.time() % 1), 2),
                'power_kw': round(50.0 + 10.0 * (time.time() % 1), 2),
                'mode': self.input['mode'],
            }
            out_data = json.dumps(payload)
            if not self.init:
                self.init = True
        except Exception as e: # pylint: disable=broad-except
            msg += str(e)

        self.output['data'] = out_data
        self.output['duration'] = round(time.time() - st, 4)

        if not msg:
            return 'Done.'
        return msg

class DoControl(eFMU):
    """Simulates a control computation step."""

    def __init__(self):
        super().__init__()
        self.input = {'data': None}
        self.output = {'control': None, 'duration': None}
        self.init = False

    def compute(self):
        st = time.time()
        msg = ''
        out_control = None

        msg += self.check_data(self.input['data'], True)

        try:
            if not msg:
                data = json.loads(self.input['data'])
                if not self.init:
                    self.init = True
                setpoint = round(data['power_kw'] * 0.9, 2) # simple control
                control_action = {
                    'setpoint_kw': setpoint,
                    'timestamp': data['timestamp'],
                }
                out_control = json.dumps(control_action)
        except Exception as e: # pylint: disable=broad-except
            msg += str(e)

        self.output['control'] = out_control
        self.output['duration'] = round(time.time() - st, 4)

        if not msg:
            return 'Done.'
        return msg

class SetData(eFMU):
    """Simulates sending a control action."""

    def __init__(self):
        super().__init__()
        self.input = {'control': None}
        self.output = {'status': None, 'duration': None}
        self.init = False

    def compute(self):
        st = time.time()
        msg = ''
        out_status = None

        msg += self.check_data(self.input['control'], True)

        try:
            if not msg:
                control = json.loads(self.input['control'])
                if not self.init:
                    self.init = True
                time.sleep(0.02) # simulate write delay
                out_status = (
                    f"OK: setpoint={control['setpoint_kw']} kW written at "
                    f"{time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        except Exception as e: # pylint: disable=broad-except
            msg += str(e)

        self.output['status'] = out_status
        self.output['duration'] = round(time.time() - st, 4)

        if not msg:
            return 'Done.'
        return msg
