# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Stackedclass module.
"""

import os
import time
import datetime as dtm
import logging
import warnings
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy as copy_dict

import pandas as pd

from .python_db.utility import PythonDBWrapper, write_db, read_db
from .triggering import triggering

# pylint: disable=pointless-string-statement

# Setup logging
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s (%(name)s:%(funcName)s)',
    datefmt='%Y-%m-%d %H:%M:%S')

def log_to_db(name, ctrl, now, db_address):
    """
    A helper function to write records into database.

    Input
    ---
    name(str): name of the controller.
    ctrl(dict): Corresponds to the dictionary retrieved by
        `self.controller[name]`. Contains information about the
        controller. See the function `__initialize_controller` code
        for detailed information of the contents of the dictionary.
    now(float): The current time in seconds since the epoch as a floating point number.
    db_address(str): address of the database
    """
    temp = {}
    for k, v in ctrl['input'][now].items():
        temp[name+'_'+k] = v
    for k, v in ctrl['output'][now].items():
        temp[name+'_'+k] = v
    e = write_db(temp, db_address)
    if 'ERROR' in e:
        print(f'An error occurred when writing "{name}" to internal PythonDB database: {e}.')


default_log_config = {
    'clear_log_period': 24*60*60,
    'dump_log_period': 1*60*60,
    'refresh_period': 60,
    'log_path': './log',
    'log_keys': ['input', 'output', 'log']
}


# pylint: disable=invalid-name,useless-object-inheritance,too-many-instance-attributes
class controller_stack(object):
    """Stack controller that manages multiple controller objects."""

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(self, controller, mapping, tz=-8, debug=False, name='Zone1',
                 parallel=True, timeout=1e3, now=None,
                 workers=os.cpu_count()*5, timestep=0.25,
                 log_config=None, log_level=logging.WARNING, log_add_ts=True):
        """
        Initialize the controller stack object.

        NOTE: The default value for workers is quite low. Try cranking it up to at
        least 100 for better results.

        Input
        -----
        controller(dict): A dictionary of dictionaries.
            example:
                {
                    'forecast1': {'fun': testcontroller2, 'sampletime': 1},
                    'mpc1': {'fun': testcontroller3, 'sampletime': 'forecast1'},
                    'control1': {'fun': testcontroller1, 'sampletime': 'mpc1'},
                    'forecast2': {'fun': testcontroller2, 'sampletime': 1},
                    'forecast3': {'fun': testcontroller1, 'sampletime': 2},
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
        tz(int): utc/GMT time zone.
        debug(bool): If ``True``, some extra print statements will be added for
            debugging purpose. The default value is ``False``.
        name(str): Name you want to give to the database.
        parallel(bool): If ``True``, the controllers in the controller stack will
            advance in parallel. The ThreadPoolExecutor (self.executor) is used.
        now(float): The time in seconds since the epoch.
        workers(int): Number of workers to be inputted to set up the ThreadPoolExecutor.
        timestep(float): Time the stack takes between checking if any controller
            computations need be done.
        log_config(dict): Dictionary to configure log saving (logs stored in memory
            will be cleared). Keys include ``clear_log_period``, ``dump_log_period``,
            ``refresh_period``, and ``log_path``.
        log_level (logging): Default level for logging when ``debug`` == ``False``.
        log_add_ts (bool): Flag to add timestamp to logname. Default is ``True``.
        """
        # Setup
        self.controller = controller
        self.mapping = mapping
        self.tz = tz
        self.debug = debug
        self.name = name
        self.parallel = parallel
        self.timeout = timeout
        if not now:
            now = time.time()
        self.workers = workers
        self.stack_timestep = timestep
        if log_config is None:
            log_config = copy_dict(default_log_config)
        self.log_config = log_config
        self.dump_log_period = log_config['dump_log_period']
        self.clear_log_period = log_config['clear_log_period']
        self.refresh_period = log_config['refresh_period']
        self.log_path = log_config['log_path']
        self.log_level = log_level
        self.log_add_ts = log_add_ts

        self.last_dump_time = now
        self.last_clear_time = now
        self.last_refresh_time = now

        # placeholders for attributes that will be set later
        self.controller_objects = {}
        self.database = None
        self.execution_list = []
        self.data_db = {}

        if parallel:
            self.lock = threading.Lock()
        # Setup self.logger
        self.logger = logging.getLogger(__name__)
        self.__check_debug()
        # Initialize
        self.__initialize(self.mapping, now)
        self.executor = ThreadPoolExecutor(max_workers=workers)

    def __initialize(self, mapping, now):
        """
        A function to call initializers of the pythonDB, controller, mapping,
        and execution list. This function is a private method only called by the
        __init__ method.

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
        # Modify self.controllers to contain more information.
        # Register the controllers on the BaseManager.
        for name, ctrl in self.controller.items():
            if not 'parameter' in ctrl.keys():
                ctrl['parameter'] = {}
            ctrl['fun'] = ctrl['function'](**ctrl['parameter'])
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
        Initialize the database columns. Columns include input & output variables for
        each device, timezone, dev_debug, dev_nodename, and dev_parallel.
        """
        self.database = PythonDBWrapper(self.name, self.db_mode)
        self.database.address = '127.0.0.1:' + str(self.database.port)
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
        self.logger.debug('SetupDB\n%s', read_db(self.database.address))
        if self.database.error != '':
            self.logger.error('SetupDB: %s', self.database.error)

    def __initialize_mapping(self, mapping):
        """
        Validate the input mapping.
        """
        m = list(mapping.keys())
        for name in sorted(self.controller.keys()):
            for c in self.controller[name]['inputs']:
                key = f'{name}_{c}'
                if key in m:
                    m.remove(key)
                else:
                    raise KeyError(f'{key} not in mapping.')
        if m:
            raise KeyError(f'{m} not a control parameter.')
        self.mapping = mapping

    def __check_debug(self):
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(self.log_level)

    def refresh_device_from_db(self):
        """
        refresh self.tz, self.debug, self.name from db
        """
        self.tz = int(self.data_db['timezone'])
        self.debug = bool(self.data_db['dev_debug'])
        self.name = str(self.data_db['dev_nodename'])
        # check if debugging
        self.__check_debug()

    def generate_execution_list(self, now):
        """
        Generate self.execution_list and execution_map.

        self.execution_list is a list of dictionaries which the controllers with
        input/output dependencies are in the same dictionary(subtask).

        execution_map is a dictionary used to help make self.execution_list with
        controller names being the keys and the index of the dictionary which
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
            if isinstance(ctrl['sampletime'], str):
                # checking for bad mappings. current fix is to time them out
                if name not in self.controller:
                    print(
                        f'Controller {name} had a faulty mapping for sample time. '
                        f'It is being removed from the stack')
                    self.controller.pop(name)
                elif ctrl['sampletime'] not in controller_queue:
                    parent_idx = execution_map[ctrl['sampletime']]
                    self.execution_list[parent_idx]['controller'].append(name)
                    execution_map[name] = parent_idx
                else:
                    # Re-add to back of queue
                    controller_queue.append(name)
            else:
                self.execution_list.append({'controller': [name], 'next': now, 'running': False})
                execution_map[name] = i
                i += 1
        self.logger.debug('Execution list: %s', self.execution_list)
        self.logger.debug('Execution map: %s', execution_map)

    def query_control(self, now):
        """
        Trigger computations for controllers if the sample times have arrived.
        A call will be made to run controller queue for each "task" queue.
        In multi thread mode, this will be submitted to self.executor.
        """
        refreshed_db = False
        if now - self.last_refresh_time > self.refresh_period:
            self.read_from_db(refresh_device=True)
            self.last_refresh_time = now
            refreshed_db = True

        if now - self.last_dump_time > self.dump_log_period:
            self.executor.submit(self.log_to_csv, path=self.log_path, add_ts=self.log_add_ts)
            self.last_dump_time = now
        if now - self.last_clear_time > self.clear_log_period:
            self.executor.submit(self.save_and_clear, path=self.log_path, add_ts=self.log_add_ts)
            self.last_clear_time = now

        for task in self.execution_list:
            if now >= task['next']:
                if not refreshed_db:
                    self.read_from_db()
                    refreshed_db = True
                name = task['controller'][0]
                # Start task
                ts = self.controller[task['controller'][0]]['sampletime']
                if self.stack_timestep != 0:
                    task['next'] = int(now / self.stack_timestep) * self.stack_timestep + ts
                else:
                    task['next'] = now + ts
                # Do control
                self.logger.debug('Executing Controller "%s"', name)
                if self.parallel:
                    self.executor.submit(controller_stack.run_controller_queue, self, task, now)
                else:
                    self.run_controller_queue(task, now)

    def run_controller_queue(self, task, now):
        """
        For every queue of dependencies, we run every controller. If it is a
        parallel stack, we open new threads for each control step.
        """
        for name in task['controller']:
            ctrl = self.controller[name]
            self.logger.debug('Executing Controller "%s"', name)
            if ctrl['running']:
                break
            ctrl['running'] = True
            if self.parallel:
                p = self.executor.submit(self.do_control, name, ctrl, now, self.parallel)
                start_rt = time.time()
                try:
                    p.result(self.timeout)  # pylint: disable=broad-exception-caught
                    if time.time() - start_rt > self.timeout:
                        warnings.warn(f'Controller "{name}" timed out.', Warning)
                        ctrl['running'] = False
                        break
                except Exception as e:  # pylint: disable=broad-exception-caught
                    warnings.warn(
                        f'ERROR: Controller "{name}": {e}\n\n{traceback.format_exc()}',
                        Warning)
                    ctrl['running'] = False
                    break
            else:
                self.do_control(name, ctrl, now, self.parallel)
            ctrl['running'] = False

    def do_control(self, name, ctrl, now, parallel=False):
        """
        This function will perform the actual computation of a controller.
        """
        self.logger.debug('QueryCTRL %s at %s (%s)', name,
                          pd.to_datetime(now, unit='s') + pd.DateOffset(hours=self.tz), now)
        if parallel:
            with self.lock:
                inputs = self.update_inputs(name, now)
        else:
            inputs = self.update_inputs(name, now)

        # Add time as input
        inputs['time'] = now
        inputs['uid'] = name
        ctrl['input'][now] = inputs
        ctrl['log'][now] = ctrl['fun'].do_step(inputs=inputs)
        ctrl['output'][now] = copy_dict(ctrl['fun'].output)
        ctrl['last'] = now
        log_to_db(name, ctrl, now, self.database.address)
        self.read_from_db()

        # Silence logging
        for k in ['input', 'output', 'log']:
            if k not in self.log_config['log_keys']:
                ctrl[k][now] = {}

    def run_query_control_for(self, seconds=None, timestep=None):
        """
        Calls query control every timestep for seconds seconds either parallely or serially.
        """
        if not timestep:
            timestep = self.stack_timestep

        global_timestep_holder = self.stack_timestep
        self.stack_timestep = timestep

        if not seconds:
            print(f'Running controller {self.name} forever.')
            seconds = 1e99
        ts = {'main': self.stack_timestep}
        trigger_test = triggering(ts)

        now = time.time()
        end_time = now + seconds + self.stack_timestep * 2
        while now < end_time:
            now = time.time()
            if now >= trigger_test.trigger['main']:
                if self.parallel:
                    self.executor.submit(controller_stack.query_control, self, now)
                else:
                    controller_stack.query_control(self, now)
                trigger_test.refresh_trigger('main', now)

        if self.parallel:
            time.sleep(self.stack_timestep * 5)
        self.executor.shutdown()
        self.executor = ThreadPoolExecutor(max_workers=self.workers)
        self.stack_timestep = global_timestep_holder

    def update_inputs(self, name, _now):
        """
        Returns a mapping of the inputs of the given controller based on self.mapping.
        """
        self.read_from_db()
        inputs = {}
        for c in self.controller[name]['inputs']:
            if c in ['time', 'uid']:
                continue
            mapping = self.mapping[name+'_'+c]
            if isinstance(mapping, (int, float)):
                inputs[c] = mapping
            elif isinstance(mapping, list):
                raise KeyError('Not implemented ' + str(mapping))
            else:
                if self.mapping[name+'_'+c] in list(self.data_db.keys()):
                    inputs[c] = self.data_db[self.mapping[name+'_'+c]]
                else:
                    inputs[c] = self.mapping[name+'_'+c]
        return inputs

    def read_from_db(self, refresh_device=False):
        """
        Read self.data_db from the database.
        refresh_device(bool): whether to refresh self.tz, self.debug, self.name from db.
        """
        self.data_db = read_db(self.database.address)
        if refresh_device:
            if self.parallel:
                with self.lock:
                    self.refresh_device_from_db()
            else:
                self.refresh_device_from_db()

    def log_to_df(self, which=None):
        """
        Return a dataframe that contains the logs.
        """
        if which is None:
            which = ['input', 'output', 'log']
        controller = self.controller
        dfs = {}
        for name, ctrl in controller.items():
            if len(ctrl['log']) > 0:
                init = True
                for w in which:
                    if w == 'log':
                        index = ['logging']
                        if hasattr(ctrl['fun'], 'columns'):
                            index = ctrl['fun'].columns
                        temp = pd.DataFrame(ctrl[w], index=index).transpose()
                    else:
                        temp = pd.DataFrame(ctrl[w]).transpose()
                    temp.index = (
                        pd.to_datetime(temp.index, unit='s', utc=True)
                        .tz_localize(None)
                        + pd.DateOffset(hours=self.tz)
                    )
                    if init:
                        dfs[name] = temp.copy(deep=True)
                        init = False
                    else:
                        dfs[name] = pd.concat([dfs[name], temp], axis=1)
        return dfs

    def save_and_clear(self, path='log', add_ts=True):
        """Save the logs to csv files and clear the current log cache in memory."""
        self.log_to_csv(path=path, add_ts=add_ts)
        self.clear_logs()

    def log_to_csv(self, path='log', add_ts=True):
        """Save the logs to a csv file."""
        # Check folder
        if not os.path.exists(path):
            os.makedirs(path)
        # Log
        now = dtm.datetime.now().strftime('%Y%m%dT%H%M%S')
        now = now if add_ts else 0
        dfs = self.log_to_df()
        for name, log in dfs.items():
            log_path = os.path.join(
                path, f'{self.name}_{name}_{now}_log.csv')
            log.to_csv(log_path)

    def clear_logs(self):
        """Clear the current log cache."""
        for _, ctrl in self.controller.items():
            for t in ['output', 'input', 'log']:
                ctrl[t] = {}

    def shutdown(self, dump_log=False):
        """Shut down the database."""
        if dump_log:
            self.log_to_csv(path=self.log_path, add_ts=self.log_add_ts)
        self.database.kill_db()
        self.executor.shutdown()

    def set_input(self, inputs):
        """Set inputs for controllers."""
        for k, v in inputs.items():
            if k in list(self.mapping.keys()):
                self.mapping[k] = v
            else:
                raise KeyError(f'{k} not a control parameter.')

    def get_output(self, name, keys=None):
        """Get output of controller {name}."""
        if keys is None:
            keys = []
        if self.parallel:
            ctrl = self.controller_objects[name]
        else:
            ctrl = self.controller[name]['fun']
        return ctrl.get_output(keys=keys)

    def get_input(self, name, keys=None):
        """Get input of controller {name}."""
        if keys is None:
            keys = []
        if self.parallel:
            ctrl = self.controller_objects[name]
        else:
            ctrl = self.controller[name]['fun']
        return ctrl.get_input(keys=keys)
