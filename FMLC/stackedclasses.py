import time
import warnings
import os

import pandas as pd
from copy import deepcopy as copy_dict
import logging

from .pythonDB.utility import PythonDB_wrapper, write_db, read_db

from concurrent.futures import ThreadPoolExecutor
import threading


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

def initialize_class(ctrl, data):
    """
    A helper function that initialize the storage of the controller.
    """
    ctrl.update_storage(data, init=True)

class controller_stack(object):
    def __init__(self, controller, mapping, tz=-8, debug=False, name='Zone1', parallel=True, \
        timeout=5, now=time.time(), workers=os.cpu_count()*5, log_config={'clear_log_period': 24*60*60, 'refresh_period':5, 'log_path':'./log'}):
        """
        Initialize the controller stack object. 
        
        NOTE: The default value for workers is quite low. Try cranking it up to at least 100 for better results

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
        parallel(bool): If `True`, the controllers in the controller stack will advance in parallel. The ThreadPoolExecutor (self.executor)
        now(float): The time in seconds since the epoch.
        workers(int): number of workers to be inputted to set up the ThreadPoolExecutor
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
        self.refresh_period = log_config['refresh_period']
        self.log_path = log_config['log_path']
        self.last_clear_time = now
        self.last_refresh_time = now
        self.workers = workers
        self.executor = ThreadPoolExecutor(max_workers=workers)
        if parallel:
            self.lock = threading.Lock()

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
        self.generate_execution_list(now)

    def __initialize_controller(self, now):
        """
        Initialize the controllers.

        Input
        -----
        now(float): The time in seconds since the epoch.

        """
        self.controller_objects = {}
        # Modify self.controllers to contain more information. Register the controllers on the BaseManager.
        for name, ctrl in self.controller.items():
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
            self.controller[name]['running'] = False
            self.controller_objects[name] = ctrl['fun']

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
        
    def generate_execution_list(self, now):
        """
        Generate self.execution_list and execution_map.

        self.execution_list is a list of dictionaries which the controllers with input/output dependencies are in the same dictionary(subtask).

        execution_map is a dictionary used to help make self.execution_list with controller names being the keys and the index of the dictionary which
        contains the controller in self.execution_list being the values.

        Input
        -----
        now(float): The time in seconds since the epoch.

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
                self.execution_list.append({'controller':[name], 'next': now, 'running':False})
                execution_map[name] = i
                i += 1
        if self.debug:
            logger.debug('Execution list: {!s}'.format(self.execution_list))
            logger.debug('Execution map: {!s}'.format(execution_map))

    def query_control(self, now):
        """
        Trigger computations for controllers if the sample times have arrived.
        A call will be made to run controller queue for each "task" queue
        In multi thread mod, this will be submitted to self.executor

        Input
        -----
        now(float): The current time in seconds since the epoch as a floating point number.
        """
        threads={}
        if now - self.last_refresh_time > self.refresh_period:
            self.read_from_db(refresh_device=True)
            self.last_refresh_time = now
        else:
            self.read_from_db()
        #If the deadline for clearing the log has passed, we open a thread that clears the log
        if now - self.last_clear_time > self.clear_log_period:
            self.executor.submit(self.save_and_clearself.log_path,)
        for task in self.execution_list:
            # CASE1: task is not running and a new step is needed.
            if now >= task['next']:
                name = task['controller'][0]
                # Start task
                task['next'] = now + self.controller[task['controller'][0]]['sampletime']
                # Do control
                logger.debug('Executing Controller "{!s}"'.format(name))
                if self.parallel:
                    self.executor.submit(controller_stack.run_controller_queue,self, task, now)
                else:
                    ctrl = self.controller[name]
                    self.run_controller_queue(task, now)
        """
        for thread_name in threads:
            thread = threads[thread_name]
            thread.join()
        """
            
    def run_controller_queue(self, task, now):
        """
        For every queue of dependencies, we run every controller. If it is a parallel stack, we open
        new threads for each control step.

        Input:
        -------
        task(dict): Container for the controller queue
        now(float): time for when the controllers are being evaluated
        """
        for name in task['controller']:
            ctrl = self.controller[name]
            logger.debug('Executing Controller "{!s}"'.format(name))
            if ctrl['running']:
                break
            ctrl['running'] = True
            if self.parallel:
                p = self.executor.submit(self.do_control, name, ctrl, now, self.parallel)
                try:
                    p.result(self.timeout)
                except:
                    print('Controller timeout: {}'.format(name))
                    warnings.warn('Controller {} timeout'.format(name), Warning)
                    ctrl['running'] = False
                    break
            else:
                self.do_control(name, ctrl, now, self.parallel)
            ctrl['running'] = False

    def do_control(self, name, ctrl, now, parallel=False):
        """
        This function will perform the actual computation of a controller.

        Input
        -----
        name(str)
        ctrl(dict)
        now(float)
        parallel(bool)
        """
    
        # Query controller
        logger.debug('QueryCTRL {} at {} ({})'.format(name, pd.to_datetime(now, unit='s')+pd.DateOffset(hours=self.tz), now))
        if parallel:
            self.lock.acquire()
            inputs = self.update_inputs(name, now)
            self.lock.release()
            ctrl['log'][now] = ctrl['fun'].do_step(inputs=ctrl['input'][now])
            ctrl['output'][now] = copy_dict(ctrl['fun'].output)
            ctrl['last'] = now
            log_to_db(name, ctrl, now, self.database.address)
            self.read_from_db()
        else:
            inputs = self.update_inputs(name, now)
            ctrl['log'][now] = ctrl['fun'].do_step(inputs=ctrl['input'][now])
            ctrl['output'][now] = copy_dict(ctrl['fun'].output)
            ctrl['last'] = now
            log_to_db(name, ctrl, now, self.database.address)
            self.read_from_db()

    def run_query_control_for(self, seconds, timestep=0.05):
        """
        Calls query control every timestep for seconds seconds either parallely or serially

        Input
        -----
        seconds(float)
        timestep(float)
        """
        t = time.time()
        end_time = t + seconds + 2 * timestep
        while time.time() <= end_time:
            t = time.time()
            if self.parallel:
                self.executor.submit(controller_stack.query_control, self, time.time())
            else:
                controller_stack.query_control(self, time.time())
            time.sleep(max(0, timestep - (t - time.time())))
        time.sleep(self.timeout)
        self.executor.shutdown()
        self.executor = ThreadPoolExecutor(max_workers=self.workers)

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
        
    def read_from_db(self, refresh_device=False):
        """
        Read self.data_db from the database.
        refresh_device(bool): whether refresh self.tz, self.debug, self.name from db
        """
        self.data_db = read_db(self.database.address)
        if refresh_device: 
            if self.parallel:
                self.lock.acquire()
                self.refresh_device_from_db()
                self.lock.release()
            else:
                self.refresh_device_from_db()
            
            
        
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
            #if self.parallel:
            #    ctrl = copy_dict(self.controller_objects[name].get_var('storage'))
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
        self.executor.shutdown()
        
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
