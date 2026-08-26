# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Utility module.
"""

# pylint: disable=bare-except, dangerous-default-value

import datetime as dtm
import importlib
import logging
import os
import io
import numpy as np
import pandas as pd

DONE_MSGS = ['Done.', 'Waiting to initialize.', 'Initialize FMLC.']

LOG_LEVEL_MAP = {
    1: logging.DEBUG,
    2: logging.INFO,
    3: logging.WARNING,
    4: logging.ERROR,
    5: logging.CRITICAL,
}

def resolve_config(config: dict) -> tuple:
    '''Parse a FMLC JSON config dict and return (controller, mapping, stack_kwargs).'''
    if 'controller' not in config or not config['controller']:
        raise ValueError("Config must contain a non-empty 'controller' dict.")
    if 'mapping' not in config or not isinstance(config['mapping'], dict):
        raise ValueError("Config must contain a 'mapping' dict.")

    raw_controller = config['controller']
    mapping = config['mapping']
    controller = {}
    for name, entry in raw_controller.items():
        fn_path = entry['function']
        try:
            module_path, class_name = fn_path.rsplit('.', 1)
            cls = getattr(importlib.import_module(module_path), class_name)
        except (ValueError, ModuleNotFoundError, AttributeError) as exc:
            raise ValueError(
                f"Cannot import '{fn_path}' for controller '{name}': {exc}"
            ) from exc
        controller[name] = {
            'function': cls,
            'sampletime': entry['sampletime'],
        }
        if 'parameter' in entry:
            controller[name]['parameter'] = entry['parameter']

    stack_kwargs = config.get('stack_config', {})
    if 'log_level' in stack_kwargs:
        log_level_int = int(stack_kwargs['log_level'])
        if log_level_int not in LOG_LEVEL_MAP:
            raise ValueError(f'log_level must be 1-5, got {log_level_int}.')
        stack_kwargs['log_level'] = LOG_LEVEL_MAP[log_level_int]

    return controller, mapping, stack_kwargs


def _fmt_ts(last_ts, tz):
    '''Format a Unix timestamp as a local datetime string adjusted by tz offset in hours.'''
    local_dt = dtm.datetime.utcfromtimestamp(last_ts) + dtm.timedelta(hours=tz)
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')


def module_status(stack):
    '''Return per-module last log message, last execution time, and duration, read from PythonDB.'''
    stack.read_from_db()
    db = stack.data_db

    result = {}
    for name in stack.controller:
        last_log = db[name + '_logfmlc'] if name + '_logfmlc' in db else ''
        if isinstance(last_log, list):
            last_log = last_log[0] if last_log else ''
        last_log = str(last_log)

        last_ts = db[name + '_lastfmlc'] if name + '_lastfmlc' in db else 0
        try:
            last_ts = float(last_ts)
        except (TypeError, ValueError):
            last_ts = 0
        last_exec = _fmt_ts(last_ts, stack.tz) if last_ts else 'Never'

        raw_dur = db[name + '_durationfmlc'] if name + '_durationfmlc' in db else -1
        try:
            last_duration = round(float(raw_dur), 1)
        except (TypeError, ValueError):
            last_duration = -1

        result[name] = {
            'last_log': last_log, 'last_exec': last_exec, 'last_duration': last_duration}
    return result


def module_io(stack, name):
    '''Return inputs, log, execution time, duration and outputs for one controller from PythonDB.'''
    stack.read_from_db()
    db = stack.data_db

    last_log = db[name + '_logfmlc'] if name + '_logfmlc' in db else ''
    if isinstance(last_log, list):
        last_log = last_log[0] if last_log else ''
    last_log = str(last_log)

    last_ts = db[name + '_lastfmlc'] if name + '_lastfmlc' in db else 0
    try:
        last_ts = float(last_ts)
    except (TypeError, ValueError):
        last_ts = 0
    last_exec = _fmt_ts(last_ts, stack.tz) if last_ts else 'Never'

    raw_dur = db[name + '_durationfmlc'] if name + '_durationfmlc' in db else -1
    try:
        last_duration = round(float(raw_dur), 1)
    except (TypeError, ValueError):
        last_duration = -1

    inputs = {k: db[name + '_' + k] if name + '_' + k in db else None
              for k in stack.controller[name]['inputs']}
    outputs = {k: db[name + '_' + k] if name + '_' + k in db else None
               for k in stack.controller[name]['outputs']}

    return {'inputs': inputs, 'log': last_log, 'last_exec': last_exec,
            'last_duration': last_duration, 'outputs': outputs}


def check_error(logs, printing=False, done_msgs=DONE_MSGS):
    '''check for error in module'''
    i = 0
    errors = pd.DataFrame()
    for n, l in logs.items():
        for t, m in l['logging'].items():
            if not str(m).lower() in [m.lower() for m in done_msgs]:
                errors.loc[i, 'module'] = n
                errors.loc[i, 'timestep'] = t
                errors.loc[i, 'message'] = m
                i += 1
    if printing:
        for e in errors.iterrows():
            e = e[1]
            print(f'==>Found error in module {e["module"]} at' \
                  + f' {e["timestep"]}:\n{e["message"]}<==\n')
    return errors

def pdlog_to_df(log, index_name='name', typ='frame'):
    '''convert the pandas log to dataframe'''
    res = pd.DataFrame()
    for r in log.items():
        try:
            if typ == 'frame':
                t = pd.read_json(io.StringIO(r[1]), typ=typ)
                if index_name:
                    t = t.set_index(index_name)
            else:
                t = pd.read_json(io.StringIO(r[1]), typ=typ)
                t = pd.DataFrame(t, columns=['value'])
            t.index.name = None
            t = t.stack(0)
            t.index = ['-'.join(ix) for ix in t.index]
            for k, v in t.items():
                res.loc[r[0], k] = v
        except:
            pass
    return res

def read_csv_logs(name='MGC', path='', only_latest=True):
    '''
    Utility to load logs from csv.
    
    Input
    -----
    name (str): Name of the controller.
    path (str): Path to the top-level folder.
    only_latest (bool): Load all files or only the latest ones.
    
    Returns
    -------
    logs (dict): Dict of logs.
    '''

    logs = {}
    files = [f for f in os.listdir(path) if f.split('_')[0]==name and f.endswith('.csv')]
    modules = np.unique([f.split('_')[1] for f in files])
    for module in modules:
        mf = sorted([f for f in files if f.startswith(f'{name}_{module}_')])
        if only_latest:
            f = mf[-1] # latest
            l = pd.read_csv(os.path.join(path, f), index_col=0)
            l.index = pd.to_datetime(l.index)
            logs[module] = l
        else:
            for f in mf:
                l = pd.read_csv(os.path.join(path, f), index_col=0)
                l.index = pd.to_datetime(l.index)
                logs[module] = pd.concat([logs[module], l], axis=1)
    return logs
