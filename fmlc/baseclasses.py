# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Baseclass module.
"""

import abc
import time
import traceback

default_output = -1  # pylint: disable=invalid-name

class eFMU:  # pylint: disable=invalid-name
    '''
    Class to handle data exchange of models and controllers.
    '''
    __metaclass__  = abc.ABCMeta

    def __init__(self):
        '''
        Wrapper for initialization.
        '''
        self.input = {}
        self.output = {}

    def do_step(self, inputs=None):
        '''
        The function to advance the simulator or controller.
        
        Input
        -----
        inputs (dict): The inputs for the simulator or controller in form of 
            {name: value}. Note that there will be a warning for not
            specified inputs. (Default = {})
        
        Return
        ------
        message (str): Message of simulator or controller for computation.
        '''
        if inputs is None:
            inputs = {}
        try:  # pylint: disable=broad-exception-caught
            st = time.time()
            self.set_inputs(inputs)
            message = self.compute()
            if 'timeout' in self.input:
                timeout = self.input['timeout'] if self.input['timeout'] else 1e6
                if st + timeout < time.time():
                    for k in self.output:
                        self.output[k] = default_output
                    message = f'ERROR: Timed out after {round(time.time()-st, 1)} > {timeout} s.'
            return message
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f'ERROR: {e}\n\n{traceback.format_exc()}'

    def get_model_variables(self):
        '''
        Function to return all model or controller input variables.
        
        Return
        ------
        variables (list): List of input variables.
        '''
        return self.input.keys()

    def set_real(self, name, value):
        '''
        Function to set a real value in the model.
        
        Input
        -----
        name (str): The name of the variable to be set.
        value (float): The value of the variable to be set.
        '''
        self.input[name] = value

    def set_inputs(self, inputs):
        '''
        Function to set the inputs of the model.
        
        Input
        -----
        inputs (dict): The inputs for the simulator or controller in form of
            {name: value}. Note that there will be a warning for not
            specified inputs.
        '''
        all_keys = list(self.input.keys())
        all_keys.append('time')
        all_keys.append('uid')
        for k, v in inputs.items():
            if k in all_keys:
                self.set_real(k, v)
                all_keys.remove(k)
            else:
                raise KeyError(f'"{k}" not in input list.')
        if 'time' in all_keys:
            all_keys.remove('time')
        if 'uid' in all_keys:
            all_keys.remove('uid')
        if len(all_keys) > 0:
            print(f'WARNING: Not all input specified, but continue step. Missing keys:{all_keys}')

    @abc.abstractmethod
    def compute(self):
        '''
        Method to compute the output
        '''

    def check_data(self, data, init=False):
        '''
        Check if data exchange is ready.
        '''
        if (data == -1 or not data) and init:
            return 'Waiting to initialize.'
        if (data == -1 or not data) and not init:
            return 'Missing data.'
        return ''

    def get_output(self, keys=None):
        '''
        Function to get the outputs of the model.
        
        Input
        -----
        keys (list): List of the outputs to be returned. If keys == [] then
            all outputs are returned. (Default = [])
            
        Return
        ------
        output (dict): The outputs of the model in form of {name: value}.
        '''
        if keys is None:
            keys = []
        if not keys:
            return self.output
        if isinstance(keys, str):
            keys = [keys]
        out = {}
        for k in keys:
            if k in self.output:
                out[k] = self.output[k]
            else:
                raise KeyError(f'{k} not in output list.')
        return out

    def get_input(self, keys=None):
        '''
        Function to get the inputs of the model.
        
        Input
        -----
        keys (list): List of the inputs to be returned. If keys == [] then
            all inputs are returned. (Default = [])
            
        Return
        ------
        input (dict): The inputs of the model in form of {name: value}.
        '''
        if keys is None:
            keys = []
        if not keys:
            return self.input
        out = {}
        for k in keys:
            if k in self.input:
                out[k] = self.input[k]
            else:
                raise KeyError(f'{k} not in input list.')
        return out

    def get_var(self, name):
        '''
        Function to get a specific variable in the model.
        
        Input
        -----
        name (str): The name of the variable.
        
        Return
        ------
        value (float or str): The value of the variable.
        '''
        return getattr(self, name)

#     def update_storage(self, data, init=False):
#         '''
#         Function to update the internal storage of inputs and outputs.
#
#         Input
#         -----
#         data (dict): The data to be stored in form of {name: value}.
#         init (bool): Flag to indicate intial setup of the storage.
#             (Default = False)
#         '''
#         if init:
#             self.storage = data
#         else:
#             for k in data.keys():
#                 if type(data[k]) == type({}):
#                     self.storage[k].update(data[k])
#                 elif type(data[k]) in [type(0), type(0.0), type('')]:
#                     self.storage[k] = data[k]

if __name__ == '__main__':
    print('This is an example controller in form of: c = a * b')
    # Simple multiplier as test controller (extend the eFMU class)
    class testcontroller1(eFMU):  # pylint: disable=invalid-name
        """Simple test controller that multiplies two inputs."""
        def __init__(self):
            super().__init__()
            self.input = {'a': None, 'b': None}
            self.output = {'c': None}
        def compute(self):
            self.output['c'] = self.input['a'] * self.input['b']
            return 'Compute ok'
    # Test controller
    controller = testcontroller1()
    # Get all variables
    variables = controller.get_model_variables()
    # Makeup some inputs
    inputs_dict = {}
    for var in variables:
        inputs_dict[var] = 2
    # Query controller
    print('Log-message:', controller.do_step(inputs=inputs_dict))
    print('Inputs:', controller.input)
    print('Outputs:', controller.output)
