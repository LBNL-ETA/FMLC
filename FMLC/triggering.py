'''
This module is part of the FMLC package.
https://github.com/LBNL-ETA/FMLC
'''

import time

class triggering(object):
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
                                                integer=self.ts[k]>1)

    def refresh_trigger(self, name, now=time.time()):
        '''
        Refresh the trigger.
        
        Input
        -----
        name (str): Name of the trigger.
        now (time.time): Current time to refresh. (Default = time.time())
        '''
        self.trigger[name] = self._get_trigger(self.ts[name], now, mode='next',
                                               integer=self.ts[name]>1)

    def _get_trigger(self, ts, now=time.time(), mode='next', integer=True):
        '''
        Get the current trigger value.
        
        Input
        -----
        ts (float): The timestep of the trigger.
        now (time.time): Current time to refresh. (Default = time.time())
        mode (str): Mode of calculation, either "next" or "prev".
            (Default = "next")
        integer (bool): Round seconds to full integer.
            Recommended when ts > 10 s. (Defualt = True)
            
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
    ts = {} 
    ts['main'] = 0.5 # seconds
    ts['print'] = 1
    print('"Main" should be triggered every {} s.'.format(ts['main']))
    print('"Print" should be triggered every {} s.'.format(ts['print']))
    trigger_test = triggering(ts)
    now_init = time.time()
    now = now_init
    while now < now_init+3:
        now = time.time()
        if now >= trigger_test.trigger['main']:
            print('Main triggered\t{}'.format(round(now, 2)))
            trigger_test.refresh_trigger('main', now)
        if now >= trigger_test.trigger['print']:
            print('Print triggered\t{}'.format(round(now, 2)))
            trigger_test.refresh_trigger('print', now)