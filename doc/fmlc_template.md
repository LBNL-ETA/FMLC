# FMLC Code Standard & Generation Template

**Version:** 3  
**Scope:** eFMU module classes, `controller_stack` configuration, JSON config, and utility usage  
**Goal:** Reference for AI/code-agent generation of new FMLC modules and stacks that match existing project conventions.

---

## 1. Global Style & Conventions

### Imports

- Standard library first (`os`, `time`, `json`, etc.).
- Third-party second (`pandas`, `fmlc`, etc.).
- Local/module imports last.
- Alias `subprocess` as `import subprocess as sp`.
- Preferred FMLC imports:

```python
from fmlc import eFMU
from fmlc.stackedclasses import controller_stack
from fmlc.utility import check_error, resolve_config
```

### Naming

| Item | Convention | Example |
|---|---|---|
| Class names | PascalCase | `CombineData`, `CtrlSafety` |
| Controller instance keys | lowerCamelCase | `getFlexgrid`, `combLog` |
| `self.input` / `self.output` keys | kebab-case | `'input-data'`, `'time-zone'` |
| Mapping keys | `{moduleName}_{key}` | `'ctrlSafety_input-data'` |

### Data Flow

- Inter-module payloads are typically JSON strings.
- Parse inbound with `json.loads()`, serialize outbound with `json.dumps()`.
- Connect modules via mapping strings: `'moduleA_output-data'`.
- FMLC injects a Unix timestamp as input key `'time'` at runtime — do not declare it in `__init__`.

### Coding Rules

- No `.get()` on dicts — use direct key access. Functions that parse external input must return fully-validated structures so callers never need defensive access.
- No type-casting of pass-through values — only convert where the type must change (e.g. `log_level` int → logging level).
- No type annotations on function signatures.
- Docstrings: one line only unless parameters need brief documentation.

---

## 2. eFMU Base Class

### Compute Contract

- Every `eFMU` subclass must implement `compute(self)`.
- `compute()` must return a status string: `'Done.'` on success, error text otherwise.
- Never early-return after a single `check_data` call. Append to `msg` and gate each block with `if not msg:`.
- Always assign all declared outputs every cycle, including error paths.
- Initialise output variables at the top of `compute()` and assign `self.output[...]` at the bottom.

### Template

```python
from fmlc import eFMU
import json
import time
import traceback

class {{ClassName}}(eFMU):
    def __init__(self):
        self.input = {
            'input-data': None,
            # 'debug': None,  # optional: enables traceback in error msg
        }
        self.output = {
            'output-data': None,
            'duration': None,  # seconds; include when runtime tracking is useful
        }
        self.init = False

    def compute(self):
        st = time.time()
        msg = ''
        out_data = None

        # 1) Validate required input (no early return)
        msg += self.check_data(self.input['input-data'], True)

        try:
            # 2) Parse input payload (before one-time init when init needs payload context)
            if not msg:
                data = json.loads(self.input['input-data'])

            # 3) One-time runtime initialisation
            if not msg and not self.init:
                # one-time setup here; may use parsed data
                self.init = True

            # 4) Business logic
            if not msg:
                out_data = json.dumps(data)

        except Exception as e:
            msg += str(e)
            if self.input['debug']:
                msg += f'\n\n{traceback.format_exc()}'

        # 5) Assign all outputs
        self.output['output-data'] = out_data
        self.output['duration'] = time.time() - st

        return 'Done.' if not msg else msg
```

### Generation Rules

- Constructor: declare input/output keys and set `self.init = False` only. No runtime logic.
- One-time init runs in `compute()` after `check_data` passes.
- Parse input payload before one-time init when init depends on payload values.
- Preserve unknown keys in pass-through modules whenever possible.
- `'time'` is injected by FMLC at runtime — do not declare it in `__init__`.
- Include optional `'timeout'` in mapping when timeout behaviour is needed; only effective with `parallel=True`.
- Duration output: `self.output['duration'] = time.time() - st` — include when runtime tracking is useful.

---

## 3. controller_stack

### Full Signature

```python
controller_stack(
    controller,                  # dict: {name: {'function': cls, 'sampletime': int|str}}
    mapping,                     # dict: {'{module}_{key}': value_or_link_string}
    tz=-8,                       # int: UTC offset in hours
    debug=False,                 # bool: verbose logging
    name='Zone1',                # str: stack/database display name
    parallel=True,               # bool: run controllers in parallel threads
    now=None,                    # float: override start timestamp (Unix)
    workers=os.cpu_count() * 5,  # int: thread-pool size
    timestep=0.25,               # float: seconds between query_control ticks
    log_level=logging.WARNING,   # logging level
    log_add_ts=True,             # bool: append timestamp to CSV log filenames
    log_clear_period=86400,      # float: seconds between clearing in-memory logs (24 h)
    log_dump_period=3600,        # float: seconds between dumping logs to CSV (1 h)
    log_refresh_period=60,       # float: seconds between DB device-state refresh
    log_path='./log',            # str: path for CSV log files
    log_keys=None,               # list: keys to log; default ['input', 'output', 'log']
    align_ts=300,                # float|None: align to even multiples of this interval (s)
    offset_query=0,              # float: extra seconds after alignment boundary
)
```

### sampletime Rules

| Value | Meaning |
|---|---|
| `int` / `float` (seconds) | Independent schedule; fires every N seconds |
| `str` (module name) | Fires immediately after that module completes |

### mapping Value Types

| Type | Example | Meaning |
|---|---|---|
| `None` | `mapping['mod_key'] = None` | No upstream data; module uses internal default |
| Literal | `mapping['mod_key'] = 42` | Static value injected every cycle |
| Link string | `mapping['mod_key'] = 'modA_output-data'` | Reads latest output from another module |
| JSON string | `mapping['mod_key'] = json.dumps({...})` | Serialised config blob |

### align_ts / offset_query

`align_ts` sleeps until the next even multiple of the interval before starting, then floors each `query_control` timestamp to that boundary. `offset_query` adds a buffer after the boundary to ensure upstream data has settled.

```python
# Execute aligned to every 5 minutes, 5 s after the boundary
stack = controller_stack(controller, mapping, align_ts=300, offset_query=5)
stack.run_query_control_for(seconds=3600)
# fires at HH:05:05, HH:10:05, HH:15:05 ...
# query_control receives HH:05:00, HH:10:00, HH:15:00 (floored)
```

Set `align_ts=None` to disable alignment.

---

## 4. JSON Config Format

`resolve_config()` in `fmlc.utility` parses a JSON config dict into `(controller, mapping, stack_kwargs)` ready for `controller_stack`. This is the format used by the FMLC Web Interface.

### Structure

```json
{
  "controller": {
    "getData": {
      "function": "mypackage.modules.GetData",
      "sampletime": 60
    },
    "doControl": {
      "function": "mypackage.modules.DoControl",
      "sampletime": "getData"
    }
  },
  "stack_config": {
    "tz": -8,
    "name": "MyStack",
    "log_level": 2,
    "align_ts": 300,
    "offset_query": 5,
    "log_path": "./log",
    "log_clear_period": 86400,
    "log_dump_period": 3600,
    "log_refresh_period": 60,
    "log_keys": ["input", "output", "log"]
  },
  "mapping": {
    "getData_mode": "read",
    "doControl_data": "getData_data",
    "doControl_control-delay": 5
  }
}
```

### resolve_config Rules

- `controller[name]['function']` must be a fully-qualified class path (`'module.path.ClassName'`). `resolve_config` imports it dynamically.
- `sampletime` is passed through as-is (int or string).
- Optional `'parameter'` dict on a controller entry is forwarded unchanged.
- All `stack_config` keys are forwarded directly to `controller_stack` as `**stack_kwargs`, except `log_level` which is converted from int 1–5 to a Python logging level via `LOG_LEVEL_MAP`.
- Unknown `stack_config` keys are ignored. Keys not present use `controller_stack` defaults.
- `log_level` mapping: `1=DEBUG`, `2=INFO`, `3=WARNING`, `4=ERROR`, `5=CRITICAL`.
- Prefix any key with `'_'` to mark it as a comment — `resolve_config` strips them.
- `parallel` and `timestep` are server-controlled overrides; do not set them in `stack_config` when using the web interface.

### Usage

```python
import json
from fmlc.utility import resolve_config
from fmlc.stackedclasses import controller_stack

with open('config.json') as f:
    config = json.load(f)

controller, mapping, stack_kwargs = resolve_config(config)
stack = controller_stack(controller, mapping, parallel=True, **stack_kwargs)
```

---

## 5. Stack Template

```python
import os
import time
import json

from fmlc.stackedclasses import controller_stack
from fmlc.utility import check_error

# from mypackage.modules.module_a import ModuleA

def make_{{stack_name}}_stack(sample_time=30, **kwargs):
    controller = {}
    controller['{{modA}}'] = {'function': {{ClassA}}, 'sampletime': sample_time}
    controller['{{modB}}'] = {'function': {{ClassB}}, 'sampletime': '{{modA}}'}
    controller['{{modC}}'] = {'function': {{ClassC}}, 'sampletime': '{{modB}}'}

    mapping = {}
    mapping['{{modA}}_input-data'] = None
    mapping['{{modB}}_input-data'] = '{{modA}}_output-data'
    mapping['{{modC}}_input-data'] = '{{modB}}_output-data'

    return controller, mapping


def build_{{stack_name}}_stack(sample_time=30, **kwargs):
    controller, mapping = make_{{stack_name}}_stack(sample_time)
    return controller_stack(
        controller, mapping, name='{{StackDisplayName}}', parallel=True, **kwargs)
```

### Stack Rules

- `make_*` returns `(controller, mapping)` — no stack instantiation.
- `build_*` applies mode toggles, instantiates, and returns a `controller_stack`.
- Keep module key spelling identical across `controller` and `mapping`.
- For multi-rate pipelines, append logging/aggregation modules at the end of the chain.

---

## 6. Run Loop

### Daemon-style (runs until interrupted)

```python
stack = build_{{stack_name}}_stack(align_ts=300, offset_query=5)
try:
    stack.run_query_control_for(seconds=None)
except KeyboardInterrupt:
    pass
finally:
    stack.shutdown(dump_log=True)
```

### Fixed-duration (production)

```python
stack.run_query_control_for(seconds=3600)
# align_ts and offset_query are read from the stack instance
```

### Fixed-iteration (testing)

Use to test multi-hour control horizons in wall-clock seconds.

```python
from fmlc.utility import check_error

sample_time = 60 * 60  # simulated interval
real_time = 15         # wall-clock seconds between iterations; must exceed compute time
iterations = 3

try:
    now = time.time()
    for i in range(iterations):
        t = now + i * sample_time
        stack.query_control(t)
        print(f'[{i+1}/{iterations}] queried at t={t}')
        if i < iterations - 1:
            time.sleep(real_time)
except KeyboardInterrupt:
    pass
finally:
    log_df = stack.log_to_df()
    check_error(log_df, printing=True)
    stack.shutdown(dump_log=False)
```

---

## 7. Utility Reference (`fmlc.utility`)

| Function / Constant | Description |
|---|---|
| `DONE_MSGS` | Non-error log messages: `['Done.', 'Waiting to initialize.', 'Initialize FMLC.']` |
| `LOG_LEVEL_MAP` | `{1: DEBUG, 2: INFO, 3: WARNING, 4: ERROR, 5: CRITICAL}` |
| `resolve_config(config)` | Parse JSON config dict → `(controller, mapping, stack_kwargs)` |
| `module_status(stack)` | Per-module `last_log`, `last_exec`, `last_duration` from PythonDB (tz-adjusted) |
| `module_io(stack, name)` | Inputs, log, exec time, duration, outputs for one controller from PythonDB |
| `check_error(logs, printing)` | Scan `log_to_df()` output for non-`DONE_MSGS` entries; returns DataFrame |
| `read_csv_logs(name, path)` | Load CSV logs written by `log_to_csv()` |

---

## 8. Practical Pattern: Enrich / Combine Module

Use when appending diagnostics or timing fields from upstream modules to a shared payload.

```python
class {{CombineOrEnrichClass}}(eFMU):
    def __init__(self):
        self.input = {
            'input-data': None,
            '{{upstreamA}}-duration': None,
            '{{upstreamB}}-duration': None,
            'prefix': None,
        }
        self.output = {'output-data': None}

    def compute(self):
        msg = ''
        out_data = None

        msg += self.check_data(self.input['input-data'], True)

        try:
            if not msg:
                data = json.loads(self.input['input-data'])

                t = self.input['{{upstreamA}}-duration']
                data['Api_{{UpstreamA}}Dur_s'] = t if t else -1

                t = self.input['{{upstreamB}}-duration']
                data['Api_{{UpstreamB}}Dur_s'] = t if t else -1

                prefix = self.input['prefix']
                rename = {k: k.replace('Api_', f'Api{prefix}_')
                          for k in data if k.startswith('Api_')}
                data = {rename.get(k, k): v for k, v in data.items()}

                out_data = json.dumps(data)

        except Exception as e:
            msg += str(e)

        self.output['output-data'] = out_data
        return 'Done.' if not msg else msg
```

---

## 9. Agent Checklist

Before finalising generated code:

- [ ] `eFMU` subclass inherits correctly from `eFMU`.
- [ ] `self.input` and `self.output` declare all referenced keys.
- [ ] `compute()` returns a string.
- [ ] Required inputs validated with `self.check_data(..., True)`; no early return.
- [ ] JSON decode/encode is consistent — no dict/string mismatch across modules.
- [ ] Mapping keys match module names exactly.
- [ ] Controller ordering reflects the intended dependency chain.
- [ ] All outputs assigned every cycle, including error paths.
- [ ] No `.get()` calls on dicts; no defensive access on validated structures.
- [ ] `stack.shutdown()` called in `finally` block.
- [ ] If using `resolve_config`, `parallel` and `timestep` are passed as explicit overrides, not via `stack_kwargs`.

---

## 10. Minimal Starter Snippets

### Module

```python
from fmlc import eFMU
import json

class {{NewModule}}(eFMU):
    def __init__(self):
        self.input = {'input-data': None}
        self.output = {'output-data': None}
        self.init = False

    def compute(self):
        msg = ''
        out_data = None

        msg += self.check_data(self.input['input-data'], True)

        if not msg:
            data = json.loads(self.input['input-data'])
            # TODO: modify data
            out_data = json.dumps(data)

        self.output['output-data'] = out_data
        return 'Done.' if not msg else msg
```

### Stack

```python
def make_{{new_stack}}_stack(sample_time=30):
    controller = {
        '{{mod1}}': {'function': {{Class1}}, 'sampletime': sample_time},
        '{{mod2}}': {'function': {{Class2}}, 'sampletime': '{{mod1}}'},
    }
    mapping = {
        '{{mod1}}_input-data': None,
        '{{mod2}}_input-data': '{{mod1}}_output-data',
    }
    return controller, mapping
```

### JSON Config (minimal)

```json
{
  "controller": {
    "{{mod1}}": {"function": "mypackage.Module1", "sampletime": 60},
    "{{mod2}}": {"function": "mypackage.Module2", "sampletime": "{{mod1}}"}
  },
  "stack_config": {
    "tz": -8,
    "name": "MyStack",
    "log_level": 2,
    "align_ts": 300
  },
  "mapping": {
    "{{mod1}}_input-data": null,
    "{{mod2}}_input-data": "{{mod1}}_output-data"
  }
}
```
