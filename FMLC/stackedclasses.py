#! /usr/bin/env python

import time
import warnings

import pandas as pd
from copy import deepcopy as copy_dict
import logging

from .pythonDB.utility import PythonDB_wrapper, write_db, read_db

import multiprocessing as mp
from multiprocessing.managers import BaseManager


# Setup logger
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)

def log_to_db(name, ctrl, now, db_address):
    temp = {}
    for k, v in ctrl['input'][now].items():
        temp[name+'_'+k] = v
    for k, v in ctrl['output'][now].items():
        temp[name+'_'+k] = v
    write_db(temp, db_address)

def control_worker_manager(wid, name, now, db_address, debug, inputs, ctrl, executed_controller, running_controller, timeout_controller, timeout):
    ''' This function calls the actual control_worker function and looks for timeout'''

    p = mp.Process(target=control_worker, args=(wid, name, now, db_address, debug, inputs, ctrl, executed_controller, running_controller))
    p.start()
    p.join(timeout=timeout)
    if p.is_alive():
        p.terminate()
        timeout_controller.add(name)
    else:
        p.terminate()

def control_worker(wid, name, now, db_address, debug, inputs, ctrl, executed_controller, running_controller):
    #logger.debug('WORKER {!s} at {!s} with PID {!s} ctrl is {!s}'.format(name, now, mp.current_process(), ctrl))
    # Compute controller
    temp = {}
    temp['input'] = {}
    temp['input'][now] = inputs
    temp['log'] = {}
    temp['log'][now] = ctrl.do_step(inputs=inputs)
    if type(temp['log'][now]) != type([]):
        temp['log'][now] = [temp['log'][now]]
    temp['output'] = {}
    temp['output'][now] = copy_dict(ctrl.get_var('output'))
    temp['last'] = now
    ctrl.update_storage(temp)
    log_to_db(name, temp, now, db_address)
    executed_controller.add(name)
    running_controller.remove(name)
    #print('return control_worker: ', name)
    
def initialize_class(ctrl, data):
    ctrl.update_storage(data, init=True)

class controller_stack(object):
    def __init__(self, controller, tz=-8, debug=False, name='Zone1', parallel=True, debug_db=False, timeout=5):
        """
        Initialize the controller stack object.

        Input
        -----
        controller(dict): A dictionary of dictionaries.
                        example:
                        {
                        'forecast1': {'fun':testcontroller2, 'sampletime':1}
                        'mpc1': {'fun':testcontroller3, 'sampletime':'forecast1'}
                        'control1': {'fun':testcontroller1, 'sampletime':'mpc1'}
                        'forecast2': {'fun':testcontroller2, 'sampletime':1}
                        'forecast3': {'fun':testcontroller1, 'sampletime':2}
                        }

        tz(int): utc/GMT time zone
        debug(bool)
        name(str)
        parallel(bool)
        debug_db(bool)
        """
        self.controller = controller
        self.tz = tz
        self.debug = debug
        self.debug_db = debug_db
        self.name = name
        self.parallel = parallel
        self.timeout = timeout
        #self.init = True

    def initialize(self, mapping, now=time.time()):
        """
        A function to call initializers of the pythonDB, controller, mapping, and execution list.

        Input
        -----
        mapping(dict): Mapping of the inputs to the controllers' input variables.
            example:
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
        now(float): The time in seconds since the epoch.
        """
        self.db_mode = 'pythonDB'
        self.initialize_controller(now)
        self.initialize_database()
        self.initialize_mapping(mapping)
        self.generate_execution_list()


    def initialize_controller(self, now):
        """
        Initialize the controllers.

        Input
        -----
        now(float): The time in seconds since the epoch.

        """
        # Modify self.controllers to contain more information. Register the controllers on the BaseManager.
        for name, ctrl in self.controller.items():
            logger.debug('Add {} to BaseManager'.format(name))
            exec("BaseManager.register(name, ctrl['fun'])")
            ctrl['fun'] = ctrl['fun']()
            ctrl['last'] = 0
            ctrl['inputs'] = ctrl['fun'].input.keys()
            ctrl['outputs'] = ctrl['fun'].output.keys()
            ctrl['log'] = {}
            ctrl['input'] = {}
            ctrl['output'] = {}
            ctrl['log'][now] = ['Initialize']
            ctrl['input'][now] = {}
            ctrl['output'][now] = {}
            self.controller[name] = ctrl
        manager = BaseManager()
        manager.register('MyList', MyList)
        manager.start()
        self.running_controllers = manager.MyList()
        self.executed_controllers = manager.MyList()
        self.timeout_controllers = manager.MyList()

        # Initialize each controller's data storage with the enriched self.controller dictionaries.
        self.controller_objects = {}
        pool = []
        for name in list(self.controller.keys()):
            # Register controller processes
            exec('self.controller_objects[name] = manager.'+name+'()')
            # Initialize controller
            p = mp.Process(target=initialize_class, args=[self.controller_objects[name], self.controller[name]])
            pool.append(p)
            p.start()
        for p in pool:
            p.join()
        logger.debug(self.controller_objects)

    def initialize_database(self):
        """
        Initialize the database columns. Columns include input & output variables for each device, timezone, dev_debug,
        dev_nodename, and dev_parallel.

        """
        self.database = PythonDB_wrapper(self.name, self.db_mode)
        self.database.address = '127.0.0.1:'+str(self.database.port)
        db_columns = {}
        for name in sorted(self.controller.keys()):
            for i in self.controller[name]['inputs']:
                db_columns[name+'_'+i] = -1
            for o in self.controller[name]['outputs']:
                db_columns[name+'_'+o] = -1
        db_columns['timezone'] = self.tz
        db_columns['dev_debug'] = self.debug_db
        db_columns['dev_nodename'] = self.name
        db_columns['dev_parallel'] = self.parallel
        write_db(db_columns, self.database.address)
        logger.debug('SetupDB\n', read_db(self.database.address))

    def initialize_mapping(self, mapping):
        """
        Validate the input mapping.
        """
        m = list(mapping.keys())
        for name in sorted(self.controller.keys()):
            for c in self.controller[name]['inputs']:
                if name+'_'+c in m: m.remove(name+'_'+c)
                else: raise KeyError('{} not in mapping.'.format(name+'_'+c))
        if len(m) != 0:
            raise KeyError('{} not a control parameter.'.format(m))
        self.mapping = mapping
            
    def refresh_device_from_db(self):
        """
        refresh self.tz, self.debug, self.name from db
        """
        self.tz = int(self.data_db['timezone'])
        self.debug = bool(self.data_db['dev_debug'])
        self.name = str(self.data_db['dev_nodename'])
        #self.parallel = bool(self.data_db['dev_parallel'])
        
    def generate_execution_list(self):
        """
        Generate self.execution_list and self.execution_map.

        self.execution_list is a map of dictionaries. The keys are index numbers, and the values are dictionaries
        which the controllers with the same sample times are in the same dictionary.

        self.execution_map is a dictionary with controller names being the keys and the index of the dictionary which
        contains the controller in self.execution_list being the values.
        """
        self.execution_list = {}
        self.execution_map = {}
        all_controller = sorted(self.controller.keys())
        i = 0
        while len(all_controller) > 0:
            name = all_controller[0]
            ctrl = self.controller[name]
            if type(ctrl['sampletime']) == type(''):
                if ctrl['sampletime'] not in all_controller:
                    self.execution_list[self.execution_map[ctrl['sampletime']]]['controller'].append(name)
                    self.execution_map[name] = self.execution_map[ctrl['sampletime']]
                    all_controller.remove(name)
                else:
                    # Shuffle
                    all_controller.remove(name)
                    all_controller.append(name)
            else:
                self.execution_list[i] = {'controller':[name], 'next':0 + ctrl['sampletime'], 'running':False}
                self.execution_map[name] = i
                i += 1
                all_controller.remove(name)
        if self.debug:
            logger.debug('Execution list: {!s}'.format(self.execution_list))
            logger.debug('Execution map: {!s}'.format(self.execution_map))
        
    def query_control(self, now, return_db=False):
        self.read_from_db()
        for task in sorted(self.execution_list.keys()):
            queued = True
            # Updated on 2019/05/10: The main loop for execution is now handled by this while loop instead of the main trigger.
            while queued:
                # self.read_from_db()
                # CASE1: task is not running and a new step is needed.
                if not self.execution_list[task]['running'] and now >= self.execution_list[task]['next']:
                    name = self.execution_list[task]['controller'][0]
                    # Not running, start task
                    self.execution_list[task]['running'] = True
                    self.execution_list[task]['next'] = now + self.controller[self.execution_list[task]['controller'][0]]['sampletime']
                    # Do control
                    logger.debug('Executing Controller "{!s}"'.format(name))
                    ctrl = self.controller[name]
                    self.do_control(name, ctrl, now, parallel=self.parallel)
                    if self.parallel:
                        queued = False
                    else:
                        queued = True
                elif self.execution_list[task]['running']:
                    reset = False
                    # Check if next module to start
                    finished_controllers = []
                    for n in self.execution_list[task]['controller']:
                        if self.executed_controllers.contains(n):
                            finished_controllers.append(n) # Store executed controller in list
                        if self.timeout_controllers.contains(n):
                            # A controller got stuck.
                            self.timeout_controllers.remove(n)
                            if self.running_controllers.contains(n):
                                self.running_controllers.remove(n)
                            self.execution_list[task]['running'] = False
                            print('Controller timeout', n)
                            warnings.warn('Controller {} timeout'.format(n), Warning)
                            reset = True
                            break
                    if reset:
                        break
                    # CASE2: all subtasks in the task are already executed
                    if self.execution_list[task]['controller'][-1] in finished_controllers:
                        # Control option done
                        self.executed_controllers.remove(self.execution_list[task]['controller'][-1])
                        self.execution_list[task]['running'] = False
                    else:
                        if len(finished_controllers) == 1: # If one controller in list then next one to be spawn
                            subtask_id = self.execution_list[task]['controller'].index(finished_controllers[0])
                            self.executed_controllers.remove(finished_controllers[0]) # Clear the execution list
                            name = self.execution_list[task]['controller'][subtask_id+1]
                            ctrl = self.controller[name]
                            logger.debug('Executing Controller "{!s}"'.format(name))
                            self.do_control(name, ctrl, now, parallel=self.parallel)
                        elif len(finished_controllers) > 1:
                            warnings.warn('Multiple entiries of Controller in executed: {}. Resetting controller.'.format(finished_controllers), Warning)
                            for n in self.execution_list[task]['controller']:
                                if self.executed_controllers.contains(n):
                                    self.executed_controllers.remove_all(n)
                    queued = not self.parallel
                else:
                    queued = False
        #self.init = False
        #if self.debug: print 'Duration query_control:',time.time()-time_st
            
    def do_control(self, name, ctrl, now, parallel=False):
        """
        Input
        -----
        name(str)
        ctrl(dict)
        now(float)
        parallel(bool)
        """
        #self.controller.keys():
        #print self.controller_objects
        #print ('Doctrl', name)
        
        
        # Query controller
        logger.debug('QueryCTRL {} at {} ({})'.format(name, pd.to_datetime(now, unit='s')+pd.DateOffset(hours=self.tz), now))
        inputs = self.update_inputs(name, now)
        if parallel:
            #print self.controller
            #data = self.controller[name]
            ctrl = self.controller_objects[name]
            p = mp.Process(target=control_worker_manager, args=[1, name, now, self.database.address, self.debug, inputs, ctrl, self.executed_controllers, self.running_controllers, self.timeout_controllers, self.timeout])
            self.running_controllers.add(name)
            p.start()

            #print(name, " returned from do_control")
        else:
            ctrl['log'][now] = ctrl['fun'].do_step(inputs=ctrl['input'][now])
            ctrl['output'][now] = copy_dict(ctrl['fun'].output)
            ctrl['last'] = now
            log_to_db(name, ctrl, now, self.database.address)
            self.read_from_db()
            self.executed_controllers.add(name)
                
    def update_inputs(self, name, now):
        """
        Returns a mapping of the inputs of the given controller based on self.mapping
        """
        self.read_from_db()
        #self.data_db = read_db(self.database.address)
        #self.refresh_device_from_db()
        #if self.debug: print 'ReadDB\n', self.data_db
        inputs = {}
        for c in self.controller[name]['inputs']:
            mapping = self.mapping[name+'_'+c]
            #print name, c, mapping
            if type(mapping) == type(0) or type(mapping) == type(0.0):
                inputs[c] = mapping
            elif type(mapping) == type([]):
                raise KeyError('Not implemented '+str(mapping))
            else:
                if self.mapping[name+'_'+c] in list(self.data_db.keys()):
                    inputs[c] = self.data_db[self.mapping[name+'_'+c]]
                else:
                    inputs[c] = self.mapping[name+'_'+c]
        self.controller[name]['input'][now] = inputs
        return inputs
        
        
    def read_from_db(self, name=None, refresh_device=True):
        #time_st = time.time()
        self.data_db = read_db(self.database.address)
        if refresh_device: self.refresh_device_from_db()
        #if self.debug: print 'Duration read_from_db for {}: {}'.format(name, time.time()-time_st)
        
    def log_to_df(self, stacks='all', which=['input','output','log']):
        if stacks == 'all':
            controller = self.controller
        else:
            raise ValueError('Only stacks == "all" implemented!')
        dfs = {}
        for name, ctrl in controller.items():
            if self.parallel:
                # print (name)
                ctrl = copy_dict(self.controller_objects[name].get_var('storage'))
            if len(ctrl['log']) > 0:
                init = True
                for w in which:
                    if w == 'log':
                        index = ['Logging']
                        if hasattr(ctrl['fun'], 'columns'): index = ctrl['fun'].columns
                        temp = pd.DataFrame(ctrl[w], index=index).transpose()
                    else:
                        temp = pd.DataFrame(ctrl[w]).transpose()
                    temp.index = pd.to_datetime(temp.index, unit='s', utc=True).tz_localize(None) + pd.DateOffset(hours=self.tz)
                        
                    if init:
                        dfs[name] = temp.copy(deep=True)
                        init = False
                    else:
                        dfs[name] = pd.concat([dfs[name], temp], axis=1)
        return dfs

    def log_to_csv(self, new=False, path='log'):
        dfs = self.log_to_df()
        mode = 'ab' if not new else 'wb'
        for name, log in dfs.items():
            log.to_csv(path+'_'+name+'.csv')

    def clear_logs(self):
        for name, ctrl in self.controller.items():
            if self.parallel:
                mp.Process(target=initialize_class, args=[self.controller_objects[name], self.controller[name]]).start()
            else:
                for t in ['output','input','log']:
                    ctrl[t] = {}
            
    def shutdown(self):
        self.database.kill_db()
        
    def set_input(self, inputs):
        for k, v in inputs.items():
            if k in list(self.mapping.keys()):
                self.mapping[k] = v
            else:
                raise KeyError('{} not a control parameter.'.format(k))
                
    def get_output(self, name, keys=[]):
        if self.parallel: ctrl = self.controller_objects[name]
        else: ctrl = self.controller[name]['fun']
        return ctrl.get_output(keys=keys)
    def get_input(self, name, keys=[]):
        if self.parallel: ctrl = self.controller_objects[name]
        else: ctrl = self.controller[name]['fun']
        return ctrl.get_input(keys=keys)


class MyList(object):
    ''' Create a list class for Basemanager.'''
    def __init__(self):
        self.list = list()

    def contains(self, x):
        return x in self.list

    def add(self, x):
        self.list.append(x)

    def remove(self, x):
        self.list.remove(x)
    
    def remove_all(self, x):
        self.list = [i for i in self.list if i != x]
    
    def size(self):
        return len(self.list)

    def __str__(self):
        return self.list.__str__()

    def __repr__(self):
        return self.list.__repr__()
# FIXME
# Check for error when db communication
