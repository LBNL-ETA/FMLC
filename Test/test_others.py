import sys
from os import path
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
import time
from FMLC.triggering import triggering
from FMLC.baseclasses import eFMU
from FMLC.stackedclasses import controller_stack

class testcontroller1(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True
    def compute(self):
        self.init= False
        self.output['c'] = self.input['a'] * self.input['b']
        return 'testcontroller1 did a computation!'


class testcontroller2(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True

    def compute(self):
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(0.2)
        return 'testcontroller2 did a computation!'

class testcontroller3(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True

    def compute(self):
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(1)
        return 'testcontroller3 did a computation!'

class testcontroller4(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True

    def compute(self):
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(10)
        return 'testcontroller4 did a computation!'

def test_input_errors():
    ##CASE1: not all inputs are set.
    controller = {}
    controller['forecast1'] = {'fun':testcontroller1, 'sampletime':0}
    controller['mpc1'] = {'fun':testcontroller2, 'sampletime':'forecast1'}
    controller['control1'] = {'fun':testcontroller1, 'sampletime':'mpc1'}
    controller['forecast2'] = {'fun':testcontroller3, 'sampletime':0}
    controller['forecast3'] = {'fun':testcontroller1, 'sampletime':0}

    mapping = {}
    mapping['forecast1_a'] = 10
    mapping['forecast1_b'] = 4
    mapping['forecast2_a'] = 20
    mapping['forecast2_b'] = 4
    mapping['forecast3_a'] = 30
    mapping['forecast3_b'] = 4
    mapping['mpc1_b'] = 'forecast1_a'
    mapping['control1_a'] = 'mpc1_c'
    try:
        controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True, timeout=2)
        AssertionError
    except KeyError as e:
        assert 'mapping' in str(e)
    except:
        AssertionError

    ##CASE1: not all given inputs are valid inputs (extra inputs)
    controller = {}
    controller['forecast1'] = {'fun':testcontroller1, 'sampletime':0}
    controller['mpc1'] = {'fun':testcontroller2, 'sampletime':'forecast1'}
    controller['control1'] = {'fun':testcontroller1, 'sampletime':'mpc1'}
    controller['forecast2'] = {'fun':testcontroller3, 'sampletime':0}
    controller['forecast3'] = {'fun':testcontroller1, 'sampletime':0}

    mapping = {}
    mapping['forecast1_d'] = 10
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
    try:
        controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True, timeout=2)
        AssertionError
    except KeyError as e:
        assert 'parameter' in str(e)
    except:
        AssertionError

def test_init_once():
    controller = {}
    controller['forecast1'] = {'fun':testcontroller1, 'sampletime':0}

    mapping = {}
    mapping['forecast1_a'] = 10
    mapping['forecast1_b'] = 4
    controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True, timeout=2)

    obj = controller.controller_objects['forecast1']
    for i in range(3):
        controller.query_control(time.time())
        assert controller.controller_objects['forecast1'] is obj
