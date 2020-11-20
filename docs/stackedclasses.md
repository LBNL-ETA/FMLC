Stackedclasses
===
Class `controller_stack` handles the parallelization, timing/triggering, data logging, and error handling of multiple controller modules. Each controller is a `eFMU` object defined in [baseclassses.py](../FMLC/baseclasses.py). 

## Important Functions
---
### \_\_init__
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
    