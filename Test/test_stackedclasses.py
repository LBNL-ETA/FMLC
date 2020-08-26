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

    def compute(self):
        self.output['c'] = self.input['a'] * self.input['b']


class testcontroller2(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True

    def compute(self):
        print('***Init2', self.init)
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(0.2)


class testcontroller3(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True

    def compute(self):
        print('***Init3', self.init)
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(1)

class testcontroller4(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}
        self.init = True

    def compute(self):
        print('***Init3', self.init)
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(10)

def test_sampletime():
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