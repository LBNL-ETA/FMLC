Stackedclasses
===
Class `controller_stack` handles the parallelization, timing/triggering, data logging, and error handling of multiple controller modules. Each controller is a `eFMU` object defined in [baseclassses.py](../FMLC/baseclasses.py). 

## Important Functions
---
## \_\_init__
Initialize the controller stack object.  
Inputs:
*  controller(dict): A dictionary of dictionaries. For each item in the first layer dictionary, keys are the name of the controllers and values are dictionaries with two items: `'fun'` specifies the controller's `eFMU` object; `'sampletime'` specifies the sample time of the controller (time interval between two calls to `do_step`). For example:
   ``` python
   class testcontroller1(eFMU):
        def __init__(self):
            self.input = {'a':None,'b':None}
            self.output = {'c':None}
        def compute(self):
            self.output['c'] = self.input['a'] * self.input['b']
            return 'Compute ok'
    {
    'forecast1': {'fun':testcontroller1, 'sampletime':1}
    'mpc1': {'fun':testcontroller1, 'sampletime':'forecast1'}
    'control1': {'fun':testcontroller1, 'sampletime':'mpc1'}
    'forecast2': {'fun':testcontroller1, 'sampletime':1}
    'forecast3': {'fun':testcontroller1, 'sampletime':2}
    }
   ```

* mapping(dict): A dictionary that maps the inputs to the controllers' input variables. Each key is in the format {controller name}_{input variable name}. Values can either be a numeric value or a string of format {controller name}_{input/output variable name}. A string indicates dependency or sharing of another controller's input/output. In the exmaple below, controller  `mpc1` 's input `a` depends on the output `c` of controller `forecast1`. The input `b` of `mpc1` shares the same value with controller `forecast1`'s input `a`.
   ```python
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
   ```
* tz(int): utc/GMT time zone
* debug(bool): If `True`, some extra print statements will be added for debugging purpose. Unless you are a developers of this package, you should always set it false. The default value is false.
* name(str): Name you want to give to the database. 
* parallel(bool): If `True`, the controllers in the controller stack will advance in parallel. Each controller will spawn its own processes when perform a computation.
* now(float): The time in seconds since the epoch.
* debug_db(bool): Default set to false.
* log_config(dict): A dictionary to configure log saving. The is mainly used by the `save_and_clear` method, which save the logs to csv files and clear the logs in memory.
   ```
   {
    'clear_log_period': time in seconds of the period of log saving.
    'log_path': path to save the log files. Filenames will have the format {log_path}_{ctrl_name}.csv
   }
   ```
Implementation Logic:
It sets up a few object attributes and calls the private function`__initialize`.

## \_\_initialize
A function to call initializers of the pythonDB, controller, mapping, and execution list. This function is a private method only called by the `__init__` method.   
Inputs:
* mapping(dict): A dictionary that maps the inputs to the controllers' input variables. Each key is in the format {controller name}_{input variable name}. Values can either be a numeric value or a string of format {controller name}_{input/output variable name}. A string indicates dependency or sharing of another controller's input/output. In the exmaple below, controller  `mpc1` 's input `a` depends on the output `c` of controller `forecast1`. The input `b` of `mpc1` shares the same value with controller `forecast1`'s input `a`.
   ```python
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
   ```
* now(float): The time in seconds since the epoch.
  
Implementation Logic:
* It calls functions `__initialize_controller`, `__initialize_database`, `__initialize_mapping`, and `generate_execution_list`.

## \_\_initialize_controller
Initialize the controllers.   
Inputs:
* now(float): The time in seconds since the epoch.
  
Implementation Logic:
* It sets up the dictionary representation of each controller, and then registers lists `running_controllers`, `executed_controllers`, and `timeout_controllers` in `BaseManager`, so that they can be syncronized across multiple processes. 
  * `running_controllers`: List to keep track of all the running controller in the stackedclasses object.
  * `executed_controllers`: List to keep track of the controllers just finished executing. Controllers will be removed after the next controller in the same task start executing. For the definition of task, see `generate_execution_list`.
  * `timeout_controllers`: List to keep track of the timed-out controllers.
* Use multiprocessing to update the storage of controllers. The storage keeps track of the inputs, outputs, and logs of each controller. 

## \_\_initialize_database
Initialize the database columns. Columns include input & output variables for each device, timezone, dev_debug, dev_nodename, and dev_parallel.

## \_\_initialize_mapping
Validate the input mapping.  
Inputs: 
* mapping(dict): A dictionary that maps the inputs to the controllers' input variables. Each key is in the format {controller name}_{input variable name}. Values can either be a numeric value or a string of format {controller name}_{input/output variable name}. A string indicates dependency or sharing of another controller's input/output. In the exmaple below, controller  `mpc1` 's input `a` depends on the output `c` of controller `forecast1`. The input `b` of `mpc1` shares the same value with controller `forecast1`'s input `a`.
   ```python
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
   ```
Implementation Logic:
* Iterate through the `inputs` field of each controller and check if they are mapped in `mapping`. Also checks if there are extraneous parameter in `mapping`.

## generate_execution_list
Generate self.execution_list. 
Implementation Logic:
*  Iterate through all controllers to generate `self.execution_list`. `self.execution_list` is a map of dictionaries. The keys are index numbers, and the values are dictionaries which the controllers with input/output dependencies are in the same dictionary(task).  

## query_control
Trigger computations for controllers if the sample times have arrived.
In single thread mod, each call of query_control will trigger a computations for each controller in the system.
In multi thread mod, each call of query_control will trigger a computation for one controller within each task. Tasks are assigned based on input dependency.  
Inputs:
* now(float): The current time in seconds since the epoch as a floating point number.

       
