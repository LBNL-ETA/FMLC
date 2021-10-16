Stackedclasses
===
Class `controller_stack` handles the parallelization, timing/triggering, data logging, and error handling of multiple controller modules. Each controller is a `eFMU` object defined in [baseclassses.py](../FMLC/baseclasses.py). 

## Important Functions
---
## \_\_init__
Initialize the controller stack object. NOTE: IF USING PARALLEL, MAKE SURE TO DRASTICALLY INCREASE THE NUMBER OF WORKERS DRASTICALLY (AT LEAST 100)
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
* workers (int): Value to feed into the max_workers argument for `self.executor`. THIS IS VERY LOW BY DEFAULT, TRY INCREASING A LOT TO SEE BETTER RESULTS.
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
* Loops through the items in `self.controllers` and initializes them and their inputs

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
Generate self.execution_list and self.execution_map. 
Implementation Logic:
*  Iterate through all controllers to generate `self.execution_list`. `self.execution_list` is a list of dicts representing controllers with no dependencies ("parent" controllers) containing the following keys:
   *`controller` is a list of names for controllers dependent on this one (1 element for now)
   *`next` contains the next time we run the controller
   *`running` is a boolean telling us whether the controller is running or not (set to false)
* `execution_map` is a dict used to help make `self.execution_list`. It maps the names of controllers in `self.execution_list` to their indices. If a controller has a dependent sample time, this map is used to find the parent controller in constant time, and the dependent controller is then added to the parent's `controller` list and also mapped in `execution_map` to the same index as its parent in case it has any dependents.

## query_control
Trigger computations for controllers if the sample times have arrived.
In single thread mod, each call of query_control will trigger a computations for each controller by calling `self.run_controller_queue` for each group of dependent controllers serially.
In multi thread mod, each call of query_control will trigger a computations for each controller by calling `self.run_controller_queue` for each group of dependent controllers parallely.
Inputs:
* now(float): The current time in seconds since the epoch as a floating point number.  

Implementation Logic:
* Save and clear the logs in memory if needed.
* For each `task` in `self.execution_list`:
  * If `self.parallel` open a thread calling `self.run_controller_queue`, else call it serially
* If `self.parallel`, join all the threads

## run_controller_queue
Sequentially compute steps for each controller in queue. 
In a single thread mod, each controller runs to completion on the main thread while in the multithreaded version, we open a thread and handle timeouts. 
Inputs:
* task(dict): Represents the controller dependency queue (stored in task["controller"])
* now(float): The current time in seconds since the epoch as a floating point number.

Implementation Logic:
* For each controller in task["controller"], we:
   * Either serially or parallely call `self.do_control` for each input if the controller is not running elsewhere at the time

## do_control  
This function will perform the actual computation of a controller.
 
Inputs:
* name(str): name of the controller:
* ctrl(dict): Corresponds to the dictionary retrieved by `self.controller[name]`. Contains information about the controller. See the function `__initialize_controller` code for detailed information of the contents of the dictionary.
* now(float): The current time in seconds since the epoch as a floating point number.
* parallel(bool): If `True`, the controllers in the controller stack will advance in parallel. Each controller will spawn its own processes when perform a computation.   


## update_inputs
Returns a mapping of the inputs of the given controller based on self.mapping.  
Inputs: 
* name(str): name of the controller.      
* now(float): The current time in seconds since the epoch as a floating point number.
  
Implementation Logic:
* Validate and read inputs `self.mapping`. 
* Update `self.controller[name]['input'][now]`.
* Return the result inputs

## log_to_df
Return a dataframe that contains the logs.  
Inputs:
* which(list): ['input','output','log'] or subset of this list.

## save_and_clear
Save the logs to csv files and clear the current log cache in memory.
Inputs:
* path(str): path to save the logs.

## shutdown:
shutdown the database.

## set_input
Set inputs for controllers.   
Inputs:
* inputs(dict): key = input variable name; value = input variable name.

## get_output
Get output of conroller {name}.  
Inputs:
* name(str): name of the controller.
* keys(list): list of output variable names.

## get_input
Get input of conroller {name}.  
Inputs:
* name(str): name of the controller.
* keys(list): list of input variable names.

## log\_to\_db  
A helper function to write records into database.   
Inputs:
* name(str): name of the controller.
* ctrl(dict): Corresponds to the dictionary retrieved by `self.controller[name]`. Contains information about the controller. See the function `__initialize_controller` code for detailed information of the contents of the dictionary.
* now(float): The current time in seconds since the epoch as a floating point number.
* db_address(str): address of the database
  
Implementation Logic:   
* Iterate through each input output pairs of the controller and save them to the database