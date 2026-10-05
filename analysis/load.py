"""Parse RES lines written by experiments/run.py into pandas DataFrames."""
import os, re
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUM = ['c', 'S', 'rho', 'seed', 'meanLimit', 'limitOverC', 'util', 'reject', 'excessReject', 'meanLatOverS',
       'p50OverS', 'p99OverS', 'timeouts', 'eMean', 'eSd', 'nPairs', 'cvR']

def load(name):
    rows = []
    path = os.path.join(ROOT, 'results', name)
    for line in open(path):
        if not line.startswith('TAG '):
            continue
        parts = line.split()
        tag = parts[1]
        if parts[2] != 'RES' or parts[3] == 'ERROR':
            rows.append({'tag': tag, 'error': True}); continue
        d = {'tag': tag, 'error': False}
        for kv in parts[3:]:
            if '=' in kv:
                k, v = kv.split('=', 1); d[k] = v
        rows.append(d)
    df = pd.DataFrame(rows)
    for col in NUM:
        if col in df: df[col] = pd.to_numeric(df[col], errors='coerce')
    # label: the tag's second field is the controller variant (e.g. envoyScaled), which may differ from algo
    df['ctl'] = df['tag'].str.split(':').str[1]
    return df

LABEL = {'vegas': 'Netflix Vegas (default)', 'vegasW': 'Netflix Vegas + window', 'g2': 'Netflix Gradient2',
         'g2W': 'Netflix Gradient2 + window (README)', 'grad': 'Netflix Gradient', 'gradW': 'Netflix Gradient + window',
         'aimd': 'Netflix AIMD', 'envoy': 'Envoy gradient', 'envoyScaled': 'Envoy gradient (window 10xS)',
         'failsafe': 'failsafe-go adaptive', 'delta': 'Delta (ours)', 'static': 'Oracle static L=c',
         'deltaAny': 'Delta, first binding rule (ablation)'}

def good_rel(df, keys, util_frac=0.95, lat_max=1.5, oracle='static'):
    """Good region relative to the oracle static limit L = c of the same cell: utilisation at least util_frac of
    the oracle's (mean over its seeds) and mean latency at most lat_max service times."""
    o = df[df['ctl'] == oracle].groupby(keys)['util'].mean().rename('util_oracle').reset_index()
    m = df.merge(o, on=keys, how='left')
    return ((m['util'] >= util_frac * m['util_oracle']) & (m['meanLatOverS'] <= lat_max)).values
