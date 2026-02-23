# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Triggering module.
"""

# pylint: disable=invalid-name, redefined-outer-name, too-few-public-methods

import time

class triggering:
    '''
    Class to handle internal triggering of models.
    '''
    def __init__(self, ts, init_now=False):
        '''
        Input
        -----
        ts (dict): Timesteps for triggering with timestep in seconds.
        init_now (bool): Initialize with current timestep. This is not 
            recommended as timesteps are not aligned. Good for testing and 
            debugging. (Default = False)
        '''
        self.ts = ts
        self.init_now = init_now
        self._initialize_all_trigger()

    def _initialize_all_trigger(self):
        '''
        Initializaiton of all triggers.        
        '''
        now = time.time()
        self.trigger = {}
        mode = 'prev' if self.init_now else 'next'
        for k in self.ts.keys():
            self.trigger[k] = self._get_trigger(self.ts[k], now, mode=mode,
                                                integer=(self.ts[k]%1) == 0)

    def refresh_trigger(self, name, now=time.time()):
        '''
        Refresh the trigger.
        
        Input
        -----
        name (str): Name of the trigger.
        now (time.time): Current time to refresh. (Default = time.time())
        '''
        self.trigger[name] = self._get_trigger(self.ts[name], now, mode='next',
                                               integer=(self.ts[name]%1) == 0)

    def _get_trigger(self, ts, now=time.time(), mode='next', integer=False):
        '''
        Get the current trigger value.
        
        Input
        -----
        ts (float): The timestep of the trigger.
        now (time.time): Current time to refresh. (Default = time.time())
        mode (str): Mode of calculation, either "next" or "prev".
            (Default = "next")
        integer (bool): Round seconds to full integer.
            Recommended when ts > 10 s. (Defualt = False)
            
        Return
        ------
        trigger (float): Next trigger as timestamp.
        '''
        trigger = round(now/ts) * ts
        if integer:
            trigger = int(trigger)
        if mode == 'next':
            trigger = trigger + ts
        elif mode == 'prev':
            trigger = trigger - ts
        else:
            print('ERROR: "mode" must be "next" or "prev"')
        return trigger

if __name__ == '__main__':
    ts_config = {}
    ts_config['main'] = 0.5 # seconds
    ts_config['print'] = 1
    print(f'"Main" should be triggered every {ts_config["main"]} s.')
    print(f'"Print" should be triggered every {ts_config["print"]} s.')
    trigger_test = triggering(ts_config)
    now_init = time.time()
    now = now_init
    while now < now_init+3:
        now = time.time()
        if now >= trigger_test.trigger['main']:
            print(f'Main triggered\t{round(now, 2)}')
            trigger_test.refresh_trigger('main', now)
        if now >= trigger_test.trigger['print']:
            print(f'Print triggered\t{round(now, 2)}')
            trigger_test.refresh_trigger('print', now)
