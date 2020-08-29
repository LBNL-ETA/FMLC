import sys
from os import path
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
import time
from FMLC.triggering import triggering
from FMLC.baseclasses import eFMU
from FMLC.stackedclasses import controller_stack
import pandas as pd
import numpy as np
import math


class testcontroller1(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True
    def compute(self):
        self.init= False
        self.output['c'] = self.input['a'] * self.input['b']


class testcontroller2(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True

    def compute(self):
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(0.2)


class testcontroller3(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True

    def compute(self):
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(1)

class testcontroller4(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True

    def compute(self):
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(10)

def test_sampletime():
    print("Testing sample time:")
    controller = {}
    controller['forecast1'] = {'fun': testcontroller1, 'sampletime': 3}
    controller = controller_stack(controller, tz=-8, debug=True, parallel=True)
    mapping = {}
    mapping['forecast1_a'] = 10
    mapping['forecast1_b'] = 4
    controller.initialize(mapping)
    now = time.time()
    while time.time() - now < 10:
        controller.query_control(time.time())
    df = pd.DataFrame(controller.log_to_df()['forecast1'])
    assert df.shape[0] == 5

    for i in (np.diff(df.index) / np.timedelta64(1, 's'))[1:]:
        assert(math.isclose(i, 3, rel_tol=0.01))

def test_stuckController():
    print("Testing stuck controllers:")
    ## mpc1 stuck
    controller = {}
    controller['forecast1'] = {'fun':testcontroller1, 'sampletime':0}
    controller['mpc1'] = {'fun':testcontroller4, 'sampletime':'forecast1'}
    controller['control1'] = {'fun':testcontroller1, 'sampletime':'mpc1'}
    controller['forecast2'] = {'fun':testcontroller1, 'sampletime':0}
    controller['forecast3'] = {'fun':testcontroller1, 'sampletime':0}
    controller = controller_stack(controller, tz=-8, debug=True, parallel=True, timeout=0.5)

    mapping = {}
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
    controller.initialize(mapping)

    for i in range(3):
        controller.query_control(time.time())
        time.sleep(1)
    df1 = pd.DataFrame(controller.log_to_df()['forecast1'])
    df2 = pd.DataFrame(controller.log_to_df()['forecast2'])
    df3 = pd.DataFrame(controller.log_to_df()['forecast3'])
    df4 = pd.DataFrame(controller.log_to_df()['mpc1'])
    df5 = pd.DataFrame(controller.log_to_df()['control1'])

    assert df1.shape[0] == 2
    assert df2.shape[0] == 3
    assert df3.shape[0] == 3
    assert df4.shape[0] == 1
    assert df5.shape[0] == 1
    assert len(df4.columns) == 1
    assert len(df5.columns) == 1
    assert controller.running_controllers.__str__() == '[]'
    assert controller.executed_controllers.__str__() == "['forecast2', 'forecast3']"
    assert controller.timeout_controllers.__str__() == '[]'

    