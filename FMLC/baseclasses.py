'''
This module is part of the FMLC package.
https://github.com/LBNL-ETA/FMLC
'''

import abc

class eFMU(object):
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
    def do_step(self, inputs={}):
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
        self.set_inputs(inputs)
        return self.compute()
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
        for k, v in inputs.items():
            if k in all_keys:
                self.set_real(k, v)
                all_keys.remove(k)
            else:
                raise KeyError('{} not in input list.'.format(k))
        if len(all_keys) > 0:
            print('WARNING: Not all input specified, but continue step. Missing keys:{}'.format(all_keys))
    @abc.abstractmethod
    def compute(self):
        '''
        Method to compute the output
        '''
    def get_output(self, keys=[]):
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
        if keys == []:
            return self.output
        else:
            if isinstance(keys, str):
                keys = [keys]
            out = {}
            for k in keys:
                if k in self.output.keys():
                    out[k] = self.output[k]
                else:
                    raise KeyError('{} not in output list.'.format(k))
            return out
    def get_input(self, keys=[]):
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
        if keys == []:
            return self.input
        else:
            out = {}
            for k in keys:
                if k in self.input.keys():
                    out[k] = self.input[k]
                else:
                    raise KeyError('{} not in input list.'.format(k))
            return out
    def update_storage(self, data, init=False):
        '''
        Function to update the internal storage of inputs and outputs.
        
        Input
        -----
        data (dict): The data to be stored in form of {name: value}.
        init (bool): Flag to indicate intial setup of the storage.
            (Default = False)
        '''
        if init:
            self.storage = data
        else:
            for k in data.keys():
                if type(data[k]) == type({}):
                    self.storage[k].update(data[k])
                elif type(data[k]) in [type(0), type(0.0), type('')]:
                    self.storage[k] = data[k]
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
        l = locals()
        exec('x = self.'+name, globals(), l)
        return l['x']
        
if __name__ == '__main__':
    print('This is an example controller in form of: c = a * b')
    # Simple multiplier as test controller (extend the eFMU class)
    class testcontroller1(eFMU):
        def __init__(self):
            self.input = {'a':None,'b':None}
            self.output = {'c':None}
        def compute(self):
            self.output['c'] = self.input['a'] * self.input['b']
            return 'Compute ok'
    # Test controller
    controller = testcontroller1()
    # Get all variables
    variables = controller.get_model_variables()
    # Makeup some inputs
    inputs = {}
    for var in variables:
        inputs[var] = 2
    # Query controller
    print('Log-message:', controller.do_step(inputs=inputs))
    print('Inputs:', controller.input)
    print('Outputs:', controller.output)
