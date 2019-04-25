#! /usr/bin/env python

import time
import pandas as pd
import numpy as np
from copy import deepcopy as copy_dict
import logging
import traceback

from pythonDB.utility import PythonDB_wrapper, write_db, read_db

import multiprocessing as mp
#from multiprocessing import Process, Manager
#from multiprocessing import Process
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

def control_worker(wid, name, now, db_address, debug, inputs, ctrl):
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
    temp['last'] = {}
    temp['last'] = now
    ctrl.update_storage(temp)
    log_to_db(name, temp, now, db_address)
    db = read_db(db_address)
    db['executed_controller'].append(name)
    db['running_controller'].remove(name)
    write_db({'executed_controller':db['executed_controller'], \
              'running_controller':db['running_controller']}, db_address)
    
def initialize_class(ctrl, data):
    ctrl.update_storage(data, init=True)
    
    

    
class controller_stack(object):
    def __init__(self, controller, tz=-8, debug=False, name='Zone1', parallel=True, debug_db=False):
        self.controller = controller
        self.tz = tz
        self.debug = debug
        self.debug_db = debug_db
        self.name = name
        self.parallel = parallel
        #self.init = True

    def initialize(self, mapping, now=time.time()):
        self.db_mode = 'pythonDB'
        self.initialize_controller(now)
        self.initialize_database()
        self.initialize_mapping(mapping)
        self.generate_execution_list()
        
    def initialize_controller(self, now):     
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
        manager.start()
        
        self.controller_objects = {}
        for name in list(self.controller.keys()):
            # Register controller processes
            exec('self.controller_objects[name] = manager.'+name+'()')
            # Initialize controller
            mp.Process(target=initialize_class, args=[self.controller_objects[name], self.controller[name]]).start()
        logger.debug(self.controller_objects)
            
    def initialize_database(self):
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
        m = list(mapping.keys())
        for name in sorted(self.controller.keys()):
            for c in self.controller[name]['inputs']:
                if name+'_'+c in m: m.remove(name+'_'+c)
                else: raise KeyError('{} not in mapping.'.format(name+'_'+c))
        if len(m) != 0:
            raise KeyError('{} not a control parameter.'.format(m))
        self.mapping = mapping
            
    def refresh_device_from_db(self):
        self.tz = int(self.data_db['timezone'])
        self.debug = bool(self.data_db['dev_debug'])
        self.name = str(self.data_db['dev_nodename'])
        #self.parallel = bool(self.data_db['dev_parallel'])
        
    def generate_execution_list(self):
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
        write_db({'executed_controller':[],'running_controller':[]}, self.database.address)                
        
    def query_control(self, now, return_db=False):
        #time_st = time.time()
        #self.data_db = read_db(self.database.address)
        #self.refresh_device_from_db()
        #if self.debug: print 'ReadDB\n', self.data_db
        #if self.init:
        #    self.query_control_initial(now)
        #else:
        self.read_from_db()
        for task in sorted(self.execution_list.keys()):
            #print (self.data_db['executed_controller'])
            #print 'DB executed controller', self.data_db['executed_controller'], \
            #    'DB running controller', self.data_db['running_controller']
            name = self.execution_list[task]['controller'][0]
            if not self.execution_list[task]['running'] and now >= self.execution_list[task]['next']:
                #print (name, 'Start')
                # Not running, start task
                self.execution_list[task]['running'] = True
                self.execution_list[task]['next'] = now + self.controller[self.execution_list[task]['controller'][0]]['sampletime']
                # Do control
                ctrl = self.controller[name]
                self.do_control(name, ctrl, now, parallel=self.parallel)
            elif self.execution_list[task]['running']:
                if self.execution_list[task]['controller'][-1] in self.data_db['executed_controller']:
                    # Control option done
                    self.data_db['executed_controller'].remove(self.execution_list[task]['controller'][-1])
                    write_db({'executed_controller':self.data_db['executed_controller']}, self.database.address)
                    self.execution_list[task]['running'] = False
                else:
                    # Check if next module to start
                    temp_name = []
                    for n in self.execution_list[task]['controller']:
                        if n in self.data_db['executed_controller']:
                            temp_name.append(n)
                    if len(temp_name) == 1:
                        subtask_id = self.execution_list[task]['controller'].index(temp_name[0])
                        self.data_db['executed_controller'].remove(temp_name[0])
                        write_db({'executed_controller':self.data_db['executed_controller']}, self.database.address)
                        ctrl = self.controller[self.execution_list[task]['controller'][subtask_id+1]]
                        self.do_control(self.execution_list[task]['controller'][subtask_id+1], ctrl, now, parallel=self.parallel)
                    elif len(temp_name) > 1:
                        warnings.warn('Multiple entiries of Controller in executed: {}. Resetting controller.'.format(temp_name), Warning)
                        for n in self.execution_list[task]['controller']:
                            if n in self.data_db['executed_controller']:
                                self.data_db['executed_controller'].remove(temp_name)
                        write_db({'executed_controller':self.data_db['executed_controller']}, self.database.address)
        #self.init = False
        #if self.debug: print 'Duration query_control:',time.time()-time_st
            
    def do_control(self, name, ctrl, now, parallel=False):
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
            mp.Process(target=control_worker, args=[1, name, now, self.database.address, self.debug, inputs, ctrl]).start()
            self.data_db['running_controller'].append(name)
            write_db({'running_controller':self.data_db['running_controller']}, self.database.address)
        else:
            ctrl['log'][now] = ctrl['fun'].do_step(inputs=ctrl['input'][now])
            ctrl['output'][now] = copy_dict(ctrl['fun'].output)
            ctrl['last'] = now
            log_to_db(name, ctrl, now, self.database.address)
            self.read_from_db()
            self.data_db['executed_controller'].append(name)
            write_db({'executed_controller':self.data_db['executed_controller']}, self.database.address)
                
    def update_inputs(self, name, now):
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
                print (name)
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
        
# FIXME
# Check for error when db communication
