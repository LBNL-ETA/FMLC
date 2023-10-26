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
            t = pd.read_json(r[1]).set_index('name')
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
    for f in sorted([f for f in os.listdir(path) if f.split('_')[0]==name and f.endswith('.csv')]):
        l = pd.read_csv(os.path.join(path, f), index_col=0)
        l.index = pd.to_datetime(l.index)
        if not only_latest and f.split('_')[1] in logs.keys():
            logs[f.split('_')[1]] = pd.concat([logs[f.split('_')[1]], l], axis=1)
        else:
            logs[f.split('_')[1]] = l
    return logs
