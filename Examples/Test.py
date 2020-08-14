#!/usr/bin/env python
# coding: utf-8

# # Environment

# In[2]:


if __package__ is None:
    import sys
    from os import path
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from FMLC.triggering import triggering
from FMLC.baseclasses import eFMU
from FMLC.stackedclasses import controller_stack


# In[ ]:


import logging
logger = logging.getLogger(__name__)
'''
import matplotlib.pyplot as plt
%matplotlib inline
'''
logger.setLevel(logging.DEBUG)


# # Triggering Class

# In[ ]:


import time


# In[ ]:


if __name__ == '__main__':
    ts = {} 
    ts['main'] = 0.5 # seconds
    ts['print'] = 1 # seconds

    trigger_test = triggering(ts)
    now_init = time.time()
    now = now_init
    while now < now_init+2:
        now = time.time()
        if now >= trigger_test.trigger['main']:
            print ('Main triggered', now)
            trigger_test.refresh_trigger('main', now)
        if now >= trigger_test.trigger['print']:
            print ('Print triggered', now)
            trigger_test.refresh_trigger('print', now)


# # Controller Base Class (eFMU)

# In[ ]:


class testcontroller1(eFMU):
    def __init__(self):
        self.input = {'a':None,'b':None}
        self.output = {'c':None}
    def compute(self):
        self.output['c'] = self.input['a'] * self.input['b']


# In[ ]:


if __name__ == '__main__':
    # Test controller
    testcontroller = testcontroller1()
    # Get all variables
    variables = testcontroller.get_model_variables()
    # Makeup some inputs
    inputs = {}
    for var in variables:
        inputs[var] = 2
    # Query controller
    print ('Log-message', testcontroller.do_step(inputs=inputs))
    print ('Input', testcontroller.input)
    print ('Output', testcontroller.output)


# # Controller Stack Class (multi-thread)

# In[ ]:


from datetime import datetime


# In[ ]:


class testcontroller2(eFMU):
    def __init__(self):
        self.input = {'a':None,'b':None}
        self.output = {'c':None}
        self.init = True
    def compute(self):
        print ('***Init2', self.init)
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(0.2)
        
class testcontroller3(eFMU):
    def __init__(self):
        self.input = {'a':None,'b':None}
        self.output = {'c':None}
        self.init = True
    def compute(self):
        print ('***Init3', self.init)
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        time.sleep(1)


# In[ ]:


if __name__ == '__main__':
    controller = {}
    controller['forecast1'] = {'fun':testcontroller2, 'sampletime':1}
    controller['mpc1'] = {'fun':testcontroller3, 'sampletime':'forecast1'}
    controller['control1'] = {'fun':testcontroller1, 'sampletime':'mpc1'}
    controller['forecast2'] = {'fun':testcontroller2, 'sampletime':1}
    controller['forecast3'] = {'fun':testcontroller1, 'sampletime':2}

    # Initialize controller
    controller = controller_stack(controller, tz=-8, debug=True, parallel=True)
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
    for i in range(40):
        #print i
        #if i == 2: write_db({'dev_debug':False}, controller.database.address); print 'Debug=False'
        #if i == 2: controller.set_input({'ctrl1_b':10})
        #if i == 4: print controller.log_to_df(which=['input'])['ctrl1']; controller.clear_logs(); print 'Clear Logs'
        controller.query_control(time.time())
        # if i <= 3: print (i, controller.data_db['mpc1_c'], controller.data_db['control1_c'])
        #print datetime.now(), 'DB executed controller', controller.data_db['executed_controller'], \
        #        'DB running controller', controller.data_db['running_controller']
        # print ('.')
        # print ('\033[F')
        time.sleep(0.1)


    #print '\n\nInput\n', controller.log_to_df(which=['input'])['mpc1']
    #print '\n\nLog\n', controller.log_to_df()
    time.sleep(2)
    controller.shutdown()


# In[ ]:


class testcontroller4(eFMU):
    def __init__(self):
        self.input = {'a':None,'b':None}
        self.output = {'c':None}
        self.init = True
        self.counter = 0
    def compute(self):
        print ('***Init4', self.init, self.counter)
        self.init = False
        self.output['c'] = self.input['a'] * self.input['b']
        self.counter += 1
        time.sleep(0.5)


# In[ ]:


if __name__ == '__main__':

    controller = {}
    controller['forecast1'] = {'fun':testcontroller4, 'sampletime':1}
    controller['mpc1'] = {'fun':testcontroller4, 'sampletime':'forecast1'}
    controller['control1'] = {'fun':testcontroller4, 'sampletime':'mpc1'}
    controller['forecast2'] = {'fun':testcontroller2, 'sampletime':1}
    controller['forecast3'] = {'fun':testcontroller1, 'sampletime':2}

    # Initialize controller
    controller = controller_stack(controller, tz=-8, debug=True, parallel=True)
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
    for i in range(40):
        #print i
        #if i == 2: write_db({'dev_debug':False}, controller.database.address); print 'Debug=False'
        #if i == 2: controller.set_input({'ctrl1_b':10})
        #if i == 4: print controller.log_to_df(which=['input'])['ctrl1']; controller.clear_logs(); print 'Clear Logs'
        controller.query_control(time.time())
        #if i <= 3: print i, controller.data_db['mpc1_c'], controller.data_db['control1_c']
        #print datetime.now(), 'DB executed controller', controller.data_db['executed_controller'], \
        #        'DB running controller', controller.data_db['running_controller']
        print ('.')
        time.sleep(0.2)


    #print '\n\nInput\n', controller.log_to_df(which=['input'])['mpc1']
    print ('\n\nLog\n', controller.log_to_df())
    time.sleep(2)
    controller.shutdown()


# In[ ]:




