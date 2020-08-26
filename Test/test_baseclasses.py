import sys
from os import path
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from FMLC.baseclasses import eFMU


def test_controller1():
    class testcontroller1(eFMU):
        def __init__(self):
            self.input = {'a': None, 'b': None}
            self.output = {'c': None}

        def compute(self):
            self.output['c'] = self.input['a'] * self.input['b']

    testcontroller = testcontroller1()
    variables = list(testcontroller.get_model_variables())
    inputs = {}
    for var in variables:
        inputs[var] = 3
    testcontroller.do_step(inputs=inputs)

    assert variables == ['a', 'b']
    assert testcontroller.get_input() == {'a': 3, 'b': 3}
    assert testcontroller.get_output() == {'c': 9}
    assert testcontroller.get_var('output') == {'c': 9}
