import time
import warnings

import pandas as pd
from copy import deepcopy as copy_dict
import logging

from .pythonDB.utility import PythonDB_wrapper, write_db, read_db

import multiprocessing as mp
import threading
from multiprocessing import Manager
from multiprocessing.managers import SyncManager


# Setup logger
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)
def log_to_db(name, ctrl, now, db_address):
    """
    A helper function to write records into database.
    
    Input
    ---
    name(str): name of the controller.
    ctrl(dict): Corresponds to the dictionary retrieved by `self.controller[name]`. Contains information about the controller. See the function `__initialize_controller` code for detailed information of the contents of the dictionary.
    now(float): The current time in seconds since the epoch as a floating point number.
    db_address(str): address of the database
    """
    temp = {}
    for k, v in ctrl['input'][now].items():
        temp[name+'_'+k] = v
    for k, v in ctrl['output'][now].items():
        temp[name+'_'+k] = v
    if write_db(temp, db_address) == list():
        print("An error occurred when writing to database.")

def control_worker_manager(name, now, db_address, debug, inputs, ctrl, executed_controller, running_controller, timeout_controller, timeout):
    """
    Spawn a new process to execute control_work function, which does the actual computation of the controller. Also monitors timeout.

    Input
    ---
    name(str): name of the controller.
    ctrl(dict): Corresponds to the dictionary retrieved by `self.controller[name]`. Contains information about the controller. See the function `__initialize_controller` code for detailed information of the contents of the dictionary.
    now(float): The current time in seconds since the epoch as a floating point number.
    db_address(str): address of the database
    inputs(dict): a mapping of the controller's inputs.
    executed_controller(dict): functionally a set of names of executed controllers.
    running_controller(dict): functionally a set of names of running controllers.
    timeout_controller(dict): functionally a set of names of timed out controllers.
    timeout(int): timeout threshold in seconds. 
    """
    p = mp.Process(target=control_worker, args=(name, now, db_address, debug, inputs, ctrl, executed_controller, running_controller))
    p.start()
    p.join(timeout=timeout)
    if p.is_alive():
        p.terminate()
        timeout_controller[name] = None
    else:
        p.terminate()

def control_worker(name, now, db_address, debug, inputs, ctrl, executed_controller, running_controller):
    """
    Do the actual computation of the controller. Cache the new results into the controller's storage. Also send new records to database.

    Input
    ---
    name(str): name of the controller.
    ctrl(dict): Corresponds to the dictionary retrieved by `self.controller[name]`. Contains information about the controller. See the function `__initialize_controller` code for detailed information of the contents of the dictionary.
    now(float): The current time in seconds since the epoch as a floating point number.
    db_address(str): address of the database
    inputs(dict): a mapping of the controller's inputs.
    executed_controller(dict): functionally a set of names of executed controllers.
    running_controller(dict): functionally a set of names of running controllers.
    """
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
    executed_controller[name] = None
    running_controller.pop(name, None)
    
def initialize_class(ctrl, data):
    """
    A helper function that initialize the storage of the controller.
    """
    ctrl.update_storage(data, init=True)

class controller_stack(object):
    def __init__(self, controller, mapping, tz=-8, debug=False, name='Zone1', parallel=True, \
        timeout=5, now=time.time(), log_config={'clear_log_period': 24*60*60, 'log_path':'./log'}):
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
        tz(int): utc/GMT time zone
        debug(bool): If `True`, some extra print statements will be added for debugging purpose. Unless you are a developers of this package, you should always set it false. The default value is false.
        name(str): Name you want to give to the database. 
        parallel(bool): If `True`, the controllers in the controller stack will advance in parallel. Each controller will spawn its own processes when perform a computation.
        now(float): The time in seconds since the epoch.
        log_config(dict): dictionary to configure log saving (logs stored in memory will be cleared).
            'clear_log_period': time in seconds of the period of log saving.
            'log_path': path to save the log files. Filenames will have the format {log_path}_{ctrl_name}.csv
        """
        self.controller = controller
        self.tz = tz
        self.debug = debug
        self.name = name
        self.parallel = parallel
        self.timeout = timeout
        self.__initialize(mapping, now)
        self.clear_log_period = log_config['clear_log_period']
        self.log_path = log_config['log_path']
        self.last_clear_time = now

    def __initialize(self, mapping, now):
        """
        A function to call initializers of the pythonDB, controller, mapping, and execution list. 
        This function is a private method only called by the __init__ method.

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
        self.__initialize_controller(now)
        self.__initialize_database()
        self.__initialize_mapping(mapping)
        self.generate_execution_list()

    def __initialize_controller(self, now):
        """
        Initialize the controllers.

        Input
        -----
        now(float): The time in seconds since the epoch.

        """
        # Modify self.controllers to contain more information. Register the controllers on the BaseManager.
        for name, ctrl in self.controller.items():
            logger.debug('Add {} to SyncManager'.format(name))
            exec("SyncManager.register(name, ctrl['fun'])")
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
        manager = Manager()
        #manager.start()
        self.running_controllers = manager.dict()
        self.executed_controllers = manager.dict()
        self.timeout_controllers = manager.dict()

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

    def __initialize_database(self):
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
        db_columns['dev_nodename'] = self.name
        db_columns['dev_parallel'] = self.parallel
        write_db(db_columns, self.database.address)
        logger.debug('SetupDB\n', read_db(self.database.address))

    def __initialize_mapping(self, mapping):
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
        
    def generate_execution_list(self):
        """
        Generate self.execution_list and execution_map.

        self.execution_list is a list of dictionaries which the controllers with input/output dependencies are in the same dictionary(subtask).

        execution_map is a dictionary used to help make self.execution_list with controller names being the keys and the index of the dictionary which
        contains the controller in self.execution_list being the values.
        """
        self.execution_list = []
        execution_map = {}
        controller_queue = sorted(self.controller.keys())
        i = 0
        while len(controller_queue) > 0:
            name = controller_queue.pop(0)
            ctrl = self.controller[name]
            if type(ctrl['sampletime']) == type(''):
                #checking for bad mappings. current fix is to time them out
                if name not in self.controller:
                    print("Controller " + name + " had a faulty mapping for sample time. It is being removed from the stack")
                    self.controller.pop(name)
                    pass
                elif ctrl['sampletime'] not in controller_queue:
                    self.execution_list[execution_map[ctrl['sampletime']]]['controller'].append(name)
                    execution_map[name] = execution_map[ctrl['sampletime']]
                else:
                    # Re-add to back of queue
                    controller_queue.append(name)
            else:
                self.execution_list.append({'controller':[name], 'next':0 + ctrl['sampletime'], 'running':False})
                execution_map[name] = i
                i += 1
        if self.debug:
            logger.debug('Execution list: {!s}'.format(self.execution_list))
            logger.debug('Execution map: {!s}'.format(execution_map))

    def query_control(self, now):
        """
        Trigger computations for controllers if the sample times have arrived.
        In single thread mod, each call of query_control will trigger a computations for each controller in the system.
        In multi thread mod, each call of query_control will trigger a computation for one controller within each task.
            tasks are assigned based on input dependency.

        Input
        -----
        now(float): The current time in seconds since the epoch as a floating point number.
        """
        self.read_from_db()
        #If the deadline for clearing the log has passed, we open a thread that clears the log
        if now - self.last_clear_time > self.clear_log_period:
            threading.Thread(target=self.save_and_clear, args=(self.log_path,)).start()
        for task in self.execution_list:
            queued = True
            while queued:
                # CASE1: task is not running and a new step is needed.
                if not task['running'] and now >= task['next']:
                    name = task['controller'][0]
                    # Not running, start task
                    task['running'] = True
                    task['next'] = now + self.controller[task['controller'][0]]['sampletime']
                    # Do control
                    logger.debug('Executing Controller "{!s}"'.format(name))
                    ctrl = self.controller[name]
                    self.do_control(name, ctrl, now, parallel=self.parallel)
                    if self.parallel:
                        queued = False
                    else:
                        queued = True
                elif task['running']:
                    reset = False
                    # Check if next module to start
                    finished_controllers = set([])
                    for n in task['controller']:
                        if n in self.executed_controllers:
                            finished_controllers.add(n) # Store executed controller in list
                        if n in self.timeout_controllers:
                            # A controller got stuck.
                            self.timeout_controllers.pop(n, None)
                            if n in self.running_controllers:
                                self.running_controllers.pop(n, None)
                            task['running'] = False
                            print('Controller timeout', n)
                            warnings.warn('Controller {} timeout'.format(n), Warning)
                            reset = True
                            break
                    if reset:
                        break
                    # CASE2: all subtasks in the task are already executed
                    if task['controller'][-1] in finished_controllers:
                        # Control option done
                        self.executed_controllers.pop(task['controller'][-1], None)
                        task['running'] = False
                    else:
                        if len(finished_controllers) == 1: # If one controller in list then next one to be spawn
                            elem = finished_controllers.pop()
                            subtask_id = task['controller'].index(elem)
                            self.executed_controllers.pop(elem, None) # Clear the execution list
                            name = task['controller'][subtask_id+1]
                            ctrl = self.controller[name]
                            logger.debug('Executing Controller "{!s}"'.format(name))
                            self.do_control(name, ctrl, now, parallel=self.parallel)
                        elif len(finished_controllers) > 1:
                            warnings.warn('Multiple entiries of Controller in executed: {}. Resetting controller.'.format(finished_controllers), Warning)
                            for n in task['controller']:
                                while n in self.executed_controllers:
                                    self.executed_controllers.pop(n, None)
                        queued = not self.parallel
                else:
                    queued = False
            
    def do_control(self, name, ctrl, now, parallel=False):
        """
        In single thread mod, this function will perform the actual computation of a controller.
        In multi thread mod, this function will spawn a new process called control_worker_manager. 
            The new process will handle the computation.

        Input
        -----
        name(str)
        ctrl(dict)
        now(float)
        parallel(bool)
        """
    
        # Query controller
        logger.debug('QueryCTRL {} at {} ({})'.format(name, pd.to_datetime(now, unit='s')+pd.DateOffset(hours=self.tz), now))
        inputs = self.update_inputs(name, now)
        if parallel:
            ctrl = self.controller_objects[name]
            p = mp.Process(target=control_worker_manager, args=[name, now, self.database.address, self.debug, inputs, ctrl, self.executed_controllers, self.running_controllers, self.timeout_controllers, self.timeout])
            self.running_controllers[name] = None
            p.start()

        else:
            ctrl['log'][now] = ctrl['fun'].do_step(inputs=ctrl['input'][now])
            ctrl['output'][now] = copy_dict(ctrl['fun'].output)
            ctrl['last'] = now
            log_to_db(name, ctrl, now, self.database.address)
            self.read_from_db()
            self.executed_controllers[name] = None
                
    def update_inputs(self, name, now):
        """
        Returns a mapping of the inputs of the given controller based on self.mapping

        Input
        ---
        name(str): name of the controller:       
        now(float): The current time in seconds since the epoch as a floating point number.
        """
        self.read_from_db()
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
        
    def read_from_db(self, refresh_device=True):
        """
        Read self.data_db from the database.
        refresh_device(bool): whether refresh self.tz, self.debug, self.name from db
        """
        self.data_db = read_db(self.database.address)
        if refresh_device: self.refresh_device_from_db()
        
    def log_to_df(self, which=['input','output','log']):
        """
        Return a dataframe that contains the logs.

        Input
        ---
        which(list): ['input','output','log'] or subset of this list.
        """
        controller = self.controller
        dfs = {}
        for name, ctrl in controller.items():
            if self.parallel:
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
    
    def save_and_clear(self, path='log'):
        """Save the logs to csv files and clear 
        the current log cache in memory.
        
        Input 
        ---
        path(str): path to save the csv file.
        """
        self.log_to_csv(path)
        self.clear_logs()

    def log_to_csv(self, new=False, path='log'):
        """Save the logs to a csv file

        Input 
        ---
        new(bool): whether the csv has already been created.
        path(str): path to save the csv file.
        """
        dfs = self.log_to_df()
        mode = 'ab' if not new else 'wb'
        for name, log in dfs.items():
            log.to_csv(path+'_'+name+'.csv')

    def clear_logs(self):
        """ Clear the current log cache """
        for name, ctrl in self.controller.items():
            for t in ['output','input','log']:
                ctrl[t] = {}
            initialize_class(self.controller_objects[name], ctrl)
            
    def shutdown(self):
        """ Shut down the database """
        self.database.kill_db()
        
    def set_input(self, inputs):
        """ Set inputs for controllers
        
        Input
        ---
        inputs(dict): key = input variable name; value = input variable name.
        """
        for k, v in inputs.items():
            if k in list(self.mapping.keys()):
                self.mapping[k] = v
            else:
                raise KeyError('{} not a control parameter.'.format(k))
                
    def get_output(self, name, keys=[]):
        """Get output of conroller {name} 

        Input
        ---
        name(str): name of the controller.
        keys(list): list of input variable names.
        """
        if self.parallel: ctrl = self.controller_objects[name]
        else: ctrl = self.controller[name]['fun']
        return ctrl.get_output(keys=keys)

    def get_input(self, name, keys=[]):
        """Get input of conroller {name} 
        
        Input
        ---
        name(str): name of the controller.
        keys(list): list of input variable names.
        """
        if self.parallel: ctrl = self.controller_objects[name]
        else: ctrl = self.controller[name]['fun']
        return ctrl.get_input(keys=keys)

