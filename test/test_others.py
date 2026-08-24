import sys
import time
from os import path

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from fmlc.triggering import triggering
from fmlc.stackedclasses import controller_stack
from fmlc.modules.dummy_modules import Multiplier

def test_input_errors():
    ##CASE1: not all inputs are set.
    controller = {}
    controller['forecast1'] = {'function': Multiplier, 'sampletime':0}
    controller['mpc1'] = {'function': Multiplier, 'sampletime':'forecast1'}
    controller['control1'] = {'function': Multiplier, 'sampletime':'mpc1'}
    controller['forecast2'] = {'function': Multiplier, 'sampletime':0}
    controller['forecast3'] = {'function': Multiplier, 'sampletime':0}

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
        controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True)
        AssertionError
    except KeyError as e:
        assert 'mapping' in str(e)
    except:
        AssertionError

    ##CASE1: not all given inputs are valid inputs (extra inputs)
    controller = {}
    controller['forecast1'] = {'function': Multiplier, 'sampletime':0}
    controller['mpc1'] = {'function': Multiplier, 'sampletime':'forecast1'}
    controller['control1'] = {'function': Multiplier, 'sampletime':'mpc1'}
    controller['forecast2'] = {'function': Multiplier, 'sampletime':0}
    controller['forecast3'] = {'function': Multiplier, 'sampletime':0}

    mapping = {}
    mapping['forecast1_d'] = 10  # invalid extra key
    mapping['forecast1_a'] = 10
    mapping['forecast1_b'] = 4
    mapping['forecast1_delay'] = None
    mapping['forecast1_timeout'] = None
    mapping['forecast2_a'] = 20
    mapping['forecast2_b'] = 4
    mapping['forecast2_delay'] = None
    mapping['forecast2_timeout'] = None
    mapping['forecast3_a'] = 30
    mapping['forecast3_b'] = 4
    mapping['forecast3_delay'] = None
    mapping['forecast3_timeout'] = None
    mapping['mpc1_a'] = 'forecast1_c'
    mapping['mpc1_b'] = 'forecast1_a'
    mapping['mpc1_delay'] = None
    mapping['mpc1_timeout'] = None
    mapping['control1_a'] = 'mpc1_c'
    mapping['control1_b'] = 'mpc1_a'
    mapping['control1_delay'] = None
    mapping['control1_timeout'] = None
    try:
        controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True)
        AssertionError
    except KeyError as e:
        assert 'parameter' in str(e)
    except:
        AssertionError

def test_init_once():
    controller = {}
    controller['forecast1'] = {'function': Multiplier, 'sampletime':0}

    mapping = {}
    mapping['forecast1_a'] = 10
    mapping['forecast1_b'] = 4
    mapping['forecast1_delay'] = None
    mapping['forecast1_timeout'] = None
    controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True)

    obj = controller.pworkers['forecast1']
    for i in range(3):
        controller.query_control(time.time())
        assert controller.pworkers['forecast1'] is obj
