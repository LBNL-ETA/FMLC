Baseclass
==============
baseclasses.py contains code for `eFMU` class, which handles data exchange of models and controllers. Each `eFMU` is used to represent a simulator or a controller by implementing an advance/compute function, and storing the inputs, outputs, and logs through the computation. The most common usage is to define a new controller class, inherit the `eFMU` class, define a `compute` method, and override the `__init__` method.

##  init
Initialize the inputs and outputs. By default, they are set as empty dictionaries. You would noramlly override this. The keys of `self.input` and `self.output` are the names of the inputs and outputs. Here is an example of the `__init__` method of a controller with inputs `"a"` and `"b"`. The output name is `"c"`. 
```python
    class testcontroller1(eFMU):
            def __init__(self):
                self.input = {'a':None,'b':None}
                self.output = {'c':None}
```

## do_step
The function to advance the simulator or controller. It takes in a dictionary and set the values of the inputs according to that dictionary. Then it calls `self.__compute__` to perform the computation, which the users needs to implement themselves.

## get_model_variables
Return all model or controller input variables as a list.

## compute:
Abstract method to compute outputs. Return a log message. Users needs to implement this methods in their `eFMU` subclasses.

## get_output:
Get the outputs of the model. Argument `keys` is a list of the outputs to be returned. If `keys == []` then all outputs are returned.

## Full Example 
``` python
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
```