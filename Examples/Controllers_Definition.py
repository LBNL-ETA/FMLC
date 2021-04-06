import os
import sys
import time
import numpy as np
import pandas as pd
import datetime as dtm
import matplotlib.pyplot as plt

# Import FMLC
#sys.path.append(r'C:\Users\Christoph\Documents\PublicRepos\FMLC')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath("Test.ipynb"))))
from FMLC.triggering import triggering
from FMLC.baseclasses import eFMU
from FMLC.stackedclasses import controller_stack

"""
Dummy modules for MicroGridController example.
"""
class communication_dummy(eFMU):
    def __init__(self):
        self.input = {'mode':None,}
        self.output = {'data':None}
    def compute(self):
        now = dtm.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ts = pd.DataFrame(index=pd.date_range(now, now+dtm.timedelta(days=1), freq='1H'))
        if self.input['mode'] == 'get_weather':
            ts['OAT'] = np.random.randint(15, 30, size=len(ts)) # Outside Temperature, in C
            self.output['data'] = ts.to_json()
            return 'Generated dummy weather forecast.'
        elif self.input['mode'] == 'get_iso':
            ts['Price'] = np.random.randint(0, 30, size=len(ts)) # AS Price, in $/MWh
            self.output['data'] = ts.to_json()
            return 'Generated dummy price forecast.'
        elif self.input['mode'] == 'set_iso':
            return 'Sent market bids.'
        elif self.input['mode'] == 'get_scada':
            self.output['data'] = {'P_pv': 10, 'P_load': 15, 'P_batt': 0}
            return 'Read scada setpoints.'
        elif self.input['mode'] == 'set_scada':
            return 'Set scada setpoints.'

class forecaster_dummy(eFMU):
    def __init__(self):
        self.input = {'wf':None,'scada':None}
        self.output = {'data':None}
    def compute(self):
        wf = pd.read_json(self.input['wf'])
        wf['P_load'] = np.random.randint(5, 30, size=len(wf)) # Load, in kW
        wf['P_pv'] = np.sin(wf.index.hour/3-2.5) * 10
        wf['P_pv'] = wf['P_pv'].mask(wf['P_pv']<0, 0)
        # Scada
        res_cols = ['P_load','P_pv']
        for c in res_cols:
            wf.loc[wf.index[0], c] = self.input['scada'][c]
        self.output['data'] = wf[res_cols].to_json()
        return 'Computed forecasts.'
        
class controller_dummy(eFMU):
    def __init__(self):
        self.input = {'data':None}
        self.output = {'control':None}
    def compute(self):
        if self.input['data'] == -1:
            return 'Wariting to initialize.'            
        data = pd.read_json(self.input['data'])
        control = {'P_batt': data['P_load'] - data['P_pv']}
        self.output['control'] = control
        return 'Computed control.'
"""
Controllers for test.ipynb example.
"""
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

class timeoutcontroller(eFMU):
    def __init__(self):
        self.input = {}
        self.output = {"a" : "default"}
    
    def compute(self):
        time.sleep(2.1)
        self.output['a'] = "seen due to late computation"
        return 'Compute ok'