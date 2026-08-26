# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
Utility module.
"""

# pylint: disable=bare-except, broad-except, dangerous-default-value, too-many-branches, too-many-locals

import datetime as dtm
import importlib
import json
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


def _classify_value(val):
    '''Classify a value: return (kind, parsed) where kind is "df", "flat", "scalar", or "skip".'''
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 'skip', None
    val_str = str(val) if not isinstance(val, str) else val
    if val_str.startswith('{') or val_str.startswith('['):
        try:
            parsed = json.loads(val_str)
            if isinstance(parsed, dict):
                if 'columns' in parsed or 'index' in parsed:
                    return 'df', parsed
                return 'flat', parsed
        except (ValueError, TypeError):
            pass
    return 'scalar', val


def _parse_log_file_ts(fname):
    '''Parse the write timestamp from a log filename; return datetime or None.'''
    parts = fname.rsplit('_', 2)
    if len(parts) < 3:
        return None
    try:
        return dtm.datetime.strptime(parts[-2], '%Y%m%dT%H%M%S')
    except ValueError:
        return None


def _select_log_files(path, stack_name, module_name, start_ts):
    '''Return filtered log file paths that cover the requested start_ts.'''
    try:
        all_files = os.listdir(path)
    except OSError:
        return []

    prefix = f'{stack_name}_{module_name}_'
    full_files = sorted([f for f in all_files if f.startswith(prefix) and f.endswith('_full.csv')])
    log_files  = sorted([f for f in all_files if f.startswith(prefix) and f.endswith('_log.csv')])

    # Always include the latest partial dump (accumulating since last clear)
    selected = [log_files[-1]] if log_files else []

    if start_ts is None:
        selected = full_files + selected
    else:
        before = [f for f in full_files if (_parse_log_file_ts(f) or dtm.datetime.max) < start_ts]
        after  = [f for f in full_files if (_parse_log_file_ts(f) or dtm.datetime.min) >= start_ts]
        # Keep one file before start_ts — it may contain data straddling the boundary
        selected = ([before[-1]] if before else []) + after + selected

    return [os.path.join(path, f) for f in selected]


def _merge_disk(stack, name, mem_df, start_ts=None):
    '''Load filtered CSV logs for module name and merge with mem_df, deduplicating on index.'''
    try:
        file_paths = _select_log_files(stack.log_path, stack.name, name, start_ts)
        if not file_paths:
            return mem_df
        frames = []
        for fp in file_paths:
            try:
                df = pd.read_csv(fp, index_col=0)
                df.index = pd.to_datetime(df.index)
                frames.append(df)
            except Exception:
                pass
        if not frames:
            return mem_df
        disk_df = pd.concat(frames)
        if not mem_df.empty:
            disk_df = pd.concat([disk_df, mem_df])
        return disk_df[~disk_df.index.duplicated(keep='last')].sort_index()
    except Exception:
        return mem_df


def gather_outputs(stack, name, keys, start=None, end=None):
    '''Build flat and DataFrame output tables for one controller.

    Returns a dict with:
      flat_df  (pd.DataFrame): datetime index, one column per scalar/flat-JSON output key.
      df_data  (dict): {iso_timestamp: {key: parsed_dict}} for DataFrame-JSON keys.

    If start is earlier than the oldest in-memory timestamp, CSV log files from
    stack.log_path are loaded and merged with the in-memory data automatically.
    '''
    dfs = stack.log_to_df()
    mem_df = dfs.get(name, pd.DataFrame())

    # Determine in-memory time bounds
    mem_start = mem_df.index.min() if not mem_df.empty else None
    start_ts = pd.Timestamp(start) if start is not None else None

    # Load from disk when requested start is earlier than in-memory data (or memory is empty)
    if start_ts is not None and (mem_start is None or start_ts < mem_start):
        src = _merge_disk(stack, name, mem_df, start_ts=start_ts)
    else:
        src = mem_df

    if src.empty:
        return {'flat_df': pd.DataFrame(), 'df_data': {}}

    if start_ts is not None:
        src = src[src.index >= start_ts]
    if end is not None:
        src = src[src.index <= pd.Timestamp(end)]

    flat_cols = {}
    df_data = {}

    for prefixed_key in keys:
        # Keys arrive as "input.xxx" or "output.xxx"; strip prefix to look up column
        if '.' in prefixed_key:
            col_name = prefixed_key.split('.', 1)[1]
        else:
            col_name = prefixed_key
        if col_name not in src.columns:
            continue
        is_df_key = False
        for ts, val in src[col_name].items():
            kind, parsed = _classify_value(val)
            if kind == 'skip':
                continue
            if kind == 'df':
                is_df_key = True
                iso = ts.isoformat()
                if iso not in df_data:
                    df_data[iso] = {}
                df_data[iso][prefixed_key] = parsed
            elif kind == 'flat':
                for sub_k, sub_v in parsed.items():
                    col = prefixed_key + '.' + sub_k
                    if col not in flat_cols:
                        flat_cols[col] = {}
                    flat_cols[col][ts] = sub_v
            elif not is_df_key:
                if prefixed_key not in flat_cols:
                    flat_cols[prefixed_key] = {}
                flat_cols[prefixed_key][ts] = val

    flat_df = pd.DataFrame(flat_cols) if flat_cols else pd.DataFrame()
    flat_df.index.name = 'datetime'
    return {'flat_df': flat_df, 'df_data': df_data}


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
