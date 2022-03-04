import pandas as pd

def check_error(logs, printing=False):
    i = 0
    errors = pd.DataFrame()
    for n, l in logs.items():
        for t, m in l['logging'].items():
            if 'error' in m.lower():
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
    for r in log.iteritems():
        try:
            t = pd.read_json(r[1]).set_index('name')
            t.index.name = None
            t = t.stack(0)
            t.index = ['-'.join(ix) for ix in t.index]
            for k, v in t.iteritems():
                res.loc[r[0], k] = v
        except:
            pass
    return res