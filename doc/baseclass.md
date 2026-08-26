# Baseclass

`baseclasses.py` contains the `eFMU` class, which handles data exchange of models and controllers. Each `eFMU` represents a simulator or controller by implementing a `compute` method and storing the current inputs and outputs. The typical usage is to subclass `eFMU`, define `__init__` to declare input/output keys, and implement `compute`.

See `doc/fmlc_template.md` for the full coding standard and generation template.

## Key Methods

### `__init__`
Declare `self.input` and `self.output` as dicts with key names and default values (`None`). Do not perform any computation here.

```python
from fmlc import eFMU

class Multiplier(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}

    def compute(self):
        self.output['c'] = self.input['a'] * self.input['b']
        return 'Done.'
```

### `do_step(inputs)`
Sets inputs from the provided dict, calls `compute()`, and returns the log message. Exceptions are caught and returned as an error string.

### `compute`
Abstract method implemented by the user. Must return a status string — `'Done.'` on success, error text otherwise.

### `check_data(data, init=False)`
Returns `'Waiting to initialize.'` if `data` is falsy or `-1`. Use to guard required inputs before processing.

### `get_model_variables()`
Returns the keys of `self.input` as a list.

### `get_output(keys=[])` / `get_input(keys=[])`
Return the full output/input dict, or a subset if `keys` is provided.

## Full Example

```python
from fmlc import eFMU

class Multiplier(eFMU):
    def __init__(self):
        self.input = {'a': None, 'b': None}
        self.output = {'c': None}

    def compute(self):
        msg = ''
        msg += self.check_data(self.input['a'], True)
        msg += self.check_data(self.input['b'], True)
        if not msg:
            self.output['c'] = self.input['a'] * self.input['b']
        return 'Done.' if not msg else msg

controller = Multiplier()
print('Log:', controller.do_step(inputs={'a': 3, 'b': 4}))
print('Output:', controller.get_output())
```