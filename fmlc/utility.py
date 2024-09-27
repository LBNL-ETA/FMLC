import os
import io
import numpy as np
import pandas as pd

def check_error(logs, printing=False):
    i = 0
    errors = pd.DataFrame()
    for n, l in logs.items():
        for t, m in l['logging'].items():
            if 'error' in str(m).lower():
                errors.loc[i, 'module'] = n
                errors.loc[i, 'timestep'] = t
                errors.loc[i, 'message'] = m
                i += 1
    if printing:
        for e in errors.iterrows():
            e = e[1]
            print(f'==>Found error in module {e["module"]} at {e["timestep"]}:\n{e["message"]}<==\n')
    return errors
    
def pdlog_to_df(log):
    res = pd.DataFrame()
    for r in log.items():
        try:
            t = pd.read_json(io.StringIO(r[1])).set_index('name')
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
