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
import warnings

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
def test_sampletime():
    '''This tests if the sample time is working properly'''
    controller = {}
    controller['forecast1'] = {'fun': testcontroller1, 'sampletime': 3}
    mapping = {}
    mapping['forecast1_a'] = 10
    mapping['forecast1_b'] = 4
    controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True)
    now = time.time()
    while time.time() - now < 10:
        controller.query_control(time.time())
    df = pd.DataFrame(controller.log_to_df()['forecast1'])
    assert df.shape[0] == 5

    for i in (np.diff(df.index) / np.timedelta64(1, 's'))[1:]:
        assert(math.isclose(i, 3, rel_tol=0.01))

def test_normal():
    controller = {}
    controller['forecast1'] = {'fun':testcontroller1, 'sampletime':1}
    controller['mpc1'] = {'fun':testcontroller2, 'sampletime':'forecast1'}
    controller['control1'] = {'fun':testcontroller1, 'sampletime':'mpc1'}
    controller['forecast2'] = {'fun':testcontroller3, 'sampletime':2}
    controller['forecast3'] = {'fun':testcontroller1, 'sampletime': 1}

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
    controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True, timeout=2, workers=100)

    controller.run_query_control_for(5)
    
    df1 = pd.DataFrame(controller.log_to_df()['forecast1'])
    df2 = pd.DataFrame(controller.log_to_df()['forecast2'])
    df3 = pd.DataFrame(controller.log_to_df()['forecast3'])
    df4 = pd.DataFrame(controller.log_to_df()['mpc1'])
    df5 = pd.DataFrame(controller.log_to_df()['control1'])
    
    # Check number of records
    assert df1.shape[0] == 7
    assert df2.shape[0] == 4
    assert df3.shape[0] == 7
    assert df4.shape[0] == 7
    assert df5.shape[0] == 7

    # Check contents of records
    assert pd.isna(df1['a'][0])
    assert pd.isna(df1['b'][0])
    assert pd.isna(df1['c'][0])
    assert pd.isna(df2['a'][0])
    assert pd.isna(df2['b'][0])
    assert pd.isna(df2['c'][0])
    assert pd.isna(df3['a'][0])
    assert pd.isna(df3['b'][0])
    assert pd.isna(df3['c'][0])
    assert pd.isna(df4['a'][0])
    assert pd.isna(df4['b'][0])
    assert pd.isna(df4['c'][0])
    assert pd.isna(df5['a'][0])
    assert pd.isna(df5['b'][0])
    assert pd.isna(df5['c'][0])
    assert list(df1['a'])[1:] == [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    assert list(df1['b'])[1:] == [4.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    assert list(df1['c'])[1:] == [40.0, 40.0, 40.0, 40.0, 40.0, 40.0]
    assert list(df2['a'])[1:] == [20.0, 20.0, 20.0]
    assert list(df2['b'])[1:] == [4.0, 4.0, 4.0]
    assert list(df2['c'])[1:] == [80.0, 80.0, 80.0]
    assert list(df3['a'])[1:] == [30.0, 30.0, 30.0, 30.0, 30.0, 30.0]
    assert list(df3['b'])[1:] == [4.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    assert list(df3['c'])[1:] == [120.0, 120.0, 120.0, 120.0, 120.0, 120.0]
    assert list(df4['a'])[1:] == [40.0, 40.0, 40.0, 40.0, 40.0, 40.0]
    assert list(df4['b'])[1:] == [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    assert list(df4['c'])[1:] == [400.0, 400.0, 400.0, 400.0, 400.0, 400.0]
    assert list(df5['a'])[1:] == [400.0, 400.0, 400.0, 400.0, 400.0, 400.0]
    assert list(df5['b'])[1:] == [40.0, 40.0, 40.0, 40.0, 40.0, 40.0]
    assert list(df5['c'])[1:] == [16000.0, 16000.0, 16000.0, 16000.0, 16000.0, 16000.0]
    assert list(df1['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
    assert list(df2['Logging']) == ['Initialize', 'testcontroller3 did a computation!', 'testcontroller3 did a computation!', 'testcontroller3 did a computation!']
    assert list(df3['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
    assert list(df4['Logging']) == ['Initialize', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!']
    assert list(df5['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']

def test_stuckController():
    '''This tests if the timeout controllers can be caught'''
    ## CASE1: mpc1 stuck
    controller = {}
    controller['forecast1'] = {'fun':testcontroller1, 'sampletime':1}
    controller['mpc1'] = {'fun':testcontroller4, 'sampletime':'forecast1'}
    controller['control1'] = {'fun':testcontroller1, 'sampletime':'mpc1'}
    controller['forecast2'] = {'fun':testcontroller1, 'sampletime':1}
    controller['forecast3'] = {'fun':testcontroller1, 'sampletime':1}

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
    controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True, timeout=0.5, workers=100)
    
    # Catch warning.
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        controller.run_query_control_for(2)
        assert len(w) == 3
        assert "timeout" in str(w[-1].message)
    df1 = pd.DataFrame(controller.log_to_df()['forecast1'])
    df2 = pd.DataFrame(controller.log_to_df()['forecast2'])
    df3 = pd.DataFrame(controller.log_to_df()['forecast3'])
    df4 = pd.DataFrame(controller.log_to_df()['mpc1'])
    df5 = pd.DataFrame(controller.log_to_df()['control1'])

    # Check number of records
    assert df1.shape[0] == 4
    assert df2.shape[0] == 4
    assert df3.shape[0] == 4
    #assert df4.shape[0] == 1
    assert df5.shape[0] == 1
    #assert len(df4.columns) == 1
    assert len(df5.columns) == 1
    # Check contents of records
    assert pd.isna(df1['a'][0])
    assert pd.isna(df1['b'][0])
    assert pd.isna(df1['c'][0])
    assert pd.isna(df2['a'][0])
    assert pd.isna(df2['b'][0])
    assert pd.isna(df2['c'][0])
    assert pd.isna(df3['a'][0])
    assert pd.isna(df3['b'][0])
    assert pd.isna(df3['c'][0])
    assert list(df1['a'])[1:] == [10.0, 10.0, 10.0]
    assert list(df1['b'])[1:] == [4.0, 4.0, 4.0]
    assert list(df1['c'])[1:] == [40.0, 40.0, 40.0]
    assert list(df2['a'])[1:] == [20.0, 20.0, 20.0]
    assert list(df2['b'])[1:] == [4.0, 4.0, 4.0]
    assert list(df2['c'])[1:] == [80.0, 80.0, 80.0]
    assert list(df3['a'])[1:] == [30.0, 30.0, 30.0]
    assert list(df3['b'])[1:] == [4.0, 4.0, 4.0]
    assert list(df3['c'])[1:] == [120.0, 120.0, 120.0]
    assert list(df1['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
    assert list(df2['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
    assert list(df3['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
    #assert list(df4['Logging']) == ['Initialize']
    assert list(df5['Logging']) == ['Initialize']
    

    ##CASE2: mpc1 and forcast2 stuck
    controller = {}
    controller['forecast1'] = {'fun':testcontroller1, 'sampletime':1}
    controller['mpc1'] = {'fun':testcontroller3, 'sampletime':'forecast1'}
    controller['control1'] = {'fun':testcontroller1, 'sampletime':'mpc1'}
    controller['forecast2'] = {'fun':testcontroller3, 'sampletime':1}
    controller['forecast3'] = {'fun':testcontroller1, 'sampletime':1}

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
    controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=True, timeout=0.8, workers=100)
    
    #Catch Warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        controller.run_query_control_for(5)
        assert len(w) == 12
        for m in w:
            assert "timeout" in str(m.message)
    


    df1 = pd.DataFrame(controller.log_to_df()['forecast1'])
    df2 = pd.DataFrame(controller.log_to_df()['forecast2'])
    df3 = pd.DataFrame(controller.log_to_df()['forecast3'])
    df4 = pd.DataFrame(controller.log_to_df()['mpc1'])
    df5 = pd.DataFrame(controller.log_to_df()['control1'])

    # Check number of records
    assert df1.shape[0] == 7 
    #assert df2.shape[0] == 1
    assert df3.shape[0] == 7
    #assert df4.shape[0] == 1
    assert df5.shape[0] == 1
    #assert len(df2.columns) == 1
    #assert len(df4.columns) == 1
    assert len(df5.columns) == 1
    # Check contents of records
    assert pd.isna(df1['a'][0])
    assert pd.isna(df1['b'][0])
    assert pd.isna(df1['c'][0])
    assert pd.isna(df3['a'][0])
    assert pd.isna(df3['b'][0])
    assert pd.isna(df3['c'][0])
    assert list(df1['a'])[1:] == [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    assert list(df1['b'])[1:] == [4.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    assert list(df1['c'])[1:] == [40.0, 40.0, 40.0, 40.0, 40.0, 40.0]
    assert list(df3['a'])[1:] == [30.0, 30.0, 30.0, 30.0, 30.0, 30.0]
    assert list(df3['b'])[1:] == [4.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    assert list(df3['c'])[1:] == [120.0, 120.0, 120.0, 120.0, 120.0, 120.0]
    assert list(df1['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
    #assert list(df2['Logging']) == ['Initialize']
    assert list(df3['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
    #assert list(df4['Logging']) == ['Initialize']
    assert list(df5['Logging']) == ['Initialize']

def test_serial():
    controller = {}
    controller['forecast1'] = {'fun':testcontroller1, 'sampletime':1}
    controller['mpc1'] = {'fun':testcontroller2, 'sampletime':'forecast1'}
    controller['control1'] = {'fun':testcontroller1, 'sampletime':'mpc1'}
    controller['forecast2'] = {'fun':testcontroller3, 'sampletime':1}
    controller['forecast3'] = {'fun':testcontroller1, 'sampletime':1}

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
    controller = controller_stack(controller, mapping, tz=-8, debug=True, parallel=False, timeout=2)

    for i in range(6):
        controller.query_control(time.time())
        time.sleep(1.5)
    
    df1 = pd.DataFrame(controller.log_to_df()['forecast1'])
    df2 = pd.DataFrame(controller.log_to_df()['forecast2'])
    df3 = pd.DataFrame(controller.log_to_df()['forecast3'])
    df4 = pd.DataFrame(controller.log_to_df()['mpc1'])
    df5 = pd.DataFrame(controller.log_to_df()['control1'])
    
    # Check number of records
    assert df1.shape[0] == 7
    assert df2.shape[0] == 7
    assert df3.shape[0] == 7
    assert df4.shape[0] == 7
    assert df5.shape[0] == 7

    # Check contents of records
    assert pd.isna(df1['a'][0])
    assert pd.isna(df1['b'][0])
    assert pd.isna(df1['c'][0])
    assert pd.isna(df2['a'][0])
    assert pd.isna(df2['b'][0])
    assert pd.isna(df2['c'][0])
    assert pd.isna(df3['a'][0])
    assert pd.isna(df3['b'][0])
    assert pd.isna(df3['c'][0])
    assert pd.isna(df4['a'][0])
    assert pd.isna(df4['b'][0])
    assert pd.isna(df4['c'][0])
    assert pd.isna(df5['a'][0])
    assert pd.isna(df5['b'][0])
    assert pd.isna(df5['c'][0])
    assert list(df1['a'])[1:] == [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    assert list(df1['b'])[1:] == [4.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    assert list(df1['c'])[1:] == [40.0, 40.0, 40.0, 40.0, 40.0, 40.0]
    assert list(df2['a'])[1:] == [20.0, 20.0, 20.0, 20.0, 20.0, 20.0]
    assert list(df2['b'])[1:] == [4.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    assert list(df2['c'])[1:] == [80.0, 80.0, 80.0, 80.0, 80.0, 80.0]
    assert list(df3['a'])[1:] == [30.0, 30.0, 30.0, 30.0, 30.0, 30.0]
    assert list(df3['b'])[1:] == [4.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    assert list(df3['c'])[1:] == [120.0, 120.0, 120.0, 120.0, 120.0, 120.0]
    assert list(df4['a'])[1:] == [40.0, 40.0, 40.0, 40.0, 40.0, 40.0]
    assert list(df4['b'])[1:] == [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    assert list(df4['c'])[1:] == [400.0, 400.0, 400.0, 400.0, 400.0, 400.0]
    assert list(df5['a'])[1:] == [400.0, 400.0, 400.0, 400.0, 400.0, 400.0]
    assert list(df5['b'])[1:] == [40.0, 40.0, 40.0, 40.0, 40.0, 40.0]
    assert list(df5['c'])[1:] == [16000.0, 16000.0, 16000.0, 16000.0, 16000.0, 16000.0]
    assert list(df1['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
    assert list(df2['Logging']) == ['Initialize', 'testcontroller3 did a computation!', 'testcontroller3 did a computation!', 'testcontroller3 did a computation!', 'testcontroller3 did a computation!', 'testcontroller3 did a computation!', 'testcontroller3 did a computation!']
    assert list(df3['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
    assert list(df4['Logging']) == ['Initialize', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!', 'testcontroller2 did a computation!']
    assert list(df5['Logging']) == ['Initialize', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!', 'testcontroller1 did a computation!']
